"""Calibration and reference-noise gates (DESIGN §8), written to ``runs/<id>/gates.json`` (DESIGN §9).

Gates computed from a run directory (``tools.layout.RunLayout``):

- ``oracle`` (subject ``reference``): on every view of every calibration scene, reference ``full`` and ``direct``
  match the analytic oracle (``tools.oracles``) on each ``oracle`` ROI: ``|bias| <= 0.5 %`` and ``rel_l1 <= 1 %``.
- ``oracle`` (subject = engine): the engine's ``direct`` mode capture matches oracle ``direct`` at ``|bias| <= 1 %``,
  ``rel_l1 <= 2 %`` (``cal_furnace`` and ``cal_handedness`` included).
- ``handedness``: on ``cal_handedness`` each quad's centroid lies within ``tolerance_px`` of its expected image
  position and its core pixels equal its radiance ``rho/pi * E * cos`` (to the subject's bias tolerance).
- ``survey_equivalence``: a scene whose oracle names an ``equivalent`` scene (``cal_survey_origin`` ->
  ``cal_point_plane``) renders the same image as it, to the subject's oracle tolerances.
- ``ref_noise`` (subject ``reference``): on every view of every targeted scene, for the measured components
  ``direct`` and ``isolated`` (``full - direct``) and every ROI (spec ROIs and ``all``), the relative standard error
  of the reference ROI mean is ``<= 1 %``. Relative to ``max(|ROI mean|, 0.01 |mean over all|)``; on ``dark`` ROIs,
  whose reference is ~0, relative to the leak normaliser of DESIGN §7 (the largest mean over ``all`` among the
  scene's views, same component; ``tools.metrics.scene_leak_normalisers``). A component that is exactly zero with
  zero standard error passes.
- ``furnace_isolated`` (engines' indirect modes on ``cal_furnace``): reported as a measurement (``passed: null``),
  not a gate (DESIGN §8).

Missing inputs are not failures of the subject unless they should exist: a calibration view an engine never ran
(no capture directory) gives ``passed: null`` with the reason; a capture directory without the capture fails.

By-design skips: when an engine lacks a capability the scene needs (``Engine.missing_capabilities``, DESIGN §4.4;
e.g. three.js has no ``light:rect``) or ``metrics.json`` records the pair as a by-design skip, its gates on that
scene are written with ``status: "skipped"``, ``by_design: true`` and the ``reason``, and ``passed: null``. They are
counted under ``skipped`` in the summary, never as failures.

Every gate carries ``status`` (``passed`` | ``failed`` | ``not_applicable`` | ``skipped``), ``by_design`` and
``reason`` (the skip reason, else null); the summary counts them per subject.

CLI: ``python -m tools.gates --run <run_dir> [--scenes all] [--engines a,b] [--scenes-root DIR] [--strict]``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from .layout import RunLayout

__all__ = ["GATES_VERSION", "GATE_STATUSES", "REFERENCE_TOL", "ENGINE_TOL", "NOISE_TOL", "NON_ENGINE_DIRS",
           "compute_gates", "write_gates", "run_engines", "noise_gate_values", "main"]

GATES_VERSION = 1
GATE_STATUSES = ("passed", "failed", "not_applicable", "skipped")
REFERENCE_TOL = {"bias": 0.005, "rel_l1": 0.01}
ENGINE_TOL = {"bias": 0.01, "rel_l1": 0.02}
NOISE_TOL = 0.01
NOISE_COMPONENTS = ("direct", "isolated")
NON_ENGINE_DIRS = {"reference", "views", "sheets", "temporal", "phase0", "perf", "inspect", "bundles", "logs"}
_REF_NEEDS = ("full.exr", "direct.exr", "full_stderr.exr", "direct_stderr.exr", "depth.exr", "normal.exr",
              "position.exr")


def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _gate(name, subject, scene, view, component, values, tolerance, passed, detail="", roi=None,
          skip: str | None = None) -> dict:
    """One gates.json entry. ``skip`` = by-design skip reason (then passed is None and status 'skipped')."""
    g = {"name": name, "subject": subject, "scene": scene, "view": view, "component": component}
    if roi is not None:
        g["roi"] = roi
    if skip:
        passed, status = None, "skipped"
    else:
        status = {True: "passed", False: "failed", None: "not_applicable"}[passed]
    g.update(values=values, tolerance=tolerance, passed=passed, detail=detail, status=status,
             by_design=bool(skip), reason=skip or None)
    return g


# ------------------------------------------------------------------------------------------------ inputs

def run_engines(layout: RunLayout) -> list[str]:
    """Engine directories in a run: subdirectories (not reference/, views/, sheets/ ...) holding scene captures."""
    out = []
    if not layout.root.is_dir():
        return out
    for d in sorted(p for p in layout.root.iterdir() if p.is_dir()):
        if d.name in NON_ENGINE_DIRS or d.name.startswith("."):
            continue
        if any((s / k).is_dir() for s in d.iterdir() if s.is_dir() for k in ("stations", "timeline", "bundles")):
            out.append(d.name)
    return out


def _engine(engine: str):
    """The registered Engine, or None for unknown names (tests, foreign run directories)."""
    try:
        from renderers import get_engine

        return get_engine(engine)
    except Exception:  # noqa: BLE001
        return None


def _direct_mode(engine: str) -> str:
    try:
        return _engine(engine).direct_mode()
    except Exception:  # noqa: BLE001 - unknown/unwired engines use the conventional name
        return "direct"


def _indirect_modes(engine: str) -> list[str]:
    try:
        return [m for m, info in _engine(engine).modes().items() if info.kind != "direct"]
    except Exception:  # noqa: BLE001
        return []


def _skip_reason(engine: str, scene, view_id: str, mode: str, by_design: dict) -> str | None:
    """By-design skip reason for (engine, scene) or None: a capability the scene needs and the engine lacks
    (DESIGN §4.4), else a by-design skip recorded in metrics.json for this view and mode."""
    eng = _engine(engine)
    caps = None
    try:
        caps = set(eng.capabilities()) if eng is not None else None
    except Exception:  # noqa: BLE001
        caps = None
    if caps:  # an engine that cannot be imported reports no capabilities: infer nothing from it
        missing = sorted(eng.missing_capabilities(scene))
        if missing:
            return f"{engine} lacks {', '.join(missing)} (by design)"
    # per view and mode, or one scene-level entry (view and mode null) as pairs.py writes for a whole scene
    return by_design.get((scene.name, view_id, engine, mode)) or by_design.get((scene.name, None, engine, None))


def _metrics_results(layout: RunLayout) -> list:
    try:
        data = json.loads(layout.metrics_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    res = data.get("results", []) if isinstance(data, dict) else []
    return [r for r in res or [] if isinstance(r, dict)]


def _metrics_reasons(layout: RunLayout) -> dict:
    """{(scene, view, engine, mode): reason} for non-ok results in metrics.json, when it exists."""
    out = {}
    for r in _metrics_results(layout):
        if r.get("status") != "ok":
            out[(r.get("scene"), r.get("view"), r.get("engine"), r.get("mode"))] = \
                f"{r.get('status')}: {r.get('reason')}"
    return out


def _metrics_by_design(layout: RunLayout) -> dict:
    """{(scene, view, engine, mode): reason} for by-design skips recorded in metrics.json."""
    return {(r.get("scene"), r.get("view"), r.get("engine"), r.get("mode")): str(r.get("reason") or "by design")
            for r in _metrics_results(layout) if r.get("status") == "skipped" and r.get("by_design")}


def _read_rgb(path: Path) -> np.ndarray:
    from .exr import read_exr

    return read_exr(path)[..., :3].astype(np.float64)


def _reference_spp_note(layout: RunLayout, scene, view_id: str) -> str:
    """'reference at 205 of the scene's 4096 spp (reduced spp)' when the run's reference of the view was rendered
    below the scene's spp (``--spp-scale``), else ''. Added to failing reference gates: they may be noise."""
    try:
        from .reference import reference_settings

        rec = json.loads((layout.reference_dir(scene.name, view_id) / "receipt.json").read_text(encoding="utf-8"))
        spp = int((rec.get("inputs") or {}).get("spp"))
        nominal = int(reference_settings(scene)["spp"])
    except Exception:  # noqa: BLE001 - informational only
        return ""
    return f"reference at {spp} of the scene's {nominal} spp (reduced spp)" if spp < nominal else ""


