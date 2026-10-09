"""Image and temporal metrics (DESIGN §7): pure numpy functions plus the metrics.json result entry (DESIGN §9).

Conventions: images are (H,W,C) linear float (C >= 3, extra channels ignored; a single channel is used as grey),
masks are bool (H,W) from ``tools.masks.view_masks``. ``Y = 0.2126 R + 0.7152 G + 0.0722 B``. Every value that can
be undefined (empty ROI, zero denominator) is returned as ``None`` so results stay JSON-ready.

Per ROI P with engine image E and reference T of the same component, ``dY = Y(E) - Y(T)`` and
``eps = 0.01 * |mean_P Y(T)|``:

- ``bias = sum dY / sum Y(T)``, ``bias_rgb`` per channel, ``bias_abs = mean dY``;
- ``rel_l1 = mean |dY| / (|Y(T)| + eps)``, ``rel_mse = mean dY^2 / (Y(T)^2 + eps^2)`` (``|Y(T)|`` keeps the
  denominator positive where a noisy isolated reference dips below zero; identical for non-negative T);
- dark ROIs: ``leak_abs = mean_P Y(E)``, ``leak_rel = leak_abs / N``, the same for the reference
  (``ref_leak_*``), and no relative metrics. ``N`` is the scene's leak normaliser of the measured component: the
  largest ``mean_all Y(T)`` over the scene's views (``scene_leak_normalisers``, passed to ``view_metrics`` as
  ``leak_norm``), so a view whose reference is entirely black still has a defined ``leak_rel``. Without
  ``leak_norm`` the view's own ``mean_all Y(T)`` is used;
- bleed ROIs: chromaticity ``c = sum rgb / sum (r+g+b)`` of E and T and their L2 distance;
- ``energy = sum_all Y(E) / sum_all Y(T) - 1``;
- ``flip``: HDR-FLIP of the engine final against the reference ``full``, mean over the image and per ROI;
- ``ref_noise_rel``: standard error of the reference ROI mean (from ``*_stderr``, independent pixels, channels
  combined linearly, i.e. as fully correlated, which bounds the luminance error from above) over ``|mean_P Y(T)|``.
  When the reference ROI mean is within ``REF_ZERO_K`` standard errors of zero (``|mean_P Y(T)| <= REF_ZERO_K *
  ref_noise_abs``: the reference is zero up to its own noise, e.g. ``full - direct`` of a lone plane), every ratio
  to it is noise: ``view_metrics`` then leaves ``bias``, ``bias_rgb``, ``rel_l1``, ``rel_mse`` (and ``energy`` for
  ROI ``all``) undefined, keeps ``bias_abs`` and sets ``ref_within_noise: true`` on the ROI.

Temporal functions take a ROI-mean series ``y`` indexed by absolute frame number (array, NaN = frame not written;
or a {frame: value} dict) and the timeline states ``[(first, last)]`` (inclusive).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["AFTERGLOW_THRESHOLD", "AFTERGLOW_TIMES", "LUMA", "NO_CHANGE_REL", "REFERENCE_IMAGES", "afterglow",
           "bleed", "chromaticity", "energy", "flicker", "flip", "flip_error_map", "frame_to_frame", "is_change",
           "isolated_stderr", "leak", "load_reference_images", "luminance", "nonfinite_count", "pixel_stderr_y",
           "ref_noise_abs", "ref_noise_rel", "REF_ZERO_K", "result_entry", "roi_mean", "roi_means", "roi_stats",
           "scene_leak_normalisers",
           "settled", "split_states", "t90", "temporal_steps", "view_metrics", "window"]

LUMA = np.array([0.2126, 0.7152, 0.0722])
AFTERGLOW_TIMES = (0.1, 0.25, 0.5, 1.0)  # seconds after the step
AFTERGLOW_THRESHOLD = 0.05
NO_CHANGE_REL = 1e-3  # |delta| < NO_CHANGE_REL * max(|pre|, |post|) => step not timed
REFERENCE_IMAGES = ("full", "direct", "full_stderr", "direct_stderr", "isolated_stderr")
REF_ZERO_K = 2.0  # a reference ROI mean within this many standard errors of zero is zero up to its noise


def _aces_inverse(y: float, a=2.51, b=0.03, c=2.43, d=0.59, e=0.14) -> float:
    """x with ACES(0.6 x) = y, ACES(x) = x(ax + b) / (x(cx + d) + e) (the fit FLIP uses)."""
    qa, qb, qc = a - y * c, b - y * d, -y * e
    return (-qb + math.sqrt(qb * qb - 4 * qa * qc)) / (2 * qa) / 0.6


# FLIP's HDR exposure range is [log2(XMAX / Ymax), log2(XMAX / Ymedian)] of the reference, where the ACES fit
# (input scaled by 0.6) reaches 0.85 at XMAX.
_FLIP_XMAX = _aces_inverse(0.85)  # ~2.11887
_FLIP_SAFE_YMAX = 1e-6  # below this FLIP's own exposure search can abort the process (median floor ~1.2e-7)


# ------------------------------------------------------------------------------------------------ basics

def _f(x) -> float | None:
    """Finite Python float, else None."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _rgb(img) -> np.ndarray:
    a = np.asarray(img, dtype=np.float64)
    if a.ndim == 2:
        a = a[..., None]
    if a.shape[-1] == 1:
        a = np.repeat(a, 3, axis=-1)
    return a[..., :3]


