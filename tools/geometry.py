"""Shape resolution to flat-shaded triangle meshes and object transforms (DESIGN §2).

Everything is built in float64 and cast to float32 only at the end, so survey-origin subtraction happens before
the precision loss (DESIGN §1).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

__all__ = ["Mesh", "GeometryError", "box_mesh", "quad_mesh", "room_boxes", "room_mesh", "load_obj",
           "concat_meshes", "transform_matrix", "world_matrix", "transformed_mesh", "array_hash",
           "signed_volume", "ray_intersect", "WALLS", "WALL_AXES"]

WALLS = ("-x", "+x", "-y", "+y", "-z", "+z")
# wall -> (normal axis, u axis, v axis) for opening coordinates (DESIGN §2).
WALL_AXES = {"-x": (0, 1, 2), "+x": (0, 1, 2), "-y": (1, 0, 2), "+y": (1, 0, 2), "-z": (2, 0, 1), "+z": (2, 0, 1)}


class GeometryError(ValueError):
    """Invalid shape parameters. ``.path`` is a dotted path relative to the shape (may be empty)."""

    def __init__(self, msg: str, path: str = ""):
        super().__init__(msg)
        self.path = path
        self.msg = msg


@dataclass(eq=False)
class Mesh:
    """Triangle mesh: positions (N,3) f32, normals (N,3) f32 (unit), indices (M,3) u32."""

    positions: np.ndarray
    normals: np.ndarray
    indices: np.ndarray

    def __post_init__(self):
        self.positions = np.ascontiguousarray(np.asarray(self.positions, dtype=np.float32).reshape(-1, 3))
        self.normals = np.ascontiguousarray(np.asarray(self.normals, dtype=np.float32).reshape(-1, 3))
        self.indices = np.ascontiguousarray(np.asarray(self.indices, dtype=np.uint32).reshape(-1, 3))
        if self.positions.shape != self.normals.shape:
            raise GeometryError(f"positions {self.positions.shape} and normals {self.normals.shape} differ")
        if self.indices.size and int(self.indices.max()) >= len(self.positions):
            raise GeometryError("index out of range")

    @property
    def n_vertices(self) -> int:
        return len(self.positions)

    @property
    def n_triangles(self) -> int:
        return len(self.indices)

    def bbox(self) -> tuple[np.ndarray, np.ndarray]:
        p = self.positions.astype(np.float64)
        if not len(p):
            return np.zeros(3), np.zeros(3)
        return p.min(axis=0), p.max(axis=0)

    def hashes(self) -> dict[str, str]:
        return {"positions": array_hash(self.positions), "normals": array_hash(self.normals),
                "indices": array_hash(self.indices)}


def array_hash(arr: np.ndarray) -> str:
    """sha256 of dtype, shape and little-endian C-order bytes."""
    a = np.ascontiguousarray(arr)
    a = a.astype(a.dtype.newbyteorder("<"), copy=False)
    h = hashlib.sha256(f"{a.dtype.str}|{list(a.shape)}|".encode())
    h.update(a.tobytes())
    return h.hexdigest()


def _flat_mesh(tris: np.ndarray, normals: np.ndarray | None = None) -> Mesh:
    """(T,3,3) float64 triangles -> unshared-vertex flat-shaded Mesh."""
    tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if normals is None:
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        normals = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-300)
    pos = tris.reshape(-1, 3)
    nrm = np.repeat(np.asarray(normals, dtype=np.float64).reshape(-1, 3), 3, axis=0)
    idx = np.arange(len(pos), dtype=np.uint32).reshape(-1, 3)
    return Mesh(pos, nrm, idx)


def _quads_to_mesh(quads: np.ndarray, normals: np.ndarray) -> Mesh:
    """(Q,4,3) CCW quads + (Q,3) normals -> Mesh with 4 vertices and 2 triangles per quad."""
    q = np.asarray(quads, dtype=np.float64).reshape(-1, 4, 3)
    pos = q.reshape(-1, 3)
    nrm = np.repeat(np.asarray(normals, dtype=np.float64).reshape(-1, 3), 4, axis=0)
    base = (np.arange(len(q), dtype=np.uint32) * 4)[:, None]
    idx = np.concatenate([base + np.array([0, 1, 2], np.uint32), base + np.array([0, 2, 3], np.uint32)], axis=1)
    return Mesh(pos, nrm, idx.reshape(-1, 3))


def concat_meshes(meshes: Iterable[Mesh]) -> Mesh:
    meshes = list(meshes)
    if not meshes:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3)))
    offs = np.cumsum([0] + [m.n_vertices for m in meshes[:-1]])
    return Mesh(np.concatenate([m.positions for m in meshes]), np.concatenate([m.normals for m in meshes]),
                np.concatenate([m.indices.astype(np.int64) + o for m, o in zip(meshes, offs)]))


def _box_quads(bmin, bmax) -> tuple[np.ndarray, np.ndarray]:
    lo = np.asarray(bmin, dtype=np.float64)
    hi = np.asarray(bmax, dtype=np.float64)
    quads, normals = [], []
    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3  # e_b x e_c = e_a
        for s in (-1, 1):
            uv = [(0, 0), (1, 0), (1, 1), (0, 1)] if s > 0 else [(0, 0), (0, 1), (1, 1), (1, 0)]
            quad = []
            for ub, uc in uv:
                p = np.empty(3)
                p[a] = hi[a] if s > 0 else lo[a]
                p[b] = hi[b] if ub else lo[b]
                p[c] = hi[c] if uc else lo[c]
                quad.append(p)
            n = np.zeros(3)
            n[a] = s
            quads.append(quad)
            normals.append(n)
    return np.array(quads), np.array(normals)


def box_mesh(bmin, bmax) -> Mesh:
    """Axis-aligned box: 6 faces x 4 vertices, 12 triangles, outward normals."""
    lo = np.asarray(bmin, dtype=np.float64)
    hi = np.asarray(bmax, dtype=np.float64)
    if lo.shape != (3,) or hi.shape != (3,) or not np.all(np.isfinite(lo)) or not np.all(np.isfinite(hi)):
        raise GeometryError("box min/max must be 3 finite numbers")
    if np.any(hi <= lo):
        raise GeometryError(f"box max {hi.tolist()} must exceed min {lo.tolist()} on every axis")
    return _quads_to_mesh(*_box_quads(lo, hi))


def quad_mesh(origin, u, v) -> Mesh:
    """Parallelogram origin, origin+u, origin+u+v, origin+v; 2 triangles, normal normalize(u x v)."""
    o, u, v = (np.asarray(x, dtype=np.float64) for x in (origin, u, v))
    n = np.cross(u, v)
    ln = np.linalg.norm(n)
    if not np.isfinite(ln) or ln <= 1e-12 * max(1.0, np.linalg.norm(u) * np.linalg.norm(v)):
        raise GeometryError("quad u and v must be non-zero and not parallel")
    return _quads_to_mesh(np.array([[o, o + u, o + u + v, o + v]]), (n / ln)[None])


def _merge_cells(us: np.ndarray, vs: np.ndarray, solid: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Merge solid grid cells (rows = v) into rectangles: horizontal runs, then identical runs stacked."""
    rects = []
    active: dict[tuple[int, int], int] = {}
    for j in range(len(vs) - 1):
        runs = []
        i = 0
        while i < len(us) - 1:
            if solid[j, i]:
                k = i
                while k + 1 < len(us) - 1 and solid[j, k + 1]:
                    k += 1
                runs.append((i, k + 1))
                i = k + 1
            else:
                i += 1
        nxt = {}
        for r in runs:
            nxt[r] = active.pop(r, j)
        for (i0, i1), j0 in active.items():
            rects.append((us[i0], us[i1], vs[j0], vs[j]))
        active = nxt
    for (i0, i1), j0 in active.items():
        rects.append((us[i0], us[i1], vs[j0], vs[len(vs) - 1]))
    return rects


