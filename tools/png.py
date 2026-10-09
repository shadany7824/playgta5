"""8-bit display images for sheets and parity (never used for measurement): sRGB encoding, PNG I/O,
labelled tiles, grids and a diverging colormap for signed error maps."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

__all__ = ["srgb_encode", "srgb_decode", "to_display", "save_png", "load_png", "diverging", "magnitude",
           "label_tile", "grid", "sheet", "DIVERGING_ANCHORS"]

# RdBu-like anchors (negative = blue, zero = near white, positive = red), positions in [-1, 1].
DIVERGING_ANCHORS = np.array([
    [-1.0, 5, 48, 97], [-0.5, 67, 147, 195], [0.0, 247, 247, 247], [0.5, 214, 96, 77], [1.0, 103, 0, 31],
], dtype=np.float64)


def srgb_encode(linear: np.ndarray) -> np.ndarray:
    """Linear [0,1] -> sRGB-encoded [0,1] (IEC 61966-2-1 piecewise curve)."""
    x = np.clip(np.nan_to_num(np.asarray(linear, dtype=np.float64), nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def srgb_decode(encoded: np.ndarray) -> np.ndarray:
    """sRGB-encoded values (uint8 or [0,1] floats) -> linear [0,1] float64."""
    e = np.asarray(encoded)
    x = e.astype(np.float64) / 255.0 if e.dtype == np.uint8 else e.astype(np.float64)
    return np.where(x <= 0.04045, x / 12.92, np.power((x + 0.055) / 1.055, 2.4))


def _rgb(img: np.ndarray) -> np.ndarray:
    a = np.asarray(img)
    if a.ndim == 2:
        a = a[:, :, None]
    if a.shape[2] == 1:
        a = np.repeat(a, 3, axis=2)
    return a[:, :, :3]


def to_display(linear: np.ndarray, exposure: float = 1.0) -> np.ndarray:
    """Linear HDR (H,W[,C]) -> uint8 sRGB (H,W,3): scale by exposure, clip, encode. No tonemapping."""
    a = _rgb(np.asarray(linear, dtype=np.float64)) * float(exposure)
    return np.round(srgb_encode(a) * 255.0).astype(np.uint8)


def _to_uint8(img: np.ndarray) -> np.ndarray:
    a = np.asarray(img)
    if a.dtype == np.uint8:
        return a
    return np.round(np.clip(np.nan_to_num(a.astype(np.float64)), 0.0, 1.0) * 255.0).astype(np.uint8)


def save_png(path, img) -> Path:
    """Save uint8 (or [0,1] float, written as-is without encoding) (H,W), (H,W,3) or (H,W,4) as PNG."""
    a = _to_uint8(img)
    if a.ndim == 3 and a.shape[2] == 1:
        a = a[:, :, 0]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    Image.fromarray(a).save(tmp, format="PNG")
    os.replace(tmp, path)
    return path


def load_png(path) -> np.ndarray:
    """Load a PNG as uint8 (H,W,3) RGB, or (H,W,4) when it has alpha."""
    with Image.open(path) as im:
        alpha = "A" in im.getbands() or "transparency" in im.info
        im = im.convert("RGBA" if alpha else "RGB")
        return np.array(im)


def diverging(signed: np.ndarray, scale: float | None = None) -> np.ndarray:
    """Signed values -> uint8 RGB: blue < 0 < red, white at 0. scale defaults to the 99th pct of |x|."""
    x = np.nan_to_num(np.asarray(signed, dtype=np.float64))
    if x.ndim == 3:
        x = x[:, :, 0] if x.shape[2] == 1 else 0.2126 * x[:, :, 0] + 0.7152 * x[:, :, 1] + 0.0722 * x[:, :, 2]
    if scale is None:
        scale = float(np.percentile(np.abs(x), 99)) if x.size else 1.0
    scale = scale if scale > 0 else 1.0
    t = np.clip(x / scale, -1.0, 1.0)
    out = np.empty(t.shape + (3,), dtype=np.float64)
    for c in range(3):
        out[..., c] = np.interp(t, DIVERGING_ANCHORS[:, 0], DIVERGING_ANCHORS[:, c + 1])
    return np.round(out).astype(np.uint8)


def magnitude(values: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """Non-negative values (e.g. |diff| in 8-bit LSB) -> grey uint8 RGB, value*gain clipped to 255."""
    a = np.abs(np.nan_to_num(np.asarray(values, dtype=np.float64))) * gain
    return np.clip(np.round(_rgb(a)), 0, 255).astype(np.uint8)


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def label_tile(img: np.ndarray, text: str = "", font_size: int = 12, bar: int | None = None,
               fg=(235, 235, 235), bg=(24, 24, 24), scale: int = 1) -> np.ndarray:
    """Return uint8 RGB tile = optional nearest-neighbour upscale of img with a caption bar on top."""
    a = _to_uint8(_rgb(img))
    if scale > 1:
        a = np.repeat(np.repeat(a, scale, axis=0), scale, axis=1)
    if not text:
        return a
    lines = text.split("\n")
    bar = bar or (font_size + 6) * len(lines)
    tile = Image.new("RGB", (a.shape[1], a.shape[0] + bar), bg)
    tile.paste(Image.fromarray(a), (0, bar))
    draw = ImageDraw.Draw(tile)
    font = _font(font_size)
    for i, line in enumerate(lines):
        draw.text((3, 2 + i * (font_size + 6)), line, fill=fg, font=font)
    return np.array(tile)


def grid(tiles: Sequence[np.ndarray | None], cols: int, pad: int = 4, bg=(40, 40, 40)) -> np.ndarray:
    """Assemble tiles (uint8 RGB, any sizes; None = empty cell) row-major into a grid image."""
    tiles = list(tiles)
    if not tiles:
        return np.zeros((1, 1, 3), np.uint8)
    cols = max(1, min(cols, len(tiles)))
    rows = (len(tiles) + cols - 1) // cols
    arrs = [None if t is None else _to_uint8(_rgb(t)) for t in tiles]
    cw = [max([arrs[r * cols + c].shape[1] for r in range(rows)
               if r * cols + c < len(arrs) and arrs[r * cols + c] is not None] or [1]) for c in range(cols)]
    rh = [max([arrs[r * cols + c].shape[0] for c in range(cols)
               if r * cols + c < len(arrs) and arrs[r * cols + c] is not None] or [1]) for r in range(rows)]
    out = np.empty((sum(rh) + pad * (rows + 1), sum(cw) + pad * (cols + 1), 3), np.uint8)
    out[:] = np.asarray(bg, np.uint8)
    y = pad
    for r in range(rows):
        x = pad
        for c in range(cols):
            k = r * cols + c
            if k < len(arrs) and arrs[k] is not None:
                t = arrs[k]
                out[y:y + t.shape[0], x:x + t.shape[1]] = t
            x += cw[c] + pad
        y += rh[r] + pad
    return out


def sheet(rows: Sequence[Sequence[tuple[np.ndarray | None, str]]], title: str = "", pad: int = 4,
          font_size: int = 12, scale: int = 1) -> np.ndarray:
    """Contact sheet: rows of (uint8 image, caption) cells, with an optional title bar."""
    rows = [list(r) for r in rows]
    cols = max((len(r) for r in rows), default=1)
    cells = []
    for r in rows:
        for c in range(cols):
            if c < len(r) and r[c][0] is not None:
                cells.append(label_tile(r[c][0], r[c][1], font_size=font_size, scale=scale))
            else:
                cells.append(None)
    body = grid(cells, cols, pad=pad)
    if title:
        body = label_tile(body, title, font_size=font_size + 2)
    return body
