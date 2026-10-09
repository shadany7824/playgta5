"""Cost measurement (DESIGN §7 "Cost", §5.4 performance gate, §9 perf.json).

    python -m tools.perf --run <dir> [--phase0] [--engines e1,e2] [--modes m1,m2] [--scenes s1,s2] [--rounds 5]
        [--frames 120] [--warmup 30] [--adapter X] [--power high-performance|low-power] [--views FILE]
        [--timeout S] [--scenes-root DIR] [--fresh] [--echo] [--strict]

A *configuration* is (engine, scene, mode) on one station view: the view the views file (``--views``, default
``scenes/phase0_parity.json``) lists for the scene, else the scene's first station. One *measurement* is one runner
launch of the configuration's bundle with timing on: ``settle_frames = warmup + frames``, ``measure.warmup_frames =
warmup``, captures only at the end (the runners read back only the last frames of a view). A timeline scene runs its
timeline from frame 0 to ``warmup + frames - 1`` and writes only that last frame.

Rounds are interleaved round-robin over all configurations: round 1 launches every configuration once (ordered by
scene, mode, engine, i.e. A, B, A, B, ... for the two engines of ``--phase0``), then round 2, and so on, so slow drift
of the machine (clocks, thermals, background load) spreads over every configuration instead of biasing one. Bundles
are built once per configuration (``RunLayout.perf_bundle_dir``); every launch writes its own
``RunLayout.perf_capture_dir(..., round)`` under ``perf/`` (``phase0/perf/`` with ``--phase0``), never into the
measurement captures.

Per configuration, from the timing.json of every successful round:

- ``gpu_ms`` and ``cpu_ms``: ``p50`` and ``p95`` (numpy linear interpolation) over the non-warmup frames pooled
  across rounds, ``mean``, ``n`` frames, and the per-round p50s with their spread (``round_p50``,
  ``round_p50_spread`` = max - min, ``round_p50_rel_spread`` = spread / median of the round p50s). GPU values are the
  frames' ``gpu_ms`` (the runner's total over its passes); frames without one are counted in ``gpu_missing_frames``,
  and ``gpu_timestamps`` is false when no measured frame has one. ``passes`` holds p50/p95 per pass name, for
  information only: the runners split a frame differently (web: ``main`` and ``probe``, shadows rendered inside
  them; native: ``shadow``, ``probe``, ``main``, ``resolve``), so only totals are compared.
- ``memory`` (the last round's; ``peak_rss_bytes`` = max over rounds) and ``precompute`` (the last round's;
  ``seconds`` = median over rounds) from timing.json, ``device`` from receipt.json, ``adapter`` = its adapter name.

``representative`` is false, with the reason, when a measured configuration ran on a software rasterizer
(``tools.parity.software_reason``: SwiftShader, llvmpipe, lavapipe, WARP, adapter_type CPU) or nothing was measured.

``--phase0`` compares ``threejs-web`` (baseline) with ``threejs-native`` for modes direct and probe on the views
file's scenes (default thin_wall, opening and courtyard_simplified; ``--scenes all`` = every scene of the file) and
computes the DESIGN §5.4 gate per (scene, mode): native GPU p50 <= web GPU p50 and native GPU p95 <= web GPU p95
(``gpu_ms`` totals). A pair is ``not_measurable`` (with the reason) when a side has no GPU timestamps and
``incomplete`` when a side was not measured. The gate fails when any pair fails; otherwise it is ``not_measurable``
or ``incomplete`` when any pair is, else it passes. CPU ms are reported next to it. Without ``--phase0`` the default
is every mode of threejs-native on thin_wall, opening and courtyard_simplified.

Writes ``perf.json`` (DESIGN §9; merged with an existing one: entries of configurations not measured now are kept,
``--fresh`` drops them; ``phase0_gate`` is replaced only by a ``--phase0`` run) and, with ``--phase0``,
``phase0/perf.json`` (this run only). ``run.json`` gets the perf config and durations (keys ``perf``, or
``perf_phase0`` for a ``--phase0`` run, so both runs of one run directory are recorded). Exit code 0 when every launch
succeeded, whatever the gate (``--strict``: also 1 when the phase0 gate did not pass); 1 when a launch failed;
2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .layout import RunLayout
from .pairs import _read_json, _rel, _write_json, resolve_engines
from .parity import device_summary, load_views_file
from .runjson import host_info, update_run_json, utc_now

__all__ = ["DEFAULT_ENGINES", "DEFAULT_FRAMES", "DEFAULT_ROUNDS", "DEFAULT_SCENES", "DEFAULT_TIMEOUT",
           "DEFAULT_WARMUP", "PERF_VERSION", "PHASE0_ENGINES", "PHASE0_MODES", "frame_values", "main",
           "memory_block", "merge_perf", "percentile", "perf_capture_request", "phase0_gate", "precompute_block",
           "representativeness", "run_perf", "stat_block", "summarize_rounds"]

PERF_VERSION = 1
DEFAULT_SCENES = ("thin_wall", "opening", "courtyard_simplified")
DEFAULT_ENGINES = ("threejs-native",)
PHASE0_ENGINES = ("threejs-web", "threejs-native")  # (baseline, system)
PHASE0_MODES = ("direct", "probe")
DEFAULT_ROUNDS, DEFAULT_FRAMES, DEFAULT_WARMUP = 5, 120, 30
DEFAULT_TIMEOUT = 3600.0
GATE_CRITERION = ("per (scene, mode): native gpu_ms p50 <= web gpu_ms p50 and native gpu_ms p95 <= web gpu_ms p95 "
                  "(totals per frame over the non-warmup frames of every round)")


# ------------------------------------------------------------------------------------------------ statistics

def _num(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if np.isfinite(x) else None


def percentile(values, q: float) -> float | None:
    """q-th percentile with numpy's default linear interpolation; None for no values."""
    v = np.asarray([x for x in values], dtype=np.float64)
    return float(np.percentile(v, q)) if v.size else None