def room_boxes(bmin, bmax, thickness: float, omit: Sequence[str] = (), openings: Sequence[dict] = ()):
    """Slab boxes of a room: list of (wall, min, max).

    The interior is [bmin, bmax]; slabs grow outward by ``thickness``. Floor/ceiling span the full outer x/y
    extent, the +-x walls the outer y extent, the +-y walls the interior x extent, so slabs tile the shell
    without overlap. Openings ({"wall", "u": [a,b], "v": [c,d]}, local axis ranges, see WALL_AXES) must lie
    within the wall's interior face and cut through the slab.
    """
    lo = np.asarray(bmin, dtype=np.float64)
    hi = np.asarray(bmax, dtype=np.float64)
    t = float(thickness)
    if lo.shape != (3,) or hi.shape != (3,):
        raise GeometryError("room min/max must be 3 numbers")
    if np.any(hi <= lo):
        raise GeometryError(f"room max {hi.tolist()} must exceed min {lo.tolist()} on every axis", "max")
    if not (t > 0 and math.isfinite(t)):
        raise GeometryError("room thickness must be > 0", "thickness")
    omit = list(omit)
    for k, w in enumerate(omit):
        if w not in WALLS:
            raise GeometryError(f"unknown wall {w!r}; expected one of {list(WALLS)}", f"omit[{k}]")
    if len(set(omit)) != len(omit):
        raise GeometryError("duplicate wall in omit", "omit")
    olo, ohi = lo - t, hi + t
    slab = {
        "-z": ([olo[0], olo[1], olo[2]], [ohi[0], ohi[1], lo[2]]),
        "+z": ([olo[0], olo[1], hi[2]], [ohi[0], ohi[1], ohi[2]]),
        "-x": ([olo[0], olo[1], lo[2]], [lo[0], ohi[1], hi[2]]),
        "+x": ([hi[0], olo[1], lo[2]], [ohi[0], ohi[1], hi[2]]),
        "-y": ([lo[0], olo[1], lo[2]], [hi[0], lo[1], hi[2]]),
        "+y": ([lo[0], hi[1], lo[2]], [hi[0], ohi[1], hi[2]]),
    }
    holes: dict[str, list] = {w: [] for w in WALLS}
    for k, op in enumerate(openings):
        p = f"openings[{k}]"
        if not isinstance(op, dict):
            raise GeometryError("opening must be an object", p)
        w = op.get("wall")
        if w not in WALLS:
            raise GeometryError(f"unknown wall {w!r}; expected one of {list(WALLS)}", f"{p}.wall")
        if w in omit:
            raise GeometryError(f"opening on omitted wall {w!r}", f"{p}.wall")
        _, ua, va = WALL_AXES[w]
        rng = []
        for key, ax in (("u", ua), ("v", va)):
            r = op.get(key)
            try:
                r = [float(r[0]), float(r[1])] if len(r) == 2 else None
            except (TypeError, ValueError, KeyError):
                r = None
            if r is None or not all(map(math.isfinite, r)):
                raise GeometryError(f"{key} must be a [min, max] pair of numbers", f"{p}.{key}")
            if not r[1] > r[0]:
                raise GeometryError(f"{key} range {r} is empty", f"{p}.{key}")
            eps = 1e-9 * max(1.0, abs(lo[ax]), abs(hi[ax]))
            if r[0] < lo[ax] - eps or r[1] > hi[ax] + eps:
                raise GeometryError(f"{key} range {r} leaves the wall's interior face "
                                    f"[{lo[ax]:g}, {hi[ax]:g}] ({'xyz'[ax]} axis)", f"{p}.{key}")
            rng.append(r)
        holes[w].append(rng)
    boxes = []
    for w in WALLS:
        if w in omit:
            continue
        smin, smax = (np.array(x, dtype=np.float64) for x in slab[w])
        if not holes[w]:
            boxes.append((w, smin, smax))
            continue
        na, ua, va = WALL_AXES[w]
        us = np.unique(np.concatenate([[smin[ua], smax[ua]], np.ravel([h[0] for h in holes[w]])]))
        vs = np.unique(np.concatenate([[smin[va], smax[va]], np.ravel([h[1] for h in holes[w]])]))
        cu = 0.5 * (us[:-1] + us[1:])
        cv = 0.5 * (vs[:-1] + vs[1:])
        solid = np.ones((len(cv), len(cu)), dtype=bool)
        for (u0, u1), (v0, v1) in holes[w]:
            solid &= ~((cv[:, None] > v0) & (cv[:, None] < v1) & (cu[None, :] > u0) & (cu[None, :] < u1))
        for u0, u1, v0, v1 in _merge_cells(us, vs, solid):
            bmn, bmx = smin.copy(), smax.copy()
            bmn[ua], bmx[ua], bmn[va], bmx[va] = u0, u1, v0, v1
            boxes.append((w, bmn, bmx))
    return boxes


