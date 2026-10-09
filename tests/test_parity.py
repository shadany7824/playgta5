"""tools/parity.py: the Phase 0 parity gate (DESIGN §5.4).

Synthetic comparisons with known answers (identical PNGs pass, +2 LSB fails, both thresholds at their boundary),
masks, devices, the overall gate, and the driver end to end on a stub engine (tests/phase0_stub.py). The real
runners (threejs-web + threejs-native) run once on a 64x48 view, marked web + native.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from tools import parity as P
from tools.exr import write_exr
from tools.layout import RunLayout
from tools.png import load_png, save_png
from tools.spec import discover_scenes, expand_views, load_scene

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("phase0_stub", HERE / "phase0_stub.py")
stub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stub)

FAST = {"ssaa": 4, "probe_cube_size": 32, "point_shadow_map": 256, "dir_shadow_map": 512}


def _scenes_root(tmp_path: Path, data_dir: Path, names=("mini_point_plane", "mini_room")) -> Path:
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
    p.write_text(json.dumps({"parity_version": 1, "description": "test", "views": views}), encoding="utf-8")
    return p


def _write_aux(d: Path, h: int, w: int, invalid_cols: int = 0) -> None:
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    n[:, :invalid_cols] = 0.0
    write_exr(d / "depth.exr", np.ones((h, w), np.float32), channels=["Z"])
    write_exr(d / "normal.exr", n)
    write_exr(d / "position.exr", np.zeros((h, w, 3), np.float32))


# ------------------------------------------------------------------------------------------------ views file

def test_default_views_file_names_existing_views_and_modes():
    from renderers.threejs import THREEJS_MODES

    vf = P.load_views_file()
    assert Path(vf["path"]) == P.DEFAULT_VIEWS_FILE and len(vf["views"]) == 5
    for v in vf["views"]:
        scene = load_scene(discover_scenes(v["scene"])[0])
        assert v["view"] in {x.id for x in expand_views(scene)}, v
        assert set(v["modes"]) <= set(THREEJS_MODES), v


@pytest.mark.parametrize("doc,msg", [
    ({"parity_version": 2, "views": [{"scene": "a", "view": "b", "modes": ["direct"]}]}, "parity_version"),
    ({"parity_version": 1, "views": []}, "non-empty"),
    ({"parity_version": 1, "views": [{"scene": "a", "view": "b"}]}, "views[0].modes"),
    ({"parity_version": 1, "views": [{"scene": "", "view": "b", "modes": ["direct"]}]}, "views[0].scene"),
    ({"parity_version": 1, "views": [{"scene": "a", "view": "b", "modes": ["direct"], "x": 1}]}, "unknown keys"),
    ({"parity_version": 1, "views": [{"scene": "a", "view": "b", "modes": ["direct"]},
                                     {"scene": "a", "view": "b", "modes": ["direct"]}]}, "listed twice"),
])
def test_views_file_errors_name_the_entry(tmp_path, doc, msg):
    p = tmp_path / "v.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=msg.replace("[", r"\[").replace("]", r"\]")):
        P.load_views_file(p)
    with pytest.raises(ValueError, match="cannot read"):
        P.load_views_file(tmp_path / "missing.json")


# ------------------------------------------------------------------------------------------------ synthetic diffs

def test_identical_pngs_pass_and_plus_two_lsb_fails(tmp_path):
    rng = np.random.default_rng(1)
    img = rng.integers(0, 254, size=(24, 40, 3), dtype=np.uint8)
    save_png(tmp_path / "web.png", img)
    save_png(tmp_path / "same.png", img)
    save_png(tmp_path / "plus2.png", img + 2)
    web = load_png(tmp_path / "web.png")

    same = P.compare_view(web, load_png(tmp_path / "same.png"))
    assert same["gate"]["passed"] is True
    a = same["all"]
    assert (a["max"], a["mean"], a["p99_9"], a["pixels_gt1"], a["fraction_gt1"], a["pixels"]) == (0, 0.0, 0.0, 0, 0.0,
                                                                                                  960)
    assert same["valid"] is None and same["linear"] is None

    plus = P.compare_view(web, load_png(tmp_path / "plus2.png"))
    a = plus["all"]
    assert plus["gate"]["passed"] is False
    assert (a["max"], a["mean"], a["p99_9"], a["pixels_gt1"], a["fraction_gt1"]) == (2, 2.0, 2.0, 960, 1.0)
    assert {c: s["max"] for c, s in a["channels"].items()} == {"R": 2, "G": 2, "B": 2}


def test_gate_thresholds_at_their_boundaries():
    base = np.zeros((10, 100, 3), np.uint8)  # 3000 channel values

    def with_ones(k: int, value: int = 1) -> np.ndarray:
        x = base.copy().reshape(-1)
        x[:k] = value
        return x.reshape(base.shape)

    # one channel 5 LSB off: p99.9 is still 0 (2997th of 3000 sorted values), mean 5/3000
    one = base.copy()
    one[3, 7, 1] = 5
    s = P.diff_stats(base, one)
    assert s["max"] == 5 and s["p99_9"] == 0.0 and s["mean"] == pytest.approx(5 / 3000)
    assert s["pixels_gt1"] == 1 and s["fraction_gt1"] == pytest.approx(1 / 1000)
    assert s["channels"]["G"]["max"] == 5 and s["channels"]["R"]["max"] == 0
    assert P.gate_check(s)["passed"] is True
    # p99.9 = 1 exactly passes, 2 fails (inverted-CDF percentile = an observed value)
    assert P.diff_stats(base, with_ones(10))["p99_9"] == 1.0
    assert P.gate_check(P.diff_stats(base, with_ones(10)))["passed"] is True
    s2 = P.diff_stats(base, with_ones(10, 2))
    assert s2["p99_9"] == 2.0 and P.gate_check(s2)["passed"] is False and s2["pixels_gt1"] == 4
    # mean 0.1 LSB exactly passes (300 of 3000 values at 1 LSB), 301 fails on the mean alone
    s3, s4 = P.diff_stats(base, with_ones(300)), P.diff_stats(base, with_ones(301))
    assert s3["mean"] == 0.1 and P.gate_check(s3)["passed"] is True
    assert s4["p99_9"] == 1.0 and P.gate_check(s4)["passed"] is False
    assert P.percentile_lsb([]) is None and P.gate_check(None)["passed"] is None
    with pytest.raises(ValueError):
        P.diff_stats(base, base[:5])
    with pytest.raises(ValueError):
        P.diff_stats(base.astype(np.float32), base)


def test_valid_mask_restricts_the_statistics():
    web = stub.pattern(12, 16)
    nat = web.copy()
    nat[:, :3] += 2  # only the first three columns differ
    mask = np.ones((12, 16), bool)
    mask[:, :4] = False
    res = P.compare_view(web, nat, web.astype(np.float64) / 255, nat.astype(np.float64) / 255, mask)
    assert res["gate"]["passed"] is False and res["all"]["pixels_gt1"] == 36
    v = res["valid"]
    assert v["pixels"] == 12 * 12 and v["max"] == 0 and v["mean"] == 0.0 and v["pixels_gt1"] == 0
    assert res["linear"]["valid"]["rel_l1"] == 0.0 and res["linear"]["all"]["rel_l1"] > 0
    with pytest.raises(ValueError, match="mask shape"):
        P.diff_stats(web, nat, mask[:5])


def test_linear_difference():
    web = np.ones((4, 5, 3))
    d = P.linear_diff(web, 1.01 * web)
    assert d["rel_l1"] == pytest.approx(0.01) and d["bias"] == pytest.approx(0.01)
    assert d["max_abs"] == pytest.approx(0.01) and d["pixels"] == 20 and d["note"] is None
    black = P.linear_diff(np.zeros((4, 5, 3)), web)
    assert black["rel_l1"] is None and black["bias"] is None and "black" in black["note"] and black["max_abs"] == 1.0
    nan = web.copy()
    nan[0, 0, 0] = np.nan
    assert P.linear_diff(nan, web)["nonfinite_pixels"] == 1


def test_software_adapters_make_the_result_not_representative():
    sw = {"adapter": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)",
          "adapter_type": "CPU"}
    assert P.software_reason(sw) == "SwiftShader, adapter_type CPU"
    assert P.software_reason({"adapter": "llvmpipe (LLVM 20.1.2, 256 bits)", "adapter_type": "CPU"}).startswith(
        "llvmpipe")
    assert "WARP" in P.software_reason({"adapter": "Microsoft Basic Render Driver", "adapter_type": "Unknown"})
    assert P.software_reason({"adapter": "Mystery", "adapter_type": "CPU"}) == "adapter_type CPU"
    gpu = {"adapter": "NVIDIA GeForce RTX 4070", "adapter_type": "DiscreteGPU", "backend": "Vulkan"}
    assert P.software_reason(gpu) is None and P.software_reason(None) is None
    assert P.software_reason({"adapter": "Warpdrive 9000", "adapter_type": "DiscreteGPU"}) is None
    d_gpu, d_sw = P.device_summary({"device": gpu}), P.device_summary({"device": sw})
    assert d_gpu["software"] is False and d_sw["software"] is True and d_gpu["backend"] == "Vulkan"
    assert P.device_summary({}) is None
    assert P.representativeness({"a": d_gpu, "b": d_gpu}) == (True, None)
    ok, why = P.representativeness({"web": d_sw, "native": d_gpu})
    assert ok is False and "web runs on a software rasterizer" in why
    ok, why = P.representativeness({"web": d_gpu, "native": None})
    assert ok is False and "no device recorded" in why


def test_overall_gate():
    def e(status, passed=None, name="v"):
        return {"scene": "s", "view": name, "mode": "direct", "status": status, "reason": None,
                "gate": {"passed": passed}}

    assert P.overall_gate([e("ok", True), e("ok", True, "w")])["status"] == "passed"
    g = P.overall_gate([e("ok", True), e("ok", False, "w"), e("failed", None, "x")])
    assert g["status"] == "failed" and g["passed"] is False and g["failed_entries"] == ["s/w/direct"]
    g = P.overall_gate([e("ok", True), e("skipped", None, "w")])
    assert g["status"] == "incomplete" and g["passed"] is None and len(g["not_compared"]) == 1
    assert P.overall_gate([])["status"] == "incomplete"


def test_parity_sheet_layout(tmp_path):
    web = stub.pattern(48, 64)
    nat = web.copy()
    nat[10:20, 10:20, 0] += 2
    out = P.parity_sheet(web, nat, tmp_path / "s.png", "title", "web\nadapter", "native\nadapter",
                         P.diff_stats(web, nat))
    img = load_png(out)
    scale = 3  # 64 px wide tiles are upscaled to >= 192 px
    assert img.shape[1] >= 3 * 64 * scale and img.shape[0] > 48 * scale
    # the |diff| x32 tile shows the 2 LSB red square as 64 in R, nothing in G/B
    assert (img[..., 0] == 64).sum() >= 100 * scale * scale and img.dtype == np.uint8


def test_find_aux_dir_prefers_the_run_then_the_cache(tmp_path, tiny_scene):
    scene = tiny_scene("mini_point_plane")
    view = expand_views(scene)[0]
    layout = RunLayout(tmp_path / "run")
    cache = tmp_path / "cache"
    d, why = P.find_aux_dir(layout, view, cache)
    assert d is None and "no reference AOVs" in why
    for key, aov in (("a" * 64, 4), ("b" * 64, 64), ("c" * 64, 256)):
        e = cache / "reference" / key
        e.mkdir(parents=True)
        (e / "receipt.json").write_text(json.dumps({"inputs": {"view_hash": view.hash if key != "c" * 64 else "x",
                                                               "aov_spp": aov}}), encoding="utf-8")
        _write_aux(e, 48, 64)
    P._cache_index.clear()
    d, why = P.find_aux_dir(layout, view, cache)
    assert d == cache / "reference" / ("b" * 64) and why.startswith("reference cache bbbb")
    rdir = layout.reference_dir(scene.name, view.id)
    rdir.mkdir(parents=True)
    _write_aux(rdir, 48, 64, invalid_cols=10)
    d, why = P.find_aux_dir(layout, view, cache)
    assert d == rdir and why == "run reference"
    m = P.valid_pixel_mask(d)
    assert m.shape == (48, 64) and m.sum() == 48 * 53  # columns >= 10 valid, eroded by one column


# ------------------------------------------------------------------------------------------------ driver (stub engine)

def test_run_parity_on_stub_engines(tmp_path, data_dir):
    root = _scenes_root(tmp_path, data_dir)
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct", "probe"]},
                                {"scene": "mini_room", "view": "inside", "modes": ["direct"]},
                                {"scene": "mini_room", "view": "outside", "modes": ["direct"]},
                                {"scene": "mini_room", "view": "nowhere", "modes": ["probe"]}])
    layout = RunLayout(tmp_path / "run")
    rdir = layout.reference_dir("mini_point_plane", "top")
    rdir.mkdir(parents=True)
    _write_aux(rdir, 48, 64, invalid_cols=10)
    # measurement bundles and captures of the same engines must survive a parity run untouched
    sentinels = [layout.station_capture("threejs-native", "mini_point_plane", "direct", "top"),
                 layout.bundle_json("threejs-web", "mini_room", "direct")]
    for s in sentinels:
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_text("measurement", encoding="utf-8")
    log = tmp_path / "launches.log"
    web = stub.make_engine("threejs-web", log=log)
    nat = stub.make_engine("threejs-native", offset=2, offset_cols=10, adapter="llvmpipe (LLVM 20)",
                           adapter_type="CPU", log=log)
    doc = P.run_parity(layout.root, views_file=vf, engines=[web, nat], scenes_root=root,
                       cache_root=tmp_path / "nocache", timeout=120, log=None)

    assert all(s.read_text(encoding="utf-8") == "measurement" for s in sentinels)
    saved = json.loads(layout.phase0_parity_json.read_text(encoding="utf-8"))
    assert saved["parity_version"] == 1 and saved["gate"] == doc["gate"]
    by = {(e["scene"], e["view"], e["mode"]): e for e in saved["entries"]}
    assert len(by) == 5
    # one launch per engine and (scene, mode), only the listed views in the bundle
    assert len(log.read_text(encoding="utf-8").splitlines()) == 6
    bundle = json.loads((layout.parity_bundle_dir("threejs-native", "mini_room", "direct") / "bundle.json")
                        .read_text(encoding="utf-8"))
    assert [s["name"] for s in bundle["capture"]["stations"]] == ["inside", "outside"]
    assert bundle["measure"]["parity"] is True and bundle["capture"]["stations"][0]["settle_frames"] == 2
    for key in (("mini_point_plane", "top", "direct"), ("mini_point_plane", "top", "probe")):
        e = by[key]
        assert e["status"] == "ok" and e["gate"]["passed"] is False  # 10 of 64 columns are 2 LSB off
        assert e["all"]["max"] == 2 and e["all"]["pixels_gt1"] == 48 * 10
        assert e["valid"]["pixels"] == 48 * 53 and e["valid"]["max"] == 0 and e["valid"]["mean"] == 0.0
        assert e["valid_mask"]["source"] == "run reference" and e["valid_mask"]["pixels"] == 48 * 53
        assert e["linear"]["all"]["rel_l1"] > 0 and e["linear"]["valid"]["rel_l1"] == 0.0
        assert e["adapters"] == {"threejs-web": "Stub GPU", "threejs-native": "llvmpipe (LLVM 20)"}
        assert (layout.root / e["files"]["sheet"]).is_file()
        assert e["files"]["web_png"] == f"phase0/captures/threejs-web/mini_point_plane/{key[2]}/top/final.png"
    room = by[("mini_room", "inside", "direct")]
    assert room["status"] == "ok" and room["valid"] is None and "no reference AOVs" in room["valid_mask"]["reason"]
    bad = by[("mini_room", "nowhere", "probe")]
    assert bad["status"] == "failed" and "no view nowhere" in bad["reason"]
    assert doc["gate"]["status"] == "failed" and doc["gate"]["passed"] is False and doc["gate"]["compared"] == 4
    assert doc["representative"] is False and "threejs-native runs on a software rasterizer" in doc["reason"]
    assert doc["devices"]["threejs-web"]["software"] is False
    assert layout.phase0_sheet_png("mini_room", "outside", "direct").is_file()
    run = json.loads(layout.run_json.read_text(encoding="utf-8"))
    assert run["config"]["parity"]["engines"] == ["threejs-web", "threejs-native"]


def test_run_parity_identical_sides_pass_and_unavailable_side_is_incomplete(tmp_path, data_dir):
    root = _scenes_root(tmp_path, data_dir, ("mini_point_plane",))
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct"]}])
    web, nat = stub.make_engine("threejs-web"), stub.make_engine("threejs-native")
    doc = P.run_parity(tmp_path / "run", views_file=vf, engines=[web, nat], scenes_root=root, timeout=120, log=None)
    e = doc["entries"][0]
    assert doc["gate"]["status"] == "passed" and e["all"]["max"] == 0 and doc["representative"] is True
    off = stub.make_engine("threejs-native", unavailable="no Vulkan adapter")
    doc = P.run_parity(tmp_path / "run2", views_file=vf, engines=[web, off], scenes_root=root, timeout=120, log=None)
    e = doc["entries"][0]
    assert e["status"] == "skipped" and e["by_design"] and "no Vulkan adapter" in e["reason"]
    assert doc["gate"]["status"] == "incomplete" and doc["representative"] is False
    skip = stub.make_engine("threejs-native", skip="adapter 'RTX' not found")
    doc = P.run_parity(tmp_path / "run3", views_file=vf, engines=[web, skip], scenes_root=root, timeout=120,
                       log=None)
    assert doc["entries"][0]["status"] == "skipped" and "RTX" in doc["entries"][0]["reason"]


def test_cli_usage_errors(tmp_path):
    assert P.main(["--run", str(tmp_path / "r"), "--views", str(tmp_path / "missing.json")]) == 2


# ------------------------------------------------------------------------------------------------ real runners

@pytest.mark.web
@pytest.mark.native
def test_real_runners_on_a_tiny_view(tmp_path, data_dir):
    from renderers.base import NotWired
    from renderers.threejs import ThreeJsNative, ThreeJsWeb

    web, nat = ThreeJsWeb(**FAST), ThreeJsNative(**FAST)
    for eng in (web, nat):
        try:
            eng.check_available()
        except NotWired as e:
            pytest.skip(f"{eng.name} not available: {e.reason}")
    root = _scenes_root(tmp_path, data_dir, ("mini_point_plane",))
    vf = _views_file(tmp_path, [{"scene": "mini_point_plane", "view": "top", "modes": ["direct"]}])
    doc = P.run_parity(tmp_path / "run", views_file=vf, engines=[web, nat], scenes_root=root, timeout=300, log=None)
    e = doc["entries"][0]
    assert e["status"] == "ok", e["reason"]
    assert e["all"]["pixels"] == 64 * 48 and e["gate"]["passed"] in (True, False)
    # a point light on a plane: both runners agree closely even on two different software rasterizers
    assert e["all"]["mean"] < 0.5 and e["linear"]["all"]["rel_l1"] < 0.01
    layout = RunLayout(tmp_path / "run")
    for eng in ("threejs-web", "threejs-native"):
        rec = json.loads((layout.parity_capture_dir(eng, "mini_point_plane", "direct") / "receipt.json")
                         .read_text(encoding="utf-8"))
        assert rec["parity"] is True
        assert layout.parity_capture(eng, "mini_point_plane", "direct", {"id": "top", "kind": "station"}).is_file()
    sw = any(d and d["software"] for d in doc["devices"].values())
    assert doc["representative"] is (not sw)
