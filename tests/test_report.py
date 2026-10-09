"""tools/report.py: report.md from synthetic run.json / metrics / gates / temporal / perf / phase0 JSON (DESIGN §9).

Checks the sections, that by-design skips are known limits and never failures, that appearance scenes show only
FLIP, the number formats, the noise-floor mark, and that missing or unreadable inputs are reported in one line.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools import report
from tools.layout import RunLayout
from tools.report import FLOOR_MARK, build_report, fmt_bytes, fmt_pct, fmt_sig, main, write_report

RECT_SKIP = "threejs-native lacks light:rect (by design)"
FUTURE = "future engine not wired: see docs/FUTURE_ADAPTER.md"
CRASH = "exit code 1: RuntimeError: boom in probe_dynamic"


def _roi(role, bias=None, noise=0.004, **kw):
    s = {"role": role, "pixels": kw.pop("pixels", 500), "bias": bias, "bias_rgb": None, "bias_abs": kw.pop("bias_abs", 0.01),
         "rel_l1": kw.pop("rel_l1", None), "rel_mse": kw.pop("rel_mse", None), "ref_mean": kw.pop("ref_mean", 1.0),
         "eng_mean": 1.1, "ref_noise_abs": kw.pop("ref_noise_abs", 0.004), "ref_noise_rel": noise}
    s.update(kw)
    return s


def _result(scene, view, mode, kind, status="ok", **kw):
    r = {"scene": scene, "view": view, "engine": kw.pop("engine", "threejs-native"), "mode": mode, "kind": kind,
         "status": status, "reason": kw.pop("reason", None), "by_design": kw.pop("by_design", False),
         "component": None if kind is None else ("direct" if kind == "direct" else "isolated"), "rois": {},
         "energy": None, "bleed": {}, "flip": None, "convergence": None,
         "files": {"capture": None, "direct_capture": None, "sheet": f"sheets/{scene}/{view}.png" if view else None},
         "warnings": kw.pop("warnings", [])}
    r.update(kw)
    return r


def _metrics() -> dict:
    lit = {"all": _roi("any", 0.1001, 0.0023, rel_l1=0.0992, rel_mse=0.0101),
           "lit_floor": _roi("lit", 0.0005, 0.004, rel_l1=0.0123, rel_mse=0.000234),  # inside 2 sigma -> marked
           "crate": _roi("bleed", -0.0321, 0.017, rel_l1=0.05, rel_mse=0.003),
           "dark_side": _roi("dark", None, None, leak_abs=0.0473, leak_rel=0.0437, ref_leak_abs=0.0, ref_leak_rel=0.0,
                             ref_noise_abs=0.0001, leak_noise_rel=0.0001)}
    results = [
        _result("thin_wall", "lit", "direct", "direct", rois={"all": _roi("any", -0.0042, 0.001, rel_l1=0.01,
                                                                          rel_mse=0.0002)},
                energy=-0.0042, flip={"mean": 0.0123, "rois": {"all": 0.0123}}),
        _result("thin_wall", "lit", "probe", "indirect", rois=lit, energy=0.1001,
                bleed={"crate": {"c_eng": [0.4, 0.3, 0.3], "c_ref": [0.38, 0.31, 0.31], "dist": 0.0245}},
                flip={"mean": 0.0680, "rois": {"all": 0.064}}, warnings=["not converged: last_rel_change 0.002"]),
        _result("thin_wall", "lit", "probe_dynamic", "indirect", status="failed", reason=CRASH),
        _result("thin_wall", None, None, None, status="skipped", reason=FUTURE, by_design=True, engine="future"),
        _result("cal_rect_plane", None, None, None, status="skipped", reason=RECT_SKIP, by_design=True),
        _result("courtyard_authored", "courtyard", "direct", "direct",
                flip={"mean": 0.0912, "rois": {"all": 0.09, "courtyard_ground": 0.11}}),
        _result("courtyard_authored", "courtyard", "probe", "indirect",
                flip={"mean": 0.0745, "rois": {"all": 0.07, "courtyard_ground": 0.08}}),
    ]
    modes = {"direct": {"kind": "direct", "dynamic": False, "counterpart": "MeshLambertMaterial; PCFShadowMap shadows",
                        "description": "Direct lighting only."},
             "probe": {"kind": "indirect", "dynamic": False, "counterpart": "LightProbe (SH9) from a CubeCamera",
                       "description": "Static global SH9 light probe."},
             "probe_dynamic": {"kind": "indirect", "dynamic": True, "counterpart": "probe re-captured every frame",
                               "description": "Per-frame SH9 probe feedback."}}
    return {"metrics_version": 1, "run": "r-test", "created_utc": "2026-10-09T10:00:00Z", "git": "abc1234",
            "engines": {"threejs-native": {"status": "ok", "reason": None, "modes": modes,
                                           "version": "three.js r186 port @ abc1234",
                                           "capabilities": ["light:point", "light:directional", "light:environment",
                                                            "shape:mesh", "timeline", "op:set_light",
                                                            "op:set_transform", "op:set_material"],
                                           "known_limits": ["Rect lights are not supported (by design).",
                                                            "HemisphereLight has no occlusion."]},
                        "future": {"status": "skipped", "reason": FUTURE, "modes": {}, "version": "not wired",
                                   "capabilities": [], "known_limits": []}},
            "scenes": {"thin_wall": {"group": "targeted", "failure_mode": "light leaking through a 5 cm wall",
                                     "comparison": "exact", "views": [{"id": "lit", "kind": "station"}],
                                     "leak_norm": {"direct": 0.29, "isolated": 1.08},
                                     "reference": {"status": "ok", "error": None, "warnings": []}},
                       "cal_rect_plane": {"group": "calibration", "comparison": "exact",
                                          "views": [{"id": "s0", "kind": "station"}]},
                       "courtyard_authored": {"group": "realworld", "comparison": "appearance",
                                              "views": [{"id": "courtyard", "kind": "station"}]}},
            "results": results, "durations": {"total_s": 12.5}}


def _gate(name, subject, scene, comp, passed, status=None, **kw):
    g = {"name": name, "subject": subject, "scene": scene, "view": kw.pop("view", "s0"), "component": comp,
         "values": kw.pop("values", {}), "tolerance": kw.pop("tolerance", {"bias": 0.01, "rel_l1": 0.02}),
         "passed": passed, "detail": kw.pop("detail", ""),
         "status": status or {True: "passed", False: "failed", None: "not_applicable"}[passed],
         "by_design": kw.pop("by_design", False), "reason": kw.pop("reason", None)}
    g.update(kw)
    return g


def _gates() -> dict:
    gates = [
        _gate("oracle", "reference", "cal_sun_plane", "full", True, roi="plane",
              values={"bias": 1e-5, "rel_l1": 2e-4, "pixels": 49152}, tolerance={"bias": 0.005, "rel_l1": 0.01}),
        _gate("ref_noise", "reference", "thin_wall", "isolated", True, view="lit", roi="lit_floor",
              values={"rel_se": 0.004}, tolerance=0.01),
        _gate("ref_noise", "reference", "thin_wall", "isolated", False, view="lit", roi="crate",
              values={"rel_se": 0.017}, tolerance=0.01, detail="rel. s.e. 1.700% > 1%"),
        _gate("oracle", "threejs-native", "cal_sun_plane", "direct", False, roi="plane",
              values={"bias": -0.0312, "rel_l1": 0.035, "pixels": 49152},
              detail="direct mode; |bias| 3.12% > 1.00%"),
        _gate("handedness", "threejs-native", "cal_handedness", "direct", True, tolerance={"px": 1.0,
                                                                                          "radiance_rel": 0.01},
              values={"quads": {"red": {"distance_px": 0.01, "radiance_rel_err": 0.0},
                                "green": {"distance_px": 0.2, "radiance_rel_err": 0.004}}}),
        _gate("oracle", "threejs-native", "cal_rect_plane", "direct", None, status="skipped", roi="plane",
              by_design=True, reason=RECT_SKIP, detail=RECT_SKIP),
        _gate("furnace_isolated", "threejs-native", "cal_furnace", "isolated", None, status="skipped",
              by_design=True, reason=RECT_SKIP, values={"mode": "probe"}, tolerance=None),
    ]
    return {"gates_version": 1, "run": "r-test", "tolerances": {"reference_oracle": {"bias": 0.005, "rel_l1": 0.01},
                                                                "engine_oracle": {"bias": 0.01, "rel_l1": 0.02},
                                                                "reference_noise_rel_se": 0.01},
            "engines": ["threejs-native"], "scenes": [], "gates": gates,
            "summary": {"reference": {"passed": 2, "failed": 1, "not_applicable": 0, "skipped": 0},
                        "threejs-native": {"passed": 1, "failed": 1, "not_applicable": 0, "skipped": 2}},
            "warnings": ["cal_survey_origin: equivalent scene 'cal_point_plane' not in the run"]}


def _temporal() -> dict:
    res = {"scene": "dyn_light_switch", "engine": "threejs-native", "mode": "probe_dynamic", "roi": "all",
           "role": "any", "fps": 60.0, "states": [],
           "steps": [{"frame": 120, "pre": 1.36, "post": 0.00376, "delta": -1.356, "timed": True, "t90_frames": 6,
                      "t90_s": 0.1, "afterglow": {"r": {"0.1": 0.107, "0.25": 0.0053, "0.5": 0.0021, "1.0": 0.0009},
                                                  "threshold": 0.05, "t05_frames": 9, "t05_s": 0.15,
                                                  "residual": 0.00304}},
                     {"frame": 240, "pre": 0.00376, "post": 1.36, "delta": 1.356, "timed": True, "t90_frames": None,
                      "t90_s": None, "afterglow": None},
                     {"frame": 300, "pre": 1.36, "post": 1.36, "delta": 0.0, "timed": False, "t90_frames": None,
                      "t90_s": None, "afterglow": None}],
           "flicker": [{"state": 0, "view": "state0", "temporal_cv": 0.0282, "f2f": 0.00144},
                       {"state": 1, "view": "state1", "temporal_cv": 0.513, "f2f": 0.322}],
           "series": [], "frames_missing": 0, "plot": "temporal/dyn_light_switch__threejs-native__probe_dynamic.png"}
    return {"temporal_version": 1, "results": [res],
            "skipped": [{"scene": "dyn_light_switch", "engine": "threejs-native", "mode": "probe", "status": "skipped",
                         "reason": "not dynamic (by design)", "by_design": True},
                        {"scene": "dyn_door", "engine": "threejs-native", "mode": "probe_dynamic",
                         "status": "failed", "reason": "FileNotFoundError: no timeline frames of x", "by_design": False}],
            "warnings": []}


def _perf_entry(engine, mode, scene, gpu, cpu, device, passes, **kw) -> dict:
    e = {"engine": engine, "mode": mode, "scene": scene, "view": kw.pop("view", "lit"), "kind": "station",
         "adapter": device["adapter"], "device": device, "status": kw.pop("status", "ok"), "reason": kw.pop("reason", None),
         "by_design": False, "rounds": 5, "rounds_requested": 5, "frames": 120, "warmup_frames": 30,
         "gpu_timestamps": True, "gpu_reason": None, "gpu_ms": {"p50": gpu[0], "p95": gpu[1]},
         "cpu_ms": {"p50": cpu[0], "p95": cpu[1]}, "passes": {k: {"p50": v, "p95": v, "n": 600} for k, v in passes.items()},
         "memory": kw.pop("memory", None), "precompute": kw.pop("precompute", None)}
    e.update(kw)
    return e


LLVMPIPE = {"adapter": "llvmpipe (LLVM 20.1.2, 256 bits)", "adapter_type": "CPU", "backend": "Vulkan", "software": True,
            "software_reason": "llvmpipe"}
SWIFTSHADER = {"adapter": "ANGLE (SwiftShader)", "adapter_type": "CPU", "backend": "WebGL2", "browser": "Chromium 141",
               "software": True, "software_reason": "SwiftShader"}


def _perf_entries() -> list[dict]:
    return [_perf_entry("threejs-native", "probe", "thin_wall", (61.234, 70.1), (21.0, 1234.5), LLVMPIPE,
                        {"shadow": 22.1, "probe": 10.0, "main": 27.0, "resolve": 3.0},
                        memory={"gpu_texture_bytes": 26279936, "gpu_buffer_bytes": 1852024, "peak_rss_bytes": 193028096},
                        precompute={"seconds": 0.775, "bytes": 131072}),
            _perf_entry("threejs-web", "probe", "thin_wall", (50.0, 65.0), (150.0, 210.0), SWIFTSHADER,
                        {"main": 40.0, "probe": 10.0}),
            _perf_entry("threejs-native", "direct", "opening", (None, None), (None, None), LLVMPIPE, {},
                        status="failed", reason="timeout after 3600 s", view="toward_door")]


def _perf() -> dict:
    return {"perf_version": 1, "representative": False, "reason": "software rasterizer (llvmpipe)",
            "entries": _perf_entries(), "scene_errors": [], "phase0_gate": None}


def _run() -> dict:
    return {"run_json_version": 1, "run": "r-test", "git": "abc1234+dirty", "started_utc": "2026-10-09T10:00:00Z",
            "finished_utc": "2026-10-09T10:30:00Z",
            "host": {"os": "Windows 11", "python": "3.12.4", "cpu": "AMD64", "cpus": 16, "node": "pc"},
            "config": {"run_all": {"scenes": "all", "engines": "threejs-native,future", "spp_scale": 1.0,
                                   "phase0": True, "perf": True}},
            "steps": [{"name": "spec", "status": "ok", "seconds": 1.2},
                      {"name": "pairs", "status": "failed", "reason": "exit code 1", "seconds": 1500.0},
                      {"name": "perf", "status": "skipped", "reason": "needs --perf", "seconds": 0.0}],
            "launches": [{"engine": "threejs-native", "scene": "thin_wall", "mode": "probe", "kind": "stations",
                          "status": "ok", "seconds": 12.5, "bundle_seconds": 0.1,
                          "device": {"adapter": "llvmpipe (LLVM 20.1.2, 256 bits)", "backend": "Vulkan",
                                     "adapter_type": "CPU"}}],
            "durations": {"run_all": {"spec": 1.2, "pairs": 1500.0},
                          "pairs": {"references_s": 900.0, "launch_s": 500.0, "total_s": 1500.0}}}


def _parity_entry(scene, view, mode, p999, mean, mx, gt1, **kw) -> dict:
    from tools.parity import gate_check

    stats = {"pixels": 49152, "max": mx, "mean": mean, "p99_9": p999, "pixels_gt1": gt1, "fraction_gt1": gt1 / 49152,
             "channels": {}}
    e = {"scene": scene, "view": view, "mode": mode, "kind": "station", "status": kw.pop("status", "ok"),
         "reason": kw.pop("reason", None), "by_design": False, "gate": gate_check(stats), "all": stats,
         "valid": {"pixels": 40000, "max": 1, "mean": None if mean is None else mean / 2, "p99_9": 1.0,
                   "pixels_gt1": 0},
         "linear": {"all": {"rel_l1": 1.3e-4, "bias": -1e-5, "max_abs": 0.01}, "valid": None},
         "files": {"sheet": f"phase0/sheets/{scene}__{view}__{mode}.png"}, "warnings": []}
    e.update(kw)
    return e


def _parity() -> dict:
    from tools.parity import CRITERION, gate_check, overall_gate

    entries = [_parity_entry("cal_point_plane", "s0", "direct", 1.0, 0.0101, 1, 0),
               _parity_entry("opening", "toward_door", "probe", 5.0, 0.0252, 161, 100),
               _parity_entry("thin_wall", "lit", "probe", None, None, None, 0, status="failed",
                             reason="threejs-web failed: exit code 1: page crashed")]
    entries[2].update(gate=gate_check(None), all=None, valid=None, linear=None)
    gate = overall_gate(entries)
    gate.update(representative=False, note="recorded, not representative: both sides are software rasterizers")
    return {"parity_version": 1, "criterion": CRITERION, "gate": gate, "representative": False,
            "reason": "threejs-native runs on a software rasterizer: llvmpipe", "devices":
            {"threejs-web": SWIFTSHADER, "threejs-native": LLVMPIPE}, "entries": entries}


def _phase0_perf() -> dict:
    from tools.perf import phase0_gate

    entries = _perf_entries()[:2]
    return {"perf_version": 1, "representative": False, "reason": "software rasterizers", "entries": entries,
            "phase0_gate": phase0_gate(entries)}


def _write(run: Path, docs: dict) -> None:
    for rel, doc in docs.items():
        p = run / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc, indent=1), encoding="utf-8")


@pytest.fixture
def full_run(tmp_path) -> Path:
    run = tmp_path / "runs" / "r-test"
    _write(run, {"run.json": _run(), "metrics.json": _metrics(), "gates.json": _gates(),
                 "temporal.json": _temporal(), "perf.json": _perf(), "phase0/parity.json": _parity(),
                 "phase0/perf.json": _phase0_perf()})
    return run


def _section(text: str, title: str) -> str:
    """Text of the '## title' section (up to the next '## ')."""
    m = re.search(rf"^## {re.escape(title)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"section {title!r} missing"
    return m.group(1)


def _subsection(text: str, title: str) -> str:
    m = re.search(rf"^### {re.escape(title)}.*?$(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
    assert m, f"subsection {title!r} missing"
    return m.group(1)


# ------------------------------------------------------------------------------------------------ formatting

def test_number_formats():
    assert fmt_sig(0.099) == "0.0990" and fmt_sig(1.0) == "1.00" and fmt_sig(12.34) == "12.3"
    assert fmt_sig(123.4) == "123" and fmt_sig(1234.5) == "1230" and fmt_sig(1.234e-5) == "1.23e-05"
    assert fmt_sig(0) == "0" and fmt_sig(None) == report.DASH and fmt_sig(float("nan")) == report.DASH
    assert fmt_sig(-0.0012345) == "-0.00123"
    assert fmt_pct(0.1) == "+10.0%" and fmt_pct(-0.00123) == "-0.123%" and fmt_pct(0) == "0%"
    assert fmt_pct(0.004, signed=False) == "0.400%" and fmt_pct(None) == report.DASH
    assert fmt_bytes(26279936) == "26.3 MB" and fmt_bytes(512) == "512 B"


# ------------------------------------------------------------------------------------------------ full report

def test_sections_and_header(full_run):
    path = write_report(full_run)
    assert path == RunLayout(full_run).report_md and path.is_file()
    text = path.read_text(encoding="utf-8")
    for title in ("Engines and modes", "Phase 0", "Calibration and reference gates", "Results per scene and view",
                  "Temporal", "Cost", "Failures", "Durations"):
        assert re.search(rf"^## {re.escape(title)}", text, re.M), title
    head = text.split("## Engines and modes")[0]
    assert "# Lighting comparison report: r-test" in head
    assert "`abc1234+dirty`" in head and "Python 3.12.4" in head and "16 CPUs" in head
    assert "| Device: threejs-native | llvmpipe (LLVM 20.1.2, 256 bits) (CPU, Vulkan, software rendering) |" in head
    assert "| Device: threejs-web | ANGLE (SwiftShader) (CPU, WebGL2, Chromium 141, software rendering) |" in head
    assert "Timings representative | no: software rasterizer (llvmpipe) (perf.json)" in head
    assert "2026-10-09T10:00:00Z to 2026-10-09T10:30:00Z" in head
    assert "Inputs not available" not in head  # every input present
    assert "score" not in text.lower()  # no blended score anywhere


def test_engines_modes_and_known_limits(full_run):
    text = _section(build_report(full_run), "Engines and modes")
    native = _subsection(text, "threejs-native")
    assert "| probe | indirect | no | LightProbe (SH9) from a CubeCamera | Static global SH9 light probe. |" in native
    assert "| probe_dynamic | indirect | yes |" in native
    assert f"By-design skips: cal_rect_plane: {RECT_SKIP}" in native
    assert "- Rect lights are not supported (by design)." in native and "- HemisphereLight has no occlusion." in native
    assert "light:rect" in text.split("### threejs-native")[0]  # capabilities lacking column
    future = _subsection(text, "future")
    assert f"Skipped on every scene (by design): {FUTURE}" in future


def test_by_design_skips_are_known_limits_not_failures(full_run):
    text = build_report(full_run)
    gates = _section(text, "Calibration and reference gates")
    limits = _subsection(gates, "Known limits: by-design skips (not failures)")
    assert RECT_SKIP in limits and "cal_rect_plane/s0" in limits and "cal_furnace/s0" in limits
    native = _subsection(gates, "threejs-native: 1 passed, 1 failed, 0 not applicable, 2 skipped by design")
    assert "cal_rect_plane" not in native  # by-design skips are not in the gate table
    assert "| oracle | cal_sun_plane / s0 | direct | plane | bias -3.12%, rel_l1 3.50%, 49152 px |" in native
    assert "FAIL" in native and "max offset 0.200 px, max radiance error 0.400%" in native
    failures = _section(text, "Failures")
    for by_design in (RECT_SKIP, FUTURE, "not dynamic", "needs --perf"):
        assert by_design not in failures, by_design
    # the real failures, each with its reason
    assert CRASH in failures and "threejs-native/probe_dynamic" in failures
    assert "gate oracle (threejs-native, direct)" in failures
    assert r"\|bias\| 3.12% > 1.00%" in failures  # '|' is escaped inside table cells
    assert "rel. s.e. 1.700% > 1%" in failures  # failed reference-noise gate
    assert "no timeline frames of x" in failures  # failed temporal entry
    assert "step pairs (failed)" in failures and "exit code 1" in failures  # failed run_all step
    assert "Phase 0 parity (run)" in failures and "page crashed" in failures  # a parity launch that failed
    assert "timeout after 3600 s" in failures  # a perf configuration that failed
    # gate verdicts on a machine that is not representative are recorded, not judged
    assert "Phase 0 parity gate" not in failures and "performance gate" not in failures


def test_scene_tables(full_run):
    text = _section(build_report(full_run), "Results per scene and view")
    tw = _subsection(text, "thin_wall")
    assert "Failure mode: light leaking through a 5 cm wall" in tw
    assert "Contact sheet: [sheets/thin_wall/lit.png](sheets/thin_wall/lit.png)" in tw
    header = next(ln for ln in tw.splitlines() if ln.startswith("| engine / mode"))
    assert "lit_floor (lit, 500 px): bias / rel_l1 / rel_mse" in header
    assert "dark_side (dark, 500 px): leak_abs / leak_rel (reference)" in header
    assert "crate (bleed, 500 px): bias / rel_l1 / rel_mse / bleed Δc" in header
    probe = next(ln for ln in tw.splitlines() if ln.startswith("| threejs-native / probe |"))
    cells = [c.strip() for c in probe.strip("|").split("|")]
    assert cells[1] == "isolated"
    assert cells[2] == "+10.0% / 0.0992 / 0.0101"  # 'all': far outside the noise -> unmarked
    assert cells[3] == f"+0.0500%{FLOOR_MARK} / 0.0123 / 2.34e-04"  # within 2 sigma of the reference noise
    assert cells[4] == f"-3.21%{FLOOR_MARK} / 0.0500 / 0.00300 / 0.0245"  # |bias| < 2 x 1.7 %; bleed adds |dc|
    assert cells[5] == "0.0473 / 4.37% (ref 0%)"  # dark ROI: leak, outside the floor
    assert cells[6] == "+10.0%" and cells[7] == "0.0680" and "not converged" in cells[8]
    noise = next(ln for ln in tw.splitlines() if ln.startswith("| reference noise (isolated) |"))
    assert "σ 0.230%" in noise and "leak_rel σ 0.0100%" in noise
    failed = next(ln for ln in tw.splitlines() if ln.startswith("| threejs-native / probe_dynamic |"))
    assert CRASH in failed
    assert "| future / all modes |" in tw and FUTURE in tw


def test_appearance_scene_shows_only_flip(full_run):
    text = _section(build_report(full_run), "Results per scene and view")
    ca = _subsection(text, "courtyard_authored")
    table = [ln for ln in ca.splitlines() if ln.startswith("|")]
    assert table[0] == "| engine / mode | FLIP mean | FLIP all | FLIP courtyard_ground | notes |"
    assert "| threejs-native / probe | 0.0745 | 0.0700 | 0.0800 |" in ca
    for word in ("bias", "rel_l1", "rel_mse", "leak", "energy", "component"):
        assert word not in ca, word


def test_temporal_cost_phase0_and_durations(full_run):
    text = build_report(full_run)
    t = _section(text, "Temporal")
    assert "[threejs-native / probe_dynamic](temporal/dyn_light_switch__threejs-native__probe_dynamic.png)" in t
    falling = next(ln for ln in t.splitlines() if "| 120 |" in ln)
    assert "0.100 s (6 frames)" in falling and "| 0.107 | 0.00530 | 0.00210 | 9.00e-04 | 0.150 s | 0.00304 |" in falling
    assert "not settled" in next(ln for ln in t.splitlines() if "| 240 |" in ln)
    assert "no change" in next(ln for ln in t.splitlines() if "| 300 |" in ln)
    assert "| threejs-native / probe_dynamic | all | 0.0282 / 0.00144 | 0.513 / 0.322 |" in t
    assert "Not measured (by design): threejs-native/probe: not dynamic (by design)" in t
    cost = _section(text, "Cost")
    assert "Representative machine: no (software rasterizer (llvmpipe))" in cost
    row = next(ln for ln in cost.splitlines() if ln.startswith("| threejs-native | probe |"))
    assert "| 5/5 | 61.2 | 70.1 | 21.0 | 1230 | shadow 22.1, probe 10.0, main 27.0, resolve 3.00 |" in row
    assert "26.3 MB textures + 1.85 MB buffers" in row and "193 MB" in row and "0.775 s, 131 kB" in row
    assert "failed: timeout after 3600 s" in cost
    assert "(threejs-native: main, probe, resolve, shadow; threejs-web: main, probe;" in cost
    assert "compare GPU totals, not passes" in cost
    p0 = _section(text, "Phase 0")
    line = next(ln for ln in p0.splitlines() if ln.startswith("| opening | toward_door | probe |"))
    assert "| 5 | 0.0252 | 161 | 100 | 1 / 0.0126 | 1.30e-04 | FAIL (not representative) |" in line
    assert "[sheet](phase0/sheets/cal_point_plane__s0__direct.png)" in p0
    assert "| thin_wall | lit | probe |" in p0 and "failed: threejs-web failed: exit code 1: page crashed" in p0
    assert "Parity gate: **FAIL** (1/3 entries passed; failed: opening/toward_door/probe; not compared:" in p0
    assert "| thin_wall | probe | lit | 50.0 / 65.0 | 61.2 / 70.1 | 1.22 / 1.08 | 150 / 21.0 | FAIL |" in p0
    assert "Performance gate: **FAIL** (" in p0 and "threejs-native GPU p50 61.234 ms > threejs-web 50.000 ms" in p0
    assert p0.count("Not representative") == 2  # parity and performance: recorded, not judged
    assert "Not representative: threejs-native runs on a software rasterizer: llvmpipe. The result" in p0
    assert "Not representative: threejs-native runs on a software rasterizer: llvmpipe (LLVM 20.1.2, 256 bits) " \
           "(llvmpipe); threejs-web runs on a software rasterizer" in p0
    d = _section(text, "Durations")
    assert "| run_all: pairs | failed | 25 min 00 s |" in d and "| pairs: references | – | 15 min 00 s |" in d
    assert "threejs-native: 1 launches" in d
    w = _section(text, "Warnings")
    assert "equivalent scene 'cal_point_plane' not in the run" in w and "not converged" in w


# ------------------------------------------------------------------------------------------------ missing inputs

def test_missing_files_each_say_so_in_one_line(tmp_path):
    run = tmp_path / "empty"
    run.mkdir()
    text = build_report(run)
    assert "Inputs not available: `run.json` missing; `metrics.json` missing; `gates.json` missing; " \
           "`temporal.json` missing; `perf.json` missing; `phase0/parity.json` missing; `phase0/perf.json` missing." \
           in text
    for title, line in (("Engines and modes", "_metrics.json missing: no engines recorded._"),
                        ("Calibration and reference gates", "_gates.json missing: no gates._"),
                        ("Results per scene and view", "_metrics.json missing: no per-scene results._"),
                        ("Temporal", "_temporal.json missing: no temporal results._"),
                        ("Durations", "_run.json missing: no durations._")):
        body = [ln for ln in _section(text, title).splitlines() if ln.strip() and not ln.startswith("_Generated")]
        assert body == [line], (title, body)
    assert "_phase0/parity.json and phase0/perf.json missing: Phase 0 was not run" in text
    assert "_perf.json missing: no cost measurements" in text
    assert "None." in _section(text, "Failures")


def test_partial_and_unreadable_inputs(full_run):
    (full_run / "perf.json").unlink()
    (full_run / "phase0" / "perf.json").unlink()
    (full_run / "temporal.json").write_text("{not json", encoding="utf-8")
    text = build_report(full_run)
    assert "`temporal.json` unreadable (JSONDecodeError" in text
    assert "_temporal.json unreadable (JSONDecodeError" in _section(text, "Temporal")
    assert "_perf.json missing: no cost measurements" in _section(text, "Cost")
    p0 = _section(text, "Phase 0")
    assert "| cal_point_plane | s0 | direct |" in p0  # parity still reported
    assert "_phase0/perf.json missing: no Phase 0 timings._" in p0 and "No performance gate recorded." in p0
    assert "Timings representative | no: threejs-native runs on a software rasterizer: llvmpipe " \
           "(phase0/parity.json)" in text
    # without perf or parity files the representativeness is inferred from the recorded devices
    (full_run / "phase0" / "parity.json").unlink()
    text = build_report(full_run)
    assert "Timings representative | no: software rasterizer (llvmpipe (LLVM 20.1.2, 256 bits) (CPU, Vulkan)); " \
           "inferred from the recorded devices" in text
    assert "_phase0/parity.json and phase0/perf.json missing: Phase 0 was not run" in text
    # a malformed section input does not lose the rest of the report
    m = json.loads((full_run / "metrics.json").read_text(encoding="utf-8"))
    m["results"][1]["rois"] = {"all": "not a dict"}
    (full_run / "metrics.json").write_text(json.dumps(m), encoding="utf-8")
    text = build_report(full_run)
    assert "## Durations" in text and "## Failures" in text


def test_cli(full_run, tmp_path, capsys):
    assert main(["--run", str(full_run)]) == 0
    assert "wrote" in capsys.readouterr().out and RunLayout(full_run).report_md.is_file()
    out = tmp_path / "elsewhere.md"
    assert main(["--run", str(full_run), "--out", str(out)]) == 0 and out.is_file()
    assert main(["--run", str(tmp_path / "nope")]) == 1
    assert "FAIL" in capsys.readouterr().out
    from tools.layout import write_latest

    write_latest(full_run, full_run.parent)
    assert main(["--run", "LATEST", "--runs-root", str(full_run.parent), "--out", str(out)]) == 0
    assert main(["--runs-root", str(tmp_path / "no_runs")]) == 1
