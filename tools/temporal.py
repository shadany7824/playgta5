"""Temporal metrics of dynamic modes on timeline scenes (DESIGN §7 "Temporal", §9 temporal.json).

    python -m tools.temporal --run <dir> [--scenes all] [--engines a,b] [--scenes-root DIR]

For every timeline scene of the run (``views/<scene>.json`` of kind ``timeline``), every engine (the engines in
``metrics.json``, plus engine directories in the run) and every mode of the engine that is ``dynamic``:

- ``y(k)``: per ROI (the spec ROIs and ``all``, masks from the reference AOVs of the state view that frame ``k``
  belongs to), the mean luminance of the isolated component, the mode's timeline frame ``k`` minus the engine's own
  ``direct`` timeline frame ``k``; frames that are missing give NaN;
- per step (``tools.metrics.temporal_steps``): ``pre``/``post`` (settled means over the last ``W`` frames of the
  previous/current state), ``t90`` in frames and seconds, and ``afterglow`` on steps where the reference isolated
  ROI mean (``ref_pre``/``ref_post`` from the state views' references) falls;
- per state (``tools.metrics.flicker``): over the last ``W`` frames, ``temporal_cv`` and ``f2f``.

Writes ``temporal.json`` and one plot per (scene, engine, mode), ``temporal/<scene>__<engine>__<mode>.png``: a
panel per ROI with ``y(k)``, the step markers and the reference state levels. Static modes are listed under
``skipped`` with reason ``not dynamic (by design)``; engines that did not run (e.g. not wired) and modes whose
frames are missing are listed there too, with their reason (``by_design`` false for real failures).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from .layout import RunLayout
from .runjson import update_run_json, utc_now

__all__ = ["TEMPORAL_VERSION", "main", "run_temporal", "temporal_for_mode"]

TEMPORAL_VERSION = 1
NOT_DYNAMIC = "not dynamic (by design)"


def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _read_json(path: Path) -> dict | None:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _mode_table(name: str, metrics: dict | None, instance=None) -> tuple[dict | None, str | None]:
    """({mode: {"kind", "dynamic"}}, reason when unknown) from an engine instance, metrics.json or the registry."""
    if instance is not None:
        return {m: {"kind": i.kind, "dynamic": bool(i.dynamic)} for m, i in instance.modes().items()}, None
    block = ((metrics or {}).get("engines") or {}).get(name)
    if block and block.get("modes"):
        return {m: {"kind": i.get("kind"), "dynamic": bool(i.get("dynamic"))} for m, i in block["modes"].items()}, None
    try:
        from renderers import get_engine

        eng = get_engine(name)
        modes = eng.modes()
    except Exception as e:  # noqa: BLE001
        return None, f"mode table unavailable ({type(e).__name__}: {e})"
    if not modes:
        return None, "engine declares no modes"
    return {m: {"kind": i.kind, "dynamic": bool(i.dynamic)} for m, i in modes.items()}, None


def _result_reason(metrics: dict | None, scene: str, engine: str, mode: str | None) -> tuple[str | None, bool]:
    """(reason, by_design) of the first non-ok metrics.json result for this scene/engine(/mode)."""
    for r in (metrics or {}).get("results", []) or []:
        if r.get("scene") == scene and r.get("engine") == engine and r.get("status") != "ok" \
                and (r.get("mode") in (None, mode)):
            return f"{r.get('status')}: {r.get('reason')}", bool(r.get("by_design"))
    return None, False


def _plot(layout: RunLayout, scene, engine: str, mode: str, rois: list[str], series: dict, ref_levels: dict,
          states: list, fps: float) -> Path:
    from . import png
    from .sheets import temporal_plot

    out = layout.temporal_png(scene.name, engine, mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    panels = []
    for i, roi in enumerate(rois):
        tmp = out.with_name(f"{out.stem}.{i}.tmp.png")
        ref = [(a, b, v) for (a, b), v in zip(states, ref_levels[roi]) if v is not None]
        temporal_plot({f"{engine}/{mode}": series[roi]}, [a for a, _ in states[1:]], tmp, fps=fps,
                      title=f"{scene.name} / {engine} / {mode}: ROI {roi}", reference=ref,
                      ylabel="ROI mean Y, isolated = final(mode) - final(direct)", size=(720, 300))
        panels.append(png.load_png(tmp))
        tmp.unlink()
    return png.save_png(out, png.grid(panels, cols=1, pad=4, bg=(252, 252, 251)))


def temporal_for_mode(layout: RunLayout, scene, engine: str, mode: str, direct_mode: str,
                      log: Callable[[str], None] | None = None) -> tuple[list[dict], dict]:
    """temporal.json results (one per ROI) for one dynamic mode, and {"frames_missing", "plot"}."""
    from .exr import read_exr
    from .masks import roi_roles, view_masks
    from .metrics import flicker, load_reference_images, luminance, roi_mean, temporal_steps, window
    from .spec import expand_views, timeline_states

    views = [v for v in expand_views(scene) if v.kind == "state"]
    states = timeline_states(scene)
    fps = float(scene.timeline.fps)
    end = int(scene.timeline.end_frame)
    roles = roi_roles(scene)
    masks = [view_masks(v, layout.reference_dir(scene.name, v.id)) for v in views]
    rois = ["all"] + [r.name for r in scene.rois if any(r.name in m for m in masks)]
    ref_levels = {roi: [] for roi in rois}
    for v, m in zip(views, masks):
        ref = load_reference_images(layout.reference_dir(scene.name, v.id), ("full", "direct"))
        iso = ref["full"] - ref["direct"]
        for roi in rois:
            ref_levels[roi].append(roi_mean(iso, m[roi]) if roi in m and m[roi].any() else None)
    series = {roi: np.full(end + 1, np.nan) for roi in rois}
    win = [(max(first, last - window(first, last) + 1), last) for first, last in states]
    stacks: list[list[np.ndarray]] = [[] for _ in states]
    missing = 0
    nonfinite = {roi: 0 for roi in rois}
    for i, (first, last) in enumerate(states):
        m = masks[i]
        for k in range(first, last + 1):
            pm = layout.timeline_frame(engine, scene.name, mode, k)
            pd = layout.timeline_frame(engine, scene.name, direct_mode, k)
            if not (pm.is_file() and pd.is_file()):
                missing += 1
                continue
            Y = luminance(read_exr(pm)[..., :3].astype(np.float64) - read_exr(pd)[..., :3].astype(np.float64))
            for roi in rois:
                if roi in m and m[roi].any():
                    series[roi][k] = float(Y[m[roi]].mean())
                    nonfinite[roi] += int(not math.isfinite(series[roi][k]))
            if k >= win[i][0]:
                stacks[i].append(Y)
    if missing == end + 1:
        raise FileNotFoundError(f"no timeline frames of {engine}/{mode} (or of its {direct_mode} mode)")
    results = []
    for roi in rois:
        y = series[roi]
        steps = temporal_steps(y, states, fps, ref_levels[roi])
        fl = []
        for i, (first, last) in enumerate(states):
            m = masks[i].get(roi)
            if m is None or not m.any() or len(stacks[i]) < 2:
                fl.append({"state": i, "view": views[i].id, "temporal_cv": None, "f2f": None,
                           "frames": len(stacks[i]), "pixels": 0 if m is None else int(m.sum())})
                continue
            f = flicker(np.stack(stacks[i]), m)
            fl.append({"state": i, "view": views[i].id, **f})
        results.append({"scene": scene.name, "engine": engine, "mode": mode, "roi": roi,
                        "role": roles.get(roi, "any"), "fps": fps,
                        "states": [{"state": i, "view": views[i].id, "first": a, "last": b,
                                    "window": [win[i][0], b], "ref_mean": ref_levels[roi][i]}
                                   for i, (a, b) in enumerate(states)],
                        "steps": steps, "flicker": fl,
                        "series": [_f(x) for x in y.tolist()], "frames_missing": missing,
                        "frames_nonfinite": nonfinite[roi]})
    plot = _plot(layout, scene, engine, mode, rois, series, ref_levels, states, fps)
    rel = plot.relative_to(layout.root).as_posix() if plot.is_relative_to(layout.root) else str(plot)
    for r in results:
        r["plot"] = rel
    return results, {"frames_missing": missing, "frames_nonfinite": max(nonfinite.values()), "plot": rel}


def _timeline_scenes(layout: RunLayout, selector, scenes_root, warnings: list) -> list:
    from .spec import SpecError, discover_scenes, load_scene

    vdir = layout.root / "views"
    names = sorted(p.stem for p in vdir.glob("*.json")) if vdir.is_dir() else []
    wanted = None
    if selector not in (None, "all"):
        wanted = {p.stem for p in discover_scenes(selector, scenes_root)}
    out = []
    for name in names:
        if wanted is not None and name not in wanted:
            continue
        vj = _read_json(vdir / f"{name}.json") or {}
        if vj.get("kind") != "timeline":
            continue
        try:
            scene = load_scene(discover_scenes(name, scenes_root)[0])
        except SpecError as e:
            warnings.append(f"{name}: spec not loadable ({e})")
            continue
        if vj.get("scene_hash") and vj["scene_hash"] != scene.hash:
            warnings.append(f"{name}: spec changed since the run (scene hash {vj['scene_hash'][:12]} -> "
                            f"{scene.hash[:12]})")
        out.append(scene)
    return out


def run_temporal(run_dir, scenes: str | Sequence[str] = "all", engines: Sequence | str | None = None,
                 scenes_root=None, log: Callable[[str], None] | None = print) -> dict:
    """Compute and write temporal.json (+ plots); returns the document."""
    from .gates import run_engines

    say = log or (lambda _m: None)
    t0 = time.perf_counter()
    started = utc_now()
    layout = RunLayout(run_dir)
    if not layout.root.is_dir():
        raise FileNotFoundError(f"run directory {layout.root} does not exist")
    metrics = _read_json(layout.metrics_json)
    instances = {}
    if engines is None:
        names = list(((metrics or {}).get("engines") or {}))
        names += [e for e in run_engines(layout) if e not in names]
    else:
        if isinstance(engines, str):
            engines = [e.strip() for e in engines.split(",") if e.strip()]
        names = []
        for e in engines:
            if isinstance(e, str):
                names.append(e)
            else:
                names.append(e.name)
                instances[e.name] = e
    warnings: list[str] = []
    results: list[dict] = []
    skipped: list[dict] = []
    scene_list = _timeline_scenes(layout, scenes, scenes_root, warnings)
    for scene in scene_list:
        for name in names:
            block = ((metrics or {}).get("engines") or {}).get(name) or {}
            if block.get("status") in ("skipped", "failed"):
                skipped.append({"scene": scene.name, "engine": name, "mode": None, "status": block["status"],
                                "reason": block.get("reason"), "by_design": block["status"] == "skipped"})
                continue
            table, why = _mode_table(name, metrics, instances.get(name))
            if table is None:
                skipped.append({"scene": scene.name, "engine": name, "mode": None, "status": "skipped",
                                "reason": why, "by_design": False})
                continue
            directs = [m for m, i in table.items() if i["kind"] == "direct"]
            for mode, i in table.items():
                if not i["dynamic"]:
                    skipped.append({"scene": scene.name, "engine": name, "mode": mode, "status": "skipped",
                                    "reason": NOT_DYNAMIC, "by_design": True})
                    continue
                reason, by_design = _result_reason(metrics, scene.name, name, mode)
                if reason and by_design:
                    skipped.append({"scene": scene.name, "engine": name, "mode": mode, "status": "skipped",
                                    "reason": reason, "by_design": True})
                    continue
                if len(directs) != 1:
                    skipped.append({"scene": scene.name, "engine": name, "mode": mode, "status": "failed",
                                    "reason": f"engine has {len(directs)} direct modes", "by_design": False})
                    continue
                if reason is None and not layout.capture_dir(name, scene.name, "timeline", mode).is_dir():
                    skipped.append({"scene": scene.name, "engine": name, "mode": mode, "status": "skipped",
                                    "reason": "not run (no capture directory)", "by_design": False})
                    continue
                try:
                    res, info = temporal_for_mode(layout, scene, name, mode, directs[0], say)
                except Exception as e:  # noqa: BLE001 - recorded, the other modes go on
                    why = f"{type(e).__name__}: {e}" + (f" ({reason})" if reason else "")
                    skipped.append({"scene": scene.name, "engine": name, "mode": mode, "status": "failed",
                                    "reason": why, "by_design": False})
                    say(f"{scene.name} {name}/{mode}: FAIL {why}")
                    continue
                results += res
                for r in res:
                    t90 = ", ".join("-" if s["t90_frames"] is None else str(s["t90_frames"]) for s in r["steps"])
                    say(f"{scene.name} {name}/{mode} [{r['roi']}]: t90 frames {t90}")
                if info["frames_missing"]:
                    warnings.append(f"{scene.name} {name}/{mode}: {info['frames_missing']} frames missing")
                if info["frames_nonfinite"]:
                    warnings.append(f"{scene.name} {name}/{mode}: {info['frames_nonfinite']} frames with non-finite "
                                    f"pixels in a ROI (their y(k) is NaN)")
    doc = {"temporal_version": TEMPORAL_VERSION, "run": layout.run_id, "created_utc": started,
           "scenes": [s.name for s in scene_list], "engines": names, "results": results, "skipped": skipped,
           "warnings": warnings, "durations": {"total_s": round(time.perf_counter() - t0, 4)}}
    from .pairs import _clean

    path = layout.temporal_json
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(_clean(doc), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    update_run_json(layout.root, {"durations": {"temporal": {"started_utc": started, "finished_utc": utc_now(),
                                                             **doc["durations"]}}})
    say(f"temporal: {len(results)} ROI results, {len(skipped)} skipped; wrote {path}")
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.temporal", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="run directory (runs/<id>)")
    ap.add_argument("--scenes", default="all", help="all | group | name | comma list (default all)")
    ap.add_argument("--engines", default=None, help="comma list (default: engines in metrics.json and the run)")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    args = ap.parse_args(argv)
    try:
        doc = run_temporal(args.run, scenes=args.scenes, engines=args.engines, scenes_root=args.scenes_root)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    for w in doc["warnings"]:
        print(f"warning: {w}")
    return 1 if any(s["status"] == "failed" for s in doc["skipped"]) else 0


if __name__ == "__main__":
    sys.exit(main())
