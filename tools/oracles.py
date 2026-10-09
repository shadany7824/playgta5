"""Analytic oracles for the calibration scenes (DESIGN §8), evaluated per pixel from the reference AOVs.

``oracle_images(scene, aux, station)`` returns ``{"direct", "full", "isolated"}`` linear RGB images (H, W, 3,
float64) for a calibration scene's ``oracle`` block, computed at each pixel's first-hit ``position`` and shading
``normal`` (the reference's ``position.exr`` / ``normal.exr``, or ``raycast_aux`` for tests). Invalid pixels
(DESIGN §6: ``|normal| <= 0.99`` or ``depth <= 0``) are 0. All materials are two-sided, so the normal is turned
toward the camera before shading.

Oracle types (``oracle.type``) and what they evaluate (no visibility: the scenes are built so nothing occludes):

- ``point_plane`` / ``survey_origin``: ``L = rho/pi * I * max(0, n.l) / d^2`` (point light).
- ``sun_plane``: ``L = rho/pi * E * max(0, n.(-dir))`` (directional light, ``dir`` = travel direction).
- ``sky_plane``: ``L = rho * L_sky`` (constant environment, unoccluded hemisphere).
- ``rect_plane``: ``L = rho/pi * L_e * E/L_e`` with the polygon form factor ``E/L_e = 1/2 |sum_i theta_i
  n.normalize(r_i x r_{i+1})|`` of the rect clipped to the receiver's horizon, zero behind the emitting side.
  Pixels on the rect itself show ``L_e`` from the front and black from behind.
- ``handedness``: coloured diffuse quads (objects) above a dark floor, lit by a directional light:
  ``L = rho/pi * E * max(0, n.(-dir))`` with each pixel's own albedo (the quad it lies on, else the floor's);
  ``handedness_checks`` turns an image into per-quad centroid / radiance verdicts against the expected pixel
  positions and radiances in the oracle block.
- ``furnace``: closed box of rect lights with radiance ``L_e`` and albedo ``rho``: ``full = L_e/(1-rho)``,
  ``direct = L_e (1+rho)``, ``isolated = L_e rho^2/(1-rho)`` at every valid pixel.

Every type except ``furnace`` has ``full = direct`` and ``isolated = 0`` (a single convex receiver cannot see
itself; the handedness quads face an empty upper hemisphere). Every light in the scene contributes, so the oracle
stays right if a scene gains a second light.

Pixels are box-filtered averages, an analytic formula at the mean hit point differs from the average by the
formula's curvature over the footprint (tools/reference.py, "Box filter vs. point oracles"); at 256x192 that is
far below the 0.5 % reference gate.

Helpers: ``polygon_irradiance`` (vectorised, horizon-clipped), ``project_point`` (pinhole, DESIGN §1 image
convention), ``raycast_aux`` (numpy ray caster producing depth/normal/position AOVs from a scene).
"""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

__all__ = ["ORACLE_TYPES", "COMPONENTS", "OracleError", "oracle_images", "oracle_spec", "handedness_checks",
           "furnace_values", "polygon_irradiance", "rect_irradiance", "rect_corners", "point_radiance",
           "sun_radiance", "camera_basis", "project_point", "pixel_rays", "raycast", "raycast_aux",
           "scene_triangles", "valid_aux", "LUMA"]

ORACLE_TYPES = ("point_plane", "sun_plane", "sky_plane", "rect_plane", "handedness", "furnace", "survey_origin")
COMPONENTS = ("direct", "full", "isolated")
LUMA = np.array([0.2126, 0.7152, 0.0722])
# A pixel is "on" a rect light when its hit point lies within this distance of the rect's plane (metres).
RECT_PLANE_TOL = 2e-3
_LIGHT_FOR_TYPE = {"point_plane": "point", "survey_origin": "point", "sun_plane": "directional",
                   "sky_plane": "environment", "rect_plane": "rect", "handedness": "directional"}


class OracleError(ValueError):
    """The scene's oracle block cannot be evaluated (unknown type, missing light/object, wrong scene shape)."""