def _capture(layout: RunLayout, engine: str, scene: str, mode: str, view, reasons: dict
             ) -> tuple[np.ndarray | None, Any, str]:
    """(image, passed-if-missing, detail): image None when unavailable; passed None = not run, False = failed."""
    path = layout.view_capture(engine, scene, mode, view)
    if path.is_file():
        try:
            return _read_rgb(path), None, str(path)
        except Exception as e:  # noqa: BLE001 - a corrupt capture fails the gate with the reason
            return None, False, f"cannot read {path.name}: {type(e).__name__}: {e}"
    why = reasons.get((scene, view.id, engine, mode))
    cdir = layout.capture_dir(engine, scene, view.kind, mode)
    if cdir.is_dir() and (cdir / "receipt.json").is_file():
        rel = path.relative_to(layout.root).as_posix()
        return None, False, f"capture missing ({rel})" + (f"; {why}" if why else "")
    return None, None, f"not run ({why})" if why else "not run (no capture directory)"


# ------------------------------------------------------------------------------------------------ gate maths

def _oracle_values(img: np.ndarray, oracle_img: np.ndarray, mask: np.ndarray) -> dict:
    from .metrics import nonfinite_count, roi_stats

    s = roi_stats(img, oracle_img, mask)
    v = {"bias": s["bias"], "rel_l1": s["rel_l1"], "bias_rgb": s["bias_rgb"], "pixels": s["pixels"],
         "mean": s["eng_mean"], "oracle_mean": s["ref_mean"]}
    bad = nonfinite_count(np.asarray(img)[mask]) if mask.any() else 0
    if bad:
        v["nonfinite_pixels"] = bad
    return v


