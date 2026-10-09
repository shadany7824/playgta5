"""tools/layout.py: every path of DESIGN §3, run dirs and the LATEST pointer."""

from __future__ import annotations

import pytest

from tools.layout import RunLayout, new_run_dir, read_latest, reference_cache_dir, write_latest
from tools.spec import expand_views


def _rel(L: RunLayout, p) -> str:
    return p.relative_to(L.root).as_posix()


def test_paths_match_design(tmp_layout):
    L = tmp_layout
    assert _rel(L, L.run_json) == "run.json"
    assert _rel(L, L.views_json("thin_wall")) == "views/thin_wall.json"
    assert _rel(L, L.reference_dir("thin_wall", "s0")) == "reference/thin_wall/s0"
    assert _rel(L, L.reference_file("thin_wall", "s0", "full.exr")) == "reference/thin_wall/s0/full.exr"
    assert _rel(L, L.engine_root("threejs-native")) == "threejs-native"
    assert _rel(L, L.bundle_dir("threejs-native", "thin_wall", "probe")) == "threejs-native/thin_wall/bundles/probe"
    assert _rel(L, L.bundle_json("e", "s", "m")) == "e/s/bundles/m/bundle.json"
    assert _rel(L, L.capture_dir("e", "s", "stations", "m")) == "e/s/stations/m"
    assert _rel(L, L.capture_dir("e", "s", "timeline", "m")) == "e/s/timeline/m"
    assert _rel(L, L.station_capture("e", "s", "m", "s0")) == "e/s/stations/m/s0/final.exr"
    assert _rel(L, L.timeline_frame("e", "s", "m", 7)) == "e/s/timeline/m/frames/00007.exr"
    assert _rel(L, L.receipt_json("e", "s", "timeline", "m")) == "e/s/timeline/m/receipt.json"
    assert _rel(L, L.timing_json("e", "s", "stations", "m")) == "e/s/stations/m/timing.json"
    assert _rel(L, L.runner_log("e", "s", "stations", "m")) == "e/s/stations/m/runner.log"
    for prop, rel in [("metrics_json", "metrics.json"), ("gates_json", "gates.json"),
                      ("temporal_json", "temporal.json"), ("perf_json", "perf.json"), ("report_md", "report.md"),
                      ("sheets_dir", "sheets"), ("temporal_dir", "temporal"), ("phase0_dir", "phase0"),
                      ("inspect_dir", "inspect"), ("phase0_parity_json", "phase0/parity.json"),
                      ("phase0_perf_json", "phase0/perf.json"), ("phase0_sheets_dir", "phase0/sheets")]:
        assert _rel(L, getattr(L, prop)) == rel
    assert _rel(L, L.sheet_png("thin_wall", "s0")) == "sheets/thin_wall/s0.png"
    assert _rel(L, L.temporal_png("dyn_door", "threejs-native", "probe_dynamic")) == \
        "temporal/dyn_door__threejs-native__probe_dynamic.png"
    assert reference_cache_dir("abc").as_posix() == "cache/reference/abc"


def test_capture_kind_aliases(tmp_layout):
    L = tmp_layout
    assert L.capture_dir("e", "s", "station", "m") == L.capture_dir("e", "s", "stations", "m")
    assert L.capture_dir("e", "s", "state", "m") == L.capture_dir("e", "s", "timeline", "m")
    with pytest.raises(ValueError):
        L.capture_dir("e", "s", "frames", "m")


def test_view_capture(tmp_layout, tiny_scene):
    L = tmp_layout
    room = expand_views(tiny_scene("mini_room"))
    assert L.view_capture("e", "mini_room", "direct", room[1]) == L.station_capture("e", "mini_room", "direct", "outside")
    tl = expand_views(tiny_scene("mini_timeline"))
    assert L.view_capture("e", "mini_timeline", "probe", tl[1]) == L.timeline_frame("e", "mini_timeline", "probe", 7)
    assert L.view_capture("e", "x", "m", {"id": "state0", "kind": "state", "capture_frame": 3}).name == "00003.exr"
    with pytest.raises(ValueError):
        L.view_capture("e", "x", "m", {"id": "a", "kind": "frame", "capture_frame": 3})


def test_new_run_dir_and_latest(tmp_path):
    root = tmp_path / "runs"
    assert read_latest(root) is None
    a = new_run_dir(root, run_id="r1")
    assert a.is_dir() and read_latest(root) == a
    assert (root / "LATEST").read_text(encoding="utf-8").strip() == "r1"
    assert new_run_dir(root, run_id="r1") == a  # explicit id: reuse
    b = new_run_dir(root)
    c = new_run_dir(root, run_id=None)
    assert len({a, b, c}) == 3 and read_latest(root) == c
    d = new_run_dir(root, run_id="r2", set_latest=False)
    assert read_latest(root) == c and d.is_dir()
    write_latest(d, root)
    assert read_latest(root) == d
    outside = tmp_path / "elsewhere" / "run"
    outside.mkdir(parents=True)
    write_latest(outside, root)
    assert read_latest(root) == outside.resolve()
    (root / "LATEST").write_text("gone\n", encoding="utf-8")
    assert read_latest(root) is None


def test_phase0_paths_never_touch_measurement_captures(tmp_layout):
    """Parity (DESIGN §5.4) and perf launches get their own trees under phase0/ and perf/."""
    L = tmp_layout
    assert _rel(L, L.parity_capture_dir("threejs-web", "thin_wall", "probe")) == \
        "phase0/captures/threejs-web/thin_wall/probe"
    assert _rel(L, L.parity_bundle_dir("threejs-native", "thin_wall", "direct")) == \
        "phase0/bundles/threejs-native/thin_wall/direct"
    assert _rel(L, L.parity_capture("e", "s", "m", {"id": "lit", "kind": "station"})) == \
        "phase0/captures/e/s/m/lit/final.png"
    assert _rel(L, L.parity_capture("e", "s", "m", {"id": "state1", "kind": "state", "capture_frame": 9}, "exr")) == \
        "phase0/captures/e/s/m/frames/00009.exr"
    with pytest.raises(ValueError):
        L.parity_capture("e", "s", "m", {"id": "a", "kind": "frame"})
    assert _rel(L, L.phase0_sheet_png("thin_wall", "lit", "probe")) == "phase0/sheets/thin_wall__lit__probe.png"
    assert _rel(L, L.perf_bundle_dir("e", "s", "m")) == "perf/bundles/e/s/m"
    assert _rel(L, L.perf_capture_dir("e", "s", "m", 3)) == "perf/captures/e/s/m/round3"
    assert _rel(L, L.perf_capture_dir("e", "s", "m", 1, phase0=True)) == "phase0/perf/captures/e/s/m/round1"
    measurement = {L.capture_dir("e", "s", k, "m") for k in ("stations", "timeline")} | {L.bundle_dir("e", "s", "m")}
    for p in (L.parity_capture_dir("e", "s", "m"), L.parity_bundle_dir("e", "s", "m"),
              L.perf_capture_dir("e", "s", "m", 1), L.perf_capture_dir("e", "s", "m", 1, phase0=True),
              L.perf_bundle_dir("e", "s", "m"), L.perf_bundle_dir("e", "s", "m", phase0=True)):
        for m in measurement:
            assert m not in p.parents and p not in m.parents and p != m