def room_mesh(bmin, bmax, thickness: float, omit: Sequence[str] = (), openings: Sequence[dict] = ()) -> Mesh:
    """Room shell as the union of closed slab boxes (see room_boxes)."""
    return concat_meshes(box_mesh(a, b) for _, a, b in room_boxes(bmin, bmax, thickness, omit, openings))


def _obj_index(tok: str, n: int, lineno: int, what: str) -> int:
    i = int(tok)
    j = n + i if i < 0 else i - 1
    if not 0 <= j < n:
        raise GeometryError(f"line {lineno}: {what} index {i} out of range (have {n})")
    return j


def load_obj(path, origin=None, coords: str = "local") -> Mesh:
    """Load an OBJ (v, vn, f; polygons fan-triangulated). Faces without (valid) vn are flat-shaded.

    coords='world': vertices are survey coordinates; ``origin`` (float64) is subtracted in float64 before the
    float32 cast. coords='local': vertices are already local.
    """
    if coords not in ("local", "world"):
        raise GeometryError(f"coords must be 'local' or 'world', not {coords!r}", "coords")
    vs: list[tuple[float, float, float]] = []
    vns: list[tuple[float, float, float]] = []
    faces: list[list[tuple[int, int]]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            tag = parts[0]
            try:
                if tag == "v":
                    vs.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif tag == "vn":
                    vns.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif tag == "f":
                    face = []
                    for tok in parts[1:]:
                        sub = tok.split("/")
                        vi = _obj_index(sub[0], len(vs), lineno, "vertex")
                        ni = _obj_index(sub[2], len(vns), lineno, "normal") if len(sub) >= 3 and sub[2] else -1
                        face.append((vi, ni))
                    if len(face) < 3:
                        raise GeometryError(f"line {lineno}: face with fewer than 3 vertices")
                    faces.append(face)
            except (IndexError, ValueError) as e:
                if isinstance(e, GeometryError):
                    raise
                raise GeometryError(f"line {lineno}: cannot parse {line!r}") from None
    if not faces:
        raise GeometryError(f"{Path(path).name}: no faces")
    P = np.array(vs, dtype=np.float64)
    if coords == "world":
        P = P - np.asarray(origin if origin is not None else (0.0, 0.0, 0.0), dtype=np.float64)
    N = np.array(vns, dtype=np.float64).reshape(-1, 3)
    if len(N):
        ln = np.linalg.norm(N, axis=1, keepdims=True)
        valid_n = ln[:, 0] > 1e-12
        N = N / np.where(ln > 1e-12, ln, 1.0)
    else:
        valid_n = np.zeros(0, bool)
    tris = []  # (v0, n0, v1, n1, v2, n2)
    for face in faces:
        for k in range(1, len(face) - 1):
            a, b, c = face[0], face[k], face[k + 1]
            tris.append((a[0], a[1], b[0], b[1], c[0], c[1]))
    T = np.array(tris, dtype=np.int64)
    tv = T[:, [0, 2, 4]]
    tn = T[:, [1, 3, 5]]
    pts = P[tv]  # (T,3,3)
    fn = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    area2 = np.linalg.norm(fn, axis=1)
    edge = np.max(np.stack([np.linalg.norm(pts[:, 1] - pts[:, 0], axis=1),
                            np.linalg.norm(pts[:, 2] - pts[:, 0], axis=1),
                            np.linalg.norm(pts[:, 2] - pts[:, 1], axis=1)]), axis=0)
    keep = area2 > 1e-12 * edge ** 2
    if not np.any(keep):
        raise GeometryError(f"{Path(path).name}: all faces are degenerate")
    tv, tn, pts, fn, area2 = tv[keep], tn[keep], pts[keep], fn[keep], area2[keep]
    fn = fn / area2[:, None]
    smooth = np.all(tn >= 0, axis=1)
    if len(valid_n):
        smooth &= np.all(np.where(tn >= 0, valid_n[np.maximum(tn, 0)], False), axis=1)
    else:
        smooth[:] = False
    meshes = []
    if np.any(~smooth):
        meshes.append(_flat_mesh(pts[~smooth], fn[~smooth]))
    if np.any(smooth):
        pairs = np.stack([tv[smooth].ravel(), tn[smooth].ravel()], axis=1)
        uniq, inv = np.unique(pairs, axis=0, return_inverse=True)
        meshes.append(Mesh(P[uniq[:, 0]], N[uniq[:, 1]], inv.reshape(-1, 3)))
    return concat_meshes(meshes)


def transform_matrix(transform: dict | None) -> np.ndarray:
    """{"translate", "rotate_z_deg", "pivot"} -> (4,4) float64: rotate about pivot, then translate."""
    t = transform or {}
    tr = np.asarray(t.get("translate", (0.0, 0.0, 0.0)), dtype=np.float64)
    pv = np.asarray(t.get("pivot", (0.0, 0.0, 0.0)), dtype=np.float64)
    th = math.radians(float(t.get("rotate_z_deg", 0.0)))
    c, s = math.cos(th), math.sin(th)
    # Exact values for multiples of 90 degrees keep axis-aligned geometry axis-aligned.
    c, s = (round(c) if abs(c - round(c)) < 1e-15 else c), (round(s) if abs(s - round(s)) < 1e-15 else s)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = tr + pv - R @ pv
    return M


def world_matrix(obj) -> np.ndarray:
    """The object's (4,4) float64 matrix mapping object space to the local frame."""
    return np.asarray(obj.transform, dtype=np.float64).reshape(4, 4)


def transformed_mesh(obj) -> Mesh:
    """obj.mesh with vertices and normals in the local frame (float64 maths, float32 result)."""
    M = world_matrix(obj)
    m = obj.mesh
    p = m.positions.astype(np.float64) @ M[:3, :3].T + M[:3, 3]
    nm = np.linalg.inv(M[:3, :3]).T
    n = m.normals.astype(np.float64) @ nm.T
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-300)
    return Mesh(p, n, m.indices.copy())