def _check(values: dict, tol: dict) -> tuple[bool, str]:
    if not values.get("pixels"):
        return False, "ROI has no pixels"
    if values.get("nonfinite_pixels"):
        return False, f"{values['nonfinite_pixels']} non-finite pixels in the ROI"
    b, r = values.get("bias"), values.get("rel_l1")
    if b is None or r is None:
        return False, "metric undefined"
    fails = []
    if abs(b) > tol["bias"]:
        fails.append(f"|bias| {abs(b):.4%} > {tol['bias']:.2%}")
    if r > tol["rel_l1"]:
        fails.append(f"rel_l1 {r:.4%} > {tol['rel_l1']:.2%}")
    return (not fails), "; ".join(fails)


def noise_gate_values(component_img, stderr_img, mask, all_mask, role: str, leak_norm: float | None = None) -> dict:
    """{'rel_se', 'se', 'mean', 'mean_all', 'pixels', 'basis'} for one ROI and component (see module docstring).

    leak_norm: the scene's leak normaliser for this component (``metrics.scene_leak_normalisers``); dark ROIs use
    it (basis 'leak_norm'), or this view's mean over ``all`` when it is None (basis 'mean_all')."""
    from .metrics import ref_noise_abs, roi_mean

    n = int(np.asarray(mask).sum())
    se = ref_noise_abs(stderr_img, mask) if n else None
    mu = roi_mean(component_img, mask) if n else None
    mall = roi_mean(component_img, all_mask)
    out = {"rel_se": None, "se": se, "mean": mu, "mean_all": mall, "pixels": n, "basis": None}
    if role == "dark" and leak_norm is not None:
        out["leak_norm"] = leak_norm
    if se is None:
        return out
    if role == "dark" and leak_norm is not None:
        den, out["basis"] = abs(leak_norm), "leak_norm"
    elif role == "dark":
        den, out["basis"] = (abs(mall) if mall else 0.0), "mean_all"
    else:
        den, out["basis"] = max(abs(mu or 0.0), 0.01 * abs(mall or 0.0)), "roi_mean"
    if den > 0:
        out["rel_se"] = _f(se / den)
    elif se == 0:
        out["rel_se"] = 0.0
    return out