def luminance(img) -> np.ndarray:
    """Y = 0.2126 R + 0.7152 G + 0.0722 B over the last axis; (H,W) or (H,W,1) input is returned as Y."""
    a = np.asarray(img, dtype=np.float64)
    if a.ndim == 2:
        return a
    if a.shape[-1] == 1:
        return a[..., 0]
    return a[..., :3] @ LUMA


def _mask(mask, shape) -> np.ndarray:
    if mask is None:
        return np.ones(shape[:2], dtype=bool)
    m = np.asarray(mask, dtype=bool)
    if m.shape != tuple(shape[:2]):
        raise ValueError(f"mask shape {m.shape} != image shape {tuple(shape[:2])}")
    return m


def roi_mean(img, mask=None) -> float | None:
    """Mean luminance over the mask (None for an empty mask)."""
    Y = luminance(img)
    m = _mask(mask, Y.shape)
    return _f(Y[m].mean()) if m.any() else None


def roi_means(img, masks: Mapping[str, np.ndarray]) -> dict[str, float | None]:
    """{roi: mean luminance} for every mask."""
    Y = luminance(img)
    return {k: (_f(Y[_mask(m, Y.shape)].mean()) if np.any(m) else None) for k, m in masks.items()}


def nonfinite_count(img) -> int:
    """Number of pixels with any non-finite channel."""
    a = np.asarray(img)
    bad = ~np.isfinite(a)
    return int(bad.any(axis=-1).sum() if a.ndim == 3 else bad.sum())


# ------------------------------------------------------------------------------------------------ ROI metrics

def roi_stats(E, T, mask=None, relative: bool = True) -> dict:
    """bias, bias_rgb, bias_abs, rel_l1, rel_mse, ref_mean, eng_mean (+ rgb means), pixels for one ROI.

    relative=False (dark ROIs) leaves bias, bias_rgb, rel_l1 and rel_mse as None.
    """
    e, t = _rgb(E), _rgb(T)
    if e.shape != t.shape:
        raise ValueError(f"engine shape {e.shape} != reference shape {t.shape}")
    m = _mask(mask, e.shape)
    n = int(m.sum())
    out = {"pixels": n, "bias": None, "bias_rgb": None, "bias_abs": None, "rel_l1": None, "rel_mse": None,
           "ref_mean": None, "eng_mean": None, "ref_mean_rgb": None, "eng_mean_rgb": None}
    if n == 0:
        return out
    ep, tp = e[m], t[m]
    ye, yt = ep @ LUMA, tp @ LUMA
    d = ye - yt
    ref_mean = float(yt.mean())
    out.update(bias_abs=_f(d.mean()), ref_mean=_f(ref_mean), eng_mean=_f(ye.mean()),
               ref_mean_rgb=[_f(x) for x in tp.mean(axis=0)], eng_mean_rgb=[_f(x) for x in ep.mean(axis=0)])
    if not relative:
        return out
    st = float(yt.sum())
    out["bias"] = _f(d.sum() / st) if st > 0 else None
    sc = tp.sum(axis=0)
    dc = (ep - tp).sum(axis=0)
    out["bias_rgb"] = [_f(dc[c] / sc[c]) if sc[c] > 0 else None for c in range(3)]
    eps = 0.01 * abs(ref_mean)
    if eps > 0:
        out["rel_l1"] = _f(np.mean(np.abs(d) / (np.abs(yt) + eps)))
        out["rel_mse"] = _f(np.mean(d * d / (yt * yt + eps * eps)))
    return out