def frame_values(timing: Mapping, key: str) -> list[float]:
    """Finite ``key`` values ('gpu_ms', 'cpu_ms') of the non-warmup frames of one timing.json."""
    out = []
    for f in timing.get("frames") or []:
        if f.get("warmup"):
            continue
        x = _num(f.get(key))
        if x is not None:
            out.append(x)
    return out


def stat_block(per_round: Sequence[Sequence[float]]) -> dict:
    """p50/p95/mean/min/max over the pooled values plus the per-round p50s and their spread."""
    pooled = [x for r in per_round for x in r]
    rp50 = [percentile(r, 50) for r in per_round]
    ok = [x for x in rp50 if x is not None]
    spread = (max(ok) - min(ok)) if ok else None
    med = statistics.median(ok) if ok else None
    return {"p50": percentile(pooled, 50), "p95": percentile(pooled, 95),
            "mean": float(np.mean(pooled)) if pooled else None, "min": min(pooled) if pooled else None,
            "max": max(pooled) if pooled else None, "n": len(pooled), "round_p50": rp50,
            "round_p50_spread": spread,
            "round_p50_rel_spread": (spread / med) if spread is not None and med and med > 0 else None}


def summarize_rounds(timings: Sequence[Mapping]) -> dict:
    """GPU/CPU/pass statistics of one configuration from the timing.json documents of its rounds."""
    gpu = [frame_values(t, "gpu_ms") for t in timings]
    cpu = [frame_values(t, "cpu_ms") for t in timings]
    measured = [sum(1 for f in (t.get("frames") or []) if not f.get("warmup")) for t in timings]
    names: list[str] = []
    for t in timings:
        for f in t.get("frames") or []:
            for k in (f.get("passes") or {}):
                if k not in names:
                    names.append(k)
    passes = {}
    for k in names:
        per = [[x for f in (t.get("frames") or []) if not f.get("warmup")
                for x in [_num((f.get("passes") or {}).get(k))] if x is not None] for t in timings]
        pooled = [x for r in per for x in r]
        passes[k] = {"p50": percentile(pooled, 50), "p95": percentile(pooled, 95), "n": len(pooled)}
    has_gpu = any(gpu) and any(bool(t.get("gpu_timestamps")) for t in timings)
    g = stat_block(gpu if has_gpu else [[] for _ in timings])
    reason = None
    if not has_gpu:
        flags = [t.get("gpu_timestamps") for t in timings]
        reason = ("timing.json reports gpu_timestamps false" if timings and not any(flags)
                  else "no measured frame has gpu_ms")
    return {"gpu_ms": g, "cpu_ms": stat_block(cpu), "passes": passes, "gpu_timestamps": bool(has_gpu),
            "gpu_reason": reason, "frames_measured": sum(measured), "frames_per_round": measured,
            "gpu_missing_frames": sum(m - len(r) for m, r in zip(measured, gpu))}