# ------------------------------------------------------------------------------------------------ per scene

def _calibration_gates(layout, scene, views, engines, reasons, by_design=None) -> tuple[list, dict]:
    from .masks import load_aux, roi_roles, view_masks
    from .oracles import handedness_checks, oracle_images, oracle_spec

    gates, images = [], {}
    oracle = oracle_spec(scene)
    roles = roi_roles(scene)
    for view in views:
        rdir = layout.reference_dir(scene.name, view.id)
        aux = load_aux(rdir)
        masks = view_masks(view, aux)
        orc = oracle_images(view.state, aux, view.station)
        rois = [r for r in masks if roles.get(r) == "oracle"] or ["all"]
        ref = {c: _read_rgb(rdir / f"{c}.exr") for c in ("full", "direct")}
        images[(view.id, "reference")] = (ref, masks)
        # imgs None => unavailable; "missing" is then the gate verdict (None = not run, False = failed)
        subjects = [{"subject": "reference", "imgs": ref, "tol": REFERENCE_TOL, "comps": ("full", "direct"),
                     "detail": "", "missing": None, "skip": None}]
        for eng in engines:
            mode = _direct_mode(eng)
            skip = _skip_reason(eng, scene, view.id, mode, by_design or {})
            if skip:
                subjects.append({"subject": eng, "imgs": None, "tol": ENGINE_TOL, "comps": ("direct",),
                                 "detail": skip, "missing": None, "skip": skip})
                continue
            img, missing, detail = _capture(layout, eng, scene.name, mode, view, reasons)
            subjects.append({"subject": eng, "imgs": None if img is None else {"direct": img}, "tol": ENGINE_TOL,
                             "comps": ("direct",), "detail": f"{mode} mode" if img is not None else detail,
                             "missing": missing, "skip": None})
            if img is not None:
                images[(view.id, eng)] = ({"direct": img}, masks)
        spp_note = _reference_spp_note(layout, scene, view.id)
        for sj in subjects:
            subject, imgs, tol, detail, skip = sj["subject"], sj["imgs"], sj["tol"], sj["detail"], sj["skip"]
            for comp in sj["comps"]:
                for r in rois:
                    if imgs is None:
                        gates.append(_gate("oracle", subject, scene.name, view.id, comp, {}, tol, sj["missing"],
                                           detail, r, skip=skip))
                        continue
                    if imgs[comp].shape[:2] != orc[comp].shape[:2]:
                        gates.append(_gate("oracle", subject, scene.name, view.id, comp,
                                           {"shape": list(imgs[comp].shape)}, tol, False,
                                           f"image {imgs[comp].shape[:2]} != reference {orc[comp].shape[:2]}", r))
                        continue
                    vals = _oracle_values(imgs[comp], orc[comp], masks[r])
                    ok, why = _check(vals, tol)
                    note = spp_note if subject == "reference" and not ok else ""
                    gates.append(_gate("oracle", subject, scene.name, view.id, comp, vals, tol, ok,
                                       "; ".join(x for x in (detail, why, note) if x), r))
            if oracle["type"] == "handedness":
                comp = sj["comps"][0]
                t = {"px": float(oracle.get("tolerance_px", 1.0)), "radiance_rel": tol["bias"]}
                if imgs is None:
                    gates.append(_gate("handedness", subject, scene.name, view.id, comp, {}, t, sj["missing"],
                                       detail, skip=skip))
                    continue
                checks = handedness_checks(imgs[comp], oracle, radiance_tol=tol["bias"])
                bad = [f"{c['quad']}: " + (c.get("note") or ("not found" if c["centroid_px"] is None else
                       f"{c['distance_px']:.2f} px off, radiance error {c['radiance_rel_err']:.2%}"))
                       for c in checks if not c["passed"]]
                gates.append(_gate("handedness", subject, scene.name, view.id, comp,
                                   {"quads": {c["quad"]: {k: c[k] for k in (
                                       "expected_px", "centroid_px", "distance_px", "pixels", "radiance",
                                       "measured", "radiance_rel_err")} for c in checks}},
                                   t, not bad, "; ".join(x for x in (detail, *bad) if x)))
        if oracle["type"] == "furnace":
            skipped = {sj["subject"]: sj["skip"] for sj in subjects if sj["skip"]}
            gates += _furnace_measurements(layout, scene, view, [e for e in engines if e not in skipped], orc,
                                           masks, rois, reasons)
            for eng, why in skipped.items():
                for mode in _indirect_modes(eng):
                    gates.append(_gate("furnace_isolated", eng, scene.name, view.id, "isolated", {"mode": mode},
                                       None, None, f"{mode}: {why}", skip=why))
    return gates, images


