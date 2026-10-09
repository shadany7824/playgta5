"""Pure-numpy OpenEXR scanline reader/writer (DESIGN §1 "Images").

Writes single-part scanline files with HALF or FLOAT channels and NONE, ZIPS or ZIP compression.
Reads single-part scanline files with HALF/FLOAT/UINT channels compressed with NONE, RLE, ZIPS, ZIP or PIZ.
Row 0 of every array is the top of the image (the data window's min y), column 0 the left.

The codecs follow the OpenEXR file layout and the reference library's compressors
(ImfZip.cpp, ImfRle.cpp, ImfPizCompressor.cpp, ImfHuf.cpp, ImfWav.cpp).
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

import numpy as np

__all__ = ["write_exr", "read_exr", "read_exr_channels", "read_exr_header", "ExrError"]

MAGIC = 20000630
_PIXEL_TYPES = {0: "uint", 1: "half", 2: "float"}
_PIXEL_DTYPES = {0: np.dtype("<u4"), 1: np.dtype("<f2"), 2: np.dtype("<f4")}
_COMPRESSIONS = {0: "none", 1: "rle", 2: "zips", 3: "zip", 4: "piz", 5: "pxr24", 6: "b44", 7: "b44a",
                 8: "dwaa", 9: "dwab"}
_LINES_PER_CHUNK = {"none": 1, "rle": 1, "zips": 1, "zip": 16, "piz": 32, "pxr24": 16, "b44": 32, "b44a": 32,
                    "dwaa": 32, "dwab": 256}
_WRITE_COMPRESSIONS = {"none": 0, "zips": 2, "zip": 3}
_ZIP_LEVEL = 4  # OpenEXR 3.x default zip level


class ExrError(ValueError):
    """Malformed or unsupported EXR file."""


# ----------------------------------------------------------------------------------------------- codecs (shared)

def _zip_predict_interleave(raw: bytes) -> bytes:
    """ImfZip.cpp compress: split even/odd bytes, then delta-encode with a +128 bias."""
    a = np.frombuffer(raw, dtype=np.uint8)
    t = np.concatenate([a[0::2], a[1::2]])
    if t.size > 1:
        d = np.empty_like(t)
        d[0] = t[0]
        d[1:] = (t[1:].astype(np.int16) - t[:-1].astype(np.int16) + 128).astype(np.uint8)
        t = d
    return t.tobytes()


def _zip_unpredict_deinterleave(data: bytes) -> bytes:
    """ImfZip.cpp uncompress: undo the delta predictor, then re-interleave the two halves."""
    d = np.frombuffer(data, dtype=np.uint8).astype(np.int64)
    if d.size > 1:
        d[1:] -= 128
    t = (np.cumsum(d) & 0xFF).astype(np.uint8)
    n = t.size
    out = np.empty(n, dtype=np.uint8)
    half = (n + 1) // 2
    out[0::2] = t[:half]
    out[1::2] = t[half:]
    return out.tobytes()


def _rle_decode(data: bytes, expected: int) -> bytes:
    """ImfRle.cpp rleUncompress: signed count < 0 => literal run of -count bytes, else count+1 repeats."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        count = data[i] - 256 if data[i] > 127 else data[i]
        i += 1
        if count < 0:
            out += data[i:i - count]
            i -= count
        else:
            out += bytes([data[i]]) * (count + 1)
            i += 1
    if len(out) != expected:
        raise ExrError(f"RLE block decoded to {len(out)} bytes, expected {expected}")
    return bytes(out)


# ----------------------------------------------------------------------------------------------- PIZ (read only)

_HUF_ENCSIZE = (1 << 16) + 1
_HUF_DECBITS = 14
_SHORT_ZEROCODE_RUN = 59
_LONG_ZEROCODE_RUN = 63
_SHORTEST_LONG_RUN = 2 + _LONG_ZEROCODE_RUN - _SHORT_ZEROCODE_RUN