# ------------------------------------------------------------------------------------------------ small helpers

def _unit(v: np.ndarray, axis: int = -1) -> np.ndarray:
    n = np.linalg.norm(v, axis=axis, keepdims=True)
    return v / np.where(n > 0, n, 1.0)


def _station(scene, station):
    """Resolve a Station from a Station, a View, a station name or None (the scene's first station)."""
    if station is None:
        if scene.timeline is not None:
            return scene.stations[scene.timeline.station]
        return next(iter(scene.stations.values()))
    if isinstance(station, str):
        return scene.stations[station]
    return getattr(station, "station", station)


def valid_aux(aux: Mapping[str, np.ndarray]) -> np.ndarray:
    """DESIGN §6 valid pixels: |normal| > 0.99 and depth > 0 (non-finite AOVs are invalid)."""
    n = np.asarray(aux["normal"], dtype=np.float64)[..., :3]
    d = np.asarray(aux["depth"], dtype=np.float64)
    d = d[..., 0] if d.ndim == 3 else d
    with np.errstate(invalid="ignore"):
        ok = (np.linalg.norm(n, axis=-1) > 0.99) & (d > 0)
    return ok & np.isfinite(n).all(axis=-1) & np.isfinite(d)


def rect_corners(light) -> np.ndarray:
    """(4, 3) corners o, o+u, o+u+v, o+v of a rect light (counter-clockwise about normalize(u x v))."""
    p = light.params
    o, u, v = (np.asarray(p[k], dtype=np.float64) for k in ("origin", "u", "v"))
    return np.array([o, o + u, o + u + v, o + v])


def _rect_frame(light):
    p = light.params
    o, u, v = (np.asarray(p[k], dtype=np.float64) for k in ("origin", "u", "v"))
    n = np.cross(u, v)
    return o, u, v, n / np.linalg.norm(n)


# ------------------------------------------------------------------------------------------------ radiometry