def memory_block(timings: Sequence[Mapping]) -> dict | None:
    """The last round's numeric memory fields (and *_source notes), with peak RSS = max over rounds."""
    mems = [t["memory"] for t in timings if isinstance(t.get("memory"), Mapping)]
    if not mems:
        return None
    out = {k: v for k, v in mems[-1].items()
           if _num(v) is not None or v is None or (k.endswith("_source") and isinstance(v, str))}
    rss = [_num(m.get("peak_rss_bytes")) for m in mems]
    rss = [x for x in rss if x is not None]
    if rss:
        out["peak_rss_bytes"] = int(max(rss))
    return out


def precompute_block(timings: Sequence[Mapping]) -> dict | None:
    """The last round's precompute block with ``seconds`` = median over rounds (``seconds_rounds`` lists them)."""
    pres = [t["precompute"] for t in timings if isinstance(t.get("precompute"), Mapping)]
    if not pres:
        return None
    out = dict(pres[-1])
    secs = [_num(p.get("seconds")) for p in pres]
    secs = [x for x in secs if x is not None]
    if secs:
        out["seconds"] = float(statistics.median(secs))
        out["seconds_rounds"] = secs
    return out


def representativeness(entries: Sequence[Mapping]) -> tuple[bool, str | None]:
    """(representative, reason) over the measured entries: false on any software adapter or when nothing ran."""
    measured = [e for e in entries if e.get("status") == "ok"]
    if not measured:
        return False, "nothing was measured"
    seen, reasons = set(), []
    for e in measured:
        d = e.get("device") or {}
        if not d:
            why = f"{e['engine']}: no device recorded"
        elif d.get("software"):
            why = f"{e['engine']} runs on a software rasterizer: {d.get('adapter')} ({d.get('software_reason')})"
        else:
            continue
        if why not in seen:
            seen.add(why)
            reasons.append(why)
    return (not reasons), ("; ".join(reasons) or None)


# ------------------------------------------------------------------------------------------------ phase0 gate

def _side(e: Mapping | None) -> dict | None:
    if not e:
        return None
    g, c = e.get("gpu_ms") or {}, e.get("cpu_ms") or {}
    return {"status": e.get("status"), "adapter": e.get("adapter"), "rounds": e.get("rounds"),
            "gpu_timestamps": e.get("gpu_timestamps"), "gpu_ms": {"p50": g.get("p50"), "p95": g.get("p95"),
                                                                  "round_p50_spread": g.get("round_p50_spread")},
            "cpu_ms": {"p50": c.get("p50"), "p95": c.get("p95"), "round_p50_spread": c.get("round_p50_spread")}}


def _ratio(a, b) -> float | None:
    return (a / b) if a is not None and b else None