def scene_leak_normalisers(ref_means: Mapping[str, Mapping[str, float | None]]) -> dict[str, float | None]:
    """The scene's leak normaliser per component (DESIGN §7): ``{component: max over views of mean_all Y(T)}``.

    ref_means: ``{view_id: {component: mean_all Y of the reference component}}`` (``component`` is ``"direct"`` or
    ``"isolated"``; values may be None). A component no view has a positive mean for maps to None (leak_rel is
    then undefined, as for a black scene).
    """
    out: dict[str, float | None] = {}
    for comps in ref_means.values():
        for comp, v in (comps or {}).items():
            v = _f(v)
            best = out.get(comp)
            if v is not None and v > 0 and (best is None or v > best):
                out[comp] = v
            else:
                out.setdefault(comp, None)
    return out


def leak(E, mask, normaliser) -> dict:
    """{leak_abs: mean_P Y(E), leak_rel: leak_abs / normaliser} (normaliser: the leak normaliser, DESIGN §7)."""
    Y = luminance(E)
    m = _mask(mask, Y.shape)
    if not m.any():
        return {"leak_abs": None, "leak_rel": None}
    a = float(Y[m].mean())
    nrm = _f(normaliser)
    return {"leak_abs": _f(a), "leak_rel": _f(a / nrm) if nrm and nrm > 0 else None}


def chromaticity(img, mask=None) -> np.ndarray | None:
    """c = sum_P rgb / sum_P (r+g+b), or None when the sum is not positive."""
    a = _rgb(img)
    m = _mask(mask, a.shape)
    s = a[m].sum(axis=0)
    tot = float(s.sum())
    return s / tot if m.any() and tot > 0 and math.isfinite(tot) else None


def bleed(E, T, mask) -> dict:
    """Colour bleeding on a ROI: {c_eng, c_ref, dist = ||c_eng - c_ref||_2} (None where undefined)."""
    ce, cr = chromaticity(E, mask), chromaticity(T, mask)
    return {"c_eng": None if ce is None else [_f(x) for x in ce],
            "c_ref": None if cr is None else [_f(x) for x in cr],
            "dist": None if ce is None or cr is None else _f(np.linalg.norm(ce - cr))}


def energy(E, T, mask=None) -> float | None:
    """sum_all Y(E) / sum_all Y(T) - 1 (gain > 0, loss < 0); None when the reference sum is not positive."""
    ye, yt = luminance(E), luminance(T)
    m = _mask(mask, yt.shape)
    st = float(yt[m].sum())
    return _f(ye[m].sum() / st - 1.0) if m.any() and st > 0 else None


def pixel_stderr_y(stderr) -> np.ndarray:
    """Per-pixel standard error of Y from per-channel standard errors (channels taken as fully correlated)."""
    a = np.abs(np.asarray(stderr, dtype=np.float64))
    if a.ndim == 2:
        return a
    if a.shape[-1] == 1:
        return a[..., 0]
    return a[..., :3] @ LUMA


def ref_noise_abs(stderr, mask=None) -> float | None:
    """Standard error of the ROI mean of Y, assuming independent pixels: sqrt(sum se_i^2) / N."""
    se = pixel_stderr_y(stderr)
    m = _mask(mask, se.shape)
    n = int(m.sum())
    return _f(math.sqrt(float(np.sum(se[m] ** 2))) / n) if n else None


def ref_noise_rel(stderr, ref, mask=None) -> float | None:
    """Relative standard error of the reference ROI mean: ref_noise_abs / |mean_P Y(ref)|."""
    a = ref_noise_abs(stderr, mask)
    mu = roi_mean(ref, mask)
    return _f(a / abs(mu)) if a is not None and mu else None


# ------------------------------------------------------------------------------------------------ FLIP

