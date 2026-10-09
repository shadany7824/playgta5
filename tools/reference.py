"""Mitsuba 3 reference renderer (DESIGN §6): converged ``full``/``direct`` images, standard errors and AOVs per view.

One Mitsuba scene is built per view state with ``mi.load_dict``: every object becomes an ``mi.Mesh`` holding the
float32 local-frame arrays of ``transformed_mesh(obj)`` (the object's world matrix applied in float64) with a
``twosided(diffuse)`` BSDF; rect lights become ``rectangle`` shapes with an ``area`` emitter (when the radiance is
non-zero) and a ``twosided(diffuse(albedo))`` BSDF; point, directional and environment lights become ``point``,
``directional`` and ``constant`` emitters (all-zero ones are left out, so they cost no light samples). The sensor
is a ``perspective`` camera with ``fov_axis="y"``, a ``box`` rfilter and an ``hdrfilm`` (RGB, float32).

``full`` = ``path`` with ``max_depth`` 64 and ``rr_depth`` 8; ``direct`` = ``path`` with ``max_depth`` 2. Each is
rendered as ``batches`` passes of ``spp / batches`` samples with distinct seeds; the image is the batch mean and
``*_stderr.exr`` the per-pixel standard error of that mean, ``std(batches, ddof=1) / sqrt(batches)``. Batch ``b``
of ``full`` and batch ``b`` of ``direct`` share a seed, so their paths agree up to the second vertex and the
isolated component ``full - direct`` is far less noisy than two independent images would be (an assumption of
independence when combining the two stderr images is therefore conservative). ``isolated_stderr.exr`` holds the
exact standard error of ``full - direct`` from the batch differences. The sampler is ``multijitter`` (stratified,
randomised per seed): batches stay independent, and per-pixel noise is about 9x lower than with ``independent``
at the same spp. It rounds a sample count n up to ``a*b`` with ``a = floor(sqrt(n))``, ``b = ceil(n/a)`` (32 -> 35);
the receipt records the counts actually used.

AOVs come from the ``aov`` integrator at ``aov_spp`` (same sampler, box filter, so values are pixel averages):
``depth.exr`` (channel ``Z``: hit distance from the camera, 0 on a miss), ``normal.exr`` (``R,G,B`` = shading
normal x, y, z, as stored in the mesh, not flipped toward the viewer; 0 on a miss) and ``position.exr``
(``R,G,B`` = local-frame hit point). A pixel is valid when ``|normal| > 0.99`` and ``depth > 0``.

Conventions verified against Mitsuba 3.9.1 (tests/test_reference.py checks each one):

- **Orientation and handedness need no fix.** ``look_at`` here builds the same camera-to-world matrix as Mitsuba's
  ``Transform4f.look_at``: columns ``left = normalize(up x dir)``, ``up' = dir x left``, ``dir``, ``position``.
  The camera's local +X therefore points to the image's *left*, and the film's x axis runs toward local -X, so the
  rendered image is not mirrored. A camera above the origin looking down -Z with ``up = +Y`` shows world +X on the
  right and +Y at the top, and ``mi.render`` returns row 0 = top of the image, the convention of DESIGN §1.
- **Depth offset is corrected.** Mitsuba starts camera rays on the near plane, so its ``depth`` AOV is the distance
  from ``o + d * near_clip / cos(theta)``, not from the camera. The reference uses ``near_clip = 1e-3`` (so nothing
  real is clipped) and adds ``near_clip / cos(theta)`` at each pixel centre back to every pixel that has a hit.
- **Rect lights.** ``rectangle`` is ``[-1, 1]^2`` in its local XY plane with normal +Z; ``to_world`` has the columns
  ``u/2, v/2, normalize(u x v), origin + (u + v)/2``. That matrix has a positive determinant and maps the local
  normal onto ``normalize(u x v)``, the side the one-sided ``area`` emitter lights.
- **Units.** RGB variants pass ``rgb`` values through (to ~5e-6 relative): emitted radiance seen by the camera equals
  the spec value, point ``intensity`` is W/sr and directional ``irradiance`` is W/m^2 on a surface perpendicular to
  the beam.
- **Box filter vs. point oracles.** Pixels are averages over the pixel footprint. An analytic formula evaluated at
  the AOV hit point (the footprint's mean position) differs from that average by the formula's curvature over the
  footprint: about 0.1 % on average and up to ~1.5 % for grazing pixels far from a rect light at 48x36. Averaging the
  formula over sub-pixel rays (tests/test_reference.py: ``plane_hits``) removes it to the noise level.

Variant: ``cuda_ad_rgb`` when a CUDA device is present, else ``llvm_ad_rgb``, else ``scalar_rgb`` (override with
the env var ``HARNESS_MITSUBA_VARIANT`` or ``--variant``).

Cache: ``cache/reference/<key>/`` with ``key = sha256(canonical JSON of the receipt inputs)``, i.e. the view hash,
spp, batches, max_depth, rr_depth, aov_spp, seed, variant and Mitsuba version, plus the sampler and
``REFERENCE_VERSION`` (bumped whenever this module changes what it renders). ``receipt.json`` there records the
inputs, the seconds per render and a whole-image noise summary. ``materialize`` copies a cache entry to
``runs/<id>/reference/<scene>/<view>/``.

CLI: ``python -m tools.reference --run <run_dir> [--scenes ...] [--spp-scale f]`` (also writes
``views/<scene>.json``).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import platform
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import REPO_ROOT
from .exr import write_exr
from .layout import REFERENCE_FILES, RunLayout, reference_cache_dir
from .spec import (Scene, SpecError, View, discover_scenes, expand_views, load_scene, sha256_json, transformed_mesh,
                   views_summary)

__all__ = ["DEFAULT_CACHE_ROOT", "DIRECT_MAX_DEPTH", "EXTRA_FILES", "NEAR_CLIP", "OUTPUT_FILES", "REFERENCE_DEFAULTS",
           "REFERENCE_VERSION", "SAMPLER", "VARIANTS", "ReferenceError", "cache_key", "describe_view",
           "ensure_reference", "load_mitsuba_scene", "look_at_matrix", "luminance", "main", "materialize",
           "mitsuba_version", "receipt_inputs", "rect_matrix", "reference_for_view", "reference_settings",
           "render_view", "run_references", "select_variant", "valid_pixels"]

REFERENCE_VERSION = 1  # bump when the rendered result for the same inputs changes
REFERENCE_DEFAULTS = {"spp": 1024, "batches": 4, "max_depth": 64, "rr_depth": 8, "aov_spp": 64, "seed": 0}
DIRECT_MAX_DEPTH = 2
VARIANTS = ("cuda_ad_rgb", "llvm_ad_rgb", "scalar_rgb")
NEAR_CLIP = 1e-3  # metres; depth AOV is corrected for it
SAMPLER = "multijitter"
MAX_LANES = 1 << 28  # samples per mi.render call (width * height * spp); larger batches are split into chunks
AOV_SPEC = "depth:depth,normal:sh_normal,position:position"  # 1 + 3 + 3 channels, in this order
EXTRA_FILES = ("isolated_stderr.exr",)
OUTPUT_FILES = tuple(REFERENCE_FILES) + EXTRA_FILES
DEFAULT_CACHE_ROOT = REPO_ROOT / "cache"
LUMA = np.array([0.2126, 0.7152, 0.0722])

_state: dict[str, Any] = {"variant": None, "skipped": []}


class ReferenceError(RuntimeError):
    """The reference cannot be produced (Mitsuba missing, no usable variant, bad settings...)."""


# ------------------------------------------------------------------------------------------------ mitsuba setup

def _mi():
    try:
        import mitsuba as mi
    except ImportError as e:  # pragma: no cover - environment dependent
        raise ReferenceError(f"mitsuba is not installed ({e}); pip install -r requirements.txt") from None
    return mi


def mitsuba_version() -> str:
    """Installed Mitsuba version string (raises ReferenceError when Mitsuba is missing)."""
    return str(_mi().__version__)


def _backend_ok(variant: str) -> bool:
    try:
        import drjit as dr
    except ImportError:  # pragma: no cover
        return False
    if variant.startswith("scalar"):
        return True
    backend = dr.JitBackend.CUDA if variant.startswith("cuda") else dr.JitBackend.LLVM
    try:
        return bool(dr.has_backend(backend))
    except Exception:  # noqa: BLE001  # pragma: no cover - older drjit
        return True


def select_variant(preferred: str | None = None) -> str:
    """Set and return the Mitsuba variant: ``preferred``, else the variant chosen earlier in this process, else
    $HARNESS_MITSUBA_VARIANT, else the first usable of VARIANTS (cuda_ad_rgb, llvm_ad_rgb, scalar_rgb).
    Every reference render calls this first."""
    mi = _mi()
    wanted = preferred or None
    if wanted is None and _state["variant"]:
        if mi.variant() != _state["variant"]:
            mi.set_variant(_state["variant"])
        return _state["variant"]
    wanted = wanted or os.environ.get("HARNESS_MITSUBA_VARIANT") or None
    candidates = [wanted] if wanted else list(VARIANTS)
    errors = []
    for v in candidates:
        if v not in mi.variants():
            errors.append(f"{v}: not compiled into this Mitsuba")
            continue
        if not _backend_ok(v):
            errors.append(f"{v}: backend unavailable")
            continue
        try:
            mi.set_variant(v)
            if not wanted and not v.startswith("scalar"):
                _smoke_render(mi)  # e.g. a CUDA device without a working OptiX: fall through to the next one
        except Exception as e:  # noqa: BLE001 - Mitsuba raises ImportError/RuntimeError per backend
            errors.append(f"{v}: {e}")
            continue
        _state["variant"] = v
        _state["skipped"] = errors  # why earlier candidates were passed over (recorded in receipts)
        return v
    raise ReferenceError("no usable Mitsuba variant (" + "; ".join(errors) + ")")


def _smoke_render(mi) -> None:
    """Render a 4x4 image of a rectangle under a constant emitter (raises when the backend cannot)."""
    scene = mi.load_dict({"type": "scene", "integrator": {"type": "path", "max_depth": 2},
                          "r": {"type": "rectangle"}, "e": {"type": "constant"},
                          "sensor": {"type": "perspective", "film": {"type": "hdrfilm", "width": 4, "height": 4}}})
    img = np.array(mi.render(scene, spp=1))
    if img.shape[:2] != (4, 4):
        raise ReferenceError(f"smoke render returned shape {img.shape}")


# ------------------------------------------------------------------------------------------------ settings / key

def reference_settings(scene: Scene | None = None, spp_scale: float = 1.0, **overrides) -> dict:
    """Effective reference settings: REFERENCE_DEFAULTS < scene.reference < overrides, then spp * spp_scale.

    spp is kept >= batches; batches must be >= 2 (the standard error needs two batches).
    """
    s = dict(REFERENCE_DEFAULTS)
    if scene is not None:
        s.update(scene.reference or {})
    s.update({k: v for k, v in overrides.items() if v is not None})
    unknown = set(s) - set(REFERENCE_DEFAULTS)
    if unknown:
        raise ReferenceError(f"unknown reference settings {sorted(unknown)}")
    for k, v in s.items():
        if isinstance(v, bool) or not float(v).is_integer():
            raise ReferenceError(f"reference.{k} must be an integer, got {v!r}")
        s[k] = int(v)
    if s["batches"] < 2:
        raise ReferenceError(f"reference.batches must be >= 2 to estimate a standard error, got {s['batches']}")
    for k in ("spp", "max_depth", "rr_depth", "aov_spp"):
        if s[k] < 1:
            raise ReferenceError(f"reference.{k} must be >= 1, got {s[k]}")
    if s["seed"] < 0:
        raise ReferenceError(f"reference.seed must be >= 0, got {s['seed']}")
    if not (spp_scale > 0 and math.isfinite(spp_scale)):
        raise ReferenceError(f"spp_scale must be a positive number, got {spp_scale!r}")
    if spp_scale != 1.0:
        s["spp"] = round(s["spp"] * spp_scale)
    s["spp"] = max(s["spp"], s["batches"])
    return s


def receipt_inputs(view: View, settings: dict, variant: str, version: str | None = None) -> dict:
    """Everything the cache key covers (DESIGN §6) plus the sampler and REFERENCE_VERSION."""
    return {"view_hash": view.hash, "spp": settings["spp"], "batches": settings["batches"],
            "max_depth": settings["max_depth"], "rr_depth": settings["rr_depth"], "aov_spp": settings["aov_spp"],
            "seed": settings["seed"], "variant": variant,
            "mitsuba_version": version if version is not None else mitsuba_version(),
            "sampler": SAMPLER, "reference_version": REFERENCE_VERSION}


def cache_key(view: View, settings: dict, variant: str, version: str | None = None) -> str:
    """sha256 of the canonical JSON of ``receipt_inputs``."""
    return sha256_json(receipt_inputs(view, settings, variant, version))


# ------------------------------------------------------------------------------------------------ scene building

def look_at_matrix(position, look_at, up) -> np.ndarray:
    """Camera-to-world (4,4) float64 identical to Mitsuba's look_at: columns left, up', forward, position."""
    p, t, u = (np.asarray(x, dtype=np.float64) for x in (position, look_at, up))
    d = t - p
    d /= np.linalg.norm(d)
    left = np.cross(u, d)
    left /= np.linalg.norm(left)
    new_up = np.cross(d, left)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = left, new_up, d, p
    return M


def rect_matrix(origin, u, v) -> np.ndarray:
    """to_world for Mitsuba's ``rectangle`` ([-1,1]^2, normal +Z): (s,t) -> origin + (s+1)/2 u + (t+1)/2 v,
    local +Z -> normalize(u x v) (the emitting side)."""
    o, u, v = (np.asarray(x, dtype=np.float64) for x in (origin, u, v))
    n = np.cross(u, v)
    n /= np.linalg.norm(n)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = u / 2, v / 2, n, o + (u + v) / 2
    return M


def _rect_corners(lt) -> np.ndarray:
    o, u, v = lt.params["origin"], lt.params["u"], lt.params["v"]
    return np.array([o, o + u, o + v, o + u + v])


def describe_view(view: View) -> dict:
    """Plain description (numpy arrays, floats) of the Mitsuba scene for a view's state and camera.

    Keys: ``camera`` (to_world, fov, near/far, width, height), ``meshes`` (id, object, material, albedo, positions,
    normals, indices in the local frame), ``rects`` (id, light, to_world, radiance, albedo, normal, emitting) and
    ``emitters`` (id, light, type and its Mitsuba parameters).
    """
    state, st = view.state, view.station
    meshes, rects, emitters = [], [], []
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for obj in state.objects:
        m = transformed_mesh(obj)
        if m.n_triangles == 0:
            continue
        b0, b1 = m.bbox()
        lo, hi = np.minimum(lo, b0), np.maximum(hi, b1)
        meshes.append({"id": f"obj_{obj.name}", "object": obj.name, "material": obj.material,
                       "albedo": state.materials[obj.material].albedo.astype(np.float64).copy(),
                       "positions": m.positions, "normals": m.normals, "indices": m.indices})
    for lt in state.lights:
        p = lt.params
        if lt.type == "rect":
            c = _rect_corners(lt)
            lo, hi = np.minimum(lo, c.min(0)), np.maximum(hi, c.max(0))
            n = np.cross(p["u"], p["v"])
            rects.append({"id": f"rect_{lt.name}", "light": lt.name, "to_world": rect_matrix(p["origin"], p["u"], p["v"]),
                          "radiance": p["radiance"].copy(), "albedo": p["albedo"].copy(),
                          "normal": n / np.linalg.norm(n), "emitting": bool(np.any(p["radiance"] > 0))})
        elif lt.type == "point":
            lo, hi = np.minimum(lo, p["position"]), np.maximum(hi, p["position"])
            if np.any(p["intensity"] > 0):
                emitters.append({"id": f"light_{lt.name}", "light": lt.name, "type": "point",
                                 "position": p["position"].copy(), "intensity": p["intensity"].copy()})
        elif lt.type == "directional":
            if np.any(p["irradiance"] > 0):
                d = p["direction"] / np.linalg.norm(p["direction"])
                emitters.append({"id": f"light_{lt.name}", "light": lt.name, "type": "directional",
                                 "direction": d, "irradiance": p["irradiance"].copy()})
        elif lt.type == "environment":
            if np.any(p["radiance"] > 0):
                emitters.append({"id": f"light_{lt.name}", "light": lt.name, "type": "constant",
                                 "radiance": p["radiance"].copy()})
        else:  # pragma: no cover - spec validation forbids it
            raise ReferenceError(f"light {lt.name!r}: unsupported type {lt.type!r}")
    if not np.all(np.isfinite(lo)):
        lo = hi = np.zeros(3)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    reach = float(np.linalg.norm(corners - st.position, axis=1).max())
    camera = {"to_world": look_at_matrix(st.position, st.look_at, st.up), "position": st.position.copy(),
              "fov": float(st.vfov_deg), "near": NEAR_CLIP, "far": max(1e4, 4.0 * reach),
              "width": int(state.width), "height": int(state.height)}
    return {"camera": camera, "meshes": meshes, "rects": rects, "emitters": emitters}


def _rgb(v) -> dict:
    return {"type": "rgb", "value": [float(x) for x in v]}


def _bsdf(albedo) -> dict:
    return {"type": "twosided", "material": {"type": "diffuse", "reflectance": _rgb(albedo)}}


def _buffer(mi, arr: np.ndarray, kind: str):
    flat = np.ascontiguousarray(arr).reshape(-1)
    if mi.variant().startswith("scalar"):
        return flat  # scalar variants take numpy arrays for mesh buffers
    return (mi.UInt32 if kind == "u" else mi.Float)(flat)


def _mesh(mi, m: dict, bsdf):
    props = mi.Properties()
    props["bsdf"] = bsdf
    mesh = mi.Mesh(m["id"], vertex_count=len(m["positions"]), face_count=len(m["indices"]), props=props,
                   has_vertex_normals=True)
    params = mi.traverse(mesh)
    params["vertex_positions"] = _buffer(mi, m["positions"].astype(np.float32), "f")
    params["vertex_normals"] = _buffer(mi, m["normals"].astype(np.float32), "f")
    params["faces"] = _buffer(mi, m["indices"].astype(np.uint32), "u")
    params.update()
    return mesh


def _mitsuba_dict(mi, desc: dict) -> dict:
    cam = desc["camera"]
    d: dict[str, Any] = {"type": "scene"}
    bsdfs: dict[tuple, Any] = {}
    for m in desc["meshes"]:
        key = tuple(float(x) for x in m["albedo"])
        if key not in bsdfs:
            bsdfs[key] = mi.load_dict(_bsdf(m["albedo"]))
        d[m["id"]] = _mesh(mi, m, bsdfs[key])
    for r in desc["rects"]:
        shape = {"type": "rectangle", "to_world": mi.ScalarTransform4f(r["to_world"].tolist()), "bsdf": _bsdf(r["albedo"])}
        if r["emitting"]:
            shape["emitter"] = {"type": "area", "radiance": _rgb(r["radiance"])}
        d[r["id"]] = shape
    for e in desc["emitters"]:
        if e["type"] == "point":
            d[e["id"]] = {"type": "point", "position": [float(x) for x in e["position"]], "intensity": _rgb(e["intensity"])}
        elif e["type"] == "directional":
            d[e["id"]] = {"type": "directional", "direction": [float(x) for x in e["direction"]],
                          "irradiance": _rgb(e["irradiance"])}
        else:
            d[e["id"]] = {"type": "constant", "radiance": _rgb(e["radiance"])}
    d["sensor"] = {
        "type": "perspective", "fov": cam["fov"], "fov_axis": "y", "near_clip": cam["near"], "far_clip": cam["far"],
        "to_world": mi.ScalarTransform4f(cam["to_world"].tolist()),
        "sampler": {"type": SAMPLER, "sample_count": 4},
        "film": {"type": "hdrfilm", "width": cam["width"], "height": cam["height"], "pixel_format": "rgb",
                 "component_format": "float32", "sample_border": False, "rfilter": {"type": "box"}},
    }
    return d


def load_mitsuba_scene(view: View, variant: str | None = None):
    """Build the Mitsuba scene of a view (sets the variant first). Returns (mi.Scene, description)."""
    select_variant(variant)
    mi = _mi()
    desc = describe_view(view)
    return mi.load_dict(_mitsuba_dict(mi, desc)), desc


# ------------------------------------------------------------------------------------------------ rendering

def luminance(rgb: np.ndarray) -> np.ndarray:
    """Y = 0.2126 R + 0.7152 G + 0.0722 B over the last axis."""
    return np.asarray(rgb, dtype=np.float64)[..., :3] @ LUMA


def valid_pixels(depth: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """DESIGN §6: a pixel is valid when |normal| > 0.99 and depth > 0."""
    dep = np.asarray(depth, dtype=np.float64)
    if dep.ndim == 3:
        dep = dep[..., 0]
    return (np.linalg.norm(np.asarray(normal, dtype=np.float64)[..., :3], axis=-1) > 0.99) & (dep > 0)


def _effective_spp(mi, n: int) -> int:
    """Sample count the sampler actually takes for a request of n (multijitter rounds up to a*b)."""
    level = mi.log_level() if hasattr(mi, "log_level") else None
    try:
        if level is not None:
            mi.set_log_level(mi.LogLevel.Error)
        return int(mi.load_dict({"type": SAMPLER, "sample_count": int(n)}).sample_count())
    finally:
        if level is not None:
            mi.set_log_level(level)


def _plan(mi, spp_per_batch: int, pixels: int) -> tuple[int, int]:
    """(chunks, spp per chunk) so that one mi.render call stays under MAX_LANES samples."""
    chunks = max(1, math.ceil(pixels * spp_per_batch / MAX_LANES))
    return chunks, _effective_spp(mi, math.ceil(spp_per_batch / chunks))


def _seed(seed: int, batch: int, chunk: int) -> int:
    return (seed * (1 << 20) + batch * (1 << 10) + chunk) % (1 << 32)


def _aov_seed(seed: int) -> int:
    return (seed * (1 << 20) + (1 << 20) - 1) % (1 << 32)


def _render(mi, scene, integrator, spp: int, seed: int, bad: list | None = None) -> np.ndarray:
    """One mi.render call as float64 (H, W, C); non-finite values are zeroed and counted in ``bad[0]``."""
    img = np.array(mi.render(scene, integrator=integrator, spp=int(spp), seed=int(seed)), dtype=np.float64)
    nonfinite = ~np.isfinite(img)
    if nonfinite.any():
        img[nonfinite] = 0.0
        if bad is not None:
            bad[0] += int(nonfinite.any(axis=-1).sum())
    return img


def _pixel_cos(desc: dict) -> np.ndarray:
    """cos(angle between the pixel-centre ray and the optical axis), (H, W)."""
    cam = desc["camera"]
    w, h = cam["width"], cam["height"]
    ty = math.tan(math.radians(cam["fov"]) / 2)
    tx = ty * w / h
    x = ((np.arange(w) + 0.5) / w * 2 - 1) * tx
    y = (1 - (np.arange(h) + 0.5) / h * 2) * ty
    return 1.0 / np.sqrt(1.0 + x[None, :] ** 2 + y[:, None] ** 2)


def _noise_summary(batches: np.ndarray, valid: np.ndarray) -> dict:
    """Whole-image noise of a (B, H, W, 3) batch stack over the valid pixels (luminance)."""
    B = batches.shape[0]
    Yb = luminance(batches)  # (B, H, W)
    Y = Yb.mean(axis=0)
    se = Yb.std(axis=0, ddof=1) / math.sqrt(B)
    n = int(valid.sum())
    if n == 0:
        return {"pixels": 0, "mean_Y": None, "mean_rgb": None, "rel_se_mean": None, "pixel_rel_se_median": None,
                "pixel_rel_se_p95": None, "pixel_se_Y_mean": None}
    mean_rgb = batches.mean(axis=0)[valid].mean(axis=0)
    means_b = Yb[:, valid].mean(axis=1)
    mean_Y = float(means_b.mean())
    se_mean = float(means_b.std(ddof=1) / math.sqrt(B))
    eps = 0.01 * abs(mean_Y) if mean_Y else 1e-12
    rel = se[valid] / (np.abs(Y[valid]) + eps)
    return {"pixels": n, "mean_Y": _finite(mean_Y), "mean_rgb": [_finite(x) for x in mean_rgb],
            "rel_se_mean": _finite(se_mean / abs(mean_Y)) if mean_Y else None,
            "pixel_rel_se_median": _finite(np.median(rel)), "pixel_rel_se_p95": _finite(np.percentile(rel, 95)),
            "pixel_se_Y_mean": _finite(se[valid].mean())}


def _finite(x) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


def _host() -> dict:
    return {"os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
            "cpu": platform.processor() or platform.machine(), "cpus": os.cpu_count()}


def _utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_view(view: View, settings: dict, out_dir, *, variant: str | None = None,
                log: Callable[[str], None] | None = None) -> dict:
    """Render ``full``, ``direct`` (batched) and the AOVs of one view into ``out_dir``; returns the receipt
    (also written as out_dir/receipt.json)."""
    started = _utc()
    t_all = time.perf_counter()
    variant = select_variant(variant)
    mi = _mi()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    say = log or (lambda _m: None)

    t0 = time.perf_counter()
    scene, desc = load_mitsuba_scene(view, variant)
    load_s = time.perf_counter() - t0
    cam = desc["camera"]
    W, H = cam["width"], cam["height"]
    B = settings["batches"]
    chunks, spp_chunk = _plan(mi, math.ceil(settings["spp"] / B), W * H)
    aov_spp = _effective_spp(mi, settings["aov_spp"])
    integrators = {
        "full": mi.load_dict({"type": "path", "max_depth": settings["max_depth"], "rr_depth": settings["rr_depth"]}),
        "direct": mi.load_dict({"type": "path", "max_depth": DIRECT_MAX_DEPTH}),
    }
    stacks: dict[str, np.ndarray] = {}
    seconds: dict[str, list] = {}
    nonfinite = {"full": [0], "direct": [0], "aov": [0]}
    for comp, integ in integrators.items():
        stack = np.zeros((B, H, W, 3))
        secs = []
        for b in range(B):
            t0 = time.perf_counter()
            acc = np.zeros((H, W, 3))
            for c in range(chunks):
                acc += _render(mi, scene, integ, spp_chunk, _seed(settings["seed"], b, c), nonfinite[comp])[..., :3]
            stack[b] = acc / chunks
            secs.append(time.perf_counter() - t0)
        stacks[comp], seconds[comp] = stack, secs
        say(f"    {comp}: {B} x {chunks * spp_chunk} spp in {sum(secs):.2f}s")

    t0 = time.perf_counter()
    aov_int = mi.load_dict({"type": "aov", "aovs": AOV_SPEC})
    A = _render(mi, scene, aov_int, aov_spp, _aov_seed(settings["seed"]), nonfinite["aov"])[..., -7:]
    seconds["aov"] = [time.perf_counter() - t0]
    depth = A[..., 0].copy()
    hit = depth > 0
    depth[hit] += (NEAR_CLIP / _pixel_cos(desc))[hit]  # rays start on the near plane (see module docstring)
    normal, position = A[..., 1:4], A[..., 4:7]
    valid = valid_pixels(depth, normal)

    t0 = time.perf_counter()
    sq = math.sqrt(B)
    iso = stacks["full"] - stacks["direct"]
    images = {
        "full.exr": stacks["full"].mean(0), "direct.exr": stacks["direct"].mean(0),
        "full_stderr.exr": stacks["full"].std(0, ddof=1) / sq, "direct_stderr.exr": stacks["direct"].std(0, ddof=1) / sq,
        "isolated_stderr.exr": iso.std(0, ddof=1) / sq, "normal.exr": normal, "position.exr": position,
    }
    for name, img in images.items():
        write_exr(out / name, img.astype(np.float32), channels="R,G,B", pixel_type="float", compression="zip")
    write_exr(out / "depth.exr", depth.astype(np.float32), channels="Z", pixel_type="float", compression="zip")
    noise = {"full": _noise_summary(stacks["full"], valid), "direct": _noise_summary(stacks["direct"], valid),
             "isolated": _noise_summary(iso, valid)}
    write_s = time.perf_counter() - t0

    inputs = receipt_inputs(view, settings, variant)
    st = view.station
    receipt = {
        "receipt_version": 1, "kind": "reference", "renderer": "mitsuba", "key": sha256_json(inputs), "inputs": inputs,
        "scene": view.scene, "view": view.id, "view_kind": view.kind, "state_index": view.state_index,
        "capture_frame": view.capture_frame, "frames": list(view.frame_range) if view.frame_range else None,
        "camera": {"station": st.name, "position": st.position.tolist(), "look_at": st.look_at.tolist(),
                   "up": st.up.tolist(), "vfov_deg": float(st.vfov_deg), "near_clip": NEAR_CLIP, "far_clip": cam["far"]},
        "image": {"width": W, "height": H},
        "render": {
            "integrators": {"full": {"type": "path", "max_depth": settings["max_depth"], "rr_depth": settings["rr_depth"]},
                            "direct": {"type": "path", "max_depth": DIRECT_MAX_DEPTH},
                            "aov": {"type": "aov", "aovs": AOV_SPEC}},
            "sampler": SAMPLER, "rfilter": "box", "film": "hdrfilm rgb float32",
            "spp_requested": settings["spp"], "spp_per_batch": chunks * spp_chunk, "spp_total": B * chunks * spp_chunk,
            "chunks_per_batch": chunks, "spp_per_chunk": spp_chunk, "aov_spp": aov_spp,
            "seeds": {"full": [[_seed(settings["seed"], b, c) for c in range(chunks)] for b in range(B)],
                      "direct": "same as full (batch b of full and direct share its seeds)",
                      "aov": _aov_seed(settings["seed"])},
            "scene": {"meshes": len(desc["meshes"]), "triangles": int(sum(len(m["indices"]) for m in desc["meshes"])),
                      "rects": len(desc["rects"]), "emitters": [e["id"] for e in desc["emitters"]]},
        },
        "timings": {"load_s": load_s, "full_s": seconds["full"], "direct_s": seconds["direct"],
                    "aov_s": seconds["aov"][0], "write_s": write_s, "total_s": time.perf_counter() - t_all},
        "noise": noise,
        "valid_pixels": int(valid.sum()),
        "nonfinite_pixels": {k: v[0] for k, v in nonfinite.items()},  # zeroed before averaging (normally 0)
        "files": list(OUTPUT_FILES),
        "drjit_version": _drjit_version(),
        "variant_skipped": list(_state["skipped"]),
        "host": _host(), "started_utc": started, "finished_utc": _utc(),
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, allow_nan=False), encoding="utf-8")
    return receipt


def _drjit_version() -> str | None:
    try:
        import drjit as dr
        return str(dr.__version__)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ cache

def _complete(d: Path, key: str) -> dict | None:
    """The cache entry's receipt when every output exists and the key matches, else None."""
    try:
        receipt = json.loads((d / "receipt.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if receipt.get("key") != key or not all((d / f).is_file() for f in OUTPUT_FILES):
        return None
    return receipt


def ensure_reference(view: View, cache_root=None, settings: dict | None = None, *, variant: str | None = None,
                     force: bool = False, log: Callable[[str], None] | None = None) -> tuple[Path, dict]:
    """Return (cache dir, receipt) for a view, rendering into cache/reference/<key>/ only on a miss.

    ``settings`` defaults to ``reference_settings(view.state)``. The receipt gets ``cache_hit`` (not stored).
    """
    settings = reference_settings(view.state) if settings is None else reference_settings(None, **settings)
    variant = select_variant(variant)
    key = cache_key(view, settings, variant)
    root = Path(cache_root) if cache_root is not None else DEFAULT_CACHE_ROOT
    final = reference_cache_dir(key, root)
    if not force:
        receipt = _complete(final, key)
        if receipt is not None:
            return final, dict(receipt, cache_hit=True)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.parent / f".{key}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        receipt = render_view(view, settings, tmp, variant=variant, log=log)
        if receipt["key"] != key:  # pragma: no cover - guards against inputs drifting between key and render
            raise ReferenceError(f"cache key mismatch {receipt['key']} != {key}")
        if final.exists():
            if not force and _complete(final, key) is not None:  # another process finished first
                return final, dict(_complete(final, key), cache_hit=True)
            shutil.rmtree(final, ignore_errors=True)
        try:
            os.replace(tmp, final)
        except OSError:  # a concurrent writer created it in between (Windows cannot replace a directory)
            done = _complete(final, key)
            if done is None:
                raise
            return final, dict(done, cache_hit=True)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return final, dict(receipt, cache_hit=False)


def materialize(layout: RunLayout, view: View, cache_dir, receipt: dict | None = None) -> Path:
    """Copy a cache entry into ``layout.reference_dir(scene, view)``; the copied receipt names its cache entry."""
    src = Path(cache_dir)
    dst = layout.ensure(layout.reference_dir(view.scene, view.id))
    for name in OUTPUT_FILES:
        if name != "receipt.json":
            shutil.copy2(src / name, dst / name)
    rec = json.loads((src / "receipt.json").read_text(encoding="utf-8"))
    rec["cache"] = {"dir": str(src.resolve()), "key": rec.get("key"),
                    "hit": bool(receipt.get("cache_hit")) if receipt else None}
    (dst / "receipt.json").write_text(json.dumps(rec, indent=1, allow_nan=False), encoding="utf-8")
    return dst


def reference_for_view(layout: RunLayout, view: View, cache_root=None, settings: dict | None = None, **kw
                       ) -> tuple[Path, dict]:
    """ensure_reference + materialize; returns (run reference dir, receipt)."""
    cdir, receipt = ensure_reference(view, cache_root, settings, **kw)
    return materialize(layout, view, cdir, receipt), receipt


# ------------------------------------------------------------------------------------------------ CLI

def run_references(run_dir, scenes: str | Sequence[str] = "all", spp_scale: float = 1.0, cache_root=None, *,
                   scenes_root=None, views: Sequence[str] | None = None, variant: str | None = None,
                   force: bool = False, log: Callable[[str], None] | None = print) -> dict:
    """Reference every view of the selected scenes into ``run_dir`` (views/<scene>.json + reference/...).

    Returns {"ok": [...], "failed": [{"scene", "view", "error"}], "hits": n, "rendered": n, "seconds": s}.
    Failures are recorded per scene/view and do not stop the others.
    """
    say = log or (lambda _m: None)
    layout = RunLayout(run_dir)
    layout.ensure(layout.root)
    t0 = time.perf_counter()
    result: dict[str, Any] = {"ok": [], "failed": [], "hits": 0, "rendered": 0}
    files = discover_scenes(scenes, scenes_root)
    if not files:
        say("no scenes selected")
    for f in files:
        try:
            scene = load_scene(f)
            vs = expand_views(scene)
        except SpecError as e:
            result["failed"].append({"scene": Path(f).stem, "view": None, "error": str(e)})
            say(f"FAIL {e}")
            continue
        layout.ensure(layout.views_json(scene.name).parent)
        layout.views_json(scene.name).write_text(json.dumps(views_summary(scene, vs), indent=1), encoding="utf-8")
        try:
            settings = reference_settings(scene, spp_scale)
        except ReferenceError as e:
            result["failed"].append({"scene": scene.name, "view": None, "error": str(e)})
            say(f"FAIL {scene.name}: {e}")
            continue
        for v in vs:
            if views and v.id not in views:
                continue
            say(f"{scene.name}/{v.id}: spp {settings['spp']} x{settings['batches']} batches, "
                f"max_depth {settings['max_depth']}, aov_spp {settings['aov_spp']}")
            try:
                dst, rec = reference_for_view(layout, v, cache_root, settings, variant=variant, force=force,
                                              log=say)
            except Exception as e:  # noqa: BLE001 - keep going; report every failure at the end
                result["failed"].append({"scene": scene.name, "view": v.id, "error": f"{type(e).__name__}: {e}"})
                say(f"FAIL {scene.name}/{v.id}: {type(e).__name__}: {e}")
                continue
            hit = rec.get("cache_hit")
            result["hits" if hit else "rendered"] += 1
            result["ok"].append({"scene": scene.name, "view": v.id, "dir": str(dst), "key": rec["key"],
                                 "cache_hit": hit})
            nz = rec["noise"]["full"]
            rel = nz.get("rel_se_mean")
            why = (f"full image rel. s.e. {rel:.2e}" if rel is not None else
                   "no valid pixels" if not nz.get("pixels") else "full image mean is 0")
            say(f"  {'cached' if hit else 'rendered'} {rec['key'][:12]} in {rec['timings']['total_s']:.1f}s ({why})")
    result["seconds"] = time.perf_counter() - t0
    say(f"{len(result['ok'])} views ok ({result['rendered']} rendered, {result['hits']} cached), "
        f"{len(result['failed'])} failed, {result['seconds']:.1f}s")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.reference",
                                 description="Render (or fetch from the cache) the Mitsuba reference for every view.")
    ap.add_argument("--run", required=True, help="run directory (runs/<id>); created if missing")
    ap.add_argument("--scenes", default="all", help="all | group | name | comma list | spec file (default all)")
    ap.add_argument("--spp-scale", type=float, default=1.0, help="multiply every scene's spp (e.g. 0.25 for a quick run)")
    ap.add_argument("--cache", default=None, help=f"cache root (default {DEFAULT_CACHE_ROOT})")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--views", default=None, help="comma list of view ids to render (default all)")
    ap.add_argument("--variant", default=None, help=f"Mitsuba variant (default: first usable of {', '.join(VARIANTS)})")
    ap.add_argument("--force", action="store_true", help="re-render even when the cache has the entry")
    ap.add_argument("--json", action="store_true", help="print the result summary as JSON at the end")
    args = ap.parse_args(argv)
    try:
        variant = select_variant(args.variant)
        print(f"mitsuba {mitsuba_version()} variant {variant}")
        res = run_references(args.run, args.scenes, args.spp_scale, args.cache, scenes_root=args.scenes_root,
                             views=[v for v in args.views.split(",") if v] if args.views else None,
                             variant=args.variant, force=args.force)
    except (ReferenceError, SpecError) as e:
        print(f"FAIL {e}")
        return 1
    if args.json:
        print(json.dumps(res, indent=1))
    if not res["ok"] and not res["failed"]:
        print(f"FAIL no scenes selected by {args.scenes!r}")
        return 1
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