def phase0_gate(entries: Sequence[Mapping], baseline: str = "threejs-web", system: str = "threejs-native") -> dict:
    """DESIGN §5.4 performance gate over the (scene, mode) pairs measured for both engines (module docstring)."""
    keys: list[tuple[str, str]] = []
    by = {}
    for e in entries:
        if e.get("engine") in (baseline, system):
            k = (e["scene"], e["mode"])
            if k not in keys:
                keys.append(k)
            by[(e["engine"],) + k] = e
    pairs = []
    for scene, mode in keys:
        w, n = by.get((baseline, scene, mode)), by.get((system, scene, mode))
        p = {"scene": scene, "mode": mode, "view": (n or w or {}).get("view"), "baseline": _side(w),
             "system": _side(n), "passed": None, "status": "incomplete", "reason": None,
             "gpu_p50_ratio": None, "gpu_p95_ratio": None, "cpu_p50_ratio": None, "cpu_p95_ratio": None}
        missing = [f"{name} not measured" + (f" ({e.get('status')}: {e.get('reason')})" if e else "")
                   for name, e in ((baseline, w), (system, n)) if not e or e.get("status") != "ok"]
        if missing:
            p["reason"] = "; ".join(missing)
        else:
            no_gpu = [f"no GPU timestamps on {name} ({e.get('gpu_reason') or 'gpu_ms missing'}; adapter "
                      f"{e.get('adapter')})" for name, e in ((baseline, w), (system, n))
                      if not e.get("gpu_timestamps") or (e.get("gpu_ms") or {}).get("p50") is None]
            wg, ng = w["gpu_ms"], n["gpu_ms"]
            wc, nc = w["cpu_ms"], n["cpu_ms"]
            p.update(cpu_p50_ratio=_ratio(nc.get("p50"), wc.get("p50")),
                     cpu_p95_ratio=_ratio(nc.get("p95"), wc.get("p95")))
            if no_gpu:
                p.update(status="not_measurable", reason="; ".join(no_gpu))
            else:
                ok50, ok95 = ng["p50"] <= wg["p50"], ng["p95"] <= wg["p95"]
                p.update(passed=bool(ok50 and ok95), status="passed" if ok50 and ok95 else "failed",
                         gpu_p50_ratio=_ratio(ng["p50"], wg["p50"]), gpu_p95_ratio=_ratio(ng["p95"], wg["p95"]))
                if not (ok50 and ok95):
                    p["reason"] = ", ".join(
                        f"{system} GPU {q} {ng[q]:.3f} ms > {baseline} {wg[q]:.3f} ms"
                        for q, ok in (("p50", ok50), ("p95", ok95)) if not ok)
        pairs.append(p)
    st = [p["status"] for p in pairs]
    if not pairs:
        status, reason = "incomplete", f"no (scene, mode) measured for {baseline} and {system}"
    elif "failed" in st:
        status = "failed"
        reason = "; ".join(f"{p['scene']}/{p['mode']}: {p['reason']}" for p in pairs if p["status"] == "failed")
    elif "not_measurable" in st:
        status = "not_measurable"
        reason = "; ".join(dict.fromkeys(p["reason"] for p in pairs if p["status"] == "not_measurable"))
    elif "incomplete" in st:
        status = "incomplete"
        reason = "; ".join(f"{p['scene']}/{p['mode']}: {p['reason']}" for p in pairs if p["status"] == "incomplete")
    else:
        status, reason = "passed", None
    rep, rep_why = representativeness([e for e in entries if e.get("engine") in (baseline, system)])
    gate = {"criterion": GATE_CRITERION, "baseline": baseline, "system": system, "status": status,
            "passed": {"passed": True, "failed": False}.get(status), "reason": reason, "representative": rep,
            "representative_reason": rep_why, "pairs": pairs}
    if not rep:
        gate["note"] = "recorded, not representative: " + (rep_why or "")
    return gate


# ------------------------------------------------------------------------------------------------ configurations

def perf_capture_request(scene, view, warmup: int, frames: int) -> dict:
    """capture dict for Engine.build_bundle: one station view (or the timeline camera) for warmup + frames frames,
    timing on, captures only at the end."""
    n = int(warmup) + int(frames)
    measure = {"timing": True, "warmup_frames": int(warmup), "parity": False}
    if scene.timeline is None:
        return {"settle_frames": n, "measure": measure,
                "stations": [{"name": view.id, "camera": view.station.name, "settle_frames": n}]}
    return {"measure": measure, "timeline": {"camera": scene.timeline.station, "end_frame": n - 1, "frames": [n - 1]}}


@dataclass
class _Config:
    engine: Any
    scene: Any
    mode: str
    view: Any  # spec View (station) or None (timeline)
    status: str = "ok"  # becomes skipped/failed when it cannot be measured
    reason: str | None = None
    by_design: bool = False
    bundle_json: Path | None = None
    bundle_seconds: float = 0.0
    timings: list = field(default_factory=list)
    receipts: list = field(default_factory=list)
    launches: list = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str]:
        return self.engine.name, self.scene.name, self.mode

    @property
    def label(self) -> str:
        return f"{self.engine.name}/{self.scene.name}/{self.mode}"


def _scene_selection(phase0: bool, scenes, vf: dict | None, scenes_root) -> list[Path]:
    from .spec import discover_scenes

    file_scenes = list(dict.fromkeys(v["scene"] for v in vf["views"])) if vf else []
    if isinstance(scenes, str):
        scenes = [s.strip() for s in scenes.split(",") if s.strip()]
    if not scenes:
        if phase0:
            picked = [s for s in DEFAULT_SCENES if s in file_scenes] or file_scenes[:3]
        else:
            picked = list(DEFAULT_SCENES)
    elif phase0 and list(scenes) == ["all"]:
        picked = file_scenes
    else:
        picked = list(scenes)
    if not picked:
        raise ValueError("no scenes selected")
    return discover_scenes(picked, scenes_root)