def _furnace_measurements(layout, scene, view, engines, orc, masks, rois, reasons) -> list:
    """Indirect modes on the furnace: isolated = final(mode) - final(direct) vs the oracle (passed: null)."""
    from .metrics import energy

    out = []
    for eng in engines:
        dmode = _direct_mode(eng)
        sdir = layout.engine_root(eng) / scene.name / "stations"
        modes = sorted(p.name for p in sdir.iterdir() if p.is_dir() and p.name != dmode) if sdir.is_dir() else []
        if not modes:
            continue
        base, _m, _d = _capture(layout, eng, scene.name, dmode, view, reasons)
        for mode in modes:
            img, _missing, detail = _capture(layout, eng, scene.name, mode, view, reasons)
            if img is None or base is None:
                out.append(_gate("furnace_isolated", eng, scene.name, view.id, "isolated", {"mode": mode}, None,
                                 None, f"{mode}: measurement unavailable ({detail})"))
                continue
            iso = img - base
            for r in rois:
                vals = _oracle_values(iso, orc["isolated"], masks[r])
                vals.update(mode=mode, energy=energy(iso, orc["isolated"], masks[r]))
                out.append(_gate("furnace_isolated", eng, scene.name, view.id, "isolated", vals, None, None,
                                 f"{mode} mode: measurement, not a gate (DESIGN §8)", r))
    return out


def _equivalence_gates(scene_name: str, equivalent: str, a: dict, b: dict) -> list:
    """Survey scene vs its local-coordinate twin, per view and subject present in both."""
    from .metrics import roi_stats

    out = []
    for (vid, subject), (imgs, masks) in sorted(a.items()):
        other = b.get((vid, subject))
        tol = REFERENCE_TOL if subject == "reference" else ENGINE_TOL
        if other is None:
            continue
        oimgs, omasks = other
        mask = masks["all"] & omasks["all"]
        for comp, img in imgs.items():
            twin = oimgs.get(comp)
            if twin is None or twin.shape != img.shape:
                continue
            s = roi_stats(img, twin, mask)
            vals = {"bias": s["bias"], "rel_l1": s["rel_l1"], "pixels": s["pixels"], "equivalent": equivalent}
            ok, why = _check(vals, tol)
            out.append(_gate("survey_equivalence", subject, scene_name, vid, comp, vals, tol, ok,
                             why or f"same image as {equivalent}", "all"))
    return out