def flip_error_map(ref_full, test) -> tuple[np.ndarray, dict]:
    """HDR-FLIP error map (H,W) of ``test`` against ``ref_full`` (linear RGB; negatives and non-finite -> 0).

    FLIP picks its exposure range from the reference. For a (near-)black reference that search aborts the whole
    process, so then a single fixed exposure is passed instead.
    """
    import flip_evaluator

    def prep(x):
        a = np.nan_to_num(_rgb(x), nan=0.0, posinf=0.0, neginf=0.0)
        return np.ascontiguousarray(np.clip(a, 0.0, None), dtype=np.float32)

    r, t = prep(ref_full), prep(test)
    if r.shape != t.shape:
        raise ValueError(f"FLIP: test shape {t.shape} != reference shape {r.shape}")
    ymax = float(luminance(r).max()) if r.size else 0.0
    kw = {}
    if not (ymax > _FLIP_SAFE_YMAX):
        c = math.log2(_FLIP_XMAX / ymax) if ymax > 0 else 0.0
        kw["parameters"] = {"startExposure": c, "stopExposure": c, "numExposures": 2}
    err, _mean, params = flip_evaluator.evaluate(r, t, "HDR", applyMagma=False, **kw)
    err = np.asarray(err, dtype=np.float64)
    if err.ndim == 3:
        err = err[..., 0]
    return err, {k: (_f(v) if isinstance(v, (int, float)) else v) for k, v in dict(params).items()}


def flip(final, ref_full, masks: Mapping[str, np.ndarray] | None = None) -> dict:
    """{"mean": mean FLIP over the image, "rois": {roi: mean over the mask}}."""
    err, _ = flip_error_map(ref_full, final)
    rois = {}
    for k, m in (masks or {}).items():
        m = _mask(m, err.shape)
        rois[k] = _f(err[m].mean()) if m.any() else None
    return {"mean": _f(err.mean()), "rois": rois}


# ------------------------------------------------------------------------------------------------ result entry

def load_reference_images(ref_dir, names: Iterable[str] = REFERENCE_IMAGES) -> dict[str, np.ndarray]:
    """{stem: (H,W,3) float32} for the reference images present in a reference view directory."""
    from .exr import read_exr

    d = Path(ref_dir)
    return {n: read_exr(d / f"{n}.exr")[..., :3] for n in names if (d / f"{n}.exr").is_file()}


def isolated_stderr(ref: Mapping[str, np.ndarray]) -> np.ndarray | None:
    """Standard error of full - direct: ``isolated_stderr`` when present, else sqrt(full_se^2 + direct_se^2)
    (independence; conservative because the reference's batches share seeds)."""
    if ref.get("isolated_stderr") is not None:
        return np.asarray(ref["isolated_stderr"], dtype=np.float64)
    a, b = ref.get("full_stderr"), ref.get("direct_stderr")
    if a is None or b is None:
        return None
    return np.sqrt(np.asarray(a, dtype=np.float64) ** 2 + np.asarray(b, dtype=np.float64) ** 2)


def result_entry(scene: str, view: str, engine: str, mode: str, kind: str, status: str = "ok",
                 reason: str | None = None, by_design: bool = False, component: str | None = None,
                 convergence: Any = None, files: Mapping | None = None) -> dict:
    """An empty metrics.json result (DESIGN §9); use directly for skipped/failed pairs."""
    if component is None:
        component = "direct" if kind == "direct" else "isolated"
    f = {"capture": None, "direct_capture": None, "sheet": None}
    f.update({k: (None if v is None else str(v)) for k, v in (files or {}).items()})
    return {"scene": scene, "view": view, "engine": engine, "mode": mode, "kind": kind, "status": status,
            "reason": reason, "by_design": bool(by_design), "component": component, "rois": {}, "energy": None,
            "bleed": {}, "flip": None, "convergence": convergence, "files": f}


def _check_image(name: str, img, shape) -> list[str]:
    if img is None:
        return [f"{name} missing"]
    a = np.asarray(img)
    if a.ndim not in (2, 3) or a.shape[:2] != tuple(shape[:2]):
        return [f"{name} has shape {tuple(a.shape)}, expected {tuple(shape[:2])}"]
    n = nonfinite_count(a)
    if n:
        nan = int(np.isnan(a).any(axis=-1).sum() if a.ndim == 3 else np.isnan(a).sum())
        return [f"{name} has {n} non-finite pixel{'s' if n != 1 else ''} (NaN {nan}, inf {n - nan})"]
    return []