def point_radiance(x, n, position, intensity, albedo) -> np.ndarray:
    """Lambertian radiance from a point light: rho/pi * I * max(0, n.l) / d^2 (no visibility). x, n: (..., 3)."""
    x = np.asarray(x, dtype=np.float64)
    to = np.asarray(position, dtype=np.float64) - x
    d2 = np.sum(to * to, axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cos = np.sum(np.asarray(n, dtype=np.float64) * to, axis=-1) / np.sqrt(d2)
        g = np.where(d2 > 0, np.maximum(cos, 0.0) / d2, 0.0)
    return (np.asarray(albedo, dtype=np.float64) / math.pi) * np.asarray(intensity, dtype=np.float64) * g[..., None]


def sun_radiance(n, direction, irradiance, albedo) -> np.ndarray:
    """Lambertian radiance from a directional light: rho/pi * E * max(0, n.(-dir))."""
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    cos = np.maximum(np.asarray(n, dtype=np.float64) @ (-d), 0.0)
    return (np.asarray(albedo, dtype=np.float64) / math.pi) * np.asarray(irradiance, dtype=np.float64) * cos[..., None]


def polygon_irradiance(x, n, corners, clip: bool = True) -> np.ndarray:
    """E / L_e at points x (..., 3) with unit normals n (..., 3) from a planar convex polygon of constant radiance.

    Lambert's contour form ``1/2 |sum_i theta_i n.normalize(r_i x r_{i+1})|`` with ``r_i = c_i - x``. With
    ``clip`` the polygon is first clipped to the receiver's upper hemisphere (``n.(c - x) > 0``), so it is exact
    for polygons that cross the receiver's horizon too. One-sidedness of the emitter is not handled here.
    """
    x = np.asarray(x, dtype=np.float64)
    shape = x.shape[:-1]
    X = x.reshape(-1, 3)
    N = np.broadcast_to(np.asarray(n, dtype=np.float64), x.shape).reshape(-1, 3)
    C = np.asarray(corners, dtype=np.float64)
    k = len(C)
    R = C[None, :, :] - X[:, None, :]  # (P, k, 3)
    if clip:
        h = np.einsum("pkc,pc->pk", R, N)
        cand = np.zeros((len(X), 2 * k, 3))
        ok = np.zeros((len(X), 2 * k), dtype=bool)
        for i in range(k):
            a, b = R[:, i], R[:, (i + 1) % k]
            ha, hb = h[:, i], h[:, (i + 1) % k]
            ina, inb = ha > 0, hb > 0
            cand[:, 2 * i] = a
            ok[:, 2 * i] = ina
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.where(ina != inb, ha / (ha - hb), 0.0)
            cand[:, 2 * i + 1] = a + (b - a) * t[:, None]
            ok[:, 2 * i + 1] = ina != inb
        order = np.argsort(~ok, axis=1, kind="stable")  # valid vertices first, in polygon order
        V = np.take_along_axis(cand, order[:, :, None], axis=1)
        m = ok.sum(axis=1)
        slots = 2 * k
    else:
        V, m, slots = R, np.full(len(X), k), k
    U = _unit(V)
    total = np.zeros(len(X))
    rows = np.arange(len(X))
    for j in range(slots):
        nxt = np.where(j + 1 < m, j + 1, 0)
        a, b = U[:, j], U[rows, nxt]
        c = np.cross(a, b)
        s = np.linalg.norm(c, axis=-1)
        dot = np.sum(a * b, axis=-1)
        ang = np.arctan2(s, dot)
        f = np.where(s > 1e-15, ang / np.where(s > 1e-15, s, 1.0), 1.0)  # theta / |a x b| (-> 1 as theta -> 0)
        total += np.where(j < m, f * np.sum(c * N, axis=-1), 0.0)
    return (0.5 * np.abs(total)).reshape(shape)


def rect_irradiance(x, n, light, clip: bool = True) -> np.ndarray:
    """E / L_e from a one-sided rect light (zero where x is not on its emitting side normalize(u x v))."""
    o, _u, _v, nl = _rect_frame(light)
    x = np.asarray(x, dtype=np.float64)
    front = (x - o) @ nl > 0
    E = polygon_irradiance(x, n, rect_corners(light), clip=clip)
    return np.where(front, E, 0.0)


def _on_rect(x, light, tol: float = RECT_PLANE_TOL) -> np.ndarray:
    o, u, v, nl = _rect_frame(light)
    return _on_parallelogram(x, o, u, v, nl, tol)


def _quad_frame(obj):
    """(origin, u, v, unit normal) of a quad object in the local frame (its transform applied)."""
    M = np.asarray(obj.transform, dtype=np.float64)
    sh = obj.shape
    o = M[:3, :3] @ np.asarray(sh["origin"], dtype=np.float64) + M[:3, 3]
    u = M[:3, :3] @ np.asarray(sh["u"], dtype=np.float64)
    v = M[:3, :3] @ np.asarray(sh["v"], dtype=np.float64)
    n = np.cross(u, v)
    return o, u, v, n / np.linalg.norm(n)


def _on_parallelogram(x, o, u, v, nl, tol: float = RECT_PLANE_TOL) -> np.ndarray:
    r = np.asarray(x, dtype=np.float64) - o
    s = r @ u / (u @ u)
    t = r @ v / (v @ v)
    e = tol / max(np.linalg.norm(u), np.linalg.norm(v))
    return (np.abs(r @ nl) <= tol) & (s >= -e) & (s <= 1 + e) & (t >= -e) & (t <= 1 + e)


def furnace_values(scene, oracle: Mapping | None = None) -> dict[str, np.ndarray]:
    """{'full', 'direct', 'isolated', 'radiance', 'albedo'} RGB constants of a furnace scene.

    radiance/albedo come from the oracle block when given, else from the (identical) rect lights.
    """
    oracle = dict(oracle if oracle is not None else (scene.oracle or {}))
    rects = [lt for lt in scene.lights if lt.type == "rect"]
    if not rects:
        raise OracleError("furnace: the scene has no rect lights")
    Le = np.asarray(oracle.get("radiance", rects[0].params["radiance"]), dtype=np.float64)
    rho = np.broadcast_to(np.asarray(oracle.get("albedo", rects[0].params["albedo"]), dtype=np.float64), (3,))
    for lt in rects:
        if not (np.allclose(lt.params["radiance"], Le) and np.allclose(lt.params["albedo"], rho)):
            raise OracleError(f"furnace: rect light {lt.name!r} differs from radiance {Le.tolist()} / albedo "
                              f"{rho.tolist()}")
    if np.any(rho >= 1):
        raise OracleError("furnace: albedo must be < 1")
    return {"full": Le / (1 - rho), "direct": Le * (1 + rho), "isolated": Le * rho ** 2 / (1 - rho),
            "radiance": Le.copy(), "albedo": rho.copy()}


# ------------------------------------------------------------------------------------------------ oracle block

def oracle_spec(scene) -> dict:
    """The scene's oracle block, checked against the scene (raises OracleError)."""
    o = scene.oracle
    if not o:
        raise OracleError(f"scene {scene.name!r} has no oracle")
    typ = o.get("type")
    if typ not in ORACLE_TYPES:
        raise OracleError(f"{scene.name}: unknown oracle type {typ!r} (known: {', '.join(ORACLE_TYPES)})")
    out = dict(o)
    want = _LIGHT_FOR_TYPE.get(typ)
    if want is not None:
        name = o.get("light")
        cands = [lt for lt in scene.lights if lt.type == want]
        if name is not None:
            cands = [lt for lt in cands if lt.name == name]
        if not cands:
            raise OracleError(f"{scene.name}: oracle {typ!r} needs a {want} light"
                              + (f" named {name!r}" if name else ""))
        out["light"] = cands[0].name
    obj = o.get("object")
    if obj is not None and not any(ob.name == obj for ob in scene.objects):
        raise OracleError(f"{scene.name}: oracle object {obj!r} is not in the scene")
    if typ == "handedness":
        quads = o.get("quads")
        if not isinstance(quads, list) or not quads:
            raise OracleError(f"{scene.name}: handedness oracle needs a 'quads' list")
        for q in quads:
            name = q.get("object") if isinstance(q, dict) else None
            ob = next((x for x in scene.objects if x.name == name), None)
            if ob is None or ob.shape.get("type") != "quad":
                raise OracleError(f"{scene.name}: handedness quad {name!r} is not a quad object")
            if len(q.get("pixel", [])) != 2:
                raise OracleError(f"{scene.name}: handedness quad {name!r} needs pixel [x, y]")
            if len(q.get("radiance", [])) != 3:
                raise OracleError(f"{scene.name}: handedness quad {name!r} needs radiance [r, g, b]")
    return out


def _receiver_albedo(scene, oracle: Mapping) -> np.ndarray:
    name = oracle.get("object")
    if name is None:
        mats = {ob.material for ob in scene.objects}
        if len(mats) != 1:
            raise OracleError(f"{scene.name}: oracle needs 'object' (the receiver) when objects use several "
                              "materials")
        return scene.materials[mats.pop()].albedo.astype(np.float64)
    return scene.materials[scene.object(name).material].albedo.astype(np.float64)


def oracle_images(scene, aux: Mapping[str, np.ndarray], station=None) -> dict[str, np.ndarray]:
    """{'direct', 'full', 'isolated'}: (H, W, 3) float64 analytic images for a calibration view.

    scene: the view's state (a Scene with an ``oracle`` block); aux: {'depth', 'normal', 'position'} from the
    reference (``tools.masks.load_aux``) or ``raycast_aux``; station: the view's camera (Station, View, name, or
    None for the first station), used to turn two-sided normals toward the viewer.
    """
    oracle = oracle_spec(scene)
    st = _station(scene, station)
    P = np.asarray(aux["position"], dtype=np.float64)[..., :3]
    Nraw = np.asarray(aux["normal"], dtype=np.float64)[..., :3]
    valid = valid_aux(aux)
    H, W = valid.shape
    out = {c: np.zeros((H, W, 3)) for c in COMPONENTS}
    if not valid.any():
        return out
    x = P[valid]
    n = _unit(Nraw[valid])
    cam = np.asarray(st.position, dtype=np.float64)
    flip = np.sum(n * (cam - x), axis=-1) < 0
    n[flip] = -n[flip]

    if oracle["type"] == "furnace":
        fv = furnace_values(scene, oracle)
        for c in COMPONENTS:
            out[c][valid] = fv[c]
        return out

    rho = np.broadcast_to(_receiver_albedo(scene, oracle), x.shape).copy()  # per-pixel albedo
    if oracle["type"] == "handedness":  # each quad's own albedo on its pixels, the floor's elsewhere
        for q in oracle["quads"]:
            ob = scene.object(q["object"])
            rho[_on_parallelogram(x, *_quad_frame(ob))] = scene.materials[ob.material].albedo
    L = np.zeros((len(x), 3))
    on_emitter = np.zeros(len(x), dtype=bool)
    for lt in scene.lights:
        p = lt.params
        if lt.type == "rect":
            on = _on_rect(x, lt) & ~on_emitter
            if on.any():
                _o, _u, _v, nl = _rect_frame(lt)
                front = (cam - x[on]) @ nl > 0
                L[on] = np.where(front[:, None], p["radiance"], 0.0)
                on_emitter |= on
    rx, rn, rho = x[~on_emitter], n[~on_emitter], rho[~on_emitter]
    Lr = np.zeros((len(rx), 3))
    for lt in scene.lights:
        p = lt.params
        if lt.type == "point":
            Lr += point_radiance(rx, rn, p["position"], p["intensity"], rho)
        elif lt.type == "directional":
            Lr += sun_radiance(rn, p["direction"], p["irradiance"], rho)
        elif lt.type == "environment":
            Lr += rho * p["radiance"]
        elif lt.type == "rect":
            Lr += (rho / math.pi) * p["radiance"] * rect_irradiance(rx, rn, lt)[:, None]
    L[~on_emitter] = Lr
    out["direct"][valid] = L
    out["full"][valid] = L
    return out


# ------------------------------------------------------------------------------------------------ handedness

def _erode(m: np.ndarray, k: int) -> np.ndarray:
    for _ in range(k):
        p = np.pad(m, 1, mode="constant")
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def handedness_checks(image, oracle: Mapping, tolerance_px: float | None = None,
                      radiance_tol: float = 0.01) -> list[dict]:
    """Per-quad verdicts for the handedness oracle on an (H, W, >=3) linear image.

    ``oracle["quads"]`` lists ``{"object", "pixel": [x, y], "radiance": [r, g, b]}`` (expected centroid and
    radiance ``rho/pi * E * cos``). A quad's pixels are those whose colour points along its radiance (cosine
    > 0.95) at more than a quarter of its brightness; the centroid uses pixel centres (x + 0.5, y + 0.5) from the
    top-left corner (DESIGN §1). ``radiance_rel_err`` compares the mean colour of the quad's core (pixels 2 px
    inside the edge) with its radiance: max over channels of |measured - expected| / max(expected). A quad more
    than ``tolerance_px`` off is named "mirrored left-right" / "mirrored top-bottom" / "rotated 180 degrees" when
    the mirrored position matches.
    """
    img = np.asarray(image, dtype=np.float64)[..., :3]
    img = np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)
    tol = float(oracle.get("tolerance_px", 1.0) if tolerance_px is None else tolerance_px)
    H, W = img.shape[:2]
    ys, xs = np.mgrid[0:H, 0:W]
    out = []
    mag = np.linalg.norm(img, axis=-1)
    for e in oracle["quads"]:
        rad = np.asarray(e["radiance"], dtype=np.float64)
        rmag = float(np.linalg.norm(rad))
        with np.errstate(invalid="ignore", divide="ignore"):
            cos = (img @ rad) / (mag * rmag)
        mask = (mag > 0.25 * rmag) & (cos > 0.95)
        exp = [float(v) for v in e["pixel"]]
        rec = {"quad": e.get("object"), "expected_px": exp, "radiance": rad.tolist(), "pixels": int(mask.sum()),
               "centroid_px": None, "distance_px": None, "measured": None, "radiance_rel_err": None,
               "position_ok": False, "radiance_ok": False, "passed": False, "tolerance_px": tol,
               "radiance_tol": radiance_tol}
        if mask.any():
            cx, cy = float(xs[mask].mean() + 0.5), float(ys[mask].mean() + 0.5)
            dist = math.hypot(cx - exp[0], cy - exp[1])
            core = _erode(mask, 2)
            if not core.any():
                core = mask
            meas = img[core].mean(axis=0)
            rel = float(np.max(np.abs(meas - rad)) / max(float(rad.max()), 1e-30))
            mx, my = W - exp[0], H - exp[1]
            note = None
            if dist > tol:
                if math.hypot(cx - mx, cy - exp[1]) <= tol:
                    note = "mirrored left-right"
                elif math.hypot(cx - exp[0], cy - my) <= tol:
                    note = "mirrored top-bottom"
                elif math.hypot(cx - mx, cy - my) <= tol:
                    note = "rotated 180 degrees"
            rec.update(centroid_px=[cx, cy], distance_px=dist, measured=meas.tolist(), radiance_rel_err=rel,
                       position_ok=dist <= tol, radiance_ok=rel <= radiance_tol)
            rec["passed"] = bool(rec["position_ok"] and rec["radiance_ok"])
            if note:
                rec["note"] = note
        out.append(rec)
    return out