def _noise_gates(layout, scene, views) -> list:
    from .masks import load_aux, roi_roles, view_masks
    from .metrics import isolated_stderr, load_reference_images, roi_mean, scene_leak_normalisers

    gates = []
    roles = roi_roles(scene)
    data = []
    for view in views:
        rdir = layout.reference_dir(scene.name, view.id)
        aux = load_aux(rdir)
        masks = view_masks(view, aux)
        ref = load_reference_images(rdir)
        comps = {"direct": (ref["direct"], ref["direct_stderr"]),
                 "isolated": (ref["full"] - ref["direct"], isolated_stderr(ref))}
        data.append((view, masks, comps))
    norms = scene_leak_normalisers({v.id: {c: roi_mean(comps[c][0], masks["all"]) for c in NOISE_COMPONENTS}
                                    for v, masks, comps in data})
    for view, masks, comps in data:
        spp_note = _reference_spp_note(layout, scene, view.id)
        for comp in NOISE_COMPONENTS:
            img, se = comps[comp]
            for r, m in masks.items():
                role = roles.get(r, "any")
                vals = noise_gate_values(img, se, m, masks["all"], role, leak_norm=norms.get(comp))
                vals["role"] = role
                if not vals["pixels"]:
                    gates.append(_gate("ref_noise", "reference", scene.name, view.id, comp, vals, NOISE_TOL, None,
                                       "ROI has no pixels in this view", r))
                    continue
                rel = vals["rel_se"]
                ok = rel is not None and rel <= NOISE_TOL
                detail = "" if ok else "; ".join(x for x in (
                    "undefined" if rel is None else f"rel. s.e. {rel:.3%} > {NOISE_TOL:.0%}", spp_note) if x)
                gates.append(_gate("ref_noise", "reference", scene.name, view.id, comp, vals, NOISE_TOL, ok,
                                   detail, r))
    return gates


# ------------------------------------------------------------------------------------------------ driver

def _run_scenes(layout: RunLayout, selector, scenes_root) -> tuple[list, list]:
    """(scenes with references in the run, warnings)."""
    from .spec import SpecError, discover_scenes, load_scene

    rroot = layout.root / "reference"
    names = sorted(p.name for p in rroot.iterdir() if p.is_dir()) if rroot.is_dir() else []
    wanted = None
    if selector not in (None, "all"):
        wanted = {p.stem for p in discover_scenes(selector, scenes_root)}
    scenes, warnings = [], []
    for name in names:
        if wanted is not None and name not in wanted:
            continue
        try:
            files = discover_scenes(name, scenes_root)
            scene = load_scene(files[0])
        except SpecError as e:
            warnings.append(f"{name}: spec not loadable ({e})")
            continue
        vj = layout.views_json(name)
        if vj.is_file():
            try:
                h = json.loads(vj.read_text(encoding="utf-8")).get("scene_hash")
                if h and h != scene.hash:
                    warnings.append(f"{name}: spec changed since the run (scene hash {h[:12]} -> {scene.hash[:12]})")
            except (OSError, json.JSONDecodeError):
                pass
        scenes.append(scene)
    return scenes, warnings


def compute_gates(run_dir, scenes: str | Sequence[str] | None = "all", engines: Iterable[str] | None = None,
                  scenes_root=None, log: Callable[[str], None] | None = None) -> dict:
    """The gates.json document for a run (DESIGN §9); see the module docstring for the gates."""
    from .spec import expand_views

    say = log or (lambda _m: None)
    layout = RunLayout(run_dir)
    if not layout.root.is_dir():
        raise FileNotFoundError(f"run directory {layout.root} does not exist")
    engines = list(engines) if engines is not None else run_engines(layout)
    reasons = _metrics_reasons(layout)
    by_design = _metrics_by_design(layout)
    scene_list, warnings = _run_scenes(layout, scenes, scenes_root)
    gates: list[dict] = []
    survey: dict[str, tuple[str, dict]] = {}
    images: dict[str, dict] = {}
    for scene in scene_list:
        views = []
        for v in expand_views(scene):
            rdir = layout.reference_dir(scene.name, v.id)
            missing = [f for f in _REF_NEEDS if not (rdir / f).is_file()]
            if missing:
                warnings.append(f"{scene.name}/{v.id}: reference incomplete (missing {', '.join(missing)})")
                continue
            views.append(v)
        if not views:
            continue
        try:
            if scene.group == "calibration" and scene.oracle:
                g, imgs = _calibration_gates(layout, scene, views, engines, reasons, by_design)
                images[scene.name] = imgs
                if scene.oracle.get("equivalent"):
                    survey[scene.name] = (scene.oracle["equivalent"], imgs)
            elif scene.group == "targeted":
                g = _noise_gates(layout, scene, views)
            else:
                continue
        except Exception as e:  # noqa: BLE001 - one broken scene must not hide the others
            warnings.append(f"{scene.name}: gates failed: {type(e).__name__}: {e}")
            gates.append(_gate("error", "reference", scene.name, None, None, {}, None, False,
                               f"{type(e).__name__}: {e}"))
            continue
        gates += g
        say(f"{scene.name}: {len(g)} gates")
    for name, (equiv, imgs) in survey.items():
        if equiv in images:
            gates += _equivalence_gates(name, equiv, imgs, images[equiv])
        else:
            warnings.append(f"{name}: equivalent scene {equiv!r} not in the run; survey_equivalence skipped")
    order = {"reference": 0}
    gates.sort(key=lambda g: (order.get(g["subject"], 1), g["subject"], g["scene"] or "", str(g["view"]),
                              g["name"], str(g["component"]), g.get("roi") or ""))
    summary: dict[str, dict] = {}
    for g in gates:  # by-design skips are counted apart, never as failures
        s = summary.setdefault(g["subject"], {k: 0 for k in GATE_STATUSES})
        s[g["status"]] += 1
    return {"gates_version": GATES_VERSION, "run": layout.run_id,
            "created_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tolerances": {"reference_oracle": REFERENCE_TOL, "engine_oracle": ENGINE_TOL,
                           "reference_noise_rel_se": NOISE_TOL},
            "engines": engines, "scenes": [s.name for s in scene_list], "gates": gates, "summary": summary,
            "warnings": warnings}


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return _f(x)
    return x


