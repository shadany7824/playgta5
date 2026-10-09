"""tools.run_all: options reach the tools they belong to, and report.md is rebuilt with the final run.json."""

from __future__ import annotations

import json

import pytest

from tools import run_all as RA
from tools.layout import RunLayout


@pytest.fixture
def calls(monkeypatch):
    seen: dict[str, list[str]] = {}

    def fake_call_tool(module, argv, echo=True):
        argv = [str(a) for a in argv]
        key = "tools.perf --phase0" if module == "tools.perf" and "--phase0" in argv else module
        seen[key] = argv
        return {"status": "ok", "returncode": 0, "reason": None, "via": "main", "tail": []}

    ok = {"status": "ok", "returncode": None, "reason": None, "via": "main", "tail": []}
    monkeypatch.setattr(RA, "call_tool", fake_call_tool)
    monkeypatch.setattr(RA, "_step_spec", lambda *a, **k: dict(ok))
    monkeypatch.setattr(RA, "_step_references", lambda *a, **k: dict(ok))
    return seen


def _value(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else None


def test_options_are_forwarded(calls, tmp_path):
    res = RA.run_all(tmp_path / "runs" / "r1", scenes="targeted", engines="threejs-native,future", spp_scale=0.05,
                     phase0=True, perf=True, runs_root=tmp_path / "runs", scenes_root=tmp_path / "scenes",
                     cache_root=tmp_path / "cache", timeout=99.0, settle_frames=3, dynamic_settle_frames=16,
                     perf_rounds=2, perf_frames=10, perf_warmup=5, log=None)
    assert res["ok"], res["steps"]
    pairs, parity, perf = calls["tools.pairs"], calls["tools.parity"], calls["tools.perf --phase0"]
    assert _value(pairs, "--settle-frames") == "3" and _value(pairs, "--dynamic-settle-frames") == "16"
    assert _value(pairs, "--engines") == "threejs-native,future" and _value(pairs, "--scenes") == "targeted"
    assert float(_value(pairs, "--timeout")) == 99.0 and _value(pairs, "--cache") == str(tmp_path / "cache")
    assert _value(parity, "--dynamic-settle-frames") == "16" and _value(parity, "--cache") == str(tmp_path / "cache")
    assert _value(parity, "--scenes-root") == str(tmp_path / "scenes") and "--settle-frames" not in parity
    assert "--phase0" in perf and (_value(perf, "--rounds"), _value(perf, "--frames"), _value(perf, "--warmup")) \
        == ("2", "10", "5")
    assert float(_value(perf, "--timeout")) == 99.0 and "--engines" not in perf
    cost = calls["tools.perf"]  # the measured engines' cost in every mode, besides the phase0 gate run
    assert "--phase0" not in cost and _value(cost, "--engines") == "threejs-native,future"
    assert (_value(cost, "--rounds"), _value(cost, "--frames"), _value(cost, "--warmup")) == ("2", "10", "5")
    perf_step = next(s for s in res["steps"] if s["name"] == "perf")
    assert [p["name"] for p in perf_step["parts"]] == ["cost", "phase0"]
    cfg = json.loads(RunLayout(res["run"]).run_json.read_text(encoding="utf-8"))["config"]["run_all"]
    assert cfg["perf_rounds"] == 2 and cfg["dynamic_settle_frames"] == 16


def test_defaults_leave_the_tools_defaults(calls, tmp_path):
    RA.run_all(tmp_path / "runs" / "r2", runs_root=tmp_path / "runs", log=None)
    assert "tools.parity" not in calls and "tools.perf" not in calls  # need --phase0 / --perf
    for flag in ("--settle-frames", "--dynamic-settle-frames", "--timeout", "--cache"):
        assert flag not in calls["tools.pairs"]


def test_report_is_rebuilt_with_the_final_run_json(monkeypatch, tmp_path):
    ok = {"status": "ok", "returncode": None, "reason": None, "via": "main", "tail": []}
    monkeypatch.setattr(RA, "_step_spec", lambda *a, **k: dict(ok))
    monkeypatch.setattr(RA, "_step_references", lambda *a, **k: dict(ok))
    real = RA.call_tool
    monkeypatch.setattr(RA, "call_tool", lambda module, argv, echo=True: real(module, argv, echo) if
                        module == "tools.report" else dict(ok))
    res = RA.run_all(tmp_path / "runs" / "r3", runs_root=tmp_path / "runs", log=None)
    text = RunLayout(res["run"]).report_md.read_text(encoding="utf-8")
    assert "no finish time recorded" not in text and "run_all: report" in text and "all steps ok" in text