def view_metrics(*, scene: str, view: str, engine: str, mode: str, kind: str, final, ref: Mapping[str, Any],
                 masks: Mapping[str, np.ndarray], roles: Mapping[str, str] | None = None, direct_final=None,
                 comparison: str = "exact", convergence: Any = None, files: Mapping | None = None,
                 leak_norm: Mapping[str, float | None] | None = None) -> dict:
    """One metrics.json result entry (DESIGN §9) for a (scene, view, engine, mode).

    final: the mode's capture; direct_final: the same engine's ``direct`` capture of the view (needed for
    indirect modes; ignored for kind 'direct'); ref: {'full', 'direct', optional '*_stderr'} images (see
    ``load_reference_images``); masks/roles from ``tools.masks``. Kind 'direct' measures the direct component
    against reference ``direct``; other kinds the isolated component ``final - direct_final`` against
    ``full - direct``. ``comparison='appearance'`` reports only FLIP. Bad inputs (missing, wrong shape, NaN/inf)
    give status 'failed' with the reason; this function does not raise on image content.

    leak_norm: ``scene_leak_normalisers(...)`` of the scene; when given, ``leak_norm[component]`` replaces this
    view's ``mean_all Y(T)`` as the normaliser of ``leak_rel``, ``ref_leak_rel`` and ``leak_noise_rel`` (None or a
    missing component leaves them undefined). The entry records the normaliser used as ``leak_norm``.
    """
    roles = dict(roles or {})
    e = result_entry(scene, view, engine, mode, kind, convergence=convergence, files=files)
    full, rdir = ref.get("full"), ref.get("direct")
    shape = np.asarray(full).shape if full is not None else None
    if shape is None or len(shape) < 2:
        e.update(status="failed", reason="reference full missing")
        return e
    problems = _check_image("reference full", full, shape)
    if comparison != "appearance":
        problems += _check_image("reference direct", rdir, shape)
    problems += _check_image("engine final", final, shape)
    if comparison != "appearance" and e["component"] == "isolated":
        problems += _check_image("engine direct capture", direct_final, shape)
    bad_masks = [k for k, m in masks.items() if np.asarray(m).shape != tuple(shape[:2])]
    if bad_masks:
        problems.append(f"masks {bad_masks} do not match the image size {tuple(shape[:2])}")
    if problems:
        e.update(status="failed", reason="; ".join(problems))
        return e

    try:
        e["flip"] = flip(final, full, masks)
    except Exception as ex:  # noqa: BLE001 - FLIP failing must not hide the other metrics
        e["flip"] = {"mean": None, "rois": {}, "error": f"{type(ex).__name__}: {ex}"}
    if comparison == "appearance":
        return e

    if e["component"] == "direct":
        E, T = _rgb(final), _rgb(rdir)
        se = ref.get("direct_stderr")
    else:
        E, T = _rgb(final) - _rgb(direct_final), _rgb(full) - _rgb(rdir)
        se = isolated_stderr(ref)
    if se is not None and np.asarray(se).shape[:2] != tuple(shape[:2]):
        se = None  # a mismatched noise image only loses the noise columns
    all_mask = masks.get("all")
    if all_mask is None:
        all_mask = np.ones(shape[:2], dtype=bool)
    if leak_norm is not None:  # the scene's brightest view of this component (DESIGN §7)
        norm = _f(leak_norm.get(e["component"]))
    else:  # this view's own mean_all Y(T)
        norm = roi_mean(T, all_mask)
    e["leak_norm"] = norm
    for name, m in masks.items():
        role = roles.get(name, "any")
        if role == "dark":
            s = roi_stats(E, T, m, relative=False)
            s.update(leak(E, m, norm))
            rl = leak(T, m, norm)
            s.update(ref_leak_abs=rl["leak_abs"], ref_leak_rel=rl["leak_rel"])
        else:
            s = roi_stats(E, T, m)
        s["role"] = role
        s["ref_noise_abs"] = ref_noise_abs(se, m) if se is not None else None
        s["ref_noise_rel"] = ref_noise_rel(se, T, m) if se is not None else None
        if role != "dark" and s.get("ref_mean") and s["ref_noise_abs"] is not None \
                and abs(s["ref_mean"]) <= REF_ZERO_K * s["ref_noise_abs"]:
            # the reference is zero up to its own noise: a ratio to it would be noise (e.g. +3e14 %)
            s.update(bias=None, bias_rgb=None, rel_l1=None, rel_mse=None, ref_within_noise=True)
        if role == "dark":
            s["leak_noise_rel"] = (_f(s["ref_noise_abs"] / norm)
                                   if s["ref_noise_abs"] is not None and norm and norm > 0 else None)
        e["rois"][name] = s
        if role == "bleed":
            e["bleed"][name] = bleed(E, T, m)
    e["energy"] = None if (e["rois"].get("all") or {}).get("ref_within_noise") else energy(E, T, all_mask)
    return e