def _huf_uncompress(data: bytes, start: int, length: int, nraw: int) -> np.ndarray:
    """ImfHuf.cpp hufUncompress -> uint16 array of nraw values."""
    if length == 0:
        if nraw:
            raise ExrError("PIZ: empty Huffman stream")
        return np.zeros(0, np.uint16)
    im, iM, _table_len, nbits = struct.unpack_from("<iiii", data, start)
    if not (0 <= im < _HUF_ENCSIZE and 0 <= iM < _HUF_ENCSIZE):
        raise ExrError("PIZ: invalid Huffman table size")
    p = start + 20
    end = start + length
    # --- hufUnpackEncTable: 6-bit code lengths, runs of zero lengths, read MSB first.
    lengths = np.zeros(_HUF_ENCSIZE, dtype=np.int64)
    c = lc = 0
    sym = im
    while sym <= iM:
        while lc < 6:
            if p >= end:
                raise ExrError("PIZ: unexpected end of Huffman table")
            c = ((c << 8) | data[p]) & 0xFFFFFFFFFFFF
            p += 1
            lc += 8
        lc -= 6
        ln = (c >> lc) & 0x3F
        if ln == _LONG_ZEROCODE_RUN:
            while lc < 8:
                c = ((c << 8) | data[p]) & 0xFFFFFFFFFFFF
                p += 1
                lc += 8
            lc -= 8
            run = ((c >> lc) & 0xFF) + _SHORTEST_LONG_RUN
            if sym + run > iM + 1:
                raise ExrError("PIZ: Huffman table too long")
            sym += run
        elif ln >= _SHORT_ZEROCODE_RUN:
            run = ln - _SHORT_ZEROCODE_RUN + 2
            if sym + run > iM + 1:
                raise ExrError("PIZ: Huffman table too long")
            sym += run
        else:
            lengths[sym] = ln
            sym += 1
    # --- hufCanonicalCodeTable
    counts = np.bincount(lengths, minlength=59)
    first = [0] * 59
    code = 0
    for ln in range(58, 0, -1):
        nc = (code + int(counts[ln])) >> 1
        first[ln] = code
        code = nc
    used = np.nonzero(lengths)[0]
    codes = {}
    nxt = list(first)
    for s in used.tolist():  # increasing symbol order, as the reference does
        ln = int(lengths[s])
        codes[s] = (ln, nxt[ln])
        nxt[ln] += 1
    # --- decode tables: short codes (<= 14 bits) in a flat table, long codes listed per 14-bit prefix.
    dec_len = [0] * (1 << _HUF_DECBITS)
    dec_sym = [0] * (1 << _HUF_DECBITS)
    dec_long: dict[int, list[int]] = {}
    for s, (ln, cd) in codes.items():
        if ln <= _HUF_DECBITS:
            base = cd << (_HUF_DECBITS - ln)
            for k in range(base, base + (1 << (_HUF_DECBITS - ln))):
                dec_len[k] = ln
                dec_sym[k] = s
        else:
            dec_long.setdefault(cd >> (ln - _HUF_DECBITS), []).append(s)
    if nbits > 8 * (end - p):
        raise ExrError("PIZ: invalid Huffman bit count")
    # --- hufDecode
    rlc = iM
    out = []
    append = out.append
    c = lc = 0
    used_bits = 0
    i = p
    iend = p + (nbits + 7) // 8
    while used_bits < nbits:
        while lc < 64 and i < iend:
            c = (c << 8) | data[i]
            i += 1
            lc += 8
        idx = (c >> (lc - _HUF_DECBITS)) if lc >= _HUF_DECBITS else (c << (_HUF_DECBITS - lc))
        idx &= (1 << _HUF_DECBITS) - 1
        ln = dec_len[idx]
        if ln:
            s = dec_sym[idx]
        else:
            s = -1
            for cand in dec_long.get(idx, ()):
                cl, cc = codes[cand]
                if lc >= cl and ((c >> (lc - cl)) & ((1 << cl) - 1)) == cc:
                    s, ln = cand, cl
                    break
            if s < 0:
                raise ExrError("PIZ: invalid Huffman code")
        lc -= ln
        used_bits += ln
        c &= (1 << lc) - 1
        if s == rlc:
            while lc < 8 and i < iend:
                c = (c << 8) | data[i]
                i += 1
                lc += 8
            lc -= 8
            used_bits += 8
            cnt = (c >> lc) & 0xFF
            c &= (1 << lc) - 1
            if not out:
                raise ExrError("PIZ: run-length code before any value")
            out.extend([out[-1]] * cnt)
        else:
            append(s)
    if len(out) != nraw:
        raise ExrError(f"PIZ: decoded {len(out)} values, expected {nraw}")
    return np.asarray(out, dtype=np.uint16)


