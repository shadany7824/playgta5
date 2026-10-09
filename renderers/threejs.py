"""three.js r186 adapter: modes, bundle builder and the two engines (DESIGN §5).

ThreeJsNative ('threejs-native') runs native/runner.py (wgpu-py on Vulkan); ThreeJsWeb ('threejs-web') runs
web/runner.py (pinned three.js in headless Chromium). Both read the same bundle format (§4.2 + §5.2).
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools.geometry import quad_mesh, transform_matrix
from tools.spec import RADIOMETRIC_FIELD, Scene, capture_kind

from .base import (ALL_CAPABILITIES, REPO_ROOT, Engine, ModeInfo, NotWired, git_sha, write_bundle)

__all__ = ["THREEJS_MODES", "THREE_REVISION", "ThreeJsBundleBuilder", "ThreeJsNative", "ThreeJsWeb",
           "split_color", "matrix_elements", "rect_quaternion", "quat_rotate", "ssaa_offsets", "scene_bounds",
           "find_chromium", "CHROMIUM_SOFTWARE_ARGS", "BUILDER_DEFAULTS", "VENDOR_DIR", "THREEJS_CAPABILITIES",
           "THREEJS_KNOWN_LIMITS", "DIR_SHADOW_FITS", "shadow_light_basis", "shadow_footprints",
           "caster_receiver_extent"]

THREE_REVISION = "186"
VENDOR_DIR = REPO_ROOT / "web" / "vendor" / "three"
# Chromium flags for machines without a GPU (SwiftShader WebGL2); a real GPU needs none.
CHROMIUM_SOFTWARE_ARGS = ("--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist")

THREEJS_MODES: dict[str, ModeInfo] = {
    "direct": ModeInfo(
        "direct", "direct", False,
        "MeshLambertMaterial; PointLight/DirectionalLight with PCFShadowMap shadows; environment -> "
        "HemisphereLight(sky = pi*L, ground = 0) + scene.background = L. No light probe, no ambient. (Rect lights "
        "map to RectAreaLight + an emitter mesh, but MeshLambertMaterial ignores RectAreaLight, so light:rect is "
        "not claimed.)",
        "Direct lighting only: three.js analytic lights with shadow maps."),
    "probe": ModeInfo(
        "probe", "indirect", False,
        "direct + one global LightProbe (SH9) from a CubeCamera at the camera position via "
        "LightProbeGenerator.fromCubeRenderTarget, captured with the probe disabled (one bounce). Re-baked at "
        "frame 0 and immediately after every timeline step.",
        "Static global SH9 light probe (one bounce), re-baked after each timeline step."),
    "probe_dynamic": ModeInfo(
        "probe_dynamic", "indirect", True,
        "direct + the same probe re-captured every frame with the previous frame's probe active (progressive "
        "multi-bounce feedback).",
        "Per-frame SH9 probe feedback (progressive multi-bounce)."),
}

# Capabilities (DESIGN §4.4). No 'light:rect': r186 MeshLambertMaterial ignores RectAreaLight. Its
# lights_lambert_pars_fragment defines only RE_Direct and RE_IndirectDiffuse, lights_fragment_begin evaluates rect
# lights only when RE_Direct_RectArea is defined, and RectAreaLight.js says "Only PBR materials are supported".
# Scenes with rect lights are by-design skips for both three.js engines. The bundle format still maps rect lights
# (RectAreaLight + emitter mesh), so the runners can draw them and tests can pin that behaviour.
THREEJS_CAPABILITIES = frozenset(ALL_CAPABILITIES - {"light:rect"})
THREEJS_KNOWN_LIMITS = (
    "Rect lights are not supported: r186 MeshLambertMaterial ignores RectAreaLight (lights_lambert_pars_fragment "
    "defines no RE_Direct_RectArea; RectAreaLight.js: 'Only PBR materials are supported'), so scenes with rect "
    "lights are by-design skips.",
    "The environment is a HemisphereLight, which has no occlusion: enclosed or shadowed surfaces still receive the "
    "full sky.",
    "The probe's SH9 irradiance is not clamped (shGetIrradianceAt), so ringing can make the isolated component "
    "negative.",
    "The probe's CubeCamera capture sees scene.background, so outdoor probe modes count the sky twice: once through "
    "the HemisphereLight and again through the SH9 projection of the background.",
    "Rect emitters without albedo are one-sided (FrontSide): seen from behind they are invisible (culled), and they "
    "do not occlude lights behind them in the shadow pass.",
)

BUILDER_DEFAULTS = {
    "ssaa": 16,
    "shadow_map_type": "PCFShadowMap",
    "point_shadow_map": 1024,
    "dir_shadow_map": 2048,
    # Depth bias is in shadow-map depth units. Directional maps are orthographic (linear depth: world equivalent =
    # bias * (far - near)). r186 point lights compare *perspective* depth in a samplerCubeShadow
    # (shadowmap_pars_fragment getPointShadow: dp = far*(z - near) / (z*(far - near)) + bias), so a constant bias
    # equals bias * z^2 * (far - near) / (far * near) metres: -0.0005 with near 0.01 is ~0.5 m at z = 3.2 m and lets
    # light through 0.2 m walls. Point lights therefore use no depth bias, only the world-unit normalBias.
    "shadow_bias": -0.0005,
    "point_shadow_bias": 0.0,
    "shadow_normal_bias": 0.02,
    "shadow_radius": 1,
    "camera_near": 0.05,
    "camera_far": 1000.0,
    "probe_cube_size": 128,
    "probe_near": 0.05,
    "probe_far": 1000.0,
    "probe_type": "HalfFloatType",
    # Lateral extent of the directional shadow camera (DESIGN §5.2): "casters" = the light-space footprint where a
    # shadow can fall (shadow_footprints / caster_receiver_extent), "scene" = a square around the whole scene
    # (the pre-fit behaviour, kept for A/B measurements). The depth range always spans the whole scene.
    "dir_shadow_fit": "casters",
    "settle_frames_static": 32,
    "settle_frames_dynamic": 64,
    "warmup_frames": 8,
}


# ------------------------------------------------------------------------------------------------ mappings (§5.2)

def split_color(v) -> tuple[list[float], float]:
    """Linear RGB value -> (color = v / max(v), intensity = max(v)); ([1,1,1], 0) for v = 0."""
    a = np.asarray(v, dtype=np.float64).reshape(3)
    m = float(a.max())
    if m <= 0.0:
        return [1.0, 1.0, 1.0], 0.0
    return (a / m).tolist(), m


def matrix_elements(M) -> list[float]:
    """(4,4) row-major maths matrix -> 16 floats column-major (three.js Matrix4.elements)."""
    return np.asarray(M, dtype=np.float64).reshape(4, 4).T.reshape(-1).tolist()


def _quat_from_basis(X, Y, Z) -> list[float]:
    """Rotation with columns X, Y, Z -> [x, y, z, w] (three.js Quaternion.setFromRotationMatrix)."""
    m11, m12, m13 = X[0], Y[0], Z[0]
    m21, m22, m23 = X[1], Y[1], Z[1]
    m31, m32, m33 = X[2], Y[2], Z[2]
    tr = m11 + m22 + m33
    if tr > 0:
        s = 0.5 / math.sqrt(tr + 1.0)
        q = [(m32 - m23) * s, (m13 - m31) * s, (m21 - m12) * s, 0.25 / s]
    elif m11 > m22 and m11 > m33:
        s = 2.0 * math.sqrt(1.0 + m11 - m22 - m33)
        q = [0.25 * s, (m12 + m21) / s, (m13 + m31) / s, (m32 - m23) / s]
    elif m22 > m33:
        s = 2.0 * math.sqrt(1.0 + m22 - m11 - m33)
        q = [(m12 + m21) / s, 0.25 * s, (m23 + m32) / s, (m13 - m31) / s]
    else:
        s = 2.0 * math.sqrt(1.0 + m33 - m11 - m22)
        q = [(m13 + m31) / s, (m23 + m32) / s, 0.25 * s, (m21 - m12) / s]
    q = np.asarray(q, dtype=np.float64)
    return (q / np.linalg.norm(q)).tolist()


def rect_quaternion(u, v) -> list[float]:
    """RectAreaLight orientation: local +X along u, local -Z = normalize(u x v) (the emitting side)."""
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    n = np.cross(u, v)
    n /= np.linalg.norm(n)
    X = u / np.linalg.norm(u)
    Z = -n
    Y = np.cross(Z, X)
    Y /= np.linalg.norm(Y)
    return _quat_from_basis(X, Y, Z)


def quat_rotate(q, vec) -> np.ndarray:
    """Rotate a vector by quaternion [x, y, z, w]."""
    x, y, z, w = (float(c) for c in q)
    qv = np.array([x, y, z])
    v = np.asarray(vec, dtype=np.float64)
    t = 2.0 * np.cross(qv, v)
    return v + w * t + np.cross(qv, t)


def ssaa_offsets(n: int) -> list[list[float]]:
    """n = k*k subpixel offsets in pixels: k x k grid ((i + 0.5) / k - 0.5), rows (y) outer, x inner."""
    k = math.isqrt(int(n))
    if k * k != int(n) or k < 1:
        raise ValueError(f"ssaa must be a square number, got {n}")
    g = [(i + 0.5) / k - 0.5 for i in range(k)]
    return [[gx, gy] for gy in g for gx in g]


def _timeline_transforms(scene: Scene) -> dict[str, list[np.ndarray]]:
    """{object: [every matrix a set_transform action gives it]} over the whole timeline."""
    extra: dict[str, list[np.ndarray]] = {}
    if scene.timeline is not None:
        for _, acts in scene.timeline.steps:
            for a in acts:
                if a["op"] == "set_transform":
                    extra.setdefault(a["object"], []).append(transform_matrix(a["transform"]))
    return extra


def scene_bounds(scene: Scene) -> tuple[np.ndarray, np.ndarray]:
    """Local-frame AABB of all geometry and rect lights over every transform the timeline gives an object."""
    pts = []
    extra = _timeline_transforms(scene)
    for o in scene.objects:
        lo, hi = o.mesh.bbox()
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        for M in [o.transform] + extra.get(o.name, []):
            pts.append(corners @ M[:3, :3].T + M[:3, 3])
    for lt in scene.lights:
        if lt.type == "rect":
            o, u, v = lt.params["origin"], lt.params["u"], lt.params["v"]
            pts.append(np.array([o, o + u, o + v, o + u + v]))
    if not pts:
        return -np.ones(3), np.ones(3)
    P = np.concatenate(pts)
    return P.min(axis=0), P.max(axis=0)


def _corners(lo, hi) -> np.ndarray:
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


# ------------------------------------------------------------------------------------------------ shadow fit (§5.2)

DIR_SHADOW_FITS = ("casters", "scene")
# Shape types whose every instance is convex: a convex solid cannot shadow its own light-facing faces, and its faces
# turned away from the light are black anyway (Lambert dotNL <= 0; DoubleSide flips the normal toward the camera).
CONVEX_SHAPES = ("box", "quad")
OBJECT3D_DEFAULT_UP = (0.0, 1.0, 0.0)  # three.core.js:13578; the shadow camera's up (docs/PHASE0.md §6 item 5)


def shadow_light_basis(position, target, up=OBJECT3D_DEFAULT_UP) -> tuple[np.ndarray, np.ndarray]:
    """World-space x and y axes of a DirectionalLight's shadow camera at ``position`` looking at ``target``:
    Matrix4.lookAt(eye, target, up) as OrthographicCamera.lookAt uses it (native/three_math, degenerate branch
    included). A point p has shadow-camera coordinates ((p - target).x_axis, (p - target).y_axis)."""
    from native.three_math import m4_look_at_rotation

    e = m4_look_at_rotation(tuple(float(c) for c in position), tuple(float(c) for c in target),
                            tuple(float(c) for c in up))
    return np.array(e[0:3]), np.array(e[4:7])


def shadow_footprints(scene: Scene, x_axis, y_axis, origin) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Light-space AABB [xmin, xmax, ymin, ymax] of every object (over every timeline transform) and visible rect
    emitter, whether it is convex, and the names. Coordinates are relative to ``origin`` along the two axes."""
    extra = _timeline_transforms(scene)
    X, Y, O = (np.asarray(a, dtype=np.float64) for a in (x_axis, y_axis, origin))
    boxes, convex, names = [], [], []

    def add(name, P, cvx):
        R = P - O
        x, y = R @ X, R @ Y
        boxes.append([x.min(), x.max(), y.min(), y.max()])
        convex.append(cvx)
        names.append(name)

    for o in scene.objects:
        P = o.mesh.positions.astype(np.float64)
        if not len(P):
            continue
        add(o.name, np.concatenate([P @ M[:3, :3].T + M[:3, 3] for M in [o.transform] + extra.get(o.name, [])]),
            o.shape.get("type") in CONVEX_SHAPES)
    for lt in scene.lights:
        if lt.type == "rect":
            p = lt.params
            o, u, v = p["origin"], p["u"], p["v"]
            add(lt.name, np.array([o, o + u, o + v, o + u + v]), True)
    return np.array(boxes, dtype=np.float64).reshape(-1, 4), np.array(convex, dtype=bool), names