def write_gates(run_dir, **kw) -> tuple[Path, dict]:
    """compute_gates + write runs/<id>/gates.json; returns (path, document)."""
    doc = _clean(compute_gates(run_dir, **kw))
    path = RunLayout(run_dir).gates_json
    path.write_text(json.dumps(doc, indent=1, allow_nan=False), encoding="utf-8")
    return path, doc


def _line(g: dict) -> str:
    st = "SKIP" if g.get("status") == "skipped" else {True: "PASS", False: "FAIL", None: "n/a "}[g["passed"]]
    v = g["values"] or {}
    if g["name"] in ("oracle", "survey_equivalence", "furnace_isolated") and v.get("bias") is not None:
        val = f"bias {v['bias']:+.3%} rel_l1 {v['rel_l1']:.3%}" if v.get("rel_l1") is not None else ""
    elif g["name"] == "ref_noise" and v.get("rel_se") is not None:
        val = f"rel s.e. {v['rel_se']:.3%}"
    else:
        val = ""
    where = f"{g['scene']}/{g['view']}" + (f" [{g['roi']}]" if g.get("roi") else "")
    detail = f"  ({g['detail']})" if g.get("detail") and g["passed"] is not True else ""
    return f"{st} {g['subject']:<16} {g['name']:<18} {where:<44} {str(g['component']):<8} {val}{detail}"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.gates", description="Compute the DESIGN §8 gates of a run.")
    ap.add_argument("--run", required=True, help="run directory (runs/<id>)")
    ap.add_argument("--scenes", default="all", help="all | group | name | comma list (default all)")
    ap.add_argument("--engines", default=None, help="comma list (default: every engine directory in the run)")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any gate fails")
    ap.add_argument("--quiet", action="store_true", help="print only failures and the summary")
    args = ap.parse_args(argv)
    try:
        path, doc = write_gates(args.run, scenes=args.scenes, scenes_root=args.scenes_root,
                                engines=[e for e in args.engines.split(",") if e] if args.engines else None)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    for g in doc["gates"]:
        if not args.quiet or g["passed"] is False:
            print(_line(g))
    for w in doc["warnings"]:
        print(f"warning: {w}")
    for subj, s in doc["summary"].items():
        print(f"{subj}: {s['passed']} passed, {s['failed']} failed, {s['not_applicable']} n/a, "
              f"{s['skipped']} skipped by design")
    print(f"wrote {path}")
    if not doc["gates"]:
        print("no gates computed (no calibration or targeted references in the run?)")
    failed = any(s["failed"] for s in doc["summary"].values())
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    sys.exit(main())