# ------------------------------------------------------------------------------------------------ camera / rays

def camera_basis(station) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(forward, image right, image up) unit vectors of a station (same frame as Mitsuba's look_at)."""
    pos, at, up = (np.asarray(v, dtype=np.float64) for v in (station.position, station.look_at, station.up))
    f = _unit(at - pos)
    r = _unit(np.cross(f, up))
    return f, r, np.cross(r, f)


def project_point(station, width: int, height: int, p) -> tuple[float, float]:
    """Image position (x, y) in pixels of a local point: x from the left edge, y from the top edge (DESIGN §1);
    pixel (i, j) covers [i, i+1) x [j, j+1)."""
    f, r, u = camera_basis(station)
    d = np.asarray(p, dtype=np.float64) - np.asarray(station.position, dtype=np.float64)
    z = float(d @ f)
    if z <= 0:
        raise ValueError("point is behind the camera")
    ty = math.tan(math.radians(station.vfov_deg) / 2)
    tx = ty * width / height
    xn, yn = float(d @ r) / z / tx, float(d @ u) / z / ty
    return (0.5 + 0.5 * xn) * width, (0.5 - 0.5 * yn) * height


def pixel_rays(station, width: int, height: int, ss: int = 1) -> np.ndarray:
    """(H, W, ss*ss, 3) unit ray directions through a regular ss x ss grid inside every pixel."""
    f, r, u = camera_basis(station)
    ty = math.tan(math.radians(station.vfov_deg) / 2)
    tx = ty * width / height
    s = (np.arange(ss) + 0.5) / ss
    xs = ((np.arange(width)[:, None] + s[None, :]) / width * 2 - 1) * tx  # (W, ss)
    ys = (1 - (np.arange(height)[:, None] + s[None, :]) / height * 2) * ty  # (H, ss)
    d = (f[None, None, None, None, :] + xs[None, :, None, :, None] * r + ys[:, None, :, None, None] * u)
    d = d.reshape(height, width, ss * ss, 3)
    return _unit(d)


def scene_triangles(scene, include_rects: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(T, 3, 3) local-frame triangles of every object (and rect light) and their (T, 3) unit normals."""
    from .geometry import transformed_mesh

    tris, norms = [], []
    for obj in scene.objects:
        m = transformed_mesh(obj)
        idx = m.indices.astype(np.int64)
        t = m.positions.astype(np.float64)[idx]
        nv = m.normals.astype(np.float64)[idx].mean(axis=1)
        tris.append(t)
        norms.append(_unit(nv))
    if include_rects:
        for lt in scene.lights:
            if lt.type != "rect":
                continue
            c = rect_corners(lt)
            _o, _u, _v, nl = _rect_frame(lt)
            tris.append(np.array([[c[0], c[1], c[2]], [c[0], c[2], c[3]]]))
            norms.append(np.array([nl, nl]))
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3))
    return np.concatenate(tris), np.concatenate(norms)


def raycast(tris: np.ndarray, origins, dirs, t_max=None, chunk_elems: int = 4_000_000
            ) -> tuple[np.ndarray, np.ndarray]:
    """Nearest hit per ray (Moller-Trumbore, both sides): (distance, triangle index), inf / -1 on a miss.

    t_max (scalar or per ray) ignores hits at or beyond it, which turns this into a shadow-ray test.
    """
    o = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    o = np.broadcast_to(o, d.shape) if len(o) == 1 else o
    T = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    tmax = np.broadcast_to(np.asarray(np.inf if t_max is None else t_max, dtype=np.float64), (len(d),))
    dist = np.full(len(d), np.inf)
    hit = np.full(len(d), -1, dtype=np.int64)
    if not len(T) or not len(d):
        return dist, hit
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    step = max(1, chunk_elems // max(1, len(T)))
    for s in range(0, len(d), step):
        oo, dd = o[s:s + step, None, :], d[s:s + step, None, :]
        pv = np.cross(dd, e2[None])
        det = np.einsum("rtk,tk->rt", pv, e1)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = oo - v0[None]
        uu = np.einsum("rtk,rtk->rt", tv, pv) * inv
        qv = np.cross(tv, e1[None])
        vv = np.einsum("rtk,rtk->rt", np.broadcast_to(dd, qv.shape), qv) * inv
        tt = np.einsum("rtk,tk->rt", qv, e2) * inv
        good = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (tt > 1e-7) & (tt < tmax[s:s + step, None])
        tt = np.where(good, tt, np.inf)
        j = np.argmin(tt, axis=1)
        dist[s:s + step] = tt[np.arange(len(j)), j]
        hit[s:s + step] = np.where(np.isfinite(dist[s:s + step]), j, -1)
    return dist, hit


def raycast_aux(scene, station=None, width: int | None = None, height: int | None = None, ss: int = 1,
                tris=None) -> dict[str, np.ndarray]:
    """Reference-style AOVs by numpy ray casting: {'depth' (H, W), 'normal' (H, W, 3), 'position' (H, W, 3)}.

    ``ss`` x ``ss`` rays per pixel are averaged like the reference's box filter (a pixel whose rays miss or
    straddle surfaces gets a shorter normal or zero depth, so ``valid_aux`` drops it as the reference would).
    Misses are 0 in every AOV. Normals are the stored (unflipped) face normals; rect lights are included.
    """
    st = _station(scene, station)
    W = int(width or scene.width)
    H = int(height or scene.height)
    if tris is None:
        tris = scene_triangles(scene)
    T, Nf = tris
    dirs = pixel_rays(st, W, H, ss).reshape(-1, 3)
    o = np.asarray(st.position, dtype=np.float64)[None]
    dist, idx = raycast(T, o, dirs)
    hit = idx >= 0
    k = ss * ss
    pos = np.where(hit[:, None], o + dirs * np.where(hit, dist, 0.0)[:, None], 0.0).reshape(H, W, k, 3)
    nrm = np.where(hit[:, None], Nf[np.maximum(idx, 0)], 0.0).reshape(H, W, k, 3)
    dep = np.where(hit, dist, 0.0).reshape(H, W, k)
    return {"depth": dep.mean(axis=-1), "normal": nrm.mean(axis=2), "position": pos.mean(axis=2)}
