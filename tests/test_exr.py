"""tools/exr.py: round trips and cross-checks against independent EXR implementations."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from tools import exr


def _img(h, w, c, seed=0):
    rng = np.random.default_rng(seed)
    a = (rng.random((h, w, c)) * 8.0).astype(np.float32)
    a[0, 0, 0] = 0.0
    if h > 2:
        a[1, :, :] = 1.25  # constant rows exercise the predictor/RLE paths
    return a


def _chunk_ys(path):
    data = path.read_bytes()
    header, pos = exr._parse_header(data)
    lpc = exr._LINES_PER_CHUNK[header["compression"]]
    x0, y0, x1, y1 = header["dataWindow"]
    n = (y1 - y0 + 1 + lpc - 1) // lpc
    offs = np.frombuffer(data, "<u8", count=n, offset=pos)
    return [struct.unpack_from("<i", data, int(o))[0] for o in offs]


@pytest.mark.parametrize("compression", ["zip", "zips", "none"])
@pytest.mark.parametrize("pixel_type", ["float", "half"])
@pytest.mark.parametrize("shape", [(48, 64, 3), (37, 5, 4), (17, 9)])
def test_roundtrip(tmp_path, compression, pixel_type, shape):
    a = _img(*shape, 1) if len(shape) == 2 else _img(*shape)
    a = a[:, :, 0] if len(shape) == 2 else a
    p = exr.write_exr(tmp_path / "x.exr", a, pixel_type=pixel_type, compression=compression)
    hdr = exr.read_exr_header(p)
    assert hdr["compression"] == compression
    assert {c["type"] for c in hdr["channels"]} == {2 if pixel_type == "float" else 1}
    back = exr.read_exr(p)
    assert back.dtype == np.float32
    expect = a if a.ndim == 3 else a[:, :, None]
    if pixel_type == "half":
        expect = expect.astype(np.float16).astype(np.float32)
    np.testing.assert_array_equal(back, expect)
    names = [c["name"] for c in hdr["channels"]]
    assert names == sorted(names)  # OpenEXR channel order


def test_default_channel_names_and_order(tmp_path):
    a = np.stack([np.full((4, 6), v, np.float32) for v in (1.0, 2.0, 3.0, 0.5)], axis=-1)
    exr.write_exr(tmp_path / "rgba.exr", a)
    assert [c["name"] for c in exr.read_exr_header(tmp_path / "rgba.exr")["channels"]] == ["A", "B", "G", "R"]
    back = exr.read_exr(tmp_path / "rgba.exr")
    np.testing.assert_array_equal(back[0, 0], [1.0, 2.0, 3.0, 0.5])  # returned as R,G,B,A
    exr.write_exr(tmp_path / "z.exr", a[:, :, 0], channels="Z")
    ch = exr.read_exr_channels(tmp_path / "z.exr")
    assert list(ch) == ["Z"] and ch["Z"].shape == (4, 6)
    assert exr.read_exr(tmp_path / "z.exr").shape == (4, 6, 1)


def test_row0_is_top_and_zip_blocks(tmp_path):
    h, w = 40, 7
    a = np.repeat(np.arange(h, dtype=np.float32)[:, None], w, axis=1)
    p = exr.write_exr(tmp_path / "rows.exr", a, compression="zip")
    assert _chunk_ys(p) == [0, 16, 32]  # 16-line ZIP blocks
    assert exr.read_exr_channels(p)["Y"][0, 0] == 0.0 and exr.read_exr_channels(p)["Y"][-1, 0] == h - 1
    p2 = exr.write_exr(tmp_path / "rows_zips.exr", a, compression="zips")
    assert _chunk_ys(p2) == list(range(h))


def test_specials_survive(tmp_path):
    a = np.array([[np.inf, -np.inf, np.nan, -0.0, 65504.0, 1e-30]], np.float32)
    back = exr.read_exr(exr.write_exr(tmp_path / "s.exr", a, channels="Y"))[:, :, 0]
    np.testing.assert_array_equal(back, a)  # assert_array_equal treats NaN == NaN


def test_errors(tmp_path):
    with pytest.raises(ValueError):
        exr.write_exr(tmp_path / "bad.exr", np.zeros((2, 2, 2)))  # 2 channels need names
    with pytest.raises(ValueError):
        exr.write_exr(tmp_path / "bad.exr", np.zeros((2, 2, 3)), channels="R,G")
    with pytest.raises(ValueError):
        exr.write_exr(tmp_path / "bad.exr", np.zeros((2, 2)), compression="piz")
    (tmp_path / "junk.exr").write_bytes(b"not an exr file at all")
    with pytest.raises(exr.ExrError):
        exr.read_exr(tmp_path / "junk.exr")


# ------------------------------------------------------------------------------------------ independent: OpenEXR


@pytest.mark.parametrize("compression", ["zip", "zips", "none"])
@pytest.mark.parametrize("pixel_type", ["float", "half"])
def test_openexr_reads_ours(tmp_path, compression, pixel_type):
    OpenEXR = pytest.importorskip("OpenEXR")
    a = _img(33, 21, 3, seed=2)
    p = exr.write_exr(tmp_path / "o.exr", a, pixel_type=pixel_type, compression=compression)
    f = OpenEXR.File(str(p), separate_channels=True)
    ch = f.channels()
    expect = a.astype(np.float16) if pixel_type == "half" else a
    for i, n in enumerate("RGB"):
        assert ch[n].pixels.dtype == expect.dtype
        np.testing.assert_array_equal(ch[n].pixels, expect[:, :, i])


@pytest.mark.parametrize("comp", ["NO_COMPRESSION", "RLE_COMPRESSION", "ZIPS_COMPRESSION", "ZIP_COMPRESSION",
                                  "PIZ_COMPRESSION"])
@pytest.mark.parametrize("shape", [(48, 64), (33, 17), (5, 3)])
def test_we_read_openexr(tmp_path, comp, shape):
    OpenEXR = pytest.importorskip("OpenEXR")
    h, w = shape
    rng = np.random.default_rng(3)
    y, x = np.mgrid[0:h, 0:w]
    smooth = (np.sin(x / 5.0) * np.cos(y / 3.0) + 1.5).astype(np.float32)
    chans = {"R": smooth, "G": (rng.random((h, w)) * 4).astype(np.float32), "B": np.zeros((h, w), np.float32),
             "Z": (smooth * 2).astype(np.float16)}
    expect = {k: v.copy() for k, v in chans.items()}
    hdr = {"compression": getattr(OpenEXR, comp), "type": OpenEXR.scanlineimage}
    OpenEXR.File(hdr, dict(chans)).write(str(tmp_path / "t.exr"))
    got = exr.read_exr_channels(tmp_path / "t.exr", native=True)
    assert set(got) == set(expect)
    for k, v in expect.items():
        assert got[k].dtype == v.dtype
        np.testing.assert_array_equal(got[k], v)
    rgb = exr.read_exr(tmp_path / "t.exr")
    assert rgb.shape == (h, w, 3)  # R,G,B only; Z is not part of the colour triple


# ------------------------------------------------------------------------------------------ independent: Mitsuba


def _mi():
    mi = pytest.importorskip("mitsuba")
    if mi.variant() is None:
        mi.set_variant("scalar_rgb")
    return mi


@pytest.mark.parametrize("compression", ["zip", "none"])
@pytest.mark.parametrize("pixel_type", ["float", "half"])
def test_mitsuba_reads_ours(tmp_path, compression, pixel_type):
    mi = _mi()
    a = _img(24, 32, 3, seed=4)
    p = exr.write_exr(tmp_path / "m.exr", a, pixel_type=pixel_type, compression=compression)
    b = np.array(mi.Bitmap(str(p)), dtype=np.float32)
    expect = a.astype(np.float16).astype(np.float32) if pixel_type == "half" else a
    np.testing.assert_array_equal(b, expect)


def test_we_read_mitsuba_piz(tmp_path):
    mi = _mi()
    y, x = np.mgrid[0:48, 0:64]
    a = np.stack([np.sin(x / 7.0) + 1.0, np.cos(y / 5.0) + 1.0, (x + y) / 100.0], -1).astype(np.float32)
    mi.Bitmap(a).write(str(tmp_path / "mi.exr"))  # Mitsuba writes PIZ
    assert exr.read_exr_header(tmp_path / "mi.exr")["compression"] == "piz"
    np.testing.assert_array_equal(exr.read_exr(tmp_path / "mi.exr"), a)
