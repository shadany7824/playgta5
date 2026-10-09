"""End-to-end pipeline on the fake engine (DESIGN §0 "Fake engine", §7, §9): tools.pairs and tools.temporal must
recover the perturbations the fake runner injects, report the future slot as a by-design skip, record a crashing
runner as a real failure without ending the run, and write the sheets and plots.

The scenes are generated into a temporary scenes root: ``pipe_static`` (two sealed rooms, a lamp in one; lit, bleed
and dark ROIs; stations ``lit`` and ``dark``) and ``pipe_timeline`` (one room whose lamp switches off at frame 20 and
on at 40, end 59). References are 64x48 at 32 spp, rendered once per module into a temporary cache.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from renderers import get_engine
from renderers.base import NotWired, ModeInfo
from renderers.future import FUTURE_REASON, FakeRenderer, FutureEngine, selector_matches
from tools.layout import RunLayout

BIAS, LEAK, TAU, NOISE, SEED = 0.1, 0.05, 3.0, 0.03, 7
REF = {"spp": 32, "batches": 2, "aov_spp": 4}
MATS = {"white": {"type": "diffuse", "albedo": [0.8, 0.8, 0.8]}, "red": {"type": "diffuse", "albedo": [0.8, 0.15, 0.1]}}
ROOM_A = {"name": "room_a", "material": "white",
          "shape": {"type": "room", "min": [-2, -1.5, 0], "max": [0, 1.5, 2], "thickness": 0.1}}
LAMP = {"name": "lamp", "type": "point", "position": [-1.0, 0.0, 1.6], "intensity": [3, 3, 3]}
CAM = {"position": [-0.2, -1.3, 1.6], "look_at": [-1.4, 0.6, 0.2], "vfov_deg": 70}
FLOOR_A = {"min": [-2, -1.5, -0.01], "max": [0, 1.5, 0.01]}

STATIC = {
    "spec_version": 1, "name": "pipe_static", "group": "targeted", "failure_mode": "light leaking into a sealed room",
    "image": {"width": 64, "height": 48}, "materials": MATS,
    "objects": [ROOM_A,
                {"name": "room_b", "material": "white",
                 "shape": {"type": "room", "min": [0.3, -1.5, 0], "max": [2.3, 1.5, 2], "thickness": 0.1}},
                {"name": "crate", "material": "red", "shape": {"type": "box", "min": [-1.6, 0.6, 0],
                                                               "max": [-1.0, 1.2, 0.6]}}],
    "lights": [LAMP],
    "stations": [{"name": "lit", **CAM},
                 {"name": "dark", "position": [2.1, -1.3, 1.6], "look_at": [0.9, 0.6, 0.2], "vfov_deg": 70}],
    "rois": [{"name": "lit_floor", "role": "lit", "box": FLOOR_A, "normal": [0, 0, 1]},
             {"name": "crate_floor", "role": "bleed", "box": {"min": [-2, 0.2, -0.01], "max": [-0.6, 1.5, 0.01]},
              "normal": [0, 0, 1]},
             # declared dark although lit: checks the leak arithmetic on a non-zero reference (and the energy)
             {"name": "crate_top", "role": "dark", "box": {"min": [-1.61, 0.59, 0.59], "max": [-0.99, 1.21, 0.61]},
              "normal": [0, 0, 1], "views": ["lit"]},
             {"name": "dark_room", "role": "dark", "box": {"min": [0.29, -1.51, -0.01], "max": [2.31, 1.51, 2.01]},
              "views": ["dark"]}],
    "reference": REF}
TIMELINE = {
    "spec_version": 1, "name": "pipe_timeline", "group": "targeted",
    "failure_mode": "stale indirect light after a switch", "image": {"width": 64, "height": 48}, "materials": MATS,
    "objects": [ROOM_A], "lights": [LAMP], "stations": [{"name": "s0", **CAM}],
    "rois": [{"name": "floor", "role": "lit", "box": FLOOR_A, "normal": [0, 0, 1]}],
    "timeline": {"station": "s0", "fps": 60, "end_frame": 59, "steps": [
        {"frame": 20, "actions": [{"op": "set_light", "light": "lamp", "intensity": [0, 0, 0]}]},
        {"frame": 40, "actions": [{"op": "set_light", "light": "lamp", "intensity": [3, 3, 3]}]}]},
    "reference": REF}


def write_scenes(root: Path) -> Path:
    (root / "targeted").mkdir(parents=True, exist_ok=True)
    for s in (STATIC, TIMELINE):
        (root / "targeted" / f"{s['name']}.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    return root


def c4(n: int) -> float:
    """E[sample std] / sigma for n normal samples."""
    return math.sqrt(2.0 / (n - 1)) * math.exp(math.lgamma(n / 2) - math.lgamma((n - 1) / 2))


def result(doc, scene, view, engine, mode):
    hits = [r for r in doc["results"] if (r["scene"], r["view"], r["engine"], r["mode"]) == (scene, view, engine, mode)]
    assert len(hits) == 1, (scene, view, engine, mode, len(hits))
    return hits[0]


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    pytest.importorskip("mitsuba")
    from tools.pairs import run_pairs
    from tools.temporal import run_temporal

    base = tmp_path_factory.mktemp("pipeline")
    scenes_root = write_scenes(base / "scenes")
    run = base / "runs" / "r1"
    engines = [FakeRenderer(name="fake-bad", crash="pipe_static/gi", nan="pipe_timeline/direct"),
               FakeRenderer(bias=BIAS, leak=LEAK, tau=TAU, noise=NOISE, seed=SEED, last_rel_change=0.002),
               FutureEngine()]
    lines: list[str] = []
    metrics = run_pairs(run, engines=engines, scenes="all", scenes_root=scenes_root, cache_root=base / "cache",
                        timeout=120, log=lines.append)
    temporal = run_temporal(run, scenes_root=scenes_root, log=lines.append)
    return SimpleNamespace(base=base, run=run, layout=RunLayout(run), metrics=metrics, temporal=temporal,
                           scenes_root=scenes_root, cache=base / "cache", log=lines)


def _ref(layout, scene, view):
    from tools.masks import view_masks
    from tools.metrics import load_reference_images
    from tools.spec import expand_views, load_scene

    sc = load_scene(layout.root.parent.parent / "scenes" / "targeted" / f"{scene}.json")
    v = next(v for v in expand_views(sc) if v.id == view)
    d = layout.reference_dir(scene, view)
    return load_reference_images(d), view_masks(v, d), v


# ------------------------------------------------------------------------------------------------ unit (no Mitsuba)

def test_registry_and_future_slot():
    fut = get_engine("future")
    assert isinstance(fut, FutureEngine) and fut.name == "future"
    with pytest.raises(NotWired) as e:
        fut.check_available()
    assert e.value.reason == FUTURE_REASON == "future engine not wired: see docs/FUTURE_ADAPTER.md"
    assert fut.direct_mode() == "direct" and any(i.dynamic for i in fut.modes().values())
    assert fut.known_limits() == []
    fake = get_engine("fake")
    assert isinstance(fake, FakeRenderer) and fake.name == "fake"
    fake.check_available()
    assert fake.direct_mode() == "direct" and fake.modes()["gi"] == ModeInfo(
        "gi", "indirect", True, fake.modes()["gi"].counterpart, fake.modes()["gi"].description)
    assert (Path(__file__).resolve().parent.parent / "docs" / "FUTURE_ADAPTER.md").is_file()


def test_fake_parameters_and_selectors(monkeypatch):
    with pytest.raises(ValueError):
        FakeRenderer(bais=0.1)
    with pytest.raises(ValueError):
        FakeRenderer(tau=-1)
    monkeypatch.setenv("HARNESS_FAKE", json.dumps({"bias": 0.25, "crash": "x/gi"}))
    f = FakeRenderer()
    assert f.params["bias"] == 0.25 and f.params["crash"] == "x/gi"
    assert FakeRenderer(bias=0.5).params["bias"] == 0.5  # explicit parameters win over the environment
    assert selector_matches(True, "a", "gi") and not selector_matches(False, "a", "gi")
    assert selector_matches("a", "a", "gi") and not selector_matches("b", "a", "gi")
    assert selector_matches("a/gi", "a", "gi") and not selector_matches("a/direct", "a", "gi")
    assert selector_matches("*/gi", "z", "gi") and selector_matches(["q", "a/*"], "a", "direct")


def test_capture_request_and_mode_order(tiny_scene):
    from renderers.threejs import THREEJS_MODES
    from tools.pairs import capture_request, ordered_modes
    from tools.spec import expand_views

    room = tiny_scene("mini_room")
    views = expand_views(room)
    c = capture_request(room, views, THREEJS_MODES["probe"])
    assert c["settle_frames"] == 4 and [s["settle_frames"] for s in c["stations"]] == [4, 4]
    assert [s["name"] for s in c["stations"]] == ["inside", "outside"]
    assert capture_request(room, views, THREEJS_MODES["probe_dynamic"])["stations"][0]["settle_frames"] == 64
    tl = tiny_scene("mini_timeline")
    tv = expand_views(tl)
    assert capture_request(tl, tv, THREEJS_MODES["direct"])["timeline"]["frames"] == list(range(12))
    assert capture_request(tl, tv, THREEJS_MODES["probe_dynamic"])["timeline"]["frames"] == list(range(12))
    assert capture_request(tl, tv, THREEJS_MODES["probe"])["timeline"]["frames"] == [3, 7, 11]
    nat = get_engine("threejs-native")
    assert ordered_modes(nat) == (["direct", "probe", "probe_dynamic"], None)
    modes, note = ordered_modes(nat, ["probe_dynamic"])
    assert modes == ["direct", "probe_dynamic"] and "isolated against it" in note
    assert ordered_modes(FakeRenderer(), ["probe"]) == ([], None)


# ------------------------------------------------------------------------------------------------ end to end

@pytest.mark.reference
def test_static_metrics_recover_bias_leak_energy(pipeline):
    from tools.masks import roi_mask, valid_mask, load_aux
    from tools.metrics import luminance, roi_mean

    m, L = pipeline.metrics, pipeline.layout
    ref_lit, masks_lit, v_lit = _ref(L, "pipe_static", "lit")
    ref_dark, masks_dark, _ = _ref(L, "pipe_static", "dark")
    iso_lit = ref_lit["full"] - ref_lit["direct"]
    norm = max(roi_mean(iso_lit, masks_lit["all"]), roi_mean(ref_dark["full"] - ref_dark["direct"],
                                                             masks_dark["all"]))
    assert m["scenes"]["pipe_static"]["leak_norm"]["isolated"] == pytest.approx(norm, rel=1e-9)

    d = result(m, "pipe_static", "lit", "fake", "direct")
    assert d["status"] == "ok" and d["component"] == "direct"
    assert d["rois"]["lit_floor"]["bias"] == pytest.approx(0.0, abs=1e-6) and d["energy"] == pytest.approx(0, abs=1e-6)

    g = result(m, "pipe_static", "lit", "fake", "gi")
    assert g["status"] == "ok" and g["component"] == "isolated" and g["kind"] == "indirect"
    assert g["rois"]["lit_floor"]["bias"] == pytest.approx(BIAS, abs=1e-5)
    assert g["rois"]["lit_floor"]["bias_rgb"] == pytest.approx([BIAS] * 3, abs=1e-5)
    assert g["rois"]["crate_floor"]["role"] == "bleed" and g["bleed"]["crate_floor"]["dist"] == pytest.approx(0, abs=1e-6)
    # leak on a declared-dark ROI over a lit surface: leak + (1 + bias) * the reference's own value
    top = g["rois"]["crate_top"]
    assert top["pixels"] > 0 and top["bias"] is None
    assert top["leak_abs"] == pytest.approx(LEAK + (1 + BIAS) * top["ref_leak_abs"], rel=1e-5)
    assert top["leak_rel"] == pytest.approx(top["leak_abs"] / norm, rel=1e-9)
    # energy = bias + leak * (dark pixels inside 'all') / sum Y(T_iso), the fake adds the leak to un-eroded ROI pixels
    aux = load_aux(L.reference_dir("pipe_static", "lit"))
    roi = next(r for r in v_lit.state.rois if r.name == "crate_top")
    n_leak = int((roi_mask(roi, aux, valid_mask(aux)) & masks_lit["all"]).sum())
    total = float(luminance(iso_lit)[masks_lit["all"]].sum())
    assert g["energy"] == pytest.approx(BIAS + LEAK * n_leak / total, rel=1e-4)

    # the sealed room: reference exactly black, leak recovered exactly, leak_rel defined by the scene normaliser
    k = result(m, "pipe_static", "dark", "fake", "gi")["rois"]["dark_room"]
    assert k["ref_leak_abs"] == 0.0 and k["leak_abs"] == pytest.approx(LEAK, rel=1e-6)
    assert k["leak_rel"] == pytest.approx(LEAK / norm, rel=1e-6)
    assert result(m, "pipe_static", "dark", "fake", "direct")["rois"]["dark_room"]["leak_abs"] == 0.0
    # convergence warnings from the receipts (last_rel_change 0.002 > 1e-3)
    assert any("not converged" in w for w in g["warnings"]) and g["convergence"]["settle_frames"] == 64
    assert d["convergence"]["settle_frames"] == 4


@pytest.mark.reference
def test_timeline_metrics(pipeline):
    m = pipeline.metrics
    for view in ("state0", "state2"):
        g = result(m, "pipe_timeline", view, "fake", "gi")
        assert g["status"] == "ok"
        assert g["rois"]["floor"]["bias"] == pytest.approx(BIAS, abs=0.01)  # HALF frames + noise + lag residual
    s1 = result(m, "pipe_timeline", "state1", "fake", "gi")
    assert s1["status"] == "ok" and s1["energy"] is None and s1["rois"]["floor"]["bias"] is None  # black reference
    assert m["scenes"]["pipe_timeline"]["ref_means"]["state1"]["isolated"] == 0.0


@pytest.mark.reference
def test_temporal_recovers_t90_afterglow_flicker(pipeline):
    t = pipeline.temporal
    rows = [r for r in t["results"] if (r["scene"], r["engine"], r["mode"]) == ("pipe_timeline", "fake", "gi")]
    assert {r["roi"] for r in rows} == {"all", "floor"}
    expect = TAU * math.log(10)
    a = math.exp(-1 / TAU)
    for r in rows:
        assert [s["frame"] for s in r["steps"]] == [20, 40]
        for s in r["steps"]:
            assert s["timed"] and abs(s["t90_frames"] - expect) <= 1.0, (r["roi"], s)
            assert s["t90_s"] == pytest.approx(s["t90_frames"] / 60)
        off, on = r["steps"]
        assert off["afterglow"] is not None and on["afterglow"] is None  # only falling steps
        n = round(0.1 * 60)
        assert off["afterglow"]["r"]["0.1"] == pytest.approx((1 + BIAS) * a ** (n + 1), rel=0.03)
        assert off["afterglow"]["residual"] == pytest.approx(0, abs=0.01)
        for f in (r["flicker"][0], r["flicker"][2]):
            assert f["frames"] == 5 and f["temporal_cv"] == pytest.approx(NOISE * c4(5), rel=0.1)
        assert r["frames_missing"] == 0 and len(r["series"]) == 60
        assert (pipeline.run / r["plot"]).is_file()
    skipped = {(s["engine"], s["mode"]): s for s in t["skipped"] if s["scene"] == "pipe_timeline"}
    assert skipped[("fake", "direct")]["reason"] == "not dynamic (by design)" and skipped[("fake", "direct")]["by_design"]
    assert skipped[("future", None)]["reason"] == FUTURE_REASON and skipped[("future", None)]["by_design"]
    assert pipeline.layout.temporal_json.is_file()
    assert json.loads(pipeline.layout.temporal_json.read_text(encoding="utf-8"))["temporal_version"] == 1


@pytest.mark.reference
def test_future_is_a_by_design_skip(pipeline):
    m = pipeline.metrics
    assert m["engines"]["future"]["status"] == "skipped" and m["engines"]["future"]["reason"] == FUTURE_REASON
    rows = [r for r in m["results"] if r["engine"] == "future"]
    assert sorted(r["scene"] for r in rows) == ["pipe_static", "pipe_timeline"]  # one per scene
    for r in rows:
        assert r["status"] == "skipped" and r["by_design"] is True and r["reason"] == FUTURE_REASON
        assert r["view"] is None and r["mode"] is None
    assert not pipeline.layout.engine_root("future").exists()


@pytest.mark.reference
def test_crash_is_a_real_failure_and_the_run_goes_on(pipeline):
    m = pipeline.metrics
    for view in ("lit", "dark"):
        c = result(m, "pipe_static", view, "fake-bad", "gi")
        assert c["status"] == "failed" and c["by_design"] is False and c["reason"].startswith("exit code 1")
        assert any("injected crash" in ln for ln in c["log_tail"]) and c["returncode"] == 1
        assert result(m, "pipe_static", view, "fake-bad", "direct")["status"] == "ok"
    n = result(m, "pipe_timeline", "state0", "fake-bad", "direct")
    assert n["status"] == "failed" and "non-finite" in n["reason"]
    g = result(m, "pipe_timeline", "state0", "fake-bad", "gi")
    assert g["status"] == "failed" and "engine direct capture" in g["reason"]
    # the engines after it ran in full
    assert all(r["status"] == "ok" for r in m["results"] if r["engine"] == "fake")
    assert m["counts"]["failed"] == 2 + 3 + 3
    run = json.loads(pipeline.layout.run_json.read_text(encoding="utf-8"))
    crash = [x for x in run["launches"] if x["engine"] == "fake-bad" and x["mode"] == "gi" and
             x["scene"] == "pipe_static"]
    assert crash and crash[0]["status"] == "failed" and crash[0]["returncode"] == 1 and crash[0]["seconds"] > 0
    t_bad = [s for s in pipeline.temporal["skipped"] if s["engine"] == "fake-bad"]
    assert any(s["mode"] == "direct" and s["by_design"] for s in t_bad)


@pytest.mark.reference
def test_outputs_and_run_json(pipeline):
    L, m = pipeline.layout, pipeline.metrics
    for scene, views in (("pipe_static", ("lit", "dark")), ("pipe_timeline", ("state0", "state1", "state2"))):
        assert json.loads(L.views_json(scene).read_text(encoding="utf-8"))["scene"] == scene
        for v in views:
            png = L.sheet_png(scene, v)
            assert png.is_file() and png.stat().st_size > 1000
            assert result(m, scene, v, "fake", "gi")["files"]["sheet"] == png.relative_to(L.root).as_posix()
            assert (L.reference_dir(scene, v) / "isolated_stderr.exr").is_file()
    assert L.temporal_png("pipe_timeline", "fake", "gi").is_file()
    assert not list(L.sheets_dir.rglob("*.tmp.png")) and not list(L.temporal_dir.rglob("*.tmp.png"))
    for mode in ("direct", "gi"):
        cdir = L.capture_dir("fake", "pipe_timeline", "timeline", mode)
        assert len(list((cdir / "frames").glob("*.exr"))) == 60  # direct and dynamic modes: every frame
        rec = json.loads((cdir / "receipt.json").read_text(encoding="utf-8"))
        assert rec["receipt_version"] == 1 and rec["engine"] == "fake" and (cdir / "timing.json").is_file()
    doc = json.loads(L.metrics_json.read_text(encoding="utf-8"))
    assert doc["metrics_version"] == 1 and set(doc["engines"]) == {"fake", "fake-bad", "future"}
    assert doc["engines"]["fake"]["modes"]["gi"]["dynamic"] is True
    gates = json.loads(L.gates_json.read_text(encoding="utf-8"))
    assert gates["gates_version"] == 1 and gates["summary"]["reference"]
    run = json.loads(L.run_json.read_text(encoding="utf-8"))
    assert run["config"]["pairs"]["engines"] == ["fake-bad", "fake", "future"]
    assert {"references_s", "launch_s", "metrics_s", "sheets_s", "gates_s", "total_s"} <= set(run["durations"]["pairs"])
    assert "temporal" in run["durations"] and run["git"] and run["host"]["python"]
    assert len(run["launches"]) == 8 and all(x["seconds"] >= 0 for x in run["launches"])


@pytest.mark.reference
def test_rerun_merges_and_existing_references(pipeline, tmp_path):
    from tools.pairs import run_pairs

    # --skip-references with a cache: references come from the cache, nothing is rendered
    lines: list[str] = []
    doc = run_pairs(tmp_path / "r2", engines=[FakeRenderer(bias=0.2)], scenes="pipe_static",
                    scenes_root=pipeline.scenes_root, cache_root=pipeline.cache, references="existing",
                    gates=False, log=lines.append)
    assert result(doc, "pipe_static", "lit", "fake", "gi")["rois"]["lit_floor"]["bias"] == pytest.approx(0.2, abs=1e-5)
    assert not any("rendered" in ln for ln in lines)
    # no reference anywhere and rendering disabled: the scene fails, the next scene still runs
    doc = run_pairs(tmp_path / "r3", engines=[FakeRenderer(), FutureEngine()], scenes="all",
                    scenes_root=pipeline.scenes_root, cache_root=tmp_path / "empty", references="existing",
                    gates=False, log=None)
    fails = [r for r in doc["results"] if r["engine"] == "fake"]
    assert fails and all(r["status"] == "failed" and "reference" in r["reason"] for r in fails)
    assert {r["scene"] for r in fails} == {"pipe_static", "pipe_timeline"}
    assert all(r["status"] == "skipped" for r in doc["results"] if r["engine"] == "future")
    # re-running one engine into the first run keeps the other engines' results
    doc = run_pairs(pipeline.run, engines=[FakeRenderer(bias=0.3)], scenes="pipe_static",
                    scenes_root=pipeline.scenes_root, cache_root=pipeline.cache, gates=False, log=None)
    assert result(doc, "pipe_static", "lit", "fake", "gi")["rois"]["lit_floor"]["bias"] == pytest.approx(0.3, abs=1e-5)
    assert result(doc, "pipe_timeline", "state0", "fake", "gi")["status"] == "ok"  # kept from the first run
    assert result(doc, "pipe_static", "lit", "fake-bad", "gi")["status"] == "failed"
    assert len([r for r in doc["results"] if r["engine"] == "future"]) == 2


@pytest.mark.reference
def test_run_all(pipeline, tmp_path, monkeypatch):
    from tools.layout import read_latest
    from tools.run_all import run_all

    monkeypatch.setenv("HARNESS_FAKE", json.dumps({"bias": BIAS, "tau": TAU}))
    res = run_all(None, scenes="all", engines="fake,future", runs_root=tmp_path / "runs",
                  scenes_root=pipeline.scenes_root, cache_root=pipeline.cache, log=None)
    run = Path(res["run"])
    assert read_latest(tmp_path / "runs") == run
    steps = {s["name"]: s for s in res["steps"]}
    assert list(steps) == ["spec", "references", "parity", "pairs", "temporal", "perf", "report"]
    assert all(steps[s]["status"] == "ok" for s in ("spec", "references", "pairs", "temporal")), steps
    assert steps["parity"]["status"] == steps["perf"]["status"] == "skipped"
    assert steps["report"]["status"] in ("ok", "failed", "missing")  # tools.report is another module's job
    doc = json.loads(RunLayout(run).run_json.read_text(encoding="utf-8"))
    assert [s["name"] for s in doc["steps"]] == list(steps)
    assert set(doc["durations"]["run_all"]) == set(steps) and doc["finished_utc"]
    m = json.loads(RunLayout(run).metrics_json.read_text(encoding="utf-8"))
    assert result(m, "pipe_static", "lit", "fake", "gi")["rois"]["lit_floor"]["bias"] == pytest.approx(BIAS, abs=1e-5)
    t = json.loads(RunLayout(run).temporal_json.read_text(encoding="utf-8"))
    assert any(r["engine"] == "fake" and r["mode"] == "gi" for r in t["results"])
    # a failed step is recorded and the later steps still run
    res = run_all(tmp_path / "runs" / "bad", scenes="no_such_scene", engines="fake", runs_root=tmp_path / "runs",
                  scenes_root=pipeline.scenes_root, cache_root=pipeline.cache, log=None)
    steps = {s["name"]: s for s in res["steps"]}
    assert not res["ok"] and steps["spec"]["status"] == "failed" and steps["pairs"]["status"] == "failed"
    assert steps["temporal"]["status"] in ("ok", "failed") and "seconds" in steps["report"]
