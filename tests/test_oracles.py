"""Analytic oracles (tools/oracles.py) and the DESIGN §8 gates (tools/gates.py) on synthetic AOVs and run dirs."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

from tools import gates, oracles
from tools.exr import write_exr
from tools.layout import RunLayout, new_run_dir
from tools.spec import discover_scenes, expand_views, load_scene, parse_scene

REPO = Path(__file__).resolve().parent.parent
SCENES = REPO / "scenes"


def scene(name):
    return load_scene(discover_scenes(name)[0])


def brute_force_rect(x, n, corners, nl, k=500):
    """E/L_e by midpoint integration over the rect: sum max(0, cos_x) max(0, cos_l) / d^2 dA."""
    o, u, v = corners[0], corners[1] - corners[0], corners[3] - corners[0]
    s = (np.arange(k) + 0.5) / k
    q = o + s[:, None, None] * u + s[None, :, None] * v
    dA = np.linalg.norm(np.cross(u, v)) / k ** 2
    r = q - x
    d = np.linalg.norm(r, axis=-1)
    cx = np.maximum(r @ n / d, 0.0)
    cl = np.maximum(-(r @ nl) / d, 0.0)
    return float(np.sum(cx * cl / d ** 2) * dA)


def make_rect(origin, u, v):
    return parse_scene({
        "spec_version": 1, "name": "r", "group": "calibration", "image": {"width": 8, "height": 8},
        "materials": {"m": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}},
        "objects": [{"name": "o", "material": "m", "shape": {"type": "box", "min": [0, 0, -9], "max": [1, 1, -8]}}],
        "lights": [{"name": "panel", "type": "rect", "origin": origin, "u": u, "v": v, "radiance": [1, 1, 1]}],
        "stations": [{"name": "s", "position": [0, 0, 5], "look_at": [0, 0, 0], "up": [0, 1, 0]}],
        "oracle": {"type": "rect_plane"}}).light("panel")


# ------------------------------------------------------------------------------------------------ form factor

@pytest.mark.parametrize("case", [
    # (receiver point, receiver normal, rect origin, u, v)
    ([0.0, 0.0, 0.0], [0, 0, 1], [-0.6, -0.3, 1.6], [0, 0.6, 0], [1.2, 0, 0]),       # cal_rect_plane, below
    ([1.7, -0.9, 0.0], [0, 0, 1], [-0.6, -0.3, 1.6], [0, 0.6, 0], [1.2, 0, 0]),      # off to the side
    ([0.3, 0.2, 0.4], [0.3, -0.2, 0.93], [-1.0, -0.5, 1.2], [0, 1.4, 0.2], [1.5, 0, 0]),  # tilted receiver
    ([0.0, 0.0, 0.0], [1, 0, 0.2], [-1.0, -1.0, 0.5], [0, 2.0, 0], [2.0, 0, 0]),     # crosses the horizon
    ([0.5, 0.0, 0.0], [0, 0, 1], [-0.2, -2.0, -0.5], [0, 4.0, 0], [0, 0, 2.0]),     # vertical, half below
])
def test_rect_form_factor_matches_numerical_integration(case):
    x, n, o, u, v = (np.array(c, dtype=np.float64) for c in case)
    n = n / np.linalg.norm(n)
    lt = make_rect(o.tolist(), u.tolist(), v.tolist())
    c = oracles.rect_corners(lt)
    nl = np.cross(u, v) / np.linalg.norm(np.cross(u, v))
    got = float(oracles.rect_irradiance(x[None], n[None], lt)[0])
    want = brute_force_rect(x, n, c, nl)
    assert want > 1e-3
    assert got == pytest.approx(want, rel=2e-3)


def test_polygon_irradiance_closed_forms():
    # centred parallel square of side 2a at height h: 4 corner rectangles (Howell's view-factor table, C-11)
    def corner(X, Y):
        return (X / math.sqrt(1 + X * X) * math.atan(Y / math.sqrt(1 + X * X))
                + Y / math.sqrt(1 + Y * Y) * math.atan(X / math.sqrt(1 + Y * Y))) / (2 * math.pi)
    for a, h in ((0.5, 1.0), (2.0, 0.7), (0.1, 3.0)):
        sq = np.array([[-a, -a, h], [a, -a, h], [a, a, h], [-a, a, h]])
        E = oracles.polygon_irradiance(np.zeros((1, 3)), np.array([[0.0, 0.0, 1.0]]), sq)[0]
        assert E == pytest.approx(math.pi * 4 * corner(a / h, a / h), rel=1e-9)
    big = np.array([[-1e4, -1e4, 1.0], [1e4, -1e4, 1.0], [1e4, 1e4, 1.0], [-1e4, 1e4, 1.0]])
    assert oracles.polygon_irradiance(np.zeros((1, 3)), np.array([[0, 0, 1.0]]), big)[0] == pytest.approx(math.pi,
                                                                                                        rel=1e-3)
    below = big * [1, 1, -1]  # entirely below the horizon
    assert oracles.polygon_irradiance(np.zeros((1, 3)), np.array([[0, 0, 1.0]]), below)[0] == 0.0
    # vectorised: many receivers at once agree with one at a time
    xs = np.random.default_rng(0).uniform(-2, 2, size=(50, 3)) * [1, 1, 0]
    ns = np.broadcast_to([0.0, 0.0, 1.0], xs.shape)
    sq = np.array([[-0.5, -0.5, 1.0], [0.5, -0.5, 1.0], [0.5, 0.5, 1.0], [-0.5, 0.5, 1.0]])
    allv = oracles.polygon_irradiance(xs, ns, sq)
    one = [oracles.polygon_irradiance(xs[i:i + 1], ns[i:i + 1], sq)[0] for i in range(50)]
    assert np.allclose(allv, one)


def test_rect_light_is_one_sided():
    lt = make_rect([-0.5, -0.5, 1.0], [1.0, 0, 0], [0, 1.0, 0])  # faces +z (away from the origin)
    assert oracles.rect_irradiance(np.zeros((1, 3)), np.array([[0, 0, 1.0]]), lt)[0] == 0.0
    above = np.array([[0.0, 0.0, 2.0]])
    assert oracles.rect_irradiance(above, np.array([[0, 0, -1.0]]), lt)[0] > 0.1


# ------------------------------------------------------------------------------------------------ oracle images

@pytest.fixture(scope="module")
def aux_cache():
    cache = {}

    def get(name, w=64, h=48):
        if (name, w, h) not in cache:
            sc = scene(name)
            v = expand_views(sc)[0]
            cache[(name, w, h)] = (sc, v, oracles.raycast_aux(v.state, v.station, w, h))
        return cache[(name, w, h)]
    return get


def test_raycast_aux_matches_the_plane(aux_cache):
    sc, v, aux = aux_cache("cal_point_plane")
    valid = oracles.valid_aux(aux)
    assert valid.all()
    assert np.allclose(aux["position"][..., 2], 0.0, atol=1e-9)
    assert np.allclose(aux["normal"], [0, 0, 1])
    cam = v.station.position
    assert np.allclose(aux["depth"], np.linalg.norm(aux["position"] - cam, axis=-1))
    # the pixel that project_point names contains the point
    p = np.array([1.1, -0.7, 0.0])
    x, y = oracles.project_point(v.station, 64, 48, p)
    assert np.linalg.norm(aux["position"][int(y), int(x)] - p) < 0.1


def test_point_plane_oracle(aux_cache):
    sc, v, aux = aux_cache("cal_point_plane")
    img = oracles.oracle_images(v.state, aux, v.station)
    lamp = sc.light("lamp").params
    rho = sc.materials["plane"].albedo
    P = aux["position"]
    d = lamp["position"] - P
    dist = np.linalg.norm(d, axis=-1)
    want = rho / math.pi * lamp["intensity"] * (d[..., 2] / dist ** 3)[..., None]
    assert np.allclose(img["direct"], want, rtol=1e-12)
    assert np.array_equal(img["full"], img["direct"]) and not img["isolated"].any()
    # survey twin: the same image from its own (local-coordinate) AOVs
    sc2, v2, aux2 = aux_cache("cal_survey_origin")
    img2 = oracles.oracle_images(v2.state, aux2, v2.station)
    assert np.allclose(img2["direct"], img["direct"], rtol=1e-6)


def test_sun_sky_and_furnace_oracles(aux_cache):
    sc, v, aux = aux_cache("cal_sun_plane")
    img = oracles.oracle_images(v.state, aux, v.station)
    d = sc.light("sun").params["direction"]
    p = sc.objects[0].shape
    n = np.cross(p["u"], p["v"])
    cos = float(n @ -d / np.linalg.norm(n) / np.linalg.norm(d))
    want = sc.materials["plane"].albedo / math.pi * sc.light("sun").params["irradiance"] * cos
    valid = oracles.valid_aux(aux)
    assert valid.sum() > 1000 and np.allclose(img["direct"][valid], want, rtol=1e-9)
    assert not img["direct"][~valid].any()

    sc, v, aux = aux_cache("cal_sky_plane")
    img = oracles.oracle_images(v.state, aux, v.station)
    valid = oracles.valid_aux(aux)
    assert 500 < valid.sum() < valid.size  # the sky is in view
    assert np.allclose(img["full"][valid], sc.materials["plane"].albedo * sc.light("sky").params["radiance"])

    sc, v, aux = aux_cache("cal_furnace")
    img = oracles.oracle_images(v.state, aux, v.station)
    valid = oracles.valid_aux(aux)
    Le = np.array([1.0, 0.9, 0.8])
    assert valid.sum() > 2000
    # rho = 0.8: full = L_e/(1-rho) = 5 L_e, direct = L_e(1+rho) = 1.8 L_e, isolated = L_e rho^2/(1-rho) = 3.2 L_e
    assert np.allclose(img["full"][valid], 5 * Le) and np.allclose(img["direct"][valid], 1.8 * Le)
    assert np.allclose(img["isolated"][valid], 3.2 * Le)
    assert np.allclose(img["full"] - img["direct"], img["isolated"])
    fv = oracles.furnace_values(sc)
    assert np.allclose(fv["albedo"], 0.8) and np.allclose(fv["isolated"], Le * 0.64 / 0.2)
    assert not np.allclose(fv["isolated"], fv["albedo"] * Le)  # one bounce (rho L_e) is not full GI here


def test_rect_plane_oracle_receiver_and_emitter(aux_cache):
    sc, v, aux = aux_cache("cal_rect_plane", 96, 72)
    img = oracles.oracle_images(v.state, aux, v.station)
    lt = sc.light("panel")
    valid = oracles.valid_aux(aux)
    on_plane = valid & (np.abs(aux["position"][..., 2]) < 1e-6)
    on_rect = valid & (np.abs(aux["position"][..., 2] - 1.6) < 1e-6)
    assert on_rect.sum() > 5 and np.allclose(img["direct"][on_rect], lt.params["radiance"])
    c = oracles.rect_corners(lt)
    nl = np.array([0.0, 0.0, -1.0])
    rho = sc.materials["plane"].albedo
    for (j, i) in list(zip(*np.nonzero(on_plane), strict=True))[::397][:6]:
        E = brute_force_rect(aux["position"][j, i], np.array([0, 0, 1.0]), c, nl, k=300)
        assert img["direct"][j, i] == pytest.approx(rho / math.pi * lt.params["radiance"] * E, rel=3e-3)


def test_two_sided_receiver_normal_is_turned_to_the_camera(aux_cache):
    sc, v, aux = aux_cache("cal_point_plane")
    flipped = dict(aux, normal=-aux["normal"])  # same plane, stored normal pointing away from the camera
    a = oracles.oracle_images(v.state, aux, v.station)["direct"]
    b = oracles.oracle_images(v.state, flipped, v.station)["direct"]
    assert np.array_equal(a, b)


def test_handedness_oracle_and_checks(aux_cache):
    sc, v, aux = aux_cache("cal_handedness", 256, 192)
    assert {lt.type for lt in sc.lights} == {"directional"}  # no rect lights: every engine can run it
    img = oracles.oracle_images(v.state, aux, v.station)["full"]
    valid = oracles.valid_aux(aux)
    E = sc.light("sun").params["irradiance"]
    floor = valid & (np.abs(aux["position"][..., 2]) < 1e-6)
    assert floor.sum() > 10000 and np.allclose(img[floor], sc.materials["floor"].albedo / math.pi * E)  # dark
    for q in sc.oracle["quads"]:  # each quad: its own albedo, rho/pi * E * cos (cos = 1, sun straight down)
        on = valid & (np.abs(aux["position"][..., 2] - 0.01) < 1e-6) & \
            (np.linalg.norm(aux["position"][..., :2] - sc.object(q["object"]).shape["origin"][:2] - 0.3, axis=-1)
             < 0.25)
        rho = sc.materials[sc.object(q["object"]).material].albedo
        assert on.sum() > 100 and np.allclose(img[on], rho / math.pi * E) and np.allclose(img[on], q["radiance"])
    checks = oracles.handedness_checks(img, sc.oracle)
    assert [c["quad"] for c in checks] == ["red", "green", "white"]
    assert all(c["passed"] for c in checks), checks
    assert all(c["distance_px"] < 0.75 and c["radiance_rel_err"] < 1e-6 for c in checks)  # 1-ray AOVs quantise edges
    lr = oracles.handedness_checks(img[:, ::-1], sc.oracle)
    red = next(c for c in lr if c["quad"] == "red")
    assert not red["passed"] and red["note"] == "mirrored left-right"
    tb = oracles.handedness_checks(img[::-1], sc.oracle)
    assert next(c for c in tb if c["quad"] == "green")["note"] == "mirrored top-bottom"
    bright = oracles.handedness_checks(img * 1.02, sc.oracle)
    assert all(c["position_ok"] and not c["radiance_ok"] for c in bright)
    swapped = oracles.handedness_checks(img[..., [1, 0, 2]], sc.oracle)  # red and green channels swapped
    assert not any(c["passed"] for c in swapped[:2])


def test_oracle_spec_errors(aux_cache):
    sc, v, aux = aux_cache("cal_point_plane")
    for bad in ({"type": "nope"}, {"type": "sun_plane"}, {"type": "point_plane", "light": "missing"},
                {"type": "point_plane", "object": "missing"}, {"type": "handedness", "quads": []},
                {"type": "handedness", "light": "lamp"}):
        sc.oracle = bad
        with pytest.raises(oracles.OracleError):
            oracles.oracle_images(sc, aux, v.station)
    sc.oracle = None
    with pytest.raises(oracles.OracleError):
        oracles.oracle_spec(sc)


# ------------------------------------------------------------------------------------------------ gates (synthetic)

CAL = ("cal_point_plane", "cal_survey_origin", "cal_handedness", "cal_furnace")
ENGINE = "threejs-native"  # no 'light:rect': cal_furnace is a by-design skip for it
OTHER = "other-engine"  # not in the registry: no capability information, so every scene is gated


@pytest.fixture(scope="module")
def scenes_root(tmp_path_factory):
    """A scenes root with four calibration scenes (real files) and thin_wall at 64x48."""
    root = tmp_path_factory.mktemp("scenes")
    (root / "calibration").mkdir()
    (root / "targeted").mkdir()
    for n in CAL:
        shutil.copy(SCENES / "calibration" / f"{n}.json", root / "calibration" / f"{n}.json")
    shutil.copytree(SCENES / "meshes", root / "meshes")
    d = json.loads((SCENES / "targeted" / "thin_wall.json").read_text(encoding="utf-8"))
    d["image"] = {"width": 64, "height": 48}
    (root / "targeted" / "thin_wall.json").write_text(json.dumps(d), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def synthetic(scenes_root):
    """{(scene, view): (View, aux, oracle images or None)} computed once."""
    out = {}
    for f in discover_scenes("all", scenes_root):
        sc = load_scene(f)
        for v in expand_views(sc):
            aux = oracles.raycast_aux(v.state, v.station)
            orc = oracles.oracle_images(v.state, aux, v.station) if sc.oracle else None
            out[(sc.name, v.id)] = (v, aux, orc)
    return out


def write_run(root: Path, synthetic, engine_scale=1.0, ref_scale=1.0, mirror=False, noise=1e-4,
              skip_engine=(), engines=(ENGINE,)) -> RunLayout:
    lay = RunLayout(new_run_dir(root / "runs", run_id="r", set_latest=False))
    for (name, vid), (_v, aux, orc) in synthetic.items():
        d = lay.ensure(lay.reference_dir(name, vid))
        valid = oracles.valid_aux(aux)
        if orc is None:  # targeted: smooth synthetic light, black in the unlit half
            lit = (valid & (aux["position"][..., 0] > 0))[..., None]
            direct = np.where(lit, 0.2 + 0.05 * np.sin(aux["position"]), 0.0)
            full = np.where(lit, 2.0 * direct + 0.1, 0.0)
        else:
            direct, full = orc["direct"] * ref_scale, orc["full"] * ref_scale
        for nm, img in (("full", full), ("direct", direct), ("full_stderr", noise * np.abs(full)),
                        ("direct_stderr", noise * np.abs(direct)), ("normal", aux["normal"]),
                        ("position", aux["position"])):
            write_exr(d / f"{nm}.exr", img.astype(np.float32), channels="R,G,B")
        write_exr(d / "depth.exr", aux["depth"].astype(np.float32), channels="Z")
        if orc is None or name in skip_engine:
            continue
        for mode, img in (("direct", orc["direct"]), ("probe", orc["direct"] + 0.5 * orc["isolated"])):
            if mode == "probe" and name != "cal_furnace":
                continue
            img = img * engine_scale
            if mirror and name == "cal_handedness":
                img = img[:, ::-1]
            for eng in engines:
                if eng == ENGINE and name == "cal_furnace":
                    continue  # by design: pairs never runs three.js on rect-light scenes
                cap = lay.station_capture(eng, name, mode, vid)
                lay.ensure(cap.parent)
                write_exr(cap, img.astype(np.float32), channels="R,G,B")
                (cap.parent.parent / "receipt.json").write_text("{}", encoding="utf-8")
    return lay


def by(doc, **kw):
    return [g for g in doc["gates"] if all(g.get(k) == v for k, v in kw.items())]


def test_gates_pass_on_perfect_images(tmp_path, scenes_root, synthetic):
    lay = write_run(tmp_path, synthetic, engines=(ENGINE, OTHER))
    path, doc = gates.write_gates(lay.root, scenes_root=scenes_root)
    assert path == lay.gates_json and json.loads(path.read_text(encoding="utf-8"))["gates_version"] == 1
    assert doc["engines"] == sorted([ENGINE, OTHER]) and set(doc["scenes"]) == set(CAL) | {"thin_wall"}
    assert not doc["warnings"], doc["warnings"]
    failed = [g for g in doc["gates"] if g["passed"] is False]
    assert not failed, failed[:3]
    for g in doc["gates"]:
        assert set(g) >= {"name", "subject", "scene", "view", "component", "values", "tolerance", "passed", "detail",
                          "status", "by_design", "reason"}
        assert g["status"] in gates.GATE_STATUSES
    ref = by(doc, subject="reference", name="oracle")
    assert {(g["scene"], g["component"]) for g in ref} == {(s, c) for s in CAL for c in ("full", "direct")}
    for subject in (ENGINE, OTHER):
        eng = by(doc, subject=subject, name="oracle")
        assert {g["scene"] for g in eng} == set(CAL) and all(g["component"] == "direct" for g in eng)
        assert all(g["tolerance"] == gates.ENGINE_TOL for g in eng)
    # three.js lacks light:rect: its cal_furnace gates are by-design skips, not failures (DESIGN §4.4, §8)
    skipped = [g for g in doc["gates"] if g["status"] == "skipped"]
    assert skipped and all(g["subject"] == ENGINE and g["scene"] == "cal_furnace" for g in skipped)
    assert all(g["by_design"] and g["passed"] is None and "light:rect" in g["reason"] for g in skipped)
    assert {g["name"] for g in skipped} == {"oracle", "furnace_isolated"}
    assert {g["values"].get("mode") for g in skipped if g["name"] == "furnace_isolated"} == {"probe", "probe_dynamic"}
    assert all(g["status"] == "passed" for g in by(doc, subject=ENGINE) if g["scene"] != "cal_furnace")
    assert len(by(doc, name="handedness")) == 3 and all(g["passed"] for g in by(doc, name="handedness"))
    assert set(by(doc, subject=ENGINE, name="handedness")[0]["values"]["quads"]) == {"red", "green", "white"}
    eq = by(doc, name="survey_equivalence")
    assert {g["subject"] for g in eq} == {"reference", ENGINE, OTHER} and all(g["passed"] for g in eq)
    fur = by(doc, subject=OTHER, name="furnace_isolated")
    assert fur and all(g["passed"] is None and g["status"] == "not_applicable" for g in fur)
    assert fur[0]["values"]["energy"] == pytest.approx(-0.5, abs=1e-6)
    noise = by(doc, name="ref_noise")
    assert {g["view"] for g in noise} == {"lit", "dark"} and {g["component"] for g in noise} == {"direct", "isolated"}
    assert {g["roi"] for g in noise if g["view"] == "dark"} == {"all", "base_floor", "base_wall", "dark_half"}
    assert all(g["passed"] for g in noise)
    s = doc["summary"]
    assert s["reference"]["failed"] == 0 and s[ENGINE]["failed"] == 0 and s[ENGINE]["passed"] >= 5
    assert s[ENGINE]["skipped"] == len(skipped) and s[OTHER]["skipped"] == 0 and s["reference"]["skipped"] == 0
    assert set(s[ENGINE]) == set(gates.GATE_STATUSES)
    assert gates.main(["--run", str(lay.root), "--scenes-root", str(scenes_root), "--strict", "--quiet"]) == 0


def test_gates_fail_on_biased_engine_and_reference(tmp_path, scenes_root, synthetic):
    lay = write_run(tmp_path, synthetic, engine_scale=1.05)
    _, doc = gates.write_gates(lay.root, scenes_root=scenes_root, scenes="calibration")
    eng = [g for g in by(doc, subject=ENGINE, name="oracle") if g["status"] != "skipped"]
    assert eng and all(g["passed"] is False for g in eng)
    assert {g["scene"] for g in eng} == set(CAL) - {"cal_furnace"}  # by-design skip, never a failure
    assert all(g["values"]["bias"] == pytest.approx(0.05, abs=1e-6) for g in eng)
    assert all("bias" in g["detail"] for g in eng)
    hand = by(doc, subject=ENGINE, name="handedness")[0]
    assert hand["passed"] is False and "radiance error" in hand["detail"]
    assert all(g["passed"] for g in by(doc, subject="reference"))
    assert by(doc, subject=ENGINE, name="survey_equivalence")[0]["passed"]  # both are biased the same way
    assert gates.main(["--run", str(lay.root), "--scenes-root", str(scenes_root), "--strict", "--quiet"]) == 1

    lay2 = write_run(tmp_path / "b", synthetic, ref_scale=1.01)
    _, doc2 = gates.write_gates(lay2.root, scenes_root=scenes_root, scenes="calibration")
    ref = by(doc2, subject="reference", name="oracle")
    assert ref and all(g["passed"] is False for g in ref)  # 1 % > the reference's 0.5 % bias tolerance


def test_gates_handedness_mirror_and_missing_engine(tmp_path, scenes_root, synthetic):
    lay = write_run(tmp_path, synthetic, mirror=True, skip_engine=("cal_furnace",), engines=(ENGINE, OTHER))
    _, doc = gates.write_gates(lay.root, scenes_root=scenes_root, scenes="calibration")
    hand = by(doc, subject=ENGINE, name="handedness")[0]
    assert hand["passed"] is False and "mirrored left-right" in hand["detail"]
    fur = by(doc, subject=OTHER, scene="cal_furnace", name="oracle")
    assert fur and fur[0]["passed"] is None and "not run" in fur[0]["detail"]
    assert fur[0]["status"] == "not_applicable" and not fur[0]["by_design"]
    # a capture directory with a receipt but no image is a failure, not "not run"
    cap = lay.station_capture(ENGINE, "cal_point_plane", "direct", "s0")
    cap.unlink()
    _, doc = gates.write_gates(lay.root, scenes_root=scenes_root, scenes="cal_point_plane")
    g = by(doc, subject=ENGINE, name="oracle")[0]
    assert g["passed"] is False and "capture missing" in g["detail"]


def test_gates_by_design_skips_from_metrics_json(tmp_path, scenes_root, synthetic):
    """A by-design skip recorded by pairs.py (scene-level entry: view and mode null) turns that engine's gates on the
    scene into skips even when the registry knows nothing about the engine."""
    lay = write_run(tmp_path, synthetic, engines=(OTHER,), skip_engine=("cal_point_plane",))
    lay.metrics_json.write_text(json.dumps({"metrics_version": 1, "results": [
        {"scene": "cal_point_plane", "view": None, "engine": OTHER, "mode": None, "status": "skipped",
         "by_design": True, "reason": f"{OTHER} lacks light:point"}]}), encoding="utf-8")
    _, doc = gates.write_gates(lay.root, scenes_root=scenes_root, scenes="calibration")
    g = by(doc, subject=OTHER, scene="cal_point_plane")
    assert g and all(x["status"] == "skipped" and x["by_design"] and x["reason"] == f"{OTHER} lacks light:point"
                     for x in g)
    assert doc["summary"][OTHER]["skipped"] == len(g) and doc["summary"][OTHER]["failed"] == 0
    others = [x for x in by(doc, subject=OTHER) if x["scene"] != "cal_point_plane"]
    assert others and all(x["status"] in ("passed", "not_applicable") for x in others)  # furnace: measurements


def test_reference_noise_gate_fails_on_noisy_reference(tmp_path, scenes_root, synthetic):
    lay = write_run(tmp_path, synthetic, noise=1.0)
    _, doc = gates.write_gates(lay.root, scenes_root=scenes_root, scenes="thin_wall")
    noise = by(doc, name="ref_noise")
    lit = [g for g in noise if g["view"] == "lit" and g["roi"] == "lit_floor"]
    assert lit and all(g["passed"] is False and g["values"]["rel_se"] > 0.01 for g in lit)
    dark = [g for g in noise if g["view"] == "dark" and g["roi"] != "all"]
    assert dark and all(g["passed"] and g["values"]["rel_se"] == 0.0 for g in dark)  # exactly black, no noise
    # dark ROIs are relative to the scene's leak normaliser: the brightest view's mean over 'all' (DESIGN §7)
    assert all(g["values"]["basis"] == "leak_norm" and g["values"]["leak_norm"] > 0 for g in dark)
    lit_all = [g for g in noise if g["view"] == "lit" and g["roi"] == "all"]
    for g in dark:
        same = next(x for x in lit_all if x["component"] == g["component"])
        assert g["values"]["leak_norm"] == pytest.approx(same["values"]["mean_all"])


def test_noise_gate_values_bases():
    img = np.full((4, 4, 3), 0.5)
    se = np.full((4, 4, 3), 0.01)
    m = np.zeros((4, 4), bool)
    m[:2] = True
    allm = np.ones((4, 4), bool)
    v = gates.noise_gate_values(img, se, m, allm, "lit")
    assert v["rel_se"] == pytest.approx(0.01 / math.sqrt(8) / 0.5) and v["basis"] == "roi_mean"
    zero = gates.noise_gate_values(np.zeros_like(img), np.zeros_like(se), m, allm, "lit")
    assert zero["rel_se"] == 0.0
    dark = img.copy()
    dark[:2] = 0.0
    v = gates.noise_gate_values(dark, se, m, allm, "dark")
    assert v["basis"] == "mean_all" and v["rel_se"] == pytest.approx(0.01 / math.sqrt(8) / 0.25)
    v = gates.noise_gate_values(np.zeros_like(img), se, m, allm, "dark", leak_norm=0.4)  # a black view
    assert v["basis"] == "leak_norm" and v["rel_se"] == pytest.approx(0.01 / math.sqrt(8) / 0.4)


def test_gates_cli_errors(tmp_path, capsys):
    assert gates.main(["--run", str(tmp_path / "missing")]) == 1
    empty = new_run_dir(tmp_path / "runs", run_id="e", set_latest=False)
    assert gates.main(["--run", str(empty)]) == 0
    assert "no gates computed" in capsys.readouterr().out


@pytest.mark.reference
def test_reference_passes_calibration_gates(tmp_path):
    """End to end: Mitsuba references of five calibration scenes (64x48, low spp) pass their oracle gates.

    cal_furnace (rho 0.8) needs more samples: Russian roulette after depth 8 carries 17 % of its energy, and its
    rel_l1 is 1.65 % at 256 spp, 0.81 % at 1024 and 0.42 % at 4096 (64x48, measured). cal_handedness keeps its
    256x192 size because the expected quad pixels are stored for it; its quads are noise-free (one sun, nothing
    above them), so 16 spp suffice."""
    pytest.importorskip("mitsuba")
    from tools import reference

    root = tmp_path / "scenes"
    (root / "calibration").mkdir(parents=True)
    shutil.copytree(SCENES / "meshes", root / "meshes")
    for n in ("cal_point_plane", "cal_survey_origin", "cal_sun_plane", "cal_furnace", "cal_handedness"):
        d = json.loads((SCENES / "calibration" / f"{n}.json").read_text(encoding="utf-8"))
        if n != "cal_handedness":
            d["image"] = {"width": 64, "height": 48}
        spp = {"cal_furnace": 2048, "cal_handedness": 16}.get(n, 256)
        d["reference"] = {"spp": spp, "batches": 4, "aov_spp": 16}
        (root / "calibration" / f"{n}.json").write_text(json.dumps(d), encoding="utf-8")
    run = new_run_dir(tmp_path / "runs", run_id="ref", set_latest=False)
    res = reference.run_references(run, "all", cache_root=tmp_path / "cache", scenes_root=root, log=None)
    assert not res["failed"], res["failed"]
    _, doc = gates.write_gates(run, scenes_root=root)
    ref = by(doc, subject="reference")
    assert len(ref) >= 11 and all(g["passed"] for g in ref), [g for g in ref if not g["passed"]]
    assert by(doc, subject="reference", name="handedness")[0]["passed"]