def signed_volume(mesh: Mesh) -> float:
    """Signed enclosed volume (positive for closed meshes with outward winding)."""
    p = mesh.positions.astype(np.float64)[mesh.indices.astype(np.int64)]
    return float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6.0)


def ray_intersect(mesh: Mesh, origins: np.ndarray, dirs: np.ndarray, chunk: int = 256) -> np.ndarray:
    """Nearest hit distance per ray (Moller-Trumbore, both sides); inf where the ray misses."""
    o = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    tri = mesh.positions.astype(np.float64)[mesh.indices.astype(np.int64)]
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    out = np.full(len(o), np.inf)
    chunk = max(1, min(chunk, 2_000_000 // max(1, len(tri))))  # bound the (rays x triangles) temporaries
    for s in range(0, len(o), chunk):
        oo, dd = o[s:s + chunk, None, :], d[s:s + chunk, None, :]
        pv = np.cross(dd, e2[None])
        det = np.einsum("rtk,tk->rt", pv, e1)
        ok = np.abs(det) > 1e-15
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = oo - v0[None]
        u = np.einsum("rtk,rtk->rt", tv, pv) * inv
        qv = np.cross(tv, e1[None])
        v = np.einsum("rtk,rtk->rt", np.broadcast_to(dd, qv.shape), qv) * inv
        t = np.einsum("rtk,tk->rt", qv, e2) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
        out[s:s + chunk] = np.where(hit, t, np.inf).min(axis=1)
    return out