def _pick_view(scene, preferred: Mapping[str, str]):
    """The station view to time: the views file's view for the scene, else the first station (None: timeline)."""
    from .spec import expand_views

    if scene.timeline is not None:
        return None
    views = {v.id: v for v in expand_views(scene)}
    want = preferred.get(scene.name)
    if want is not None and want not in views:
        raise ValueError(f"views file names view {want!r} of {scene.name}, which has views {', '.join(views)}")
    return views[want] if want is not None else next(iter(views.values()))


def _entry(c: _Config, cfg: dict) -> dict:
    """perf.json entry of one configuration (DESIGN §9 + details)."""
    ok_rounds = len(c.timings)
    view = None if c.view is None else c.view.id
    e = {"engine": c.engine.name, "mode": c.mode, "scene": c.scene.name, "view": view,
         "kind": "timeline" if c.view is None else "station", "adapter": None, "device": None,
         "status": c.status, "reason": c.reason, "by_design": c.by_design, "rounds": ok_rounds,
         "rounds_requested": cfg["rounds"], "frames": cfg["frames"], "warmup_frames": cfg["warmup"],
         "gpu_timestamps": None, "gpu_reason": None, "gpu_ms": None, "cpu_ms": None, "passes": None,
         "frames_measured": 0, "frames_per_round": [], "gpu_missing_frames": 0, "memory": None,
         "precompute": None, "settings": None, "representative": None, "representative_reason": None,
         "measured_utc": cfg["started_utc"], "phase0": cfg["phase0"], "requested": {
             "adapter": cfg["adapter"], "power": cfg["power"]},
         "launches": c.launches, "warnings": []}
    if c.status == "ok" and not ok_rounds:
        fails = [f"round {L['round']}: {L['status']}: {L['reason']}" for L in c.launches if L["status"] != "ok"]
        e.update(status="failed", reason="no round succeeded" + (f" ({'; '.join(fails)})" if fails else ""))
    if not ok_rounds:
        return e
    if ok_rounds < cfg["rounds"]:
        e["warnings"].append(f"{cfg['rounds'] - ok_rounds} of {cfg['rounds']} rounds failed")
    s = summarize_rounds(c.timings)
    dev = device_summary(c.receipts[0]) if c.receipts else None
    devs = {json.dumps(device_summary(r), sort_keys=True) for r in c.receipts}
    if len(devs) > 1:
        e["warnings"].append("the device differs between rounds")
    rec = c.receipts[0] if c.receipts else {}
    st = rec.get("settings") or {}
    meas = st.get("measurement") if isinstance(st.get("measurement"), Mapping) else {}
    e.update(adapter=(dev or {}).get("adapter"), device=dev, gpu_timestamps=s["gpu_timestamps"],
             gpu_reason=s["gpu_reason"], gpu_ms=s["gpu_ms"], cpu_ms=s["cpu_ms"], passes=s["passes"],
             frames_measured=s["frames_measured"], frames_per_round=s["frames_per_round"],
             gpu_missing_frames=s["gpu_missing_frames"], memory=memory_block(c.timings),
             precompute=precompute_block(c.timings),
             settings={"ssaa": st.get("ssaa", meas.get("ssaa")), "parity": rec.get("parity"),
                       "engine_version": rec.get("engine_version"), "image": cfg["images"].get(c.scene.name)},
             representative=not (dev or {}).get("software", True) if dev else False,
             representative_reason=(dev or {}).get("software_reason") if dev else "no device recorded")
    if e["representative"] is False and dev:
        e["representative_reason"] = f"software rasterizer: {dev.get('adapter')} ({dev.get('software_reason')})"
    if e["status"] == "ok" and ok_rounds < cfg["rounds"]:
        e["reason"] = e["warnings"][0]
    return e


def merge_perf(old: Mapping | None, new: dict) -> dict:
    """Keep the old document's entries for configurations (engine, scene, mode) not in ``new``; keep its
    phase0_gate unless ``new`` has one; recompute ``representative`` over every entry."""
    if not old or old.get("perf_version") != PERF_VERSION:
        return new
    keys = {(e["engine"], e["scene"], e["mode"]) for e in new["entries"]}
    kept = [e for e in old.get("entries", []) if (e.get("engine"), e.get("scene"), e.get("mode")) not in keys]
    out = dict(new)
    out["entries"] = kept + new["entries"]
    if out.get("phase0_gate") is None and old.get("phase0_gate") is not None:
        out["phase0_gate"] = old["phase0_gate"]
    out["representative"], out["reason"] = representativeness(out["entries"])
    if kept:
        out["kept_entries"] = len(kept)
    return out


