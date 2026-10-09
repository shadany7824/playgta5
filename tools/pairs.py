"""Comparison driver (DESIGN pipeline step 4; §3, §4, §7, §9): every engine x mode against the Mitsuba reference.

    python -m tools.pairs --run <dir> [--engines threejs-native,future] [--scenes all|group|names] [--modes m1,m2]
        [--spp-scale f] [--settle-frames N] [--dynamic-settle-frames N] [--timeout S] [--jobs 1]

For each selected scene:

1. expand its views (``tools.spec.expand_views``) and write ``views/<scene>.json``;
2. ensure the references (``tools.reference``: cache hit or render) and materialize them into
   ``reference/<scene>/<view>/`` (a complete run copy with the expected cache key is reused as is);
3. for each engine: ``check_available`` (``NotWired`` -> one skipped result for the scene, ``by_design: true``, the
   reason), ``check_supports`` (``Unsupported`` -> one by-design skip naming the missing capabilities), then ONE
   launch per mode, the direct mode first (indirect modes are isolated against it, so it always runs when an
   indirect mode is selected): build the bundle (stations: ``settle_frames`` 4 for non-dynamic and 64 for dynamic
   modes; timeline: the direct and dynamic modes capture every frame, static modes only the state capture frames),
   clear the capture directory, run ``renderers.base.launch``. Failures (exit code, log tail, missing or non-finite
   captures, bundle errors, timeouts) become ``failed`` results and the run goes on; runner exit 2 is a by-design
   skip;
4. metrics per view and mode (``tools.metrics.view_metrics``): kind ``direct`` against reference ``direct``, other
   kinds as ``final(mode) - final(direct)`` of the same engine against ``full - direct``; dark-ROI leaks are
   normalised per scene (``tools.metrics.scene_leak_normalisers``: max over the scene's views of the reference's
   mean over ``all``), so a view whose reference is entirely black still gets a ``leak_rel``. A result whose
   receipt reports ``convergence.last_rel_change > 1e-3`` carries a warning (station views: that station's entry;
   timeline: the receipt's end-of-timeline value, warned on the last state, which it measures);
5. a contact sheet per view (``sheets/<scene>/<view>.png``): a direct block (reference | each engine's direct mode;
   rows final, direct, relative error) above an isolated block (reference | each indirect mode; rows final,
   isolated, relative error), so each block has its own display exposure.

Then ``metrics.json`` (DESIGN §9; merged with an existing one: results of (scene, engine) pairs not re-run are
kept, ``--fresh`` drops them) and ``gates.json`` (``tools.gates``), and ``run.json`` gets the pairs config, git sha,
host, per-step durations and per-launch seconds. Exit code 0 when no result failed, 1 otherwise, 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from .layout import RunLayout, reference_cache_dir
from .runjson import host_info, update_run_json, utc_now

__all__ = ["CONVERGENCE_WARN", "DEFAULT_ENGINES", "DEFAULT_TIMEOUT", "METRICS_VERSION", "SETTLE_DYNAMIC",
           "SETTLE_STATIC", "capture_request", "ensure_scene_references", "main", "ordered_modes", "resolve_engines",
           "run_pairs"]

METRICS_VERSION = 1
DEFAULT_ENGINES = ("threejs-native", "future")
SETTLE_STATIC = 4
SETTLE_DYNAMIC = 64
DEFAULT_TIMEOUT = 3600.0
CONVERGENCE_WARN = 1e-3

_lock = threading.Lock()


# ------------------------------------------------------------------------------------------------ helpers

def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _clean(x):
    """JSON-ready copy: numpy scalars to Python, non-finite floats to None, Paths to strings."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return _f(x)
    if isinstance(x, Path):
        return x.as_posix()
    return x


