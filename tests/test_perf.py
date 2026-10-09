"""tools/perf.py: cost measurement and the Phase 0 performance gate (DESIGN §7 cost, §5.4, §9 perf.json).

Percentile maths on synthetic timing.json files, the gate's cases, merging, and the driver end to end on a stub engine
(tests/phase0_stub.py: known frame times, launch order logged) so the interleaving is checked without a GPU. The real
native runner runs once on a 64x48 view (marker native).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from tools import perf as F
from tools.layout import RunLayout
from tools.spec import expand_views

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("phase0_stub", HERE / "phase0_stub.py")
stub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stub)

FAST = {"ssaa": 4, "probe_cube_size": 32, "point_shadow_map": 256, "dir_shadow_map": 512}


def _timing(gpu, cpu, warm: int = 0, gpu_timestamps: bool = True, rss: int = 100, pre_s: float = 1.0) -> dict:
    """timing.json with ``warm`` warm-up frames (1000 ms, must be ignored) followed by the given frames."""
    frames = [{"frame": i, "station": "s", "warmup": True, "cpu_ms": 1000.0, "gpu_ms": 1000.0,
               "passes": {"main": 1000.0}} for i in range(warm)]
    frames += [{"frame": warm + i, "station": "s", "warmup": False, "cpu_ms": c, "gpu_ms": g,
                "passes": None if g is None else {"main": 0.75 * g, "shadow": 0.25 * g}}
               for i, (g, c) in enumerate(zip(gpu, cpu))]
    return {"timing_version": 1, "units": "ms", "gpu_timestamps": gpu_timestamps, "warmup_frames": warm,
            "frames": frames, "memory": {"gpu_texture_bytes": 64, "gpu_buffer_bytes": 8, "peak_rss_bytes": rss,
                                         "texture_items": [["t", 64]], "peak_rss_source": "test"},
            "precompute": {"seconds": pre_s, "bytes": 5, "items": {"programs": 2}}}


def _scenes_root(tmp_path: Path, data_dir: Path, names=("mini_point_plane", "mini_room", "mini_timeline")) -> Path:
    root = tmp_path / "scenes"
    for n in names:
        d = json.loads((data_dir / f"{n}.json").read_text(encoding="utf-8"))
        (root / d["group"]).mkdir(parents=True, exist_ok=True)
        shutil.copy(data_dir / f"{n}.json", root / d["group"] / f"{n}.json")
    if (data_dir / "meshes").is_dir():
        shutil.copytree(data_dir / "meshes", root / "meshes", dirs_exist_ok=True)
    return root


def _views_file(tmp_path: Path, views: list) -> Path:
    p = tmp_path / "views.json"
    p.write_text(json.dumps({"parity_version": 1, "views": views}), encoding="utf-8")
    return p


# ------------------------------------------------------------------------------------------------ statistics

def test_percentiles_pooled_over_rounds_from_synthetic_timing_files(tmp_path):
    """Two rounds written as timing.json files: gpu 1..10 and 11..20 ms (cpu = 2 x gpu) after 3 warm-up frames."""
    paths = []
    for r, gpu in enumerate((list(range(1, 11)), list(range(11, 21)))):
        p = tmp_path / f"round{r + 1}" / "timing.json"
        p.parent.mkdir()
        p.write_text(json.dumps(_timing([float(g) for g in gpu], [2.0 * g for g in gpu], warm=3, rss=100 * (r + 1),
                                        pre_s=1.0 + r)), encoding="utf-8")
        paths.append(p)
    timings = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    s = F.summarize_rounds(timings)
    g, c = s["gpu_ms"], s["cpu_ms"]
    assert s["gpu_timestamps"] is True and s["frames_measured"] == 20 and s["frames_per_round"] == [10, 10]
    assert g["n"] == 20 and g["p50"] == pytest.approx(10.5) and g["p95"] == pytest.approx(1 + 0.95 * 19)
    assert g["mean"] == pytest.approx(10.5) and (g["min"], g["max"]) == (1.0, 20.0)
    assert g["round_p50"] == pytest.approx([5.5, 15.5]) and g["round_p50_spread"] == pytest.approx(10.0)
    assert g["round_p50_rel_spread"] == pytest.approx(10.0 / 10.5)
    assert c["p50"] == pytest.approx(21.0) and c["p95"] == pytest.approx(2 * (1 + 0.95 * 19))
    assert s["passes"]["main"]["p50"] == pytest.approx(0.75 * 10.5) and s["passes"]["shadow"]["n"] == 20
    assert np.percentile(np.arange(1, 21), 95) == pytest.approx(g["p95"])  # numpy's linear interpolation
    assert s["gpu_missing_frames"] == 0
    mem, pre = F.memory_block(timings), F.precompute_block(timings)
    assert mem == {"gpu_texture_bytes": 64, "gpu_buffer_bytes": 8, "peak_rss_bytes": 200, "peak_rss_source": "test"}
    assert pre["seconds"] == pytest.approx(1.5) and pre["seconds_rounds"] == [1.0, 2.0] and pre["bytes"] == 5


def test_missing_gpu_timestamps():
    t = _timing([None] * 4, [1.0, 2.0, 3.0, 4.0], warm=1, gpu_timestamps=False)
    s = F.summarize_rounds([t])
    assert s["gpu_timestamps"] is False and s["gpu_ms"]["p50"] is None and s["gpu_ms"]["n"] == 0
    assert "gpu_timestamps false" in s["gpu_reason"] and s["cpu_ms"]["p50"] == pytest.approx(2.5)
    assert s["gpu_missing_frames"] == 4
    partial = F.summarize_rounds([_timing([None, 4.0, 6.0], [1.0, 1.0, 1.0])])
    assert partial["gpu_ms"]["p50"] == pytest.approx(5.0) and partial["gpu_missing_frames"] == 1
    assert F.frame_values({"frames": [{"warmup": False, "gpu_ms": float("nan")}, {"warmup": False, "gpu_ms": True},
                                      {"gpu_ms": 3}]}, "gpu_ms") == [3.0]
    assert F.percentile([], 50) is None and F.stat_block([[], []])["round_p50"] == [None, None]
    assert F.memory_block([{}]) is None and F.precompute_block([{}]) is None


def _entry(engine, scene, mode, gpu=(5.0, 6.0), cpu=(1.0, 2.0), status="ok", adapter="RTX", software=False,
           gpu_timestamps=True):
    return {"engine": engine, "scene": scene, "mode": mode, "view": "v", "status": status, "reason": None,
            "adapter": adapter, "rounds": 5, "gpu_timestamps": gpu_timestamps, "gpu_reason": None,
            "gpu_ms": {"p50": gpu[0], "p95": gpu[1], "round_p50_spread": 0.1} if gpu else {"p50": None, "p95": None},
            "cpu_ms": {"p50": cpu[0], "p95": cpu[1], "round_p50_spread": 0.1},
            "device": {"adapter": adapter, "software": software, "software_reason": "llvmpipe" if software else None}}


def test_phase0_gate_cases():
    W, N = "threejs-web", "threejs-native"
    ok = F.phase0_gate([_entry(W, "a", "direct", (10.0, 12.0)), _entry(N, "a", "direct", (10.0, 12.0)),
                        _entry(W, "a", "probe", (10.0, 12.0)), _entry(N, "a", "probe", (4.0, 5.0))])
    assert ok["status"] == "passed" and ok["passed"] is True and ok["representative"] is True and "note" not in ok
    p = ok["pairs"][1]
    assert (p["scene"], p["mode"], p["gpu_p50_ratio"], p["gpu_p95_ratio"]) == ("a", "probe", 0.4, 5.0 / 12.0)
    assert p["baseline"]["gpu_ms"]["p50"] == 10.0 and p["system"]["cpu_ms"]["p95"] == 2.0

    bad = F.phase0_gate([_entry(W, "a", "direct", (10.0, 12.0)), _entry(N, "a", "direct", (9.0, 12.5))])
    assert bad["status"] == "failed" and bad["passed"] is False and "p95 12.500 ms > threejs-web 12.000" in bad["reason"]
    assert "p50" not in bad["pairs"][0]["reason"]

    nm = F.phase0_gate([_entry(W, "a", "direct", None, gpu_timestamps=False), _entry(N, "a", "direct")])
    assert nm["status"] == "not_measurable" and nm["passed"] is None and "no GPU timestamps on threejs-web" in nm["reason"]
    assert nm["pairs"][0]["cpu_p50_ratio"] == 1.0

    inc = F.phase0_gate([_entry(W, "a", "direct"), _entry(N, "a", "direct", status="failed")])
    assert inc["status"] == "incomplete" and "threejs-native not measured (failed" in inc["reason"]
    assert F.phase0_gate([_entry(W, "a", "direct")])["pairs"][0]["status"] == "incomplete"
    assert F.phase0_gate([])["status"] == "incomplete"

    mixed = F.phase0_gate([_entry(W, "a", "direct", (1.0, 1.0)), _entry(N, "a", "direct", (2.0, 2.0)),
                           _entry(W, "b", "direct", None, gpu_timestamps=False), _entry(N, "b", "direct")])
    assert mixed["status"] == "failed"  # one failing pair fails the gate whatever the others are

    sw = F.phase0_gate([_entry(W, "a", "direct", software=True), _entry(N, "a", "direct", (1.0, 1.0))])
    assert sw["status"] == "passed" and sw["representative"] is False and "not representative" in sw["note"]


def test_representativeness_and_merge():
    W, N = "threejs-web", "threejs-native"
    assert F.representativeness([]) == (False, "nothing was measured")
    assert F.representativeness([_entry(N, "a", "direct")]) == (True, None)
    ok, why = F.representativeness([_entry(N, "a", "direct", software=True), _entry(N, "b", "direct", software=True)])
    assert ok is False and why.count("software rasterizer") == 1  # one reason per distinct device
    assert F.representativeness([_entry(N, "a", "direct", status="failed", software=True)])[0] is False

    old = {"perf_version": 1, "entries": [_entry(N, "a", "direct"), _entry(N, "b", "probe", software=True)],
           "phase0_gate": {"status": "passed"}}
    new = {"perf_version": 1, "entries": [_entry(N, "b", "probe")], "phase0_gate": None, "representative": True,
           "reason": None}
    m = F.merge_perf(old, new)
    assert [(e["scene"], e["mode"]) for e in m["entries"]] == [("a", "direct"), ("b", "probe")]
    assert m["entries"][1]["device"]["software"] is False and m["phase0_gate"] == {"status": "passed"}
    assert m["kept_entries"] == 1 and m["representative"] is True
    assert F.merge_perf(None, new) is new and F.merge_perf({"perf_version": 99}, new) is new


def test_perf_capture_request(tiny_scene):
    s = tiny_scene("mini_room")
    v = expand_views(s)[1]
    cap = F.perf_capture_request(s, v, warmup=30, frames=120)
    assert cap["stations"] == [{"name": v.id, "camera": v.station.name, "settle_frames": 150}]
    assert cap["measure"] == {"timing": True, "warmup_frames": 30, "parity": False}
    tl = F.perf_capture_request(tiny_scene("mini_timeline"), None, warmup=2, frames=3)
    assert tl["timeline"]["end_frame"] == 4 and tl["timeline"]["frames"] == [4]


def test_scene_selection(tmp_path):
    vf = {"views": [{"scene": s, "view": "x", "modes": ["direct"]} for s in
                    ("cal_point_plane", "thin_wall", "opening", "offscreen_source", "courtyard_simplified")]}
    stems = lambda files: [Path(f).stem for f in files]  # noqa: E731
    assert stems(F._scene_selection(False, None, vf, None)) == list(F.DEFAULT_SCENES)
    assert stems(F._scene_selection(True, None, vf, None)) == list(F.DEFAULT_SCENES)
    assert stems(F._scene_selection(True, "all", vf, None)) == [v["scene"] for v in vf["views"]]
    assert stems(F._scene_selection(True, "thin_wall", vf, None)) == ["thin_wall"]
    other = {"views": [{"scene": "cal_point_plane", "view": "s0", "modes": ["direct"]}]}
    assert stems(F._scene_selection(True, None, other, None)) == ["cal_point_plane"]


# ------------------------------------------------------------------------------------------------ driver (stub engine)

def test_run_perf_phase0_interleaves_rounds_on_stub_engines(tmp_path, data_dir):
    root = _scenes_root(tmp_path, data_dir)
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct"]},
                                {"scene": "mini_room", "view": "outside", "modes": ["direct"]}])
    layout = RunLayout(tmp_path / "run")
    sentinel = layout.station_capture("threejs-native", "mini_room", "direct", "outside")
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("measurement", encoding="utf-8")
    log = tmp_path / "launches.log"
    web = stub.make_engine("threejs-web", gpu_ms=10.0, log=log)
    nat = stub.make_engine("threejs-native", gpu_ms=5.0, adapter="llvmpipe (LLVM 20)", adapter_type="CPU", log=log)
    doc = F.run_perf(layout.root, phase0=True, engines=[web, nat], scenes="mini_point_plane,mini_room",
                     rounds=2, frames=4, warmup=2, views_file=vf, scenes_root=root, timeout=120, log=None)

    # interleaved: every configuration once per round, A, B, A, B within each (scene, mode)
    lines = [ln.split() for ln in log.read_text(encoding="utf-8").splitlines()]
    order = [(eng, Path(out).parts[-3], Path(out).parts[-2], Path(out).parts[-1]) for eng, out in lines]
    configs = [(e, s, m) for s in ("mini_point_plane", "mini_room") for m in ("direct", "probe")
               for e in ("threejs-web", "threejs-native")]
    assert order == [(e, s, m, f"round{r}") for r in (1, 2) for (e, s, m) in configs]
    assert sentinel.read_text(encoding="utf-8") == "measurement"
    for e, s, m in configs:
        b = json.loads((layout.perf_bundle_dir(e, s, m, phase0=True) / "bundle.json").read_text(encoding="utf-8"))
        assert b["capture"]["stations"][0]["settle_frames"] == 6 and b["measure"]["warmup_frames"] == 2
        assert b["capture"]["stations"][0]["name"] == {"mini_point_plane": "top", "mini_room": "outside"}[s]
        for r in (1, 2):
            assert (layout.perf_capture_dir(e, s, m, r, phase0=True) / "timing.json").is_file()

    run = doc["this_run"]
    assert len(run["entries"]) == 8 and all(e["status"] == "ok" and e["rounds"] == 2 for e in run["entries"])
    w = next(e for e in run["entries"] if e["engine"] == "threejs-web" and e["scene"] == "mini_room"
             and e["mode"] == "probe")
    # stub frames: gpu = base + 0.5 * (i % 4) for i = 2..5 -> base + {1.0, 1.5, 0.0, 0.5}; warm-up frames excluded
    assert w["gpu_ms"]["n"] == 8 and w["gpu_ms"]["p50"] == pytest.approx(10.75)
    assert w["gpu_ms"]["p95"] == pytest.approx(np.percentile([10, 10.5, 11, 11.5] * 2, 95))
    assert w["gpu_ms"]["round_p50"] == pytest.approx([10.75] * 2) and w["gpu_ms"]["round_p50_spread"] == 0.0
    assert w["cpu_ms"]["p50"] == pytest.approx(5.375) and w["memory"]["peak_rss_bytes"] == 12345
    assert w["precompute"]["seconds"] == 0.5 and w["adapter"] == "Stub GPU" and w["representative"] is True
    assert w["view"] == "outside" and [L["sequence"] for L in w["launches"]] == [7, 15]
    gate = run["phase0_gate"]
    assert gate["status"] == "passed" and len(gate["pairs"]) == 4
    assert all(p["gpu_p50_ratio"] == pytest.approx(5.75 / 10.75) for p in gate["pairs"])
    assert gate["representative"] is False and "llvmpipe" in gate["note"]
    assert doc["representative"] is False and "threejs-native runs on a software rasterizer" in doc["reason"]
    p0 = json.loads(layout.phase0_perf_json.read_text(encoding="utf-8"))
    pj = json.loads(layout.perf_json.read_text(encoding="utf-8"))
    assert p0["phase0_gate"]["status"] == "passed" and pj["perf_version"] == 1 and len(pj["entries"]) == 8
    for key in ("engine", "mode", "scene", "adapter", "rounds", "gpu_ms", "cpu_ms", "memory", "precompute"):
        assert key in pj["entries"][0]  # DESIGN §9

    # a later non-phase0 run measures native only: perf.json keeps the web entries and the phase0 gate
    doc2 = F.run_perf(layout.root, engines=[nat], modes="direct", scenes="mini_point_plane", rounds=1, frames=2,
                      warmup=1, views_file=vf, scenes_root=root, timeout=120, log=None)
    assert doc2["phase0_gate"]["status"] == "passed" and len(doc2["entries"]) == 8 and doc2["kept_entries"] == 7
    assert (layout.perf_capture_dir("threejs-native", "mini_point_plane", "direct", 1) / "timing.json").is_file()
    assert json.loads(layout.phase0_perf_json.read_text(encoding="utf-8"))["config"]["rounds"] == 2  # untouched


def test_run_perf_gate_not_measurable_skips_and_timeline(tmp_path, data_dir):
    root = _scenes_root(tmp_path, data_dir)
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct"]}])
    web = stub.make_engine("threejs-web", gpu_ms="none")
    nat = stub.make_engine("threejs-native")
    doc = F.run_perf(tmp_path / "run", phase0=True, engines=[web, nat], modes="direct", scenes="mini_point_plane",
                     rounds=1, frames=3, warmup=1, views_file=vf, scenes_root=root, timeout=120, log=None)
    gate = doc["phase0_gate"]
    assert gate["status"] == "not_measurable" and "no GPU timestamps on threejs-web" in gate["reason"]
    assert doc["representative"] is True  # stub adapters are 'DiscreteGPU'

    skip = stub.make_engine("threejs-native", skip="no adapter matches 'RTX'")
    gone = stub.make_engine("threejs-web", unavailable="no Chromium")
    doc = F.run_perf(tmp_path / "run2", phase0=True, engines=[gone, skip], scenes="mini_point_plane",
                     rounds=2, frames=2, warmup=0, views_file=vf, scenes_root=root, timeout=120, log=None)
    st = {(e["engine"], e["mode"]): (e["status"], e["reason"]) for e in doc["this_run"]["entries"]}
    assert st[("threejs-web", "direct")] == ("skipped", "no Chromium")
    assert st[("threejs-native", "probe")] == ("skipped", "no adapter matches 'RTX'")
    nat_entry = next(e for e in doc["this_run"]["entries"] if e["engine"] == "threejs-native")
    assert len(nat_entry["launches"]) == 1  # a by-design skip is not retried in later rounds
    assert doc["phase0_gate"]["status"] == "incomplete" and doc["representative"] is False

    tl = F.run_perf(tmp_path / "run3", engines=[nat], modes="probe", scenes="mini_timeline", rounds=1, frames=3,
                    warmup=2, views_file=vf, scenes_root=root, timeout=120, log=None)
    e = tl["this_run"]["entries"][0]
    assert e["status"] == "ok" and e["kind"] == "timeline" and e["view"] is None and e["gpu_ms"]["n"] == 3
    b = json.loads((RunLayout(tmp_path / "run3").perf_bundle_dir("threejs-native", "mini_timeline", "probe")
                    / "bundle.json").read_text(encoding="utf-8"))
    assert b["capture"]["timeline"] == {"camera": "s0", "end_frame": 4, "frames": [4]}


def test_cli_usage_errors(tmp_path):
    assert F.main(["--run", str(tmp_path / "r"), "--rounds", "0"]) == 2
    assert F.main(["--run", str(tmp_path / "r"), "--phase0", "--views", str(tmp_path / "missing.json")]) == 2


# ------------------------------------------------------------------------------------------------ real runner

@pytest.mark.native
def test_real_native_runner_two_rounds(tmp_path, data_dir):
    from renderers.base import NotWired
    from renderers.threejs import ThreeJsNative

    nat = ThreeJsNative(**FAST)
    try:
        nat.check_available()
    except NotWired as e:
        pytest.skip(f"threejs-native not available: {e.reason}")
    root = _scenes_root(tmp_path, data_dir, ("mini_point_plane",))
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct"]}])
    doc = F.run_perf(tmp_path / "run", engines=[nat], modes="direct", scenes="mini_point_plane", rounds=2,
                     frames=3, warmup=1, views_file=vf, scenes_root=root, timeout=300, log=None)
    for e in doc["this_run"]["entries"]:
        assert e["status"] == "ok", e["reason"]
        assert e["rounds"] == 2 and e["cpu_ms"]["n"] == 6 and e["cpu_ms"]["p50"] > 0
        assert e["memory"]["gpu_texture_bytes"] > 0 and e["device"]["backend"] == "Vulkan"
        if e["gpu_timestamps"]:
            assert e["gpu_ms"]["n"] == 6 and e["gpu_ms"]["p50"] > 0
            assert set(e["passes"]) == {"shadow", "probe", "main", "resolve"}
        assert e["representative"] is (not e["device"]["software"])
