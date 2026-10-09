"""tools/masks.py: valid pixels, ROI selection on synthetic AOVs, 4-neighbourhood erosion, view filters."""

from __future__ import annotations

import numpy as np
import pytest

from tools import masks as MK
from tools.exr import write_exr
from tools.spec import ROI, expand_views

H, W = 12, 16


def _aux():
    """Floor (z = 0, normal +z) in rows 6..11, wall (x = 2, normal -x) in rows 1..5, sky (miss) in row 0.

    Position x runs with the column (0..1.5 m), so a box on x selects columns."""
    depth = np.full((H, W), 3.0)
    normal = np.zeros((H, W, 3))
    pos = np.zeros((H, W, 3))
    cols = np.arange(W) * 0.1
    depth[0] = 0.0  # miss
    normal[1:6] = [-1.0, 0.0, 0.0]
    pos[1:6, :, 0] = 2.0
    pos[1:6, :, 1] = cols[None, :]
    pos[1:6, :, 2] = np.linspace(1.0, 0.2, 5)[:, None]
    normal[6:] = [0.0, 0.0, 1.0]
    pos[6:, :, 0] = cols[None, :]
    pos[6:, :, 1] = np.linspace(1.0, 0.2, 6)[:, None]
    normal[5, 7] = [-0.6, 0.0, 0.6]  # silhouette pixel: |n| ~ 0.85 -> invalid
    return {"depth": depth, "normal": normal, "position": pos}


def test_erode_four_neighbourhood():
    m = np.zeros((7, 7), bool)
    m[2:5, 2:5] = True
    e = MK.erode(m)
    assert e.sum() == 1 and e[3, 3]
    plus = np.zeros((5, 5), bool)
    plus[2, 1:4] = plus[1:4, 2] = True
    assert MK.erode(plus).sum() == 1 and MK.erode(plus)[2, 2]  # diagonals do not matter
    single = np.zeros((5, 5), bool)
    single[2, 2] = True
    assert not MK.erode(single).any()
    assert MK.erode(np.ones((4, 6), bool)).all()  # the image border is not an edge
    half = np.zeros((4, 6), bool)
    half[:, :3] = True
    assert MK.erode(half)[:, :2].all() and not MK.erode(half)[:, 2:].any()
    assert MK.erode(m, 0).sum() == 9 and MK.erode(m, 2).sum() == 0


def test_valid_mask_rules():
    a = _aux()
    v = MK.valid_mask(a)
    assert not v[0].any()  # depth 0
    assert not v[5, 7]  # short normal
    assert v[1:, :].sum() == (H - 1) * W - 1
    a2 = dict(a, normal=a["normal"].copy())
    a2["normal"][8, 3] = np.nan
    assert not MK.valid_mask(a2)[8, 3]
    a3 = dict(a, depth=a["depth"][..., None])  # (H,W,1) depth accepted
    np.testing.assert_array_equal(MK.valid_mask(a3), v)


def test_roi_box_normal_and_erosion():
    a = _aux()
    floor = ROI("floor", "lit", np.array([-1.0, -1.0, -0.01]), np.array([5.0, 5.0, 0.01]), np.array([0.0, 0.0, 1.0]),
                0.9)
    raw = MK.roi_mask(floor, a)
    assert raw[6:].all() and not raw[:6].any()
    out = MK.view_masks("s0", a, rois=[floor])
    # floor rows 6..11 eroded: row 6 touches the wall rows above, the bottom border is not an edge
    assert out["floor"][7:].all() and not out["floor"][:7].any()
    # 'all' eroded: rows next to the sky and the pixels around the silhouette pixel go
    allm = out["all"]
    assert not allm[:2].any() and allm[2:].sum() == (H - 2) * W - 5
    assert not allm[5, 7] and not allm[4, 7] and not allm[6, 7] and not allm[5, 6] and not allm[5, 8]
    assert allm[4, 6]  # diagonal neighbour stays
    # every ROI is inside 'all'
    assert not (out["floor"] & ~allm).any()
    # floor x = 0.1 * column, so a box x in [0.25, 0.85] picks floor columns 3..8 (the wall is at x = 2)
    strip = ROI("strip", "any", np.array([0.25, -5, -5]), np.array([0.85, 5, 5]))
    sm = MK.view_masks("s0", a, rois=[strip])["strip"]
    cols = np.nonzero(sm.any(axis=0))[0]
    assert cols.tolist() == list(range(4, 8))  # raw columns 3..8, eroded by one on each side
    wall = ROI("wall", "dark", np.array([1.99, -5, -5]), np.array([2.01, 5, 5]), np.array([-1.0, 0, 0]), 0.95)
    wm = MK.view_masks("s0", a, rois=[wall])["wall"]
    assert wm[2:5].sum() > 0 and not wm[5:].any() and not wm[:2].any()
    flipped = ROI("w2", "dark", np.array([1.99, -5, -5]), np.array([2.01, 5, 5]), np.array([1.0, 0, 0]), 0.0)
    assert not MK.view_masks("s0", a, rois=[flipped])["w2"].any()  # stored normals are not flipped


def test_view_filter_and_real_scene(tiny_scene, tmp_path):
    sc = tiny_scene("mini_room")
    views = {v.id: v for v in expand_views(sc)}
    h, w = sc.height, sc.width
    aux = {"depth": np.ones((h, w)), "normal": np.tile([0.0, 0.0, 1.0], (h, w, 1)),
           "position": np.zeros((h, w, 3))}
    inside = MK.view_masks(views["inside"], aux)
    outside = MK.view_masks(views["outside"], aux)
    assert set(inside) == {"all", "floor"} and set(outside) == {"all", "floor", "back_wall"}
    assert inside["all"].all() and inside["floor"].all() and not outside["back_wall"].any()
    assert inside["floor"].dtype == bool and inside["floor"].shape == (h, w)
    # from a reference directory
    write_exr(tmp_path / "depth.exr", aux["depth"].astype(np.float32), channels="Z")
    write_exr(tmp_path / "normal.exr", aux["normal"].astype(np.float32), channels="R,G,B")
    write_exr(tmp_path / "position.exr", aux["position"].astype(np.float32), channels="R,G,B")
    from_dir = MK.view_masks(views["outside"], tmp_path)
    for k in outside:
        np.testing.assert_array_equal(from_dir[k], outside[k])
    loaded = MK.load_aux(tmp_path)
    assert loaded["depth"].shape == (h, w) and loaded["normal"].shape == (h, w, 3)


def test_bad_inputs():
    with pytest.raises(KeyError):
        MK.view_masks("s0", {"depth": np.ones((2, 2))})
    with pytest.raises(TypeError):
        MK.view_masks("s0", 42)