def _rel(layout: RunLayout, p: Path | None) -> str | None:
    if p is None:
        return None
    try:
        return Path(p).relative_to(layout.root).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _read_json(path: Path) -> dict | None:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _write_json(path: Path, doc: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(_clean(doc), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _read_rgb(path: Path) -> np.ndarray:
    from .exr import read_exr

    return read_exr(path)[..., :3].astype(np.float64)


def resolve_engines(engines: Sequence | str | None) -> list:
    """Engine instances from names (comma string or list) or ready instances; default DEFAULT_ENGINES."""
    from renderers import get_engine

    if engines is None:
        engines = list(DEFAULT_ENGINES)
    if isinstance(engines, str):
        engines = [e.strip() for e in engines.split(",") if e.strip()]
    out = []
    for e in engines:
        eng = get_engine(e) if isinstance(e, str) else e
        if any(o.name == eng.name for o in out):
            raise ValueError(f"engine {eng.name!r} given twice")
        out.append(eng)
    return out


def ordered_modes(engine, requested: Sequence[str] | None = None) -> tuple[list[str], str | None]:
    """(modes to run, note): the engine's direct mode first, then its other modes in declaration order, filtered
    by ``requested``; the direct mode is added when an indirect mode is requested without it."""
    modes = engine.modes()
    direct = engine.direct_mode()
    order = [direct] + [m for m in modes if m != direct]
    if not requested:
        return order, None
    picked = [m for m in order if m in requested]
    note = None
    if picked and direct not in picked:
        picked.insert(0, direct)
        note = f"{direct} added: indirect modes are isolated against it"
    return picked, note


def capture_request(scene, views: list, info, settle_frames: int = SETTLE_STATIC,
                    dynamic_settle_frames: int = SETTLE_DYNAMIC) -> dict:
    """The capture dict for Engine.build_bundle (DESIGN §4.2 capture block)."""
    if scene.timeline is None:
        n = int(dynamic_settle_frames if info.dynamic else settle_frames)
        return {"settle_frames": n,
                "stations": [{"name": v.id, "camera": v.station.name, "settle_frames": n} for v in views]}
    tl = scene.timeline
    if info.kind == "direct" or info.dynamic:
        frames = list(range(int(tl.end_frame) + 1))
    else:
        frames = sorted({int(v.capture_frame) for v in views})
    return {"timeline": {"camera": tl.station, "end_frame": int(tl.end_frame), "frames": frames}}


# ------------------------------------------------------------------------------------------------ references

def _complete_ref(d: Path, key: str | None = None) -> bool:
    from .reference import OUTPUT_FILES

    if not all((d / f).is_file() for f in OUTPUT_FILES):
        return False
    if key is None:
        return True
    rec = _read_json(d / "receipt.json") or {}
    return rec.get("key") == key


def ensure_scene_references(layout: RunLayout, scene, views: list, spp_scale: float = 1.0, cache_root=None,
                            references: str = "ensure", log: Callable[[str], None] | None = None
                            ) -> tuple[dict[str, Path], list[str]]:
    """({view id: run reference dir}, warnings). references='ensure': reuse a complete run copy with the expected
    cache key, else ensure (cache hit or render) and materialize; 'existing': never render (use the run copy or a
    complete cache entry). Raises ReferenceError when a view has no usable reference."""
    from . import reference as R

    say = log or (lambda _m: None)
    settings = R.reference_settings(scene, spp_scale)
    out, warnings = {}, []
    root = Path(cache_root) if cache_root is not None else R.DEFAULT_CACHE_ROOT
    for v in views:
        rdir = layout.reference_dir(scene.name, v.id)
        try:
            variant = R.select_variant()
            key = R.cache_key(v, settings, variant)
        except R.ReferenceError as e:
            if _complete_ref(rdir):
                warnings.append(f"{v.id}: Mitsuba unavailable ({e}); using the run's existing reference")
                out[v.id] = rdir
                continue
            raise
        if _complete_ref(rdir, key):
            out[v.id] = rdir
            continue
        cdir = reference_cache_dir(key, root)
        if references == "existing":
            if _complete_ref(cdir, key):
                R.materialize(layout, v, cdir, {"cache_hit": True})
                out[v.id] = rdir
                continue
            if _complete_ref(rdir):
                warnings.append(f"{v.id}: run reference has different settings than expected (key mismatch)")
                out[v.id] = rdir
                continue
            raise R.ReferenceError(f"{scene.name}/{v.id}: no reference in the run or the cache, and rendering "
                                   f"is disabled (--skip-references)")
        say(f"  reference {scene.name}/{v.id}: spp {settings['spp']} x{settings['batches']}")
        d, rec = R.reference_for_view(layout, v, cache_root, settings)
        say(f"    {'cached' if rec.get('cache_hit') else 'rendered'} {rec['key'][:12]}")
        out[v.id] = d
    return out, warnings


# ------------------------------------------------------------------------------------------------ launches

def _launch_mode(layout: RunLayout, engine, scene, views, mode: str, info, cfg: dict, say) -> dict:
    """Build the bundle and run the runner for one (engine, scene, mode). Never raises."""
    rec = _launch_mode_inner(layout, engine, scene, views, mode, info, cfg)
    say(f"  {engine.name}/{mode}: {rec['status']}{' (' + rec['reason'] + ')' if rec['reason'] else ''} "
        f"in {rec['bundle_seconds'] + rec['seconds']:.1f} s")
    return rec


def _launch_mode_inner(layout: RunLayout, engine, scene, views, mode: str, info, cfg: dict) -> dict:
    from renderers.base import NotWired, Unsupported, launch
    from .spec import capture_kind

    kind = capture_kind(scene)
    rec = {"engine": engine.name, "scene": scene.name, "mode": mode, "kind": kind, "status": "failed",
           "reason": None, "by_design": False, "seconds": 0.0, "bundle_seconds": 0.0, "returncode": None,
           "log_tail": [], "receipt": None, "warnings": [], "capture_dir": layout.capture_dir(
               engine.name, scene.name, kind, mode)}
    t0 = time.perf_counter()
    try:
        capture = capture_request(scene, views, info, cfg["settle_frames"], cfg["dynamic_settle_frames"])
        bundle_json = engine.build_bundle(scene, mode, views, capture, layout.bundle_dir(engine.name, scene.name,
                                                                                         mode))
    except (NotWired, Unsupported) as e:
        rec.update(status="skipped", reason=e.reason, by_design=True, bundle_seconds=time.perf_counter() - t0)
        return rec
    except Exception as e:  # noqa: BLE001 - recorded as the failure reason
        tb = traceback.format_exc().rstrip().splitlines()
        rec.update(reason=f"bundle: {type(e).__name__}: {e}", log_tail=tb[-40:],
                   bundle_seconds=time.perf_counter() - t0)
        return rec
    rec["bundle_seconds"] = time.perf_counter() - t0
    rec["frames_requested"] = capture.get("timeline", {}).get("frames")
    cdir = rec["capture_dir"]
    if cdir.exists():
        shutil.rmtree(cdir, ignore_errors=True)  # stale captures must not hide a failure
    res = launch(engine, bundle_json, cdir, cfg["timeout"], echo=cfg.get("echo", False))
    rec.update(status=res.status, reason=res.reason or None, by_design=res.by_design, seconds=res.seconds,
               returncode=res.returncode, log_tail=list(res.log_tail) if res.status != "ok" else [])
    if res.ok:
        rec["receipt"] = _read_json(cdir / "receipt.json")
        if rec["receipt"] is None:
            rec["warnings"].append("runner wrote no receipt.json")
        frames = rec.get("frames_requested")
        if frames:
            missing = [f for f in frames if not layout.timeline_frame(engine.name, scene.name, mode, f).is_file()]
            if missing:
                rec["warnings"].append(f"{len(missing)} of {len(frames)} timeline frames missing "
                                       f"(first {missing[0]})")
    return rec


def _view_convergence(scene, view, receipt: dict | None) -> tuple[Any, list[str]]:
    if not receipt:
        return None, []
    conv = receipt.get("convergence") or {}
    if view.kind == "station":
        c = conv.get(view.id)
        applies = True
    else:
        c = conv.get(scene.timeline.station)
        if c is None and len(conv) == 1:
            c = next(iter(conv.values()))
        applies = view.capture_frame == scene.timeline.end_frame
    if not isinstance(c, dict):
        return c, []
    x = _f(c.get("last_rel_change"))
    if applies and x is not None and x > CONVERGENCE_WARN:
        n = c.get("settle_frames", c.get("frames"))
        return c, [f"not converged: last_rel_change {x:.3g} > {CONVERGENCE_WARN:g}"
                   + (f" after {n} frames" if n is not None else "")]
    return c, []


def _scene_entries(scene, engine, reason: str, status: str, by_design: bool, extra: dict | None = None) -> dict:
    from .metrics import result_entry

    e = result_entry(scene.name, None, engine, None, None, status=status, reason=reason, by_design=by_design)
    e["component"] = None
    e["warnings"] = []
    e.update(extra or {})
    return e


# ------------------------------------------------------------------------------------------------ per scene

def _sheet(layout: RunLayout, scene, view, ref: dict, masks: dict, columns: list) -> Path:
    """Direct block above isolated block, written to sheets/<scene>/<view>.png."""
    from . import png
    from .sheets import contact_sheet

    out = layout.sheet_png(scene.name, view.id)
    out.parent.mkdir(parents=True, exist_ok=True)
    full, direct = ref["full"], ref["direct"]
    dcols = [("reference", full, direct)]
    icols = [("reference", full, full - direct)]
    for label, kind, final, comp in columns:
        (dcols if kind == "direct" else icols).append((label, final, comp))
    mask = masks.get("all")
    parts = []
    for tag, cols, comp in (("direct", dcols, "direct"), ("isolated", icols, "isolated")):
        tmp = out.with_name(f"{out.stem}.{tag}.tmp.png")
        title = f"{scene.name} / {view.id}: {comp} component" + (
            " (final(mode) - final(direct), same engine)" if tag == "isolated" else "")
        contact_sheet(title, cols, tmp, component_label=comp, mask=mask)
        parts.append(png.load_png(tmp))
        tmp.unlink()
    return png.save_png(out, png.grid(parts, cols=1, pad=6))


def _process_scene(layout: RunLayout, path: Path, engines: list, avail: dict, cfg: dict, say) -> dict:
    """Run one scene; returns {"scene": Scene, "info", "results", "launches", "durations"}."""
    from renderers.base import Unsupported
    from .masks import roi_roles, view_masks
    from .metrics import load_reference_images, roi_mean, scene_leak_normalisers, view_metrics
    from .spec import expand_views, load_scene, views_summary

    dur = {"references_s": 0.0, "launch_s": 0.0, "metrics_s": 0.0, "sheets_s": 0.0}
    results: list[dict] = []
    scene = load_scene(path)
    views = expand_views(scene)
    layout.ensure(layout.views_json(scene.name).parent)
    _write_json(layout.views_json(scene.name), views_summary(scene, views))
    info = {"group": scene.group, "failure_mode": scene.failure_mode, "comparison": scene.comparison,
            "kind": "timeline" if scene.timeline is not None else "stations",
            "views": [{"id": v.id, "kind": v.kind, "station": v.station.name, "capture_frame": v.capture_frame,
                       "frames": list(v.frame_range) if v.frame_range else None} for v in views],
            "reference": {"status": "ok", "error": None, "warnings": []}, "leak_norm": None}
    say(f"{scene.name}: {len(views)} views ({info['kind']}, {scene.comparison})")

    # references
    t0 = time.perf_counter()
    ref_error = None
    try:
        ref_dirs, warns = ensure_scene_references(layout, scene, views, cfg["spp_scale"], cfg["cache_root"],
                                                  cfg["references"], say)
        info["reference"]["warnings"] = warns
    except Exception as e:  # noqa: BLE001 - the scene is reported as failed, the run goes on
        ref_error = f"reference: {type(e).__name__}: {e}"
        info["reference"].update(status="failed", error=ref_error)
        say(f"  FAIL {ref_error}")
        ref_dirs = {}
    dur["references_s"] = time.perf_counter() - t0

    roles = roi_roles(scene)
    refs, masks = {}, {}
    if ref_error is None:
        try:
            for v in views:
                masks[v.id] = view_masks(v, ref_dirs[v.id])
                refs[v.id] = load_reference_images(ref_dirs[v.id])
        except Exception as e:  # noqa: BLE001
            ref_error = f"reference unreadable: {type(e).__name__}: {e}"
            info["reference"].update(status="failed", error=ref_error)
    leak_norm = None
    if ref_error is None:
        ref_means = {v.id: {"direct": roi_mean(refs[v.id]["direct"], masks[v.id]["all"]),
                            "isolated": roi_mean(refs[v.id]["full"] - refs[v.id]["direct"], masks[v.id]["all"])}
                     for v in views}
        leak_norm = scene_leak_normalisers(ref_means)
        info["leak_norm"] = leak_norm
        info["ref_means"] = ref_means

    # engines: availability, capabilities, launches
    tasks = []
    for eng in engines:
        a = avail[eng.name]
        if a["status"] != "ok":
            results.append(_scene_entries(scene, eng.name, a["reason"], a["status"], a["status"] == "skipped"))
            continue
        try:
            eng.check_supports(scene)
        except Unsupported as e:
            results.append(_scene_entries(scene, eng.name, e.reason, "skipped", True, {"missing": e.missing}))
            say(f"  {eng.name}: skipped by design ({e.reason})")
            continue
        modes, note = ordered_modes(eng, cfg["modes"])
        if not modes:
            results.append(_scene_entries(
                scene, eng.name, f"none of the requested modes ({', '.join(cfg['modes'])}) exist in {eng.name} "
                f"(modes: {', '.join(eng.modes())})", "skipped", True))
            continue
        if note:
            say(f"  {eng.name}: {note}")
        if ref_error is not None:
            for m in modes:
                for v in views:
                    e = _entry_for(scene, v, eng, m, "failed", ref_error, False)
                    results.append(e)
            continue
        for m in modes:
            tasks.append((eng, m))

    t0 = time.perf_counter()

    def run_task(t):
        eng, m = t
        return _launch_mode(layout, eng, scene, views, m, eng.modes()[m], cfg, say)

    if cfg["jobs"] > 1 and len(tasks) > 1:
        with ThreadPoolExecutor(max_workers=int(cfg["jobs"])) as ex:
            launches = list(ex.map(run_task, tasks))
    else:
        launches = [run_task(t) for t in tasks]
    dur["launch_s"] = time.perf_counter() - t0
    by_key = {(r["engine"], r["mode"]): r for r in launches}

    # metrics
    t0 = time.perf_counter()
    columns: dict[str, list] = {v.id: [] for v in views}
    captures: dict[tuple, np.ndarray | None] = {}

    def load_capture(eng, mode, v):
        key = (eng.name, mode, v.id)
        if key not in captures:
            p = layout.view_capture(eng.name, scene.name, mode, v)
            try:
                captures[key] = _read_rgb(p) if p.is_file() else None
            except Exception:  # noqa: BLE001 - reported by the caller as unreadable
                captures[key] = None
        return captures[key]

    for eng, mode in tasks:
        L = by_key[(eng.name, mode)]
        minfo = eng.modes()[mode]
        dmode = eng.direct_mode()
        for v in views:
            cap = layout.view_capture(eng.name, scene.name, mode, v)
            files = {"capture": _rel(layout, cap),
                     "direct_capture": None if minfo.kind == "direct" else _rel(
                         layout, layout.view_capture(eng.name, scene.name, dmode, v)),
                     "sheet": _rel(layout, layout.sheet_png(scene.name, v.id))}
            conv, cwarn = _view_convergence(scene, v, L.get("receipt"))
            if L["status"] != "ok":
                e = _entry_for(scene, v, eng, mode, L["status"], L["reason"], L["by_design"], files, conv)
                if L["log_tail"]:
                    e["log_tail"] = L["log_tail"]
                    e["returncode"] = L["returncode"]
                results.append(e)
                columns[v.id].append((f"{eng.name}/{mode}", minfo.kind, None, None))
                continue
            final = load_capture(eng, mode, v)
            if final is None:
                why = "capture missing" if not cap.is_file() else "capture unreadable"
                e = _entry_for(scene, v, eng, mode, "failed", f"{why}: {files['capture']}", False, files, conv)
                results.append(e)
                columns[v.id].append((f"{eng.name}/{mode}", minfo.kind, None, None))
                continue
            direct_final = None
            dl = by_key.get((eng.name, dmode))
            if minfo.kind != "direct":
                if dl is None or dl["status"] != "ok":
                    if scene.comparison != "appearance":
                        st = "not run" if dl is None else f"{dl['status']}: {dl['reason']}"
                        e = _entry_for(scene, v, eng, mode, "failed", f"direct mode {dmode} {st}", False, files,
                                       conv)
                        results.append(e)
                        columns[v.id].append((f"{eng.name}/{mode}", minfo.kind, final, None))
                        continue
                else:
                    direct_final = load_capture(eng, dmode, v)
            e = view_metrics(scene=scene.name, view=v.id, engine=eng.name, mode=mode, kind=minfo.kind,
                             final=final, ref=refs[v.id], masks=masks[v.id], roles=roles,
                             direct_final=direct_final, comparison=scene.comparison, convergence=conv, files=files,
                             leak_norm=leak_norm)
            e["warnings"] = list(L["warnings"]) + cwarn
            for w in cwarn:
                say(f"  warning {eng.name}/{mode}/{v.id}: {w}")
            results.append(e)
            comp = final if minfo.kind == "direct" else (None if direct_final is None or direct_final.shape
                                                         != final.shape else final - direct_final)
            columns[v.id].append((f"{eng.name}/{mode}", minfo.kind, final, comp))
    dur["metrics_s"] = time.perf_counter() - t0

    # sheets
    t0 = time.perf_counter()
    if ref_error is None:
        for v in views:
            try:
                _sheet(layout, scene, v, refs[v.id], masks[v.id], columns[v.id])
            except Exception as e:  # noqa: BLE001 - a sheet must not fail the run
                info.setdefault("warnings", []).append(f"sheet {v.id}: {type(e).__name__}: {e}")
    dur["sheets_s"] = time.perf_counter() - t0

    launch_rows = [{"engine": r["engine"], "scene": r["scene"], "mode": r["mode"], "kind": r["kind"],
                    "status": r["status"], "reason": r["reason"], "seconds": round(r["seconds"], 4),
                    "bundle_seconds": round(r["bundle_seconds"], 4), "returncode": r["returncode"],
                    # the receipt's device, so the report can name each engine's adapter (DESIGN §4.3)
                    "device": {k: v for k, v in ((r.get("receipt") or {}).get("device") or {}).items()
                               if k in ("adapter", "backend", "adapter_type", "vendor", "driver", "browser",
                                        "software_rendering")} or None}
                   for r in launches]
    return {"scene": scene, "info": info, "results": results, "launches": launch_rows, "durations": dur}


def _entry_for(scene, v, eng, mode, status, reason, by_design, files=None, conv=None) -> dict:
    from .metrics import result_entry

    kind = eng.modes()[mode].kind
    e = result_entry(scene.name, v.id, eng.name, mode, kind, status=status, reason=reason, by_design=by_design,
                     convergence=conv, files=files)
    e["warnings"] = []
    return e


# ------------------------------------------------------------------------------------------------ driver

def _engine_block(eng, avail: dict) -> dict:
    try:
        version = eng.version()
    except Exception as e:  # noqa: BLE001
        version = f"unknown ({type(e).__name__}: {e})"
    try:
        modes = {m: {"kind": i.kind, "dynamic": bool(i.dynamic), "counterpart": i.counterpart,
                     "description": i.description} for m, i in eng.modes().items()}
    except Exception:  # noqa: BLE001
        modes = {}
    try:
        caps = sorted(eng.capabilities())
    except Exception:  # noqa: BLE001
        caps = []
    try:
        limits = list(eng.known_limits()) if hasattr(eng, "known_limits") else []
    except Exception:  # noqa: BLE001
        limits = []
    return {"status": avail["status"], "reason": avail["reason"], "modes": modes, "version": version,
            "capabilities": caps, "known_limits": limits}


def _merge_metrics(old: dict | None, new: dict, redone: set) -> dict:
    if not old or old.get("metrics_version") != METRICS_VERSION:
        return new
    kept = [r for r in old.get("results", []) if (r.get("scene"), r.get("engine")) not in redone]
    engines = dict(old.get("engines", {}))
    engines.update(new["engines"])
    scenes = dict(old.get("scenes", {}))
    scenes.update(new["scenes"])
    out = dict(new)
    out.update(engines=engines, scenes=scenes, results=kept + new["results"])
    return out


def run_pairs(run_dir, engines: Sequence | str | None = None, scenes: str | Sequence[str] = "all",
              modes: Sequence[str] | str | None = None, spp_scale: float = 1.0, settle_frames: int = SETTLE_STATIC,
              dynamic_settle_frames: int = SETTLE_DYNAMIC, timeout: float = DEFAULT_TIMEOUT, jobs: int = 1,
              scenes_root=None, cache_root=None, references: str = "ensure", fresh: bool = False,
              gates: bool = True, echo: bool = False, log: Callable[[str], None] | None = print) -> dict:
    """Run the comparison (see the module docstring); returns the metrics.json document (plus 'gates_path')."""
    from renderers.base import NotWired, git_sha
    from .spec import discover_scenes

    say = log or (lambda _m: None)

    def say_locked(m):
        with _lock:
            say(m)

    started = utc_now()
    t_all = time.perf_counter()
    layout = RunLayout(run_dir)
    layout.ensure(layout.root)
    if isinstance(modes, str):
        modes = [m.strip() for m in modes.split(",") if m.strip()]
    if references not in ("ensure", "existing"):
        raise ValueError("references must be 'ensure' or 'existing'")
    engs = resolve_engines(engines)
    cfg = {"engines": [e.name for e in engs], "scenes": scenes if isinstance(scenes, str) else list(scenes),
           "modes": list(modes) if modes else None, "spp_scale": float(spp_scale),
           "settle_frames": int(settle_frames), "dynamic_settle_frames": int(dynamic_settle_frames),
           "timeout": float(timeout), "jobs": max(1, int(jobs)), "scenes_root": None if scenes_root is None else
           str(scenes_root), "cache_root": None if cache_root is None else str(cache_root),
           "references": references, "fresh": bool(fresh), "echo": bool(echo)}

    avail: dict[str, dict] = {}
    for eng in engs:
        try:
            eng.check_available()
            avail[eng.name] = {"status": "ok", "reason": None}
        except NotWired as e:
            avail[eng.name] = {"status": "skipped", "reason": e.reason}
            say(f"{eng.name}: not available (by design): {e.reason}")
        except Exception as e:  # noqa: BLE001 - an availability probe that crashes is a real failure
            avail[eng.name] = {"status": "failed", "reason": f"check_available: {type(e).__name__}: {e}"}
            say(f"{eng.name}: FAIL {avail[eng.name]['reason']}")

    files = discover_scenes(scenes, scenes_root)
    doc = {"metrics_version": METRICS_VERSION, "run": layout.run_id, "created_utc": started, "git": git_sha(),
           "engines": {e.name: _engine_block(e, avail[e.name]) for e in engs}, "scenes": {}, "results": [],
           "durations": {}}
    old = None if fresh else _read_json(layout.metrics_json)
    redone: set = set()
    launches: list[dict] = []
    durations = {"references_s": 0.0, "launch_s": 0.0, "metrics_s": 0.0, "sheets_s": 0.0, "gates_s": 0.0}
    for path in files:
        try:
            r = _process_scene(layout, Path(path), engs, avail, cfg, say_locked)
        except Exception as e:  # noqa: BLE001 - a broken scene must not end the run
            name = Path(path).stem
            say(f"{name}: FAIL {type(e).__name__}: {e}")
            doc["scenes"][name] = {"error": f"{type(e).__name__}: {e}"}
            for eng in engs:
                redone.add((name, eng.name))
                doc["results"].append({"scene": name, "view": None, "engine": eng.name, "mode": None, "kind": None,
                                       "status": "failed", "reason": f"scene: {type(e).__name__}: {e}",
                                       "by_design": False, "component": None, "rois": {}, "energy": None,
                                       "bleed": {}, "flip": None, "convergence": None,
                                       "files": {"capture": None, "direct_capture": None, "sheet": None},
                                       "warnings": []})
            continue
        scene = r["scene"]
        doc["scenes"][scene.name] = r["info"]
        doc["results"] += r["results"]
        launches += r["launches"]
        for eng in engs:
            redone.add((scene.name, eng.name))
        for k, v in r["durations"].items():
            durations[k] += v
        doc["durations"] = {k: round(v, 4) for k, v in durations.items()}
        _write_json(layout.metrics_json, _merge_metrics(old, doc, redone))  # progress survives a crash

    doc["durations"] = {k: round(v, 4) for k, v in durations.items()}
    merged = _merge_metrics(old, doc, redone)
    _write_json(layout.metrics_json, merged)

    gates_path = None
    if gates:
        t0 = time.perf_counter()
        try:
            from .gates import write_gates

            gates_path, gdoc = write_gates(layout.root, scenes="all", scenes_root=scenes_root)
            for subj, s in gdoc.get("summary", {}).items():
                say(f"gates {subj}: {s['passed']} passed, {s['failed']} failed, {s['not_applicable']} n/a, "
                    f"{s.get('skipped', 0)} skipped by design")
        except Exception as e:  # noqa: BLE001 - recorded; metrics.json is already written
            merged.setdefault("warnings", []).append(f"gates: {type(e).__name__}: {e}")
            say(f"gates: FAIL {type(e).__name__}: {e}")
        durations["gates_s"] = time.perf_counter() - t0
    durations["total_s"] = time.perf_counter() - t_all
    merged["durations"] = {k: round(v, 4) for k, v in durations.items()}
    _write_json(layout.metrics_json, merged)

    finished = utc_now()
    keys = {(r["engine"], r["scene"]) for r in launches} | redone

    def mutate(d):
        d["launches"] = [x for x in d.get("launches", []) if (x.get("engine"), x.get("scene")) not in keys] + launches
        d["engines"] = sorted(set(d.get("engines", [])) | {e.name for e in engs})
        d["scenes"] = sorted(set(d.get("scenes", [])) | set(doc["scenes"]))
        d.setdefault("started_utc", started)

    update_run_json(layout.root, {"git": doc["git"], "host": host_info(), "config": {"pairs": cfg},
                                  "durations": {"pairs": {"started_utc": started, "finished_utc": finished,
                                                          **merged["durations"]}}}, mutate)
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for r in doc["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    say(f"pairs: {counts['ok']} ok, {counts['skipped']} skipped, {counts['failed']} failed results; "
        f"{len(launches)} launches in {durations['total_s']:.1f} s; wrote {layout.metrics_json}")
    merged["gates_path"] = None if gates_path is None else str(gates_path)
    merged["counts"] = counts
    return merged


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.pairs", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="run directory (runs/<id>); created if missing")
    ap.add_argument("--engines", default=",".join(DEFAULT_ENGINES),
                    help=f"comma list (default {','.join(DEFAULT_ENGINES)}; threejs-web only when asked)")
    ap.add_argument("--scenes", default="all", help="all | group | name | comma list (default all)")
    ap.add_argument("--modes", default=None, help="comma list of modes (default: every mode of each engine)")
    ap.add_argument("--spp-scale", type=float, default=1.0, help="reference spp multiplier (e.g. 0.25)")
    ap.add_argument("--settle-frames", type=int, default=SETTLE_STATIC, help="station frames, non-dynamic modes")
    ap.add_argument("--dynamic-settle-frames", type=int, default=SETTLE_DYNAMIC, help="station frames, dynamic modes")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per runner launch")
    ap.add_argument("--jobs", type=int, default=1, help="parallel launches per scene (1 keeps timings clean)")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--cache", default=None, help="reference cache root (default <repo>/cache)")
    ap.add_argument("--skip-references", action="store_true",
                    help="never render references: use the run's copies or complete cache entries")
    ap.add_argument("--fresh", action="store_true", help="do not merge with an existing metrics.json")
    ap.add_argument("--no-gates", action="store_true", help="do not write gates.json")
    ap.add_argument("--echo", action="store_true", help="echo runner output")
    args = ap.parse_args(argv)
    try:
        doc = run_pairs(args.run, engines=args.engines, scenes=args.scenes, modes=args.modes,
                        spp_scale=args.spp_scale, settle_frames=args.settle_frames,
                        dynamic_settle_frames=args.dynamic_settle_frames, timeout=args.timeout, jobs=args.jobs,
                        scenes_root=args.scenes_root, cache_root=args.cache,
                        references="existing" if args.skip_references else "ensure", fresh=args.fresh,
                        gates=not args.no_gates, echo=args.echo)
    except ValueError as e:
        print(f"FAIL {e}")
        return 2
    except Exception as e:  # noqa: BLE001 - e.g. SpecError for a bad --scenes selector
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    return 1 if doc["counts"].get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
