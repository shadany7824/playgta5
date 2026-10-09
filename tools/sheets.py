"""Contact sheets and temporal plots (display only; DESIGN §3 sheets/, temporal/). Pillow + numpy, no matplotlib.

``contact_sheet``: a grid with one column per image source (reference first, then each mode) and three rows:
``final`` | the measured component (``isolated``, or ``direct``) | the signed relative error of that component
against the reference column's, clipped to +-1 (blue = too dark, red = too bright), labelled with the mean of the
clipped |error| (so it saturates at 1 where ``rel_l1`` in metrics.json does not). Each image row uses one
display exposure taken from the reference: 0.8 / (99th-percentile luminance); a component row whose exposure would
exceed ``COMPONENT_EXPOSURE_MAX`` times the final row's (a reference component that is ~0) uses the final's.
Non-finite pixels show magenta.

``temporal_plot``: ROI-mean luminance per frame for several series, with dashed step markers and optional
per-state reference levels.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import png
from .metrics import luminance

__all__ = ["COMPONENT_EXPOSURE_MAX", "MASKED_RGB", "MIN_TILE_WIDTH", "NONFINITE_RGB", "SERIES_COLORS", "contact_sheet",
           "error_tile", "exposure_for", "relative_error", "temporal_plot"]

MIN_TILE_WIDTH = 192  # images narrower than this are upscaled (nearest) so captions fit
NONFINITE_RGB = (255, 0, 255)
COMPONENT_EXPOSURE_MAX = 1e3  # component-row exposure at most this many times the final row's, else the final's
MASKED_RGB = (64, 64, 64)
_EMPTY_RGB = (48, 48, 48)
# Categorical slots in fixed order (light surface), then neutral chart ink.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
_SURFACE, _INK, _INK2, _GRID, _MARK = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1", "#8c8b86"


def exposure_for(img, target: float = 0.8, percentile: float = 99.0) -> float:
    """Display exposure mapping the given luminance percentile of ``img`` to ``target`` (1.0 if undefined)."""
    if img is None:
        return 1.0
    Y = luminance(img)
    Y = Y[np.isfinite(Y)]
    if not Y.size:
        return 1.0
    p = float(np.percentile(Y, percentile))
    if not p > 0:
        pos = Y[Y > 0]
        p = float(pos.max()) if pos.size else 0.0
    return target / p if p > 0 and math.isfinite(target / p) else 1.0


def relative_error(component, ref_component, mask=None) -> np.ndarray:
    """Signed per-pixel (Y(c) - Y(r)) / (|Y(r)| + eps), eps = 0.01 |mean Y(r)| (over ``mask``), clipped to +-1."""
    yc, yr = luminance(component), luminance(ref_component)
    sel = np.isfinite(yr) if mask is None else (np.asarray(mask, bool) & np.isfinite(yr))
    mu = abs(float(yr[sel].mean())) if sel.any() else 0.0
    eps = 0.01 * mu if mu > 0 else 1e-12
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        e = (yc - yr) / (np.abs(yr) + eps)
    return np.clip(np.nan_to_num(e, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)


def _display(img, exposure: float) -> np.ndarray:
    a = np.asarray(img, dtype=np.float64)
    out = png.to_display(a, exposure)
    bad = ~np.isfinite(a)
    bad = bad.any(axis=-1) if a.ndim == 3 else bad
    out[bad] = NONFINITE_RGB
    return out


def error_tile(err, mask=None, nonfinite=None) -> np.ndarray:
    """Diverging uint8 RGB of a signed error in [-1, 1]; masked-out pixels grey, non-finite source magenta."""
    out = png.diverging(np.asarray(err, dtype=np.float64), scale=1.0)
    if mask is not None:
        out[~np.asarray(mask, bool)] = MASKED_RGB
    if nonfinite is not None:
        out[np.asarray(nonfinite, bool)] = NONFINITE_RGB
    return out


def _nonfinite(img) -> np.ndarray | None:
    if img is None:
        return None
    a = np.asarray(img)
    bad = ~np.isfinite(a)
    return bad.any(axis=-1) if a.ndim == 3 else bad


def contact_sheet(view_label: str, columns: Sequence[tuple], out_png, *, component_label: str = "isolated",
                  mask=None, font_size: int = 12, scale: int | None = None) -> Path:
    """Write a labelled contact sheet; columns = [(label, final, component, error_or_None), ...].

    The first column is the reference (its error cell is left blank unless given). For other columns an error of
    None is computed with ``relative_error(component, reference component, mask)``. A None image draws an empty
    "missing" cell. ``mask`` (e.g. masks['all']) greys out invalid pixels in the error row. Returns the PNG path.
    """
    if not columns:
        raise ValueError("contact_sheet needs at least the reference column")
    cols = [tuple(c) + (None,) * (4 - len(c)) for c in columns]
    ref_final, ref_comp = cols[0][1], cols[0][2]
    shapes = [np.asarray(x).shape[:2] for c in cols for x in c[1:4] if x is not None]
    if not shapes:
        raise ValueError("contact_sheet: no images")
    h, w = shapes[0]
    s = scale if scale is not None else max(1, math.ceil(MIN_TILE_WIDTH / w))
    exp_final, exp_comp = exposure_for(ref_final), exposure_for(ref_comp)
    if ref_final is not None and exp_comp > COMPONENT_EXPOSURE_MAX * exp_final:
        # the reference component is ~0 next to its final (e.g. full - direct of a lone plane is ~1e-13): its own
        # exposure (~1e8) would saturate every other column, so show the component row on the final's scale
        exp_comp = exp_final
    blank = np.full((h, w, 3), _EMPTY_RGB, np.uint8)

    rows = [[], [], []]
    for i, (label, final, comp, err) in enumerate(cols):
        rows[0].append((blank if final is None else _display(final, exp_final),
                        f"{label}\nfinal x{exp_final:.3g}" + ("" if final is not None else " (missing)")))
        rows[1].append((blank if comp is None else _display(comp, exp_comp),
                        f"{label}\n{component_label} x{exp_comp:.3g}" + ("" if comp is not None else " (missing)")))
        if err is None and i > 0 and comp is not None and ref_comp is not None \
                and np.asarray(comp).shape[:2] == np.asarray(ref_comp).shape[:2]:
            err = relative_error(comp, ref_comp, mask)
        if err is None or (mask is not None and np.asarray(err).shape[:2] != np.asarray(mask).shape):
            rows[2].append((blank, f"{label}\nrel. error: n/a"))
            continue
        e = np.asarray(err, dtype=np.float64)
        e = e if e.ndim == 2 else luminance(e)
        sel = np.ones(e.shape, bool) if mask is None else np.asarray(mask, bool)
        mae = float(np.mean(np.abs(np.clip(np.nan_to_num(e[sel]), -1, 1)))) if sel.any() else float("nan")
        rows[2].append((error_tile(np.clip(np.nan_to_num(e), -1, 1), mask, _nonfinite(comp)),
                        f"{label}\nclipped rel. err: mean|e| {mae:.3f}"))  # not rel_l1: |e| is clipped to 1
    img = png.sheet(rows, title=view_label, font_size=font_size, scale=s)
    return png.save_png(out_png, img)


# ------------------------------------------------------------------------------------------------ temporal plot

def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo
    if not span > 0:
        return [lo]
    raw = span / max(1, n)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step) * step
    ticks, t = [], first
    while t <= hi + 1e-9 * step:
        ticks.append(round(t, 12))
        t += step
    return ticks


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    return f"{v:.3g}" if 1e-3 <= a < 1e4 else f"{v:.2e}"


def _dashed_v(draw: ImageDraw.ImageDraw, x: float, y0: float, y1: float, fill, dash: int = 4) -> None:
    y = y0
    while y < y1:
        draw.line([(x, y), (x, min(y + dash, y1))], fill=fill, width=1)
        y += 2 * dash


def _dashed_h(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, fill, dash: int = 6, width: int = 2) -> None:
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x + dash, x1), y)], fill=fill, width=width)
        x += 2 * dash


def temporal_plot(series: Mapping[str, Sequence[float]], steps: Sequence[int], out_png, *, fps: float | None = None,
                  title: str = "", ylabel: str = "ROI mean Y (isolated)",
                  reference: Sequence[tuple[int, int, float]] | None = None,
                  size: tuple[int, int] = (720, 360)) -> Path:
    """Line chart of y(frame) per series (arrays indexed by frame; NaN breaks the line) with dashed vertical step
    markers and optional reference levels [(first, last, value)] drawn as dashed black segments. Returns the path."""
    W, H = int(size[0]), int(size[1])
    im = Image.new("RGB", (W, H), _SURFACE)
    d = ImageDraw.Draw(im)
    font = png._font(12)
    small = png._font(10)
    data = {k: np.asarray([np.nan if v is None else v for v in y], dtype=np.float64) for k, y in series.items()}
    names = list(data)
    legend_rows = 1 if names or reference else 0
    left, right, top, bottom = 64, 16, 44 if title else 24, 40 + 18 * legend_rows
    x0, x1, y0, y1 = left, W - right, top, H - bottom

    vals = [v[np.isfinite(v)] for v in data.values()]
    if reference:
        vals.append(np.asarray([r[2] for r in reference], dtype=np.float64))
    allv = np.concatenate([v for v in vals if v.size] or [np.zeros(1)])
    allv = allv[np.isfinite(allv)] if allv.size else np.zeros(1)
    lo, hi = (float(allv.min()), float(allv.max())) if allv.size else (0.0, 1.0)
    if not hi > lo:
        pad = abs(hi) * 0.1 or 1.0
        lo, hi = lo - pad, hi + pad
    else:
        pad = 0.06 * (hi - lo)
        lo, hi = lo - pad, hi + pad
    nframes = max([len(v) for v in data.values()] + [max(steps, default=0) + 1]
                  + [int(r[1]) + 1 for r in (reference or [])] + [2])
    fmax = nframes - 1

    def px(f):
        return x0 + (x1 - x0) * (f / fmax)

    def py(v):
        return y1 - (y1 - y0) * ((v - lo) / (hi - lo))

    if title:
        d.text((4, 6), title, fill=_INK, font=font)
    for t in _nice_ticks(lo, hi):  # recessive horizontal grid + y labels
        y = py(t)
        d.line([(x0, y), (x1, y)], fill=_GRID, width=1)
        label = _fmt(t)
        d.text((x0 - 6 - d.textlength(label, font=small), y - 6), label, fill=_INK2, font=small)
    for t in _nice_ticks(0, fmax, 8):
        if float(t).is_integer():
            x = px(t)
            d.line([(x, y1), (x, y1 + 4)], fill=_INK2, width=1)
            label = str(int(t))
            d.text((x - d.textlength(label, font=small) / 2, y1 + 6), label, fill=_INK2, font=small)
    d.line([(x0, y1), (x1, y1)], fill=_INK2, width=1)
    xlabel = "frame" + (f" ({fps:g} fps)" if fps else "")
    d.text(((x0 + x1) / 2 - d.textlength(xlabel, font=small) / 2, y1 + 20), xlabel, fill=_INK2, font=small)
    d.text((4, y0 - 14), ylabel, fill=_INK2, font=small)

    for f in steps:  # step markers
        x = px(f)
        _dashed_v(d, x, y0, y1, _MARK)
        lab = f"step {int(f)}"
        d.text((min(x + 3, x1 - d.textlength(lab, font=small)), y0 + 2), lab, fill=_INK2, font=small)
    for i, name in enumerate(names):
        y = data[name]
        col = SERIES_COLORS[i % len(SERIES_COLORS)]
        seg: list = []
        for k, v in enumerate(list(y) + [float("nan")]):  # NaN breaks the line; the sentinel flushes the last run
            if math.isfinite(v):
                seg.append((px(k), py(v)))
                continue
            if len(seg) > 1:
                d.line(seg, fill=col, width=2, joint="curve")
            elif seg:
                d.ellipse([seg[0][0] - 2, seg[0][1] - 2, seg[0][0] + 2, seg[0][1] + 2], fill=col)
            seg = []
    for first, last, v in reference or []:
        if v is not None and math.isfinite(v):
            _dashed_h(d, px(first), px(last), py(v), _INK)
    if legend_rows:  # legend: swatch + name in ink
        x, y = x0, H - 18
        items = [(n, SERIES_COLORS[i % len(SERIES_COLORS)], False) for i, n in enumerate(names)]
        if reference:
            items.append(("reference", _INK, True))
        for name, col, dashed in items:
            if dashed:
                _dashed_h(d, x, x + 18, y + 6, col, dash=4)
            else:
                d.line([(x, y + 6), (x + 18, y + 6)], fill=col, width=3)
            d.text((x + 22, y), name, fill=_INK, font=small)
            x += 22 + d.textlength(name, font=small) + 14
    return png.save_png(out_png, np.array(im))