def _wdec14(l, h):
    ls = l.astype(np.uint16).view(np.int16).astype(np.int32)
    hi = h.astype(np.uint16).view(np.int16).astype(np.int32)
    ai = ls + (hi & 1) + (hi >> 1)
    return (ai & 0xFFFF).astype(np.int32), ((ai - hi) & 0xFFFF).astype(np.int32)


def _wdec16(l, h):
    m = l.astype(np.int32)
    d = h.astype(np.int32)
    bb = (m - (d >> 1)) & 0xFFFF
    aa = (d + bb - 32768) & 0xFFFF
    return aa, bb


def _wav2_decode(a: np.ndarray, maxval: int) -> None:
    """ImfWav.cpp wav2Decode on a (ny, nx) int32 view, in place."""
    ny, nx = a.shape
    dec = _wdec14 if maxval < (1 << 14) else _wdec16
    n = min(nx, ny)
    p = 1
    while p <= n:
        p <<= 1
    p >>= 1
    p2 = p
    p >>= 1
    while p >= 1:
        cy = max(0, (ny - p2) // p2 + 1) if ny >= p2 else 0
        cx = max(0, (nx - p2) // p2 + 1) if nx >= p2 else 0
        if cy and cx:
            ys = slice(0, cy * p2, p2)
            ys1 = slice(p, p + cy * p2, p2)
            xs = slice(0, cx * p2, p2)
            xs1 = slice(p, p + cx * p2, p2)
            i00, i10 = dec(a[ys, xs], a[ys1, xs])
            i01, i11 = dec(a[ys, xs1], a[ys1, xs1])
            a[ys, xs], a[ys, xs1] = dec(i00, i01)
            a[ys1, xs], a[ys1, xs1] = dec(i10, i11)
        if (nx & p) and cy:
            xo = cx * p2
            ys = slice(0, cy * p2, p2)
            ys1 = slice(p, p + cy * p2, p2)
            i00, b = dec(a[ys, xo], a[ys1, xo])
            a[ys1, xo] = b
            a[ys, xo] = i00
        if (ny & p) and cx:
            yo = cy * p2
            xs = slice(0, cx * p2, p2)
            xs1 = slice(p, p + cx * p2, p2)
            i00, b = dec(a[yo, xs], a[yo, xs1])
            a[yo, xs1] = b
            a[yo, xs] = i00
        p2 = p
        p >>= 1


def _piz_decode(data: bytes, channels: list, nx: int, ny: int) -> bytes:
    """ImfPizCompressor.cpp uncompress for one block of ny lines -> uncompressed scanline bytes."""
    sizes = [_PIXEL_DTYPES[ch["type"]].itemsize // 2 for ch in channels]
    counts = [nx * ny * s for s in sizes]
    total = sum(counts)
    min_nz, max_nz = struct.unpack_from("<HH", data, 0)
    pos = 4
    bitmap = np.zeros(8192, dtype=np.uint8)
    if max_nz >= 8192:
        raise ExrError("PIZ: bitmap out of range")
    if min_nz <= max_nz:
        nb = max_nz - min_nz + 1
        bitmap[min_nz:max_nz + 1] = np.frombuffer(data, dtype=np.uint8, count=nb, offset=pos)
        pos += nb
    bits = np.unpackbits(bitmap, bitorder="little").astype(bool)
    bits[0] = True
    lut = np.nonzero(bits)[0].astype(np.uint16)  # reverseLutFromBitmap
    maxval = lut.size - 1
    (length,) = struct.unpack_from("<i", data, pos)
    pos += 4
    buf = _huf_uncompress(data, pos, length, total).astype(np.int32)
    off = 0
    for cnt, size in zip(counts, sizes):
        region = buf[off:off + cnt].reshape(ny, nx, size)
        for j in range(size):
            comp = region[:, :, j].copy()
            _wav2_decode(comp, maxval)
            region[:, :, j] = comp
        off += cnt
    vals = lut[buf]
    # Rearrange per line: for each line, each channel's nx*size uint16 words (little-endian).
    parts = []
    off = 0
    for cnt, size in zip(counts, sizes):
        parts.append(vals[off:off + cnt].reshape(ny, nx * size))
        off += cnt
    return np.concatenate(parts, axis=1).astype("<u2").tobytes()


# ----------------------------------------------------------------------------------------------- header

def _read_cstr(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\0", pos)
    return data[pos:end].decode("latin-1"), end + 1


def _parse_attr(typ: str, raw: bytes):
    if typ == "chlist":
        chans, pos = [], 0
        while raw[pos] != 0:
            name, pos = _read_cstr(raw, pos)
            ptype, plinear, xs, ys = struct.unpack_from("<iB3xii", raw, pos)
            pos += 16
            chans.append({"name": name, "type": ptype, "pLinear": plinear, "xSampling": xs, "ySampling": ys})
        return chans
    if typ == "compression":
        return _COMPRESSIONS.get(raw[0], f"unknown({raw[0]})")
    if typ == "lineOrder":
        return {0: "increasing_y", 1: "decreasing_y", 2: "random_y"}.get(raw[0], raw[0])
    if typ == "box2i":
        return tuple(struct.unpack("<iiii", raw))
    if typ == "v2f":
        return tuple(struct.unpack("<ff", raw))
    if typ == "v2i":
        return tuple(struct.unpack("<ii", raw))
    if typ == "float":
        return struct.unpack("<f", raw)[0]
    if typ == "int":
        return struct.unpack("<i", raw)[0]
    if typ == "string":
        return raw.decode("utf-8", "replace")
    return raw


def _parse_header(data: bytes) -> tuple[dict, int]:
    if len(data) < 8:
        raise ExrError("file too short")
    magic, version = struct.unpack_from("<iI", data, 0)
    if magic != MAGIC:
        raise ExrError("not an OpenEXR file (bad magic)")
    flags = version & ~0xFF
    if version & 0x200:
        raise ExrError("tiled EXR files are not supported")
    if version & 0x800:
        raise ExrError("deep EXR files are not supported")
    if version & 0x1000:
        raise ExrError("multi-part EXR files are not supported")
    if flags & ~0x400:
        raise ExrError(f"unsupported EXR version flags 0x{flags:x}")
    pos = 8
    header: dict = {}
    while data[pos] != 0:
        name, pos = _read_cstr(data, pos)
        typ, pos = _read_cstr(data, pos)
        (size,) = struct.unpack_from("<i", data, pos)
        pos += 4
        header[name] = _parse_attr(typ, data[pos:pos + size])
        pos += size
    pos += 1
    for req in ("channels", "compression", "dataWindow"):
        if req not in header:
            raise ExrError(f"missing required attribute {req!r}")
    return header, pos


def read_exr_header(path) -> dict:
    """Parse and return the header attributes (channels as a list of dicts, compression as a name)."""
    data = Path(path).read_bytes()
    return _parse_header(data)[0]


# ----------------------------------------------------------------------------------------------- read

def _decode_chunk(comp: str, data: bytes, expected: int, channels: list, nx: int, ny: int) -> bytes:
    if len(data) >= expected or comp == "none":
        if len(data) != expected:
            raise ExrError(f"chunk has {len(data)} bytes, expected {expected}")
        return data
    if comp in ("zip", "zips"):
        raw = _zip_unpredict_deinterleave(zlib.decompress(data))
    elif comp == "rle":
        raw = _zip_unpredict_deinterleave(_rle_decode(data, expected))
    elif comp == "piz":
        raw = _piz_decode(data, channels, nx, ny)
    else:
        raise ExrError(f"compression {comp!r} is not supported by tools.exr")
    if len(raw) != expected:
        raise ExrError(f"decompressed chunk has {len(raw)} bytes, expected {expected}")
    return raw


def read_exr_channels(path, native: bool = False) -> dict[str, np.ndarray]:
    """Read every channel as an (H, W) array keyed by channel name.

    HALF and FLOAT channels come back as float32 (HALF stays float16 with ``native=True``); UINT as uint32.
    """
    data = Path(path).read_bytes()
    header, pos = _parse_header(data)
    channels = sorted(header["channels"], key=lambda c: c["name"].encode("latin-1"))
    for ch in channels:
        if ch["xSampling"] != 1 or ch["ySampling"] != 1:
            raise ExrError(f"channel {ch['name']!r}: subsampled channels are not supported")
        if ch["type"] not in _PIXEL_DTYPES:
            raise ExrError(f"channel {ch['name']!r}: unknown pixel type {ch['type']}")
    comp = header["compression"]
    if comp not in _LINES_PER_CHUNK:
        raise ExrError(f"unknown compression {comp!r}")
    x0, y0, x1, y1 = header["dataWindow"]
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w <= 0 or h <= 0:
        raise ExrError("empty data window")
    lpc = _LINES_PER_CHUNK[comp]
    nchunks = (h + lpc - 1) // lpc
    offsets = np.frombuffer(data, dtype="<u8", count=nchunks, offset=pos)
    line_dtype = np.dtype([(f"c{i}", _PIXEL_DTYPES[ch["type"]], (w,)) for i, ch in enumerate(channels)])
    lines = np.empty(h, dtype=line_dtype)
    for off in offsets.tolist():
        y, size = struct.unpack_from("<ii", data, off)
        ly = y - y0
        if not 0 <= ly < h:
            raise ExrError(f"chunk at offset {off} has y={y} outside the data window")
        ny = min(lpc, h - ly)
        payload = data[off + 8:off + 8 + size]
        raw = _decode_chunk(comp, payload, ny * line_dtype.itemsize, channels, w, ny)
        lines[ly:ly + ny] = np.frombuffer(raw, dtype=line_dtype, count=ny)
    out = {}
    for i, ch in enumerate(channels):
        arr = np.ascontiguousarray(lines[f"c{i}"])
        if ch["type"] == 1 and not native:
            arr = arr.astype(np.float32)
        else:
            arr = arr.astype(arr.dtype.newbyteorder("="))
        out[ch["name"]] = arr
    return out


def _channel_order(names: list[str]) -> list[str]:
    s = set(names)
    for group in (("R", "G", "B", "A"), ("R", "G", "B"), ("X", "Y", "Z")):
        if set(group) <= s and len(s) == len(group):
            return list(group)
    if {"R", "G", "B"} <= s:
        return ["R", "G", "B"] + (["A"] if "A" in s else [])
    return sorted(names)


def read_exr(path) -> np.ndarray:
    """Read an EXR as float32 (H, W, C): channels R,G,B[,A] when present, else the single channel.

    Files with other channel sets come back in X,Y,Z order when that is the set, else sorted by name.
    """
    chans = read_exr_channels(path)
    order = _channel_order(list(chans))
    return np.stack([chans[n].astype(np.float32) for n in order], axis=-1)


# ----------------------------------------------------------------------------------------------- write

def _attr(name: str, typ: str, value: bytes) -> bytes:
    return name.encode("latin-1") + b"\0" + typ.encode("latin-1") + b"\0" + struct.pack("<i", len(value)) + value


def _parse_channels(channels, c: int) -> list[str]:
    if channels is None:
        default = {1: ["Y"], 3: ["R", "G", "B"], 4: ["R", "G", "B", "A"]}
        if c not in default:
            raise ValueError(f"write_exr: give channels= for an image with {c} channels")
        return default[c]
    names = [n.strip() for n in channels.split(",")] if isinstance(channels, str) else [str(n) for n in channels]
    if len(names) != c:
        raise ValueError(f"write_exr: {len(names)} channel names for an image with {c} channels")
    if len(set(names)) != len(names) or any(not n for n in names):
        raise ValueError(f"write_exr: invalid channel names {names}")
    return names


def write_exr(path, img, channels=None, pixel_type: str = "float", compression: str = "zip") -> Path:
    """Write ``img`` ((H, W) or (H, W, C)) as a scanline EXR; row 0 = top.

    channels: None -> 'Y' | 'R,G,B' | 'R,G,B,A' by C, or a comma string / list of names.
    pixel_type: 'float' (FLOAT32) or 'half'. compression: 'zip' (16-line blocks), 'zips' or 'none'.
    """
    a = np.asarray(img)
    if a.ndim == 2:
        a = a[:, :, None]
    if a.ndim != 3 or a.shape[0] < 1 or a.shape[1] < 1:
        raise ValueError(f"write_exr: expected (H, W) or (H, W, C), got shape {np.shape(img)}")
    h, w, c = a.shape
    names = _parse_channels(channels, c)
    if pixel_type not in ("float", "half"):
        raise ValueError(f"write_exr: pixel_type must be 'float' or 'half', not {pixel_type!r}")
    comp = compression.lower()
    if comp not in _WRITE_COMPRESSIONS:
        raise ValueError(f"write_exr: compression must be one of {sorted(_WRITE_COMPRESSIONS)}, not {compression!r}")
    ptype = 2 if pixel_type == "float" else 1
    dt = _PIXEL_DTYPES[ptype]
    order = sorted(range(c), key=lambda i: names[i].encode("latin-1"))
    sorted_names = [names[i] for i in order]

    chlist = b"".join(n.encode("latin-1") + b"\0" + struct.pack("<iB3xii", ptype, 0, 1, 1) for n in sorted_names) + b"\0"
    long_names = any(len(n) > 31 for n in sorted_names)
    header = b"".join([
        _attr("channels", "chlist", chlist),
        _attr("compression", "compression", bytes([_WRITE_COMPRESSIONS[comp]])),
        _attr("dataWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1)),
        _attr("displayWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1)),
        _attr("lineOrder", "lineOrder", b"\0"),
        _attr("pixelAspectRatio", "float", struct.pack("<f", 1.0)),
        _attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0)),
        _attr("screenWindowWidth", "float", struct.pack("<f", 1.0)),
    ]) + b"\0"
    prefix = struct.pack("<iI", MAGIC, 2 | (0x400 if long_names else 0)) + header

    # One record per scanline: each channel's W values, channels in sorted order.
    line_dtype = np.dtype([(f"c{k}", dt, (w,)) for k in range(c)])
    lines = np.empty(h, dtype=line_dtype)
    for k, i in enumerate(order):
        lines[f"c{k}"] = a[:, :, i].astype(dt)

    lpc = _LINES_PER_CHUNK[comp]
    nchunks = (h + lpc - 1) // lpc
    chunks = []
    for ci in range(nchunks):
        y = ci * lpc
        raw = lines[y:y + lpc].tobytes()
        if comp != "none":
            packed = zlib.compress(_zip_predict_interleave(raw), _ZIP_LEVEL)
            if len(packed) < len(raw):
                raw = packed
        chunks.append(struct.pack("<ii", y, len(raw)) + raw)
    offsets = []
    off = len(prefix) + 8 * nchunks
    for ch in chunks:
        offsets.append(off)
        off += len(ch)
    blob = prefix + np.asarray(offsets, dtype="<u8").tobytes() + b"".join(chunks)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    return path