# ------------------------------------------------------------------------------------------------ driver

def run_perf(run_dir, phase0: bool = False, engines: Sequence | str | None = None,
             modes: Sequence[str] | str | None = None, scenes: Sequence[str] | str | None = None,
             rounds: int = DEFAULT_ROUNDS, frames: int = DEFAULT_FRAMES, warmup: int = DEFAULT_WARMUP,
             adapter: str | None = None, power: str | None = None, views_file=None, timeout: float = DEFAULT_TIMEOUT,
             scenes_root=None, fresh: bool = False, echo: bool = False,
             log: Callable[[str], None] | None = print) -> dict:
    """Run the cost measurement (module docstring); returns the perf.json document (plus "path", "phase0_path")."""
    from renderers.base import NotWired, Unsupported, git_sha, launch
    from .spec import load_scene

    say = log or (lambda _m: None)
    if int(rounds) < 1 or int(frames) < 1 or int(warmup) < 0:
        raise ValueError("--rounds and --frames must be >= 1 and --warmup >= 0")
    started, t_all = utc_now(), time.perf_counter()
    layout = RunLayout(run_dir)
    layout.ensure(layout.root)
    if isinstance(modes, str):
        modes = [m.strip() for m in modes.split(",") if m.strip()]
    if modes is None and phase0:
        modes = list(PHASE0_MODES)
    engs = resolve_engines(list(PHASE0_ENGINES if phase0 else DEFAULT_ENGINES) if engines is None else engines)
    vf = None
    try:
        vf = load_views_file(views_file)
    except ValueError:
        if phase0 or views_file is not None:
            raise
    preferred: dict[str, str] = {}
    for v in (vf or {}).get("views", []):
        preferred.setdefault(v["scene"], v["view"])
    files = _scene_selection(phase0, scenes, vf, scenes_root)
    cfg = {"phase0": bool(phase0), "engines": [e.name for e in engs], "modes": list(modes) if modes else None,
           "scenes": [Path(f).stem for f in files], "rounds": int(rounds), "frames": int(frames),
           "warmup": int(warmup), "settle_frames": int(warmup) + int(frames), "adapter": adapter, "power": power,
           "views_file": (vf or {}).get("path"), "timeout": float(timeout),
           "scenes_root": None if scenes_root is None else str(scenes_root), "fresh": bool(fresh),
           "echo": bool(echo), "started_utc": started, "images": {},
           "order": "round-robin: for each round, every configuration once (scene, mode, engine order)"}
    extra = (["--adapter", adapter] if adapter else []) + (["--power", power] if power else [])

    avail: dict[str, dict] = {}
    for eng in engs:
        try:
            eng.check_available()
            avail[eng.name] = {"status": "ok", "reason": None}
        except NotWired as e:
            avail[eng.name] = {"status": "skipped", "reason": e.reason}
            say(f"{eng.name}: not available: {e.reason}")
        except Exception as e:  # noqa: BLE001
            avail[eng.name] = {"status": "failed", "reason": f"check_available: {type(e).__name__}: {e}"}
            say(f"{eng.name}: FAIL {avail[eng.name]['reason']}")

    # configurations (scene, mode, engine order) and their bundles
    configs: list[_Config] = []
    scene_errors: list[dict] = []
    for path in files:
        try:
            scene = load_scene(path)
            view = _pick_view(scene, preferred)
        except Exception as e:  # noqa: BLE001 - a bad scene must not end the run
            say(f"{Path(path).stem}: FAIL {type(e).__name__}: {e}")
            scene_errors.append({"scene": Path(path).stem, "reason": f"{type(e).__name__}: {e}"})
            continue
        cfg["images"][scene.name] = [int(scene.width), int(scene.height)]
        per_engine = {e.name: ([m for m in e.modes() if m in modes] if modes else list(e.modes())) for e in engs}
        order = list(modes) if modes else list(dict.fromkeys(m for e in engs for m in e.modes()))
        for mode in order:
            for eng in engs:
                if mode not in per_engine[eng.name]:
                    if modes and avail[eng.name]["status"] == "ok":
                        configs.append(_Config(eng, scene, mode, view, "skipped", f"{eng.name} has no mode {mode!r} "
                                               f"(modes: {', '.join(eng.modes())})", True))
                    elif modes:
                        configs.append(_Config(eng, scene, mode, view, avail[eng.name]["status"],
                                               avail[eng.name]["reason"], avail[eng.name]["status"] == "skipped"))
                    continue
                c = _Config(eng, scene, mode, view)
                configs.append(c)
                if avail[eng.name]["status"] != "ok":
                    c.status, c.reason = avail[eng.name]["status"], avail[eng.name]["reason"]
                    c.by_design = c.status == "skipped"
                    continue
                t0 = time.perf_counter()
                try:
                    c.bundle_json = eng.build_bundle(scene, mode, [] if view is None else [view],
                                                     perf_capture_request(scene, view, warmup, frames),
                                                     layout.perf_bundle_dir(eng.name, scene.name, mode, phase0))
                except (NotWired, Unsupported) as e:
                    c.status, c.reason, c.by_design = "skipped", e.reason, True
                except Exception as e:  # noqa: BLE001
                    c.status, c.reason = "failed", f"bundle: {type(e).__name__}: {e}"
                    say(f"{c.label}: FAIL {c.reason}\n" + traceback.format_exc().rstrip())
                c.bundle_seconds = time.perf_counter() - t0
    ready = [c for c in configs if c.status == "ok"]
    say(f"perf: {len(ready)} configurations x {rounds} rounds, {warmup} warm-up + {frames} timed frames each"
        + (f"; not measured: {', '.join(c.label + ' (' + str(c.reason) + ')' for c in configs if c.status != 'ok')}"
           if len(ready) != len(configs) else ""))

    # interleaved rounds
    seq = 0
    for r in range(1, int(rounds) + 1):
        for c in ready:
            if c.status != "ok":  # by-design skip in an earlier round
                continue
            seq += 1
            cdir = layout.perf_capture_dir(c.engine.name, c.scene.name, c.mode, r, phase0)
            if cdir.exists():
                shutil.rmtree(cdir, ignore_errors=True)
            res = launch(c.engine, c.bundle_json, cdir, timeout, extra=extra, echo=echo)
            row = {"round": r, "sequence": seq, "status": res.status, "reason": res.reason or None,
                   "seconds": round(res.seconds, 4), "returncode": res.returncode,
                   "capture_dir": _rel(layout, cdir)}
            if res.ok:
                timing, receipt = _read_json(cdir / "timing.json"), _read_json(cdir / "receipt.json")
                if timing is None:
                    row.update(status="failed", reason="runner wrote no readable timing.json")
                else:
                    c.timings.append(timing)
                    if receipt is not None:
                        c.receipts.append(receipt)
                    g, cpu = frame_values(timing, "gpu_ms"), frame_values(timing, "cpu_ms")
                    row["gpu_ms_p50"], row["cpu_ms_p50"] = percentile(g, 50), percentile(cpu, 50)
            else:
                row["log_tail"] = list(res.log_tail)
                if res.by_design:  # the same skip every round
                    c.status, c.reason, c.by_design = "skipped", res.reason, True
            c.launches.append(row)
            say(f"  round {r} #{seq} {c.label}: {row['status']}"
                + (f" ({row['reason']})" if row["reason"] else "")
                + (f" gpu p50 {row['gpu_ms_p50']:.2f} ms" if row.get("gpu_ms_p50") is not None else "")
                + (f" cpu p50 {row['cpu_ms_p50']:.2f} ms" if row.get("cpu_ms_p50") is not None else "")
                + f" in {res.seconds:.1f} s")

    entries = [_entry(c, cfg) for c in configs]
    for e in entries:
        if e["status"] == "ok":
            g, cpu = e["gpu_ms"], e["cpu_ms"]
            say(f"{e['engine']}/{e['scene']}/{e['mode']}: gpu p50 {_f3(g['p50'])} p95 {_f3(g['p95'])} ms, "
                f"cpu p50 {_f3(cpu['p50'])} p95 {_f3(cpu['p95'])} ms over {e['rounds']} rounds "
                f"(round p50 spread {_f3(g['round_p50_spread'])} ms gpu)")
    representative, why = representativeness(entries)
    gate = phase0_gate(entries) if phase0 else None
    cfg.pop("images", None)
    engines_block = {}
    for eng in engs:
        try:
            version = eng.version()
        except Exception as e:  # noqa: BLE001
            version = f"unknown ({type(e).__name__}: {e})"
        engines_block[eng.name] = {**avail[eng.name], "version": version}
    doc = {"perf_version": PERF_VERSION, "run": layout.run_id, "created_utc": started, "git": git_sha(),
           "host": host_info(), "representative": representative, "reason": why, "config": cfg,
           "engines": engines_block,
           "statistics": "p50/p95 by numpy linear interpolation over the non-warmup frames of every round pooled; "
                         "round_p50 = per-round p50",
           "entries": entries, "scene_errors": scene_errors, "phase0_gate": gate,
           "durations": {"total_s": round(time.perf_counter() - t_all, 4), "launches": seq}}
    phase0_path = _write_json(layout.phase0_perf_json, doc) if phase0 else None
    merged = merge_perf(None if fresh else _read_json(layout.perf_json), doc)
    path = _write_json(layout.perf_json, merged)
    key = "perf_phase0" if phase0 else "perf"  # a cost run and a --phase0 run in one run.json keep both records
    update_run_json(layout.root, {"config": {key: cfg}, "durations": {key: {
        "started_utc": started, "finished_utc": utc_now(), **doc["durations"]}}})
    if gate is not None:
        say(f"phase0 performance gate: {gate['status']}" + (f" ({gate['reason']})" if gate["reason"] else ""))
        for p in gate["pairs"]:
            b, s = p["baseline"] or {}, p["system"] or {}
            say(f"  {p['scene']}/{p['mode']}: {p['status']}; gpu p50 web {_f3((b.get('gpu_ms') or {}).get('p50'))} "
                f"native {_f3((s.get('gpu_ms') or {}).get('p50'))}, p95 web {_f3((b.get('gpu_ms') or {}).get('p95'))} "
                f"native {_f3((s.get('gpu_ms') or {}).get('p95'))} ms")
    if not representative:
        say(f"NOT representative: {why}")
    say(f"wrote {path}" + (f" and {phase0_path}" if phase0_path else ""))
    merged = dict(merged)
    merged["path"] = str(path)
    merged["phase0_path"] = None if phase0_path is None else str(phase0_path)
    merged["this_run"] = doc
    return merged


