"""tools/sheets.py: contact sheet geometry, exposure, error colouring, NaN cells and the temporal plot."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tools import sheets
from tools.png import load_png

H, W = 48, 64


def _ref():
    yy, xx = np.mgrid[0:H, 0:W]
    full = np.stack([xx / W + 0.1, yy / H + 0.1, np.full((H, W), 0.5)], -1)
    direct = 0.7 * full
    return full, direct, full - direct


def _expected_size(ncols, h=H, w=W, font=12, pad=4):
    s = max(1, math.ceil(sheets.MIN_TILE_WIDTH / w))
    cell_h = h * s + (font + 6) * 2  # two caption lines
    width = ncols * w * s + pad * (ncols + 1)
    height = 3 * cell_h + pad * 4 + (font + 2 + 6)  # three rows + title bar
    return height, width, s, cell_h


def test_exposure_and_relative_error():
    img = np.zeros((10, 10, 3))
    img[:] = 1.0
    assert sheets.exposure_for(img) == pytest.approx(0.8)
    assert sheets.exposure_for(2.0 * img) == pytest.approx(0.4)
    assert sheets.exposure_for(np.zeros((4, 4, 3))) == 1.0 and sheets.exposure_for(None) == 1.0
    sparse = np.zeros((40, 40, 3))
    sparse[0, 0] = 4.0  # p99 is 0 -> falls back to the brightest pixel
    assert sheets.exposure_for(sparse) == pytest.approx(0.2)
    ref = np.full((4, 4, 3), 0.5)
    e = sheets.relative_error(1.2 * ref, ref)
    assert e == pytest.approx(np.full((4, 4), 0.2 / 1.01))
    assert sheets.relative_error(10 * ref, ref).max() == 1.0 and sheets.relative_error(0 * ref, ref).min() < -0.98
    bad = ref.copy()
    bad[0, 0] = np.nan
    assert np.isfinite(sheets.relative_error(bad, ref)).all()


def test_contact_sheet_layout_and_colours(tmp_path):
    full, direct, iso = _ref()
    eng_iso = 1.5 * iso  # +50 % isolated: the error tile is red
    eng_final = direct + eng_iso
    nan_final = eng_final.copy()
    nan_final[10, 10] = np.nan
    cols = [("reference", full, iso, None), ("direct", direct, np.zeros_like(iso), None),
            ("probe", eng_final, eng_iso, None), ("bad", nan_final, nan_final - direct, None)]
    out = sheets.contact_sheet("mini / s0", cols, tmp_path / "sheets" / "mini" / "s0.png")
    assert out.is_file()
    img = load_png(out)
    h, w, s, cell_h = _expected_size(len(cols))
    assert img.shape == (h, w, 3)
    title, pad, cap = 20, 4, 36
    cw = W * s

    def pixel(row, col, y, x):  # (y, x) inside the image part of cell (row, col)
        top = title + pad + row * (cell_h + pad) + cap
        left = pad + col * (cw + pad)
        return img[top + y * s + s // 2, left + x * s + s // 2].astype(int)

    r, _, b = pixel(2, 2, 20, 30)
    assert r > b + 60  # probe too bright -> red
    r, _, b = pixel(2, 1, 20, 30)
    assert b > r + 60  # direct mode has no isolated light -> blue (-1)
    assert pixel(0, 3, 10, 10).tolist() == list(sheets.NONFINITE_RGB)  # NaN shows magenta
    assert pixel(1, 1, 20, 30).tolist() == [0, 0, 0]
    # the reference's final row uses exposure 0.8 / p99: brightest pixels stay below white
    assert pixel(0, 0, H - 1, W - 1).max() < 255


def test_contact_sheet_missing_mask_and_given_error(tmp_path):
    full, _, iso = _ref()
    mask = np.ones((H, W), bool)
    mask[:5] = False
    given = np.full((H, W), 0.5)
    out = sheets.contact_sheet("v", [("reference", full, iso), ("future", None, None, None),
                                     ("fake", full, iso, given)], tmp_path / "x.png", mask=mask,
                               component_label="direct")
    img = load_png(out)
    h, w, s, cell_h = _expected_size(3)
    assert img.shape == (h, w, 3)
    top = 20 + 4 + 2 * (cell_h + 4) + 36
    left = 4 + 2 * (W * s + 4)
    assert img[top + 1, left + 1].tolist() == list(sheets.MASKED_RGB)  # masked rows grey
    r, _, b = img[top + 20 * s, left + 20 * s].astype(int)
    assert r > b  # the supplied +0.5 error is drawn as given
    with pytest.raises(ValueError):
        sheets.contact_sheet("v", [], tmp_path / "y.png")


def test_contact_sheet_large_images_not_upscaled(tmp_path):
    big = np.full((100, 256, 3), 0.25)
    img = load_png(sheets.contact_sheet("v", [("reference", big, big, None), ("m", big, big, None)],
                                        tmp_path / "b.png"))
    h, w, s, _ = _expected_size(2, h=100, w=256)
    assert s == 1 and img.shape == (h, w, 3)


def test_temporal_plot(tmp_path):
    fps, step, end = 60, 120, 239
    k = np.arange(end + 1)
    y = np.where(k < step, 1.0, 0.2 + 0.8 * np.exp(-(k - step) / 9.0))
    y2 = np.where(k < step, 1.05, 0.25).astype(float)
    y2[50:60] = np.nan
    out = sheets.temporal_plot({"probe_dynamic": y, "probe": y2}, [step], tmp_path / "t.png", fps=fps,
                               title="dyn / floor", reference=[(0, step - 1, 1.0), (step, end, 0.2)])
    img = load_png(out)
    assert img.shape == (360, 720, 3)
    colours = {tuple(c) for c in img.reshape(-1, 3)}
    for hexcol in sheets.SERIES_COLORS[:2]:
        assert tuple(int(hexcol[i:i + 2], 16) for i in (1, 3, 5)) in colours
    small = load_png(sheets.temporal_plot({"a": [1.0, 1.0, 1.0]}, [], tmp_path / "s.png", size=(300, 200)))
    assert small.shape == (200, 300, 3)
    empty = load_png(sheets.temporal_plot({}, [5], tmp_path / "e.png"))
    assert empty.shape == (360, 720, 3)
    single = load_png(sheets.temporal_plot({"a": [np.nan, 2.0, np.nan]}, [1], tmp_path / "p.png"))
    assert single.shape == (360, 720, 3)


def test_contact_sheet_size_mismatch_does_not_crash(tmp_path):
    full, _, iso = _ref()
    small = np.full((10, 12, 3), 0.5)
    out = sheets.contact_sheet("v", [("reference", full, iso), ("wrong size", small, small, None)],
                               tmp_path / "m.png", mask=np.ones((H, W), bool))
    assert load_png(out).shape[0] > H


def test_component_row_of_a_zero_reference_uses_the_final_exposure(tmp_path):
    """full - direct of a lone plane is ~1e-13: its own exposure (~1e13) would saturate the engines' columns."""
    full, direct, _ = _ref()
    noise_iso = np.full((H, W, 3), 1e-13)
    eng_iso = 0.05 * full
    cols = [("reference", full, noise_iso, None), ("probe", direct + eng_iso, eng_iso, None)]
    out = sheets.contact_sheet("zero / s0", cols, tmp_path / "z.png")
    img = load_png(out)
    h, w, s, cell_h = _expected_size(len(cols))
    top = 20 + 4 + (cell_h + 4) + 36  # the component row's image
    left = 4 + W * s + 4  # the probe column
    tile = img[top:top + H * s, left:left + W * s].astype(int)
    assert 0 < tile.max() < 255  # on the final's scale: visible, not saturated white