def caster_receiver_extent(boxes: np.ndarray, convex: np.ndarray) -> np.ndarray | None:
    """[xmin, xmax, ymin, ymax] of the light-space region where a shadow can fall, or None when nowhere.

    A point is shadowed only by geometry between it and the light, and the two share light-space (x, y). So a
    shadow on object B cast by object A lies in footprint(A) ∩ footprint(B); with A = B only when B is not convex.
    The region is the AABB of the union of those intersections over every pair (each object is both a caster and a
    receiver). Points outside it cannot be shadowed, and three.js treats points outside the shadow camera's
    frustum as lit (shadowmap_pars_fragment getShadow: frustumTest), so fitting the camera to it is exact.
    """
    B = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    if not len(B):
        return None
    lox = np.maximum(B[:, None, 0], B[None, :, 0])
    hix = np.minimum(B[:, None, 1], B[None, :, 1])
    loy = np.maximum(B[:, None, 2], B[None, :, 2])
    hiy = np.minimum(B[:, None, 3], B[None, :, 3])
    ok = (lox <= hix) & (loy <= hiy)
    ok[np.diag_indices(len(B))] = ~np.asarray(convex, dtype=bool)
    if not ok.any():
        return None
    return np.array([lox[ok].min(), hix[ok].max(), loy[ok].min(), hiy[ok].max()])


