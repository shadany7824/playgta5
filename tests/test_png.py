"""tools/png.py: sRGB display encoding, PNG I/O, colormaps, tiles and grids."""

from __future__ import annotations

import numpy as np

from tools import png


def test_to_display_values():
    lin = np.array([[[0.0, 0.5, 1.0], [2.0, -1.0, 0.0031308]]])
    out = png.to_display(lin)
    assert out.dtype == np.uint8 and out.shape == (1, 2, 3)
    assert out[0, 0].tolist() == [0, 188, 255] and out[0, 1, :2].tolist() == [255, 0] and out[0, 1, 2] == 10
    assert png.to_display(np.full((1, 1), 0.25), exposure=2.0)[0, 0].tolist() == [188, 188, 188]
    np.testing.assert_allclose(png.srgb_decode(png.srgb_encode(np.linspace(0, 1, 11))), np.linspace(0, 1, 11),
                               atol=1e-12)


def test_png_roundtrip(tmp_path):
    a = (np.arange(4 * 5 * 3) % 256).astype(np.uint8).reshape(4, 5, 3)
    png.save_png(tmp_path / "x.png", a)
    np.testing.assert_array_equal(png.load_png(tmp_path / "x.png"), a)
    png.save_png(tmp_path / "g.png", a[:, :, 0])
    assert png.load_png(tmp_path / "g.png").shape == (4, 5, 3)


def test_diverging_and_magnitude():
    d = png.diverging(np.array([[-1.0, 0.0, 1.0]]), scale=1.0)
    neg, zero, pos = d[0].astype(int)
    assert neg[2] > neg[0] and pos[0] > pos[2] and zero.min() > 240
    assert png.magnitude(np.array([[0.5, -2.0, 100.0]]), gain=32)[0, :, 0].tolist() == [16, 64, 255]


def test_tiles_grid_sheet():
    a = np.zeros((10, 20, 3), np.uint8)
    t = png.label_tile(a, "web", font_size=10)
    assert t.shape[1] == 20 and t.shape[0] > 10
    assert png.label_tile(a, scale=2).shape == (20, 40, 3)
    g = png.grid([a, a, None, a], cols=2, pad=2)
    assert g.shape == (2 * 10 + 3 * 2, 2 * 20 + 3 * 2, 3)
    s = png.sheet([[(a, "web"), (a, "native"), (a, "|diff| x32")]], title="parity")
    assert s.ndim == 3 and s.shape[1] >= 3 * 20