def _f3(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.perf", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="run directory (runs/<id>); created if missing")
    ap.add_argument("--phase0", action="store_true", help="threejs-web vs threejs-native, direct + probe, and the "
                                                          "DESIGN §5.4 performance gate")
    ap.add_argument("--engines", default=None, help="comma list (default threejs-native; --phase0: threejs-web,"
                                                    "threejs-native)")
    ap.add_argument("--modes", default=None, help="comma list (default every mode; --phase0: direct,probe)")
    ap.add_argument("--scenes", default=None, help=f"comma list / group / all (default {','.join(DEFAULT_SCENES)}; "
                                                   "--phase0: those of the views file, 'all' = every one)")
    ap.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="interleaved rounds (launches per config)")
    ap.add_argument("--frames", type=int, default=DEFAULT_FRAMES, help="timed frames per launch")
    ap.add_argument("--warmup", type=int, default=DEFAULT_WARMUP, help="warm-up frames per launch (not timed)")
    ap.add_argument("--adapter", default=None, help="adapter substring passed to the runners")
    ap.add_argument("--power", default=None, choices=["high-performance", "low-power"], help="passed to the runners")
    ap.add_argument("--views", default=None, help="views file naming the view per scene (default "
                                                  "scenes/phase0_parity.json)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per runner launch")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--fresh", action="store_true", help="do not merge with an existing perf.json")
    ap.add_argument("--echo", action="store_true", help="echo runner output")
    ap.add_argument("--strict", action="store_true", help="also exit 1 when the phase0 gate did not pass")
    args = ap.parse_args(argv)
    try:
        doc = run_perf(args.run, phase0=args.phase0, engines=args.engines, modes=args.modes, scenes=args.scenes,
                       rounds=args.rounds, frames=args.frames, warmup=args.warmup, adapter=args.adapter,
                       power=args.power, views_file=args.views, timeout=args.timeout, scenes_root=args.scenes_root,
                       fresh=args.fresh, echo=args.echo)
    except ValueError as e:
        print(f"FAIL {e}")
        return 2
    except Exception as e:  # noqa: BLE001 - e.g. SpecError for a bad --scenes selector
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    run = doc["this_run"]
    if run["scene_errors"] or any(e["status"] == "failed" for e in run["entries"]):
        return 1
    if args.strict and args.phase0 and (run["phase0_gate"] or {}).get("passed") is not True:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