# ------------------------------------------------------------------------------------------------ builder

class ThreeJsBundleBuilder:
    """Scene + mode + views + capture -> bundle.json + arrays (DESIGN §4.2, §5.2). Options: BUILDER_DEFAULTS."""

    def __init__(self, **options):
        unknown = set(options) - set(BUILDER_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown builder options {sorted(unknown)}")
        self.opt = {**BUILDER_DEFAULTS, **options}

    def build(self, scene: Scene, mode: str, views: list, capture: dict | None, out_dir) -> Path:
        bundle, arrays = self.bundle(scene, mode, views, capture)
        return write_bundle(Path(out_dir), bundle, arrays)

    # -- top level
    def bundle(self, scene: Scene, mode: str, views: list, capture: dict | None = None) -> tuple[dict, dict]:
        if mode not in THREEJS_MODES:
            raise ValueError(f"unknown three.js mode {mode!r}; modes: {list(THREEJS_MODES)}")
        capture = dict(capture or {})
        kind = capture_kind(scene)
        engine_data, arrays = self.engine_data(scene, mode, capture)
        measure = {"timing": True, "warmup_frames": int(self.opt["warmup_frames"]), "parity": False}
        measure.update(capture.get("measure", {}))
        fps = scene.timeline.fps if scene.timeline is not None else float(capture.get("fps", 60))
        bundle = {
            "bundle_version": 1,
            "engine": "threejs",
            "mode": mode,
            "scene": scene.name,
            "kind": kind,
            "image": {"width": int(scene.width), "height": int(scene.height)},
            "fps": int(fps) if float(fps).is_integer() else float(fps),
            "seed": int(capture.get("seed", 1)),
            "capture": self.capture_block(scene, mode, views, capture),
            "measure": measure,
            "arrays": {},
            "engine_data": engine_data,
        }
        return bundle, arrays

    def capture_block(self, scene: Scene, mode: str, views: list, capture: dict) -> dict:
        """§4.2 capture: stations [{name, camera, settle_frames}] or timeline {camera, end_frame, frames}."""
        dynamic = THREEJS_MODES[mode].dynamic
        settle = int(capture.get("settle_frames", self.opt["settle_frames_dynamic" if dynamic
                                                           else "settle_frames_static"]))
        if scene.timeline is None:
            if "stations" in capture:
                st = [dict(s) for s in capture["stations"]]
                for s in st:
                    s.setdefault("camera", s["name"])
                    s.setdefault("settle_frames", settle)
            else:
                st = [{"name": v.id, "camera": v.station.name, "settle_frames": settle}
                      for v in views if v.kind == "station"]
            for s in st:
                if s["camera"] not in scene.stations:
                    raise ValueError(f"capture station {s['name']!r}: no camera {s['camera']!r} in {scene.name}")
            if not st:
                raise ValueError(f"{scene.name}: no stations to capture")
            return {"stations": st}
        tl = scene.timeline
        block = dict(capture.get("timeline", {}))
        block.setdefault("camera", tl.station)
        block.setdefault("end_frame", tl.end_frame)
        frames = block.get("frames", capture.get("frames"))
        if frames is None:
            frames = list(range(int(block["end_frame"]) + 1))
        frames = sorted({int(f) for f in frames})
        if frames and (frames[0] < 0 or frames[-1] > int(block["end_frame"])):
            raise ValueError(f"capture frames must lie in [0, {block['end_frame']}]")
        block["frames"] = frames
        if block["camera"] not in scene.stations:
            raise ValueError(f"capture timeline camera {block['camera']!r} not in {scene.name}")
        return {"timeline": block}

    # -- engine_data
    def engine_data(self, scene: Scene, mode: str, capture: dict | None = None) -> tuple[dict, dict]:
        o = self.opt
        capture = capture or {}
        arrays: dict[str, np.ndarray] = {}
        lo, hi = scene_bounds(scene)
        center = 0.5 * (lo + hi)
        corners = _corners(lo, hi)
        diag = float(np.linalg.norm(hi - lo)) or 1.0

        materials = {n: {"type": "MeshLambertMaterial", "color": m.albedo.tolist(), "emissive": [0.0, 0.0, 0.0],
                         "side": "DoubleSide"} for n, m in scene.materials.items()}
        meshes = []
        for ob in scene.objects:
            arrays[f"{ob.name}.position"] = ob.mesh.positions
            arrays[f"{ob.name}.normal"] = ob.mesh.normals
            arrays[f"{ob.name}.index"] = ob.mesh.indices
            meshes.append({"name": ob.name, "material": ob.material, "position": f"{ob.name}.position",
                           "normal": f"{ob.name}.normal", "index": f"{ob.name}.index",
                           "matrix": matrix_elements(ob.transform), "castShadow": True, "receiveShadow": True})

        lights, emitters = [], []
        background = [0.0, 0.0, 0.0]
        shadow_common = {"bias": o["shadow_bias"], "normalBias": o["shadow_normal_bias"], "radius": o["shadow_radius"]}
        for lt in scene.lights:
            p = lt.params
            if lt.type == "point":
                color, inten = split_color(p["intensity"])
                pos = p["position"]
                far = 1.05 * float(np.max(np.linalg.norm(corners - pos, axis=1))) + 0.1
                near = min(0.05, max(0.01, 1e-3 * far))
                lights.append({"name": lt.name, "type": "PointLight", "color": color, "intensity": inten,
                               "distance": 0, "decay": 2, "position": pos.tolist(), "castShadow": True,
                               "shadow": {"mapSize": [o["point_shadow_map"]] * 2, **shadow_common,
                                          "bias": o["point_shadow_bias"], "near": near, "far": far}})
            elif lt.type == "directional":
                color, inten = split_color(p["irradiance"])
                d = p["direction"] / np.linalg.norm(p["direction"])
                pos, camera, fit = self.directional_shadow_camera(scene, d, center, corners, diag)
                lights.append({"name": lt.name, "type": "DirectionalLight", "color": color, "intensity": inten,
                               "position": pos.tolist(), "target": center.tolist(), "castShadow": True,
                               "shadow": {"mapSize": [o["dir_shadow_map"]] * 2, **shadow_common, "camera": camera,
                                          "fit": fit}})
            elif lt.type == "rect":
                color, inten = split_color(p["radiance"])
                u, v = p["u"], p["v"]
                lights.append({"name": lt.name, "type": "RectAreaLight", "color": color, "intensity": inten,
                               "width": float(np.linalg.norm(u)), "height": float(np.linalg.norm(v)),
                               "position": (p["origin"] + 0.5 * (u + v)).tolist(), "quaternion": rect_quaternion(u, v)})
                qm = quad_mesh(p["origin"], u, v)
                arrays[f"{lt.name}.position"] = qm.positions
                arrays[f"{lt.name}.normal"] = qm.normals
                arrays[f"{lt.name}.index"] = qm.indices
                two_sided = bool(np.any(p["albedo"] > 0))
                emitters.append({"name": lt.name, "position": f"{lt.name}.position", "normal": f"{lt.name}.normal",
                                 "index": f"{lt.name}.index", "matrix": matrix_elements(np.eye(4)),
                                 "emissive": p["radiance"].tolist(), "side": "DoubleSide" if two_sided else "FrontSide",
                                 "color": p["albedo"].tolist(), "castShadow": True, "receiveShadow": True})
            else:  # environment
                color, inten = split_color(p["radiance"])
                lights.append({"name": lt.name, "type": "HemisphereLight", "skyColor": color,
                               "groundColor": [0.0, 0.0, 0.0], "intensity": math.pi * inten, "up": [0.0, 0.0, 1.0]})
                background = p["radiance"].tolist()

        cameras = {}
        for st in scene.stations.values():
            reach = float(np.max(np.linalg.norm(corners - st.position, axis=1)))
            cameras[st.name] = {"position": st.position.tolist(), "lookAt": st.look_at.tolist(), "up": st.up.tolist(),
                                "fov": float(st.vfov_deg), "near": float(o["camera_near"]),
                                "far": max(float(o["camera_far"]), 2.0 * reach)}
        info = THREEJS_MODES[mode]
        probe = {"enabled": info.kind == "indirect", "dynamic": bool(info.dynamic), "cubeSize": int(o["probe_cube_size"]),
                 "near": float(o["probe_near"]), "far": max(float(o["probe_far"]), 2.0 * diag),
                 "type": o["probe_type"]}
        n_ssaa = int(capture.get("ssaa", o["ssaa"]))
        engine_data = {
            "three_revision": THREE_REVISION,
            "frame": {"up": [0.0, 0.0, 1.0], "origin_world": scene.origin.tolist()},
            "materials": materials,
            "meshes": meshes,
            "emitters": emitters,
            "lights": lights,
            "background": background,
            "cameras": cameras,
            "probe": probe,
            "timeline": self.timeline_block(scene),
            "renderer": {"shadowMapType": o["shadow_map_type"], "ssaa": n_ssaa, "ssaa_offsets": ssaa_offsets(n_ssaa),
                         "parity": {"toneMapping": "ACESFilmicToneMapping",
                                    "exposure": float(scene.display.get("exposure", 1.0)), "outputColorSpace": "srgb"},
                         "measurement": {"toneMapping": "NoToneMapping", "outputColorSpace": "srgb-linear",
                                         "type": "FloatType", "format": "RGBAFormat"}},
        }
        return engine_data, arrays

    def directional_shadow_camera(self, scene: Scene, d, center, corners, diag) -> tuple[np.ndarray, dict, str]:
        """(light position, shadow camera {left, right, top, bottom, near, far}, fit used) for travel direction d.

        The light sits up-beam of the scene AABB and looks at its centre; near/far span the whole scene, so every
        caster between the light and a receiver is in the map. Laterally, fit "casters" covers only the light-space
        region where a shadow can fall (caster_receiver_extent) plus a pad of 1 % of its size and 2 normalBias
        (PCF kernel and normal offset at the edge); fit "scene" (or no possible shadow) is a square around every
        scene corner, the pre-fit behaviour.
        """
        o = self.opt
        if o["dir_shadow_fit"] not in DIR_SHADOW_FITS:
            raise ValueError(f"dir_shadow_fit must be one of {DIR_SHADOW_FITS}, got {o['dir_shadow_fit']!r}")
        rel = corners - center
        s = rel @ d
        r_perp = float(np.max(np.linalg.norm(rel - s[:, None] * d, axis=1)))
        half = 1.02 * r_perp + 1e-3 * diag
        margin = max(0.5, 0.1 * diag)
        pos = center + d * (float(s.min()) - margin)
        cam = {"left": -half, "right": half, "top": half, "bottom": -half, "near": 0.5 * margin,
               "far": float(s.max() - s.min()) + 1.5 * margin}
        if o["dir_shadow_fit"] == "scene":
            return pos, cam, "scene"
        X, Y = shadow_light_basis(pos, center)
        boxes, convex, _names = shadow_footprints(scene, X, Y, center)
        ext = caster_receiver_extent(boxes, convex)
        if ext is None:  # nothing can be shadowed: keep the whole-scene square
            return pos, cam, "scene"
        pad = 0.01 * float(max(ext[1] - ext[0], ext[3] - ext[2])) + 2.0 * float(o["shadow_normal_bias"]) + 1e-3
        left, right = max(-half, float(ext[0]) - pad), min(half, float(ext[1]) + pad)
        bottom, top = max(-half, float(ext[2]) - pad), min(half, float(ext[3]) + pad)
        cam.update(left=left, right=right, top=top, bottom=bottom)
        return pos, cam, "casters"

    def timeline_block(self, scene: Scene) -> dict | None:
        """Timeline steps as three.js ops: light {name, intensity, color}, matrix {mesh, matrix},
        material {name, color}. Rect-light ops also carry 'emissive', environment ops 'background'."""
        tl = scene.timeline
        if tl is None:
            return None
        events = []
        for frame, acts in tl.steps:
            ops = []
            for a in acts:
                if a["op"] == "set_light":
                    lt = scene.light(a["light"])
                    val = np.asarray(a[RADIOMETRIC_FIELD[lt.type]], dtype=np.float64)
                    color, inten = split_color(val)
                    op = {"op": "light", "name": lt.name, "intensity": inten, "color": color}
                    if lt.type == "environment":
                        op["intensity"] = math.pi * inten
                        op["background"] = val.tolist()
                    elif lt.type == "rect":
                        op["emissive"] = val.tolist()
                    ops.append(op)
                elif a["op"] == "set_transform":
                    ops.append({"op": "matrix", "mesh": a["object"],
                                "matrix": matrix_elements(transform_matrix(a["transform"]))})
                else:
                    ops.append({"op": "material", "name": a["material"],
                                "color": np.asarray(a["albedo"], dtype=np.float64).tolist()})
            events.append({"frame": int(frame), "ops": ops})
        fps = tl.fps
        return {"fps": int(fps) if float(fps).is_integer() else float(fps), "events": events}


# ------------------------------------------------------------------------------------------------ chromium

_CHROME_RELS = ("chrome-linux/chrome", "chrome-linux64/chrome", "chrome-win/chrome.exe", "chrome-win64/chrome.exe",
                "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
                "chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium")


def _default_browsers_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ms-playwright"


def find_chromium(ask_playwright: bool = True) -> Path | None:
    """Chromium for the web runner: $HARNESS_CHROMIUM, then $PLAYWRIGHT_BROWSERS_PATH/chromium-*/..., then
    Playwright's default browser directory, then (optionally) Playwright's own executable_path."""
    env = os.environ.get("HARNESS_CHROMIUM")
    if env and Path(env).is_file():
        return Path(env)
    roots = []
    pbp = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if pbp and pbp != "0":
        roots.append(Path(pbp))
    roots.append(_default_browsers_dir())

    def rev(d: Path) -> int:
        tail = d.name.split("-", 1)[-1]
        return int(tail) if tail.isdigit() else -1

    for root in roots:
        if not root.is_dir():
            continue
        for d in sorted(root.glob("chromium-*"), key=rev, reverse=True):
            for rel in _CHROME_RELS:
                exe = d / rel
                if exe.is_file():
                    return exe
    if ask_playwright and importlib.util.find_spec("playwright") is not None:
        try:
            code = ("from playwright.sync_api import sync_playwright\n"
                    "with sync_playwright() as p: print(p.chromium.executable_path)")
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
            exe = Path(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else None
            if exe and exe.is_file():
                return exe
        except (OSError, subprocess.SubprocessError, IndexError):
            pass
    return None


# ------------------------------------------------------------------------------------------------ engines

class _ThreeJsEngine(Engine):
    runner_rel = ""

    def __init__(self, **builder_options):
        self.builder = ThreeJsBundleBuilder(**builder_options)

    def modes(self) -> dict[str, ModeInfo]:
        return dict(THREEJS_MODES)

    def capabilities(self) -> set[str]:
        return set(THREEJS_CAPABILITIES)

    def known_limits(self) -> list[str]:
        return list(THREEJS_KNOWN_LIMITS)

    @property
    def runner_path(self) -> Path:
        return REPO_ROOT / self.runner_rel

    def build_bundle(self, scene, mode: str, views: list, capture: dict, out_dir: Path) -> Path:
        self.check_supports(scene)
        return self.builder.build(scene, mode, views, capture, out_dir)

    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]:
        return [sys.executable, str(self.runner_path), "--bundle", str(bundle_json), "--out", str(out_dir),
                *[str(e) for e in extra]]

    def _require_runner(self) -> None:
        if not self.runner_path.is_file():
            raise NotWired(f"{self.runner_rel} not present")


class ThreeJsNative(_ThreeJsEngine):
    """three.js r186 lighting ported to wgpu-py on Vulkan (the measured system)."""

    name = "threejs-native"
    runner_rel = "native/runner.py"
    _probe_cache: dict[str, object] = {}

    def runner_env(self) -> dict[str, str]:
        return {"WGPU_BACKEND_TYPE": os.environ.get("WGPU_BACKEND_TYPE", "Vulkan")}

    def adapters(self) -> list[dict]:
        """wgpu adapters visible to a fresh interpreter with the runner's environment (cached)."""
        key = os.environ.get("WGPU_BACKEND_TYPE", "Vulkan")
        if key not in self._probe_cache:
            code = ("import json, wgpu\n"
                    "print(json.dumps([dict(a.info) for a in wgpu.gpu.enumerate_adapters_sync()]))")
            env = dict(os.environ, **self.runner_env())
            try:
                out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                                     env=env)
                if out.returncode != 0:
                    err = (out.stderr.strip().splitlines() or ["(no output)"])[-1]
                    self._probe_cache[key] = NotWired(f"wgpu adapter probe failed: {err}")
                else:
                    self._probe_cache[key] = json.loads(out.stdout.strip().splitlines()[-1])
            except (OSError, subprocess.SubprocessError, ValueError, IndexError) as e:
                self._probe_cache[key] = NotWired(f"wgpu adapter probe failed: {e}")
        res = self._probe_cache[key]
        if isinstance(res, NotWired):
            raise res
        return list(res)

    def check_available(self) -> None:
        self._require_runner()
        if importlib.util.find_spec("wgpu") is None:
            raise NotWired("wgpu (wgpu-py) is not installed")
        ads = self.adapters()
        if not ads:
            raise NotWired("no wgpu adapter found")
        if not any(str(a.get("backend_type", "")).lower() == "vulkan" for a in ads):
            got = ", ".join(f"{a.get('device')} ({a.get('backend_type')})" for a in ads)
            raise NotWired(f"no Vulkan adapter (wgpu sees: {got})")

    def version(self) -> str:
        return f"three.js r{THREE_REVISION} port @ {git_sha()}"


class ThreeJsWeb(_ThreeJsEngine):
    """Pinned, unmodified three.js r186 WebGL build in headless Chromium (Phase 0 parity / perf baseline)."""

    name = "threejs-web"
    runner_rel = "web/runner.py"

    def check_available(self) -> None:
        self._require_runner()
        if importlib.util.find_spec("playwright") is None:
            raise NotWired("playwright is not installed")
        if not (VENDOR_DIR / "build" / "three.module.js").is_file():
            raise NotWired("web/vendor/three/build/three.module.js missing")
        if find_chromium() is None:
            raise NotWired("no Chromium found (set HARNESS_CHROMIUM or PLAYWRIGHT_BROWSERS_PATH, or run "
                           "'python -m playwright install chromium')")

    def version(self) -> str:
        try:
            v = json.loads((VENDOR_DIR / "package.json").read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError):
            v = "?"
        return f"three.js r{THREE_REVISION} WebGL build (npm three@{v}, unmodified) in Chromium"
