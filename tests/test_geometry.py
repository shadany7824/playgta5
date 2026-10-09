"""tools/geometry.py: shapes, rooms (openings, omit, sealing), OBJ loading, transforms."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from tools import geometry as g


def _face_normals(m: g.Mesh) -> np.ndarray:
    p = m.positions.astype(np.float64)[m.indices.astype(np.int64)]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def _assert_outward(m: g.Mesh, center):
    p = m.positions.astype(np.float64)[m.indices.astype(np.int64)]
    fn = _face_normals(m)
    stored = m.normals.astype(np.float64)[m.indices.astype(np.int64)].mean(axis=1)
    np.testing.assert_allclose(fn, stored, atol=1e-6)  # winding agrees with the stored normal
    assert np.all(np.einsum("ij,ij->i", fn, p.mean(axis=1) - center) > 0)


def test_box_mesh_outward():
    lo, hi = np.array([-1.0, -2.0, 0.0]), np.array([3.0, 1.0, 0.5])
    m = g.box_mesh(lo, hi)
    assert (m.n_vertices, m.n_triangles) == (24, 12)
    assert m.positions.dtype == np.float32 and m.indices.dtype == np.uint32
    _assert_outward(m, (lo + hi) / 2)
    assert g.signed_volume(m) == pytest.approx(np.prod(hi - lo))
    with pytest.raises(g.GeometryError):
        g.box_mesh([0, 0, 0], [1, 0, 1])


def test_quad_normal():
    u, v = np.array([2.0, 0.0, 0.0]), np.array([0.0, 0.0, 3.0])
    m = g.quad_mesh([1, 1, 1], u, v)
    n = np.cross(u, v) / np.linalg.norm(np.cross(u, v))
    np.testing.assert_allclose(_face_normals(m), [n, n], atol=1e-7)
    np.testing.assert_allclose(m.normals, np.tile(n, (4, 1)))
    with pytest.raises(g.GeometryError):
        g.quad_mesh([0, 0, 0], u, 2 * u)


def _random_dirs(n, seed=0):
    d = np.random.default_rng(seed).normal(size=(n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _boxes_overlap_volume(boxes):
    tot = 0.0
    for (_, a0, a1), (_, b0, b1) in itertools.combinations(boxes, 2):
        ext = np.minimum(a1, b1) - np.maximum(a0, b0)
        if np.all(ext > 0):
            tot += float(np.prod(ext))
    return tot


def test_sealed_room_is_watertight():
    lo, hi, t = np.array([-2.0, -1.5, 0.0]), np.array([2.0, 1.5, 2.5]), 0.1
    boxes = g.room_boxes(lo, hi, t)
    assert sorted(w for w, _, _ in boxes) == sorted(g.WALLS)
    assert _boxes_overlap_volume(boxes) == 0.0
    shell = np.prod(hi - lo + 2 * t) - np.prod(hi - lo)
    assert sum(float(np.prod(b1 - b0)) for _, b0, b1 in boxes) == pytest.approx(shell)
    m = g.room_mesh(lo, hi, t)
    assert g.signed_volume(m) == pytest.approx(shell)  # every slab closed and outward
    rng = np.random.default_rng(1)
    origins = lo + 0.05 + rng.random((400, 3)) * (hi - lo - 0.1)
    hits = g.ray_intersect(m, origins, _random_dirs(400))
    assert np.all(np.isfinite(hits)), "a ray left the sealed room"


def test_room_opening_leaves_hole():
    lo, hi = np.array([-2.0, -1.5, 0.0]), np.array([2.0, 1.5, 2.5])
    op = {"wall": "+x", "u": [-0.5, 0.5], "v": [0.0, 2.0]}
    m = g.room_mesh(lo, hi, 0.2, openings=[op])
    boxes = g.room_boxes(lo, hi, 0.2, openings=[op])
    assert _boxes_overlap_volume(boxes) == 0.0
    plus_x = [b for b in boxes if b[0] == "+x"]
    assert len(plus_x) == 3  # left, right, lintel
    o = np.array([[0.0, 0.0, 1.0]] * 3)
    through = np.array([[2.0, 0.0, 1.0], [2.0, 0.4, 0.2], [2.0, -0.45, 1.9]]) - o
    assert np.all(np.isinf(g.ray_intersect(m, o, through)))  # straight out of the door
    blocked = np.array([[2.0, 1.0, 1.0], [2.0, 0.0, 2.2], [2.0, -0.7, 0.5]]) - o
    t = g.ray_intersect(m, o, blocked / np.linalg.norm(blocked, axis=1, keepdims=True))
    assert np.all(np.isfinite(t))
    # Rays from inside escape only through the opening's solid angle.
    rng = np.random.default_rng(2)
    origins = lo + 0.2 + rng.random((300, 3)) * (hi - lo - 0.4)
    d = _random_dirs(300, 3)
    miss = np.isinf(g.ray_intersect(m, origins, d))
    assert miss.any()
    # every escaping ray crosses x = 2 inside the opening rectangle
    s = (2.0 - origins[miss, 0]) / d[miss, 0]
    assert np.all(s > 0)
    cross = origins[miss] + s[:, None] * d[miss]
    assert np.all((cross[:, 1] >= -0.5) & (cross[:, 1] <= 0.5) & (cross[:, 2] >= 0.0) & (cross[:, 2] <= 2.0))


def test_room_omit():
    lo, hi = np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0])
    boxes = g.room_boxes(lo, hi, 0.1, omit=["+z"])
    assert "+z" not in {w for w, _, _ in boxes} and len(boxes) == 5
    m = g.room_mesh(lo, hi, 0.1, omit=["+z"])
    o = np.array([[0.5, 0.5, 0.5]])
    assert np.isinf(g.ray_intersect(m, o, [[0.0, 0.0, 1.0]]))[0]
    assert np.isfinite(g.ray_intersect(m, o, [[0.0, 0.0, -1.0]]))[0]


def test_room_validation():
    with pytest.raises(g.GeometryError) as e:
        g.room_boxes([0, 0, 0], [1, 1, 1], 0.1, openings=[{"wall": "+x", "u": [0.5, 1.5], "v": [0, 0.5]}])
    assert e.value.path == "openings[0].u"
    with pytest.raises(g.GeometryError) as e:
        g.room_boxes([0, 0, 0], [1, 1, 1], 0.1, omit=["+w"])
    assert e.value.path == "omit[0]"
    with pytest.raises(g.GeometryError) as e:
        g.room_boxes([0, 0, 0], [1, 1, 1], 0.1, omit=["+x"], openings=[{"wall": "+x", "u": [0.2, 0.4], "v": [0, 1]}])
    assert e.value.path == "openings[0].wall"
    with pytest.raises(g.GeometryError) as e:
        g.room_boxes([0, 0, 0], [1, 1, 1], 0.0)
    assert e.value.path == "thickness"


def test_obj_fan_flat_and_smooth(tmp_path):
    p = tmp_path / "m.obj"
    p.write_text(
        "# quad (flat) + pentagon (smooth via vn), negative index on last face\n"
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "v 0 0 1\nv 1 0 1\nv 1.5 0.5 1\nv 1 1 1\nv 0 1 1\n"
        "vn 0 0 2\n"
        "f 1 2 3 4\n"
        "f 5//1 6//1 7//1 8//1 9//1\n"
        "f -3 -2 -1\n", encoding="utf-8")
    m = g.load_obj(p)
    assert m.n_triangles == 2 + 3 + 1
    np.testing.assert_allclose(np.linalg.norm(m.normals, axis=1), 1.0, atol=1e-6)
    fn = _face_normals(m)
    np.testing.assert_allclose(fn, np.tile([0, 0, 1.0], (6, 1)), atol=1e-6)
    # smooth face vertices are shared (5 unique (v, vn) pairs); flat faces get their own vertices
    assert m.n_vertices == 2 * 3 + 5 + 3


def test_obj_world_coords_subtract_origin_in_float64(tmp_path):
    p = tmp_path / "w.obj"
    p.write_text("v 346001.2345 6297003.4567 571.0001\nv 346002.2345 6297003.4567 571.0001\n"
                 "v 346001.2345 6297004.4567 571.0001\nf 1 2 3\n", encoding="utf-8")
    origin = np.array([346000.0, 6297000.0, 570.0])
    m = g.load_obj(p, origin=origin, coords="world")
    np.testing.assert_allclose(m.positions[0], [1.2345, 3.4567, 1.0001], atol=1e-6)
    naive = (np.array([346001.2345, 6297003.4567, 571.0001], np.float32).astype(np.float64) - origin)
    assert np.max(np.abs(naive - [1.2345, 3.4567, 1.0001])) > 1e-3  # what float32-first would lose
    with pytest.raises(g.GeometryError):
        g.load_obj(p, coords="survey")


def test_transform_rotate_about_pivot_then_translate():
    M = g.transform_matrix({"translate": [1, 0, 0], "rotate_z_deg": 90, "pivot": [1, 1, 0]})
    p = M @ np.array([2.0, 1.0, 5.0, 1.0])
    np.testing.assert_allclose(p[:3], [1 + 1, 2, 5])  # (2,1) about (1,1) by 90 deg -> (1,2), then +x
    assert M[0, 0] == 0.0 and M[1, 0] == 1.0  # exact for multiples of 90 degrees

    class O:
        transform = M
        mesh = g.quad_mesh([0, 0, 0], [1, 0, 0], [0, 0, 1])  # normal -y

    tm = g.transformed_mesh(O)
    np.testing.assert_allclose(tm.normals[0], [1.0, 0.0, 0.0], atol=1e-7)  # -y rotated by +90 deg about z
    np.testing.assert_allclose(g.world_matrix(O), M)


def test_array_hash_stable():
    a = np.arange(12, dtype=np.float32).reshape(4, 3)
    assert g.array_hash(a) == g.array_hash(a.copy())
    assert g.array_hash(a) != g.array_hash(a.reshape(3, 4))
    assert g.array_hash(a) != g.array_hash(a.astype(np.float64))