# ------------------------------------------------------------------------------------------------ temporal

def split_states(timeline, end_frame: int | None = None) -> list[tuple[int, int]]:
    """[(first, last)] inclusive per state: [0, f1-1], [f1, f2-1], ..., [fn, end_frame] (DESIGN §2).

    timeline: a spec Timeline, a dict {"steps": [...], "end_frame": n} (steps as frames, (frame, actions) pairs
    or {"frame": f} dicts), or a list of step frames together with ``end_frame``.
    """
    if isinstance(timeline, Mapping):
        steps, end = timeline.get("steps", []), timeline.get("end_frame", end_frame)
    elif hasattr(timeline, "steps"):
        steps, end = timeline.steps, getattr(timeline, "end_frame", end_frame)
    else:
        steps, end = list(timeline), end_frame
    if end is None:
        raise ValueError("split_states: end_frame is required")
    frames = []
    for s in steps:
        if isinstance(s, Mapping):
            frames.append(int(s["frame"]))
        elif isinstance(s, (tuple, list)):
            frames.append(int(s[0]))
        else:
            frames.append(int(s))
    starts = [0] + frames
    ends = [f - 1 for f in frames] + [int(end)]
    return list(zip(starts, ends))


def window(first: int, last: int) -> int:
    """W = min(10, len(state) / 4) frames (at least 1)."""
    return max(1, min(10, (int(last) - int(first) + 1) // 4))


def _series(y) -> np.ndarray:
    if isinstance(y, Mapping):
        if not y:
            return np.zeros(0)
        out = np.full(max(int(k) for k in y) + 1, np.nan)
        for k, v in y.items():
            out[int(k)] = np.nan if v is None else float(v)
        return out
    return np.asarray([np.nan if v is None else v for v in y] if isinstance(y, list) else y, dtype=np.float64)


def settled(series, start: int, end: int, W: int | None = None) -> float | None:
    """Mean of y over the last W frames of the state [start, end] (NaN frames ignored)."""
    y = _series(series)
    W = window(start, end) if W is None else int(W)
    lo = max(int(start), int(end) - W + 1)
    seg = y[lo:int(end) + 1]
    seg = seg[np.isfinite(seg)]
    return _f(seg.mean()) if seg.size else None


def is_change(pre: float | None, post: float | None, rel: float = NO_CHANGE_REL) -> bool:
    """True unless |post - pre| < rel * max(|pre|, |post|) (or either is undefined)."""
    if pre is None or post is None:
        return False
    d = abs(post - pre)
    return d > 0 and d >= rel * max(abs(pre), abs(post))


def _settle_frames(ok: np.ndarray) -> int | None:
    """Smallest n with ok[k] for every k >= n; None when the last frame is not ok (never settles)."""
    if ok.size == 0 or not ok[-1]:
        return None
    bad = np.nonzero(~ok)[0]
    return 0 if bad.size == 0 else int(bad[-1] + 1)


def t90(series, step_frame: int, end: int, pre: float | None, post: float | None) -> int | None:
    """Smallest n >= 0 with |y(k) - post| <= 0.1 |post - pre| for every k in [step_frame + n, end].

    None for a no-change step or when the last frame of the state is still outside the band.
    """
    if not is_change(pre, post):
        return None
    y = _series(series)[int(step_frame):int(end) + 1]
    with np.errstate(invalid="ignore"):
        ok = np.abs(y - post) <= 0.1 * abs(post - pre)
    return _settle_frames(ok)


def afterglow(series, step_frame: int, end: int, ref_pre: float | None, ref_post: float | None,
              post: float | None, fps: float, times: Sequence[float] = AFTERGLOW_TIMES,
              threshold: float = AFTERGLOW_THRESHOLD) -> dict | None:
    """Afterglow after a step where the reference isolated ROI mean falls; None otherwise.

    r(k) = (y(k) - ref_post) / (ref_pre - ref_post). Returns {"r": {"0.1": r(f + round(0.1 fps)), ...}
    (None past the state's end), "t05_frames"/"t05_s": smallest n with r(k) <= threshold for every k >= f + n
    (None if never), "residual": (post - ref_post) / (ref_pre - ref_post)}.
    """
    if ref_pre is None or ref_post is None:
        return None
    den = ref_pre - ref_post
    if not (den > 0 and is_change(ref_pre, ref_post)):
        return None
    y = _series(series)[int(step_frame):int(end) + 1]
    r = (y - ref_post) / den
    r_at = {}
    for t in times:
        i = round(float(t) * fps)
        r_at[str(float(t))] = _f(r[i]) if 0 <= i < r.size else None
    with np.errstate(invalid="ignore"):
        n = _settle_frames(r <= threshold)
    return {"r": r_at, "threshold": threshold, "t05_frames": n, "t05_s": None if n is None else n / fps,
            "residual": None if post is None else _f((post - ref_post) / den)}


def frame_to_frame(y) -> float | None:
    """mean |y(k) - y(k-1)| / |mean y| over a series (NaN frames dropped)."""
    y = _series(y)
    y = y[np.isfinite(y)]
    if y.size < 2 or not abs(y.mean()) > 0:
        return None
    return _f(np.mean(np.abs(np.diff(y))) / abs(y.mean()))


def flicker(frames, mask=None) -> dict:
    """Flicker over a window of frames (T,H,W[,C]) of the isolated component, on a ROI.

    temporal_cv = mean over the ROI of per-pixel temporal std (ddof=1) / max(|temporal mean|, eps),
    eps = 0.01 |ROI mean|; f2f = frame_to_frame of the ROI-mean series.
    """
    st = np.asarray(frames, dtype=np.float64)
    Y = st if st.ndim == 3 else (st[..., 0] if st.shape[-1] == 1 else st[..., :3] @ LUMA)
    m = _mask(mask, Y.shape[1:])
    if Y.shape[0] < 2 or not m.any():
        return {"temporal_cv": None, "f2f": None, "frames": int(Y.shape[0]), "pixels": int(m.sum())}
    P = Y[:, m]  # (T, N)
    mu = P.mean(axis=0)
    sd = P.std(axis=0, ddof=1)
    eps = 0.01 * abs(float(mu.mean()))
    den = np.maximum(np.abs(mu), eps)
    cv = _f(np.mean(sd / den)) if eps > 0 or np.all(den > 0) else None
    return {"temporal_cv": cv, "f2f": frame_to_frame(P.mean(axis=1)), "frames": int(Y.shape[0]),
            "pixels": int(m.sum())}


def temporal_steps(series, states: Sequence[tuple[int, int]], fps: float,
                   ref_means: Sequence[float | None] | None = None) -> list[dict]:
    """temporal.json ``steps`` for one ROI series: one entry per step (state i >= 1).

    ref_means: the reference isolated ROI mean of every state view (enables afterglow on falling steps).
    """
    out = []
    for i in range(1, len(states)):
        (pf, pl), (f, l) = states[i - 1], states[i]
        pre, post = settled(series, pf, pl), settled(series, f, l)
        timed = is_change(pre, post)
        n = t90(series, f, l, pre, post) if timed else None
        ag = None
        if ref_means is not None and len(ref_means) > i:
            ag = afterglow(series, f, l, ref_means[i - 1], ref_means[i], post, fps)
        out.append({"frame": int(f), "pre": pre, "post": post,
                    "delta": None if pre is None or post is None else _f(post - pre), "timed": timed,
                    "t90_frames": n, "t90_s": None if n is None else n / fps, "afterglow": ag})
    return out
