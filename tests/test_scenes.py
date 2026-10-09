"""Scene specs under scenes/ (DESIGN §2, §8; docs/SCENES.md): validation, views, geometry intents, phase0 views."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from tools import oracles
from tools.geometry import ray_intersect, transformed_mesh
from tools.masks import view_masks
from tools.spec import discover_scenes, expand_views, load_scene

REPO = Path(__file__).resolve().parent.parent
SCENES = REPO / "scenes"

EXPECTED = {  # scene -> (group, view ids)
    "cal_point_plane": ("calibration", ["s0"]),
    "cal_sun_plane": ("calibration", ["s0"]),
    "cal_sky_plane": ("calibration", ["s0"]),
    "cal_rect_plane": ("calibration", ["s0"]),
    "cal_handedness": ("calibration", ["s0"]),
    "cal_furnace": ("calibration", ["s0"]),
    "cal_survey_origin": ("calibration", ["s0"]),
    "sealed_room": ("targeted", ["lit", "dark"]),
    "thin_wall": ("targeted", ["lit", "dark"]),
    "opening": ("targeted", ["toward_door", "far_corner"]),
    "offscreen_source": ("targeted", ["s0", "s1"]),
    "occluded_canyon": ("targeted", ["street", "low_wall"]),
    "dyn_light_switch": ("targeted", ["state0", "state1", "state2"]),
    "dyn_door": ("targeted", ["state0", "state1", "state2"]),
    "dyn_material": ("targeted", ["state0", "state1", "state2"]),
    "courtyard_simplified": ("realworld", ["courtyard", "window_room", "deep_room"]),
    "courtyard_authored": ("realworld", ["courtyard", "window_room", "deep_room"]),
}
SPP = {"calibration": 1024, "targeted": 4096, "realworld": 2048}
SPP_OVERRIDE = {"cal_furnace": 4096}  # rho = 0.8: long paths, Russian roulette noise (docs/SCENES.md)
DARK_MATERIALS = {("cal_handedness", "floor")}  # the dark floor the coloured quads are found against
SURVEY_ORIGIN = [346000.0, 6297000.0, 570.0]
BIG = {"courtyard_simplified", "courtyard_authored"}
_cache: dict = {}


def scene(name):
    if name not in _cache:
        _cache[name] = load_scene(discover_scenes(name)[0])
    return _cache[name]


def _generator():
    spec = importlib.util.spec_from_file_location("scenes_generate", SCENES / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rays(n, seed=0):
    d = np.random.default_rng(seed).normal(size=(n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _scene_mesh_tris(sc):
    return oracles.scene_triangles(sc)[0]


# ------------------------------------------------------------------------------------------------ files

def test_generated_files_are_up_to_date():
    gen = _generator()
    stale = []
    for path, text in gen.outputs().items():
        disk = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else None
        if disk != text:
            stale.append(path.relative_to(REPO).as_posix())
    assert not stale, f"run python scenes/generate.py (stale: {stale})"


def test_scene_set_is_complete():
    found = {p.stem: p.parent.name for p in discover_scenes("all")}
    assert found == {k: g for k, (g, _) in EXPECTED.items()}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_scene_validates_and_expands(name):
    group, view_ids = EXPECTED[name]
    sc = scene(name)
    assert sc.group == group and sc.name == name
    assert (sc.width, sc.height) == (256, 192)
    views = expand_views(sc)
    assert [v.id for v in views] == view_ids
    assert sc.reference["spp"] == SPP_OVERRIDE.get(name, SPP[group]) and sc.reference["batches"] == 4
    assert sc.description
    if group == "calibration":
        assert sc.oracle and sc.oracle["type"] in oracles.ORACLE_TYPES
        assert any(r.role == "oracle" for r in sc.rois)
        oracles.oracle_spec(sc)  # the oracle block is consistent with the scene
    if group == "targeted":
        assert sc.failure_mode and len(sc.stations) in (1, 2)
        assert len(sc.stations) == 2 or sc.timeline is not None
        assert {r.role for r in sc.rois} & {"dark", "lit", "bleed"}
    if group == "realworld":
        assert sc.origin.tolist() == SURVEY_ORIGIN
        assert {lt.type for lt in sc.lights} >= {"directional", "environment"}
        assert sc.comparison == ("appearance" if name == "courtyard_authored" else "exact")
    for m in sc.materials.values():  # albedos 0.5-0.8 (the brightest channel; coloured paints have dim channels)
        if (name, m.name) in DARK_MATERIALS:
            assert float(m.albedo.max()) <= 0.1, (name, m.name, m.albedo)
            continue
        assert 0.5 <= float(m.albedo.max()) <= 0.8, (name, m.name, m.albedo)
    for v in views:  # every ROI restricted to views names real ones; every view sees at least one spec ROI
        assert any(r.views is None or v.id in r.views for r in sc.rois), (name, v.id)


def test_calibration_scenes_have_no_occluders_between_light_and_receiver():
    for name in ("cal_point_plane", "cal_sun_plane", "cal_sky_plane", "cal_rect_plane", "cal_survey_origin"):
        assert len(scene(name).objects) == 1 and len(scene(name).lights) == 1


def test_timeline_steps_far_apart():
    for name in ("dyn_light_switch", "dyn_door", "dyn_material"):
        tl = scene(name).timeline
        frames = [f for f, _ in tl.steps]
        assert frames == [120, 240] and tl.end_frame == 359 and tl.fps == 60
        bounds = [0] + frames + [tl.end_frame + 1]
        assert min(np.diff(bounds)) >= 90, name
        states = [v.state for v in expand_views(scene(name))]
        assert len({v.hash for v in expand_views(scene(name))}) >= 2  # the steps change the rendered state
        assert len(states) == 3


# ------------------------------------------------------------------------------------------------ geometry

def test_sealed_rooms_are_watertight():
    sc = scene("sealed_room")
    rng = np.random.default_rng(3)
    for room in sc.objects:
        lo, hi = np.array(room.shape["min"]), np.array(room.shape["max"])
        assert room.shape["thickness"] >= 0.2 and not room.shape.get("openings") and not room.shape.get("omit")
        mesh = transformed_mesh(room)
        pts = lo + (hi - lo) * rng.uniform(0.02, 0.98, size=(400, 3))
        dirs = _rays(400, 4)
        t = ray_intersect(mesh, pts, dirs)
        assert np.all(np.isfinite(t)), f"{room.name}: a ray escaped"
        hit = pts + dirs * t[:, None]
        assert np.all((hit >= lo - 1e-6) & (hit <= hi + 1e-6)), f"{room.name}: a ray left the interior"
    # the two rooms are separate: the unlit room is far from the light's room
    a, b = (np.array(o.shape["max"]) for o in sc.objects)
    lo_b = np.array(sc.objects[1].shape["min"])
    assert lo_b[0] - a[0] >= 1.0
    lamp = sc.light("lamp").params["position"]
    assert np.all(lamp > np.array(sc.objects[0].shape["min"])) and np.all(lamp < a)


def test_dark_half_of_thin_wall_and_closed_door_room_are_sealed():
    rng = np.random.default_rng(5)
    for name, lo, hi, limit in (("thin_wall", [-2.9, -1.9, 0.1], [-0.1, 1.9, 2.4], -0.025),
                                ("dyn_door", [0.2, -1.9, 0.1], [3.9, 1.9, 2.4], 0.05)):
        sc = scene(name)
        tris = _scene_mesh_tris(sc)
        pts = np.array(lo) + (np.array(hi) - np.array(lo)) * rng.uniform(size=(300, 3))
        dirs = _rays(300, 6)
        t, _ = oracles.raycast(tris, pts, dirs)
        assert np.all(np.isfinite(t)), name
        hit = pts + dirs * t[:, None]
        if name == "thin_wall":
            assert hit[:, 0].max() <= limit + 1e-6, "a ray from the unlit half crossed the 5 cm wall"
        else:
            assert hit[:, 0].min() >= limit - 1e-6, "a ray from room B passed the closed door"


def test_thin_wall_is_5cm_and_spans_the_room():
    sc = scene("thin_wall")
    wall = sc.object("wall")
    lo, hi = np.array(wall.shape["min"]), np.array(wall.shape["max"])
    assert hi[0] - lo[0] == pytest.approx(0.05, abs=1e-12)
    room = sc.object("room").shape
    assert lo[1] < room["min"][1] and hi[1] > room["max"][1] and lo[2] < room["min"][2] and hi[2] > room["max"][2]
    lamp = sc.light("lamp").params["position"]
    assert lamp[0] - hi[0] == pytest.approx(0.3, abs=1e-9)


def test_furnace_is_closed_and_faces_inward():
    sc = scene("cal_furnace")
    assert all(np.allclose(lt.params["albedo"], 0.8) for lt in sc.lights) and sc.oracle["albedo"] == [0.8] * 3
    tris, normals = oracles.scene_triangles(sc)
    rng = np.random.default_rng(7)
    pts = rng.uniform([-0.95, -0.95, 0.05], [0.95, 0.95, 1.95], size=(500, 3))
    dirs = _rays(500, 8)
    t, idx = oracles.raycast(tris, pts, dirs)
    assert np.all(np.isfinite(t))
    n_rect = 2 * 6
    assert np.all(idx >= len(tris) - n_rect), "every ray from inside hits a rect light"
    assert np.all(np.sum(normals[idx] * dirs, axis=1) < 0), "every rect light faces the interior"


def test_survey_obj_resolves_to_the_point_plane():
    a, b = scene("cal_point_plane"), scene("cal_survey_origin")
    assert b.origin.tolist() == SURVEY_ORIGIN and a.origin.tolist() == [0.0, 0.0, 0.0]
    ta = transformed_mesh(a.objects[0])
    tb = transformed_mesh(b.objects[0])
    tri_a = sorted(map(tuple, np.sort(ta.positions[ta.indices].astype(np.float64).reshape(-1, 3, 3), axis=1)
                       .reshape(-1, 9).round(9)))
    tri_b = sorted(map(tuple, np.sort(tb.positions[tb.indices].astype(np.float64).reshape(-1, 3, 3), axis=1)
                       .reshape(-1, 9).round(9)))
    assert tri_a == tri_b  # identical local triangles (exact: binary fractions)
    assert np.allclose(tb.normals, [0, 0, 1])
    obj_lines = (SCENES / "meshes" / "survey_plane.obj").read_text(encoding="utf-8").splitlines()
    world = np.array([[float(x) for x in ln.split()[1:]] for ln in obj_lines if ln.startswith("v ")])
    naive = world.astype(np.float32).astype(np.float64) - np.array(SURVEY_ORIGIN)
    assert np.abs(naive - (world - SURVEY_ORIGIN)).max() >= 0.1  # float32-first would visibly move the plane
    for attr in ("materials", "lights", "stations", "rois"):
        da = json.loads((SCENES / "calibration" / "cal_point_plane.json").read_text(encoding="utf-8"))[attr]
        db = json.loads((SCENES / "calibration" / "cal_survey_origin.json").read_text(encoding="utf-8"))[attr]
        assert da == db, attr
    assert b.oracle["equivalent"] == "cal_point_plane"


def test_handedness_expected_positions():
    import math

    from renderers.base import needs_capabilities
    from renderers.threejs import THREEJS_CAPABILITIES

    sc = scene("cal_handedness")
    st = sc.stations["s0"]
    assert st.position.tolist() == [0.0, 0.0, 4.0] and st.up.tolist() == [0.0, 1.0, 0.0]
    assert needs_capabilities(sc) <= THREEJS_CAPABILITIES  # no rect lights: three.js can run it
    sun = sc.light("sun").params
    d = sun["direction"] / np.linalg.norm(sun["direction"])
    q = {e["object"]: e for e in sc.oracle["quads"]}
    assert q["red"]["pixel"][0] > 128 + 40 and q["red"]["pixel"][1] == pytest.approx(96)  # +x -> right
    assert q["green"]["pixel"][1] < 96 - 40 and q["green"]["pixel"][0] == pytest.approx(128)  # +y -> top
    assert q["white"]["pixel"] == pytest.approx([128, 96])
    for name, e in q.items():
        sh = sc.object(name).shape
        assert sh["type"] == "quad" and sh["origin"][2] == pytest.approx(0.01)
        n = np.cross(sh["u"], sh["v"])
        n /= np.linalg.norm(n)
        c = np.array(sh["origin"]) + 0.5 * (np.array(sh["u"]) + np.array(sh["v"]))
        assert e["pixel"] == pytest.approx(oracles.project_point(st, 256, 192, c), abs=1e-3)
        rho = sc.materials[sc.object(name).material].albedo
        assert e["radiance"] == pytest.approx(rho / math.pi * sun["irradiance"] * max(0.0, float(n @ -d)), rel=1e-6)
    floor = sc.materials["floor"].albedo
    white = np.array(q["white"]["radiance"])
    # the floor is too dark to be taken for the white quad (handedness_checks: > 1/4 of the quad's brightness)
    assert np.linalg.norm(floor / math.pi * sun["irradiance"]) < 0.25 * np.linalg.norm(white)


def test_rect_plane_light_is_above_the_receiver_and_faces_it():
    sc = scene("cal_rect_plane")
    c = oracles.rect_corners(sc.light("panel"))
    assert c[:, 2].min() > 1.0  # entirely above the plane z = 0: never crosses a receiver's horizon
    u, v = sc.light("panel").params["u"], sc.light("panel").params["v"]
    assert np.cross(u, v)[2] < 0  # emits downward


def test_sun_plane_direction_and_tilt():
    sc = scene("cal_sun_plane")
    d = sc.light("sun").params["direction"]
    d = d / np.linalg.norm(d)
    assert np.degrees(np.arccos(-d[2])) == pytest.approx(30.0, abs=1e-4)
    p = sc.objects[0].shape
    n = np.cross(p["u"], p["v"])
    n /= np.linalg.norm(n)
    cos = float(n @ -d)
    for flipped in (d * [-1, 1, 1], d * [1, -1, 1]):  # a sign error in x or y changes the result by > 5 %
        assert abs(max(0.0, float(n @ -flipped)) / cos - 1) > 0.05


# ------------------------------------------------------------------------------------------------ ROIs and light paths

def _light_visible(state, aux, mask, light, tris):
    """Per masked pixel: is the (point or directional) light unoccluded from the first-hit point?"""
    P = aux["position"][mask]
    p = light.params
    if light.type == "point":
        d = p["position"] - P
        dist = np.linalg.norm(d, axis=1)
        d = d / dist[:, None]
        t, _ = oracles.raycast(tris, P + 1e-4 * d, d, t_max=dist - 2e-4)
    else:
        d = np.broadcast_to(-p["direction"] / np.linalg.norm(p["direction"]), P.shape)
        t, _ = oracles.raycast(tris, P + 1e-4 * d, d)
    return ~np.isfinite(t)


def _view_data(name, w=64, h=48):
    sc = scene(name)
    out = []
    for v in expand_views(sc):
        aux = oracles.raycast_aux(v.state, v.station, w, h)
        out.append((v, aux, view_masks(v, aux), _scene_mesh_tris(v.state)))
    return out


@pytest.mark.parametrize("name", [n for n in sorted(EXPECTED) if n not in BIG])
def test_rois_cover_pixels_in_their_views(name):
    sc = scene(name)
    for v, _aux, masks, _t in _view_data(name):
        for r in sc.rois:
            if r.views is not None and v.id not in r.views:
                continue
            assert masks[r.name].sum() >= 10, f"{name}/{v.id}: ROI {r.name} has {masks[r.name].sum()} px at 64x48"


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(BIG))
def test_courtyard_rois_cover_pixels(name):
    sc = scene(name)
    for v, _aux, masks, _t in _view_data(name, 48, 36):
        for r in sc.rois:
            if r.views is None or v.id in r.views:
                assert masks[r.name].sum() >= 20, f"{name}/{v.id}: ROI {r.name}"


def test_targeted_light_paths():
    """The direct-light facts each targeted scene is built on (docs/SCENES.md)."""
    def frac(name, view, roi, light="lamp"):
        for v, aux, masks, tris in _view_data(name, 48, 36):
            if v.id == view:
                m = masks[roi]
                assert m.sum() >= 10, (name, view, roi)
                return float(_light_visible(v.state, aux, m, v.state.light(light), tris).mean())
        raise KeyError(view)

    assert frac("sealed_room", "dark", "dark_room") == 0.0
    assert frac("sealed_room", "lit", "lit_floor") == 1.0
    for roi in ("base_floor", "base_wall", "dark_half"):
        assert frac("thin_wall", "dark", roi) == 0.0
    assert frac("opening", "far_corner", "far_corner") == 0.0  # bounce light only
    assert 0.3 < frac("opening", "toward_door", "door_floor") < 0.9  # partly in the doorway's direct beam
    for view in ("s0", "s1"):  # the sunlit patch is never in view
        assert frac("offscreen_source", view, "all", "sun") == 0.0
    for view, roi in (("street", "street"), ("street", "low_wall_w"), ("street", "low_wall_e"),
                      ("low_wall", "low_wall_e")):
        assert frac("occluded_canyon", view, roi, "sun") == 0.0
    assert frac("dyn_light_switch", "state0", "behind_shelf") == 0.0
    assert frac("dyn_light_switch", "state0", "lit_floor") == 1.0
    assert frac("dyn_door", "state0", "room_b") == 0.0
    assert frac("dyn_door", "state1", "door_floor") > 0.3  # the open door lets direct light into room B
    assert frac("dyn_material", "state0", "panel") == 1.0


def test_offscreen_source_patch_exists_behind_the_camera():
    sc = scene("offscreen_source")
    tris = _scene_mesh_tris(sc)
    d = sc.light("sun").params["direction"]
    d = d / np.linalg.norm(d)
    xs, ys = np.meshgrid(np.linspace(0.2, 5.8, 57), np.linspace(-1.9, 1.9, 39))
    P = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], axis=1)
    t, _ = oracles.raycast(tris, P + 1e-4 * -d, np.broadcast_to(-d, P.shape))
    lit = P[~np.isfinite(t)]
    assert len(lit) > 20
    for st in sc.stations.values():
        f, _r, _u = oracles.camera_basis(st)
        assert lit[:, 0].max() < st.position[0]  # the patch lies behind both cameras (x < camera x)


@pytest.mark.slow
def test_courtyard_deep_room_has_no_window():
    for name in sorted(BIG):
        sc = scene(name)
        tris = _scene_mesh_tris(sc)
        o = np.array([-0.6, -10.3, 1.5])
        d = _rays(1500, 9)
        t, _ = oracles.raycast(tris, o[None], d)
        assert np.all(np.isfinite(t))
        hit = o + d * t[:, None]
        inside = np.all((hit >= [-3.93, -11.71, 0.09]) & (hit <= [3.93, -9.07, 2.96]), axis=1)
        s = (-9.075 - o[1]) / d[~inside, 1]
        cross = o + d[~inside] * s[:, None]
        assert np.all((s > 0) & (np.abs(cross[:, 0]) <= 0.5) & (cross[:, 2] <= 2.25)), \
            f"{name}: light leaves the deep room other than through its doorway"


def test_courtyards_share_building_and_stations():
    a, b = json.loads((SCENES / "realworld" / "courtyard_simplified.json").read_text(encoding="utf-8")), \
        json.loads((SCENES / "realworld" / "courtyard_authored.json").read_text(encoding="utf-8"))
    assert a["stations"] == b["stations"] and a["origin"] == b["origin"] == SURVEY_ORIGIN
    shapes_a = {o["name"]: o["shape"] for o in a["objects"]}
    shapes_b = {o["name"]: o["shape"] for o in b["objects"]}
    assert all(shapes_b.get(k) == v for k, v in shapes_a.items()), "authored = simplified + detail"
    assert len(shapes_b) > len(shapes_a) + 50
    assert any(lt["type"] == "point" for lt in b["lights"]) and not any(lt["type"] == "point" for lt in a["lights"])
    assert len({o["material"] for o in b["objects"]}) >= 8


# ------------------------------------------------------------------------------------------------ phase 0

def test_phase0_parity_views():
    from renderers.threejs import THREEJS_MODES

    doc = json.loads((SCENES / "phase0_parity.json").read_text(encoding="utf-8"))
    views = doc["views"]
    assert 4 <= len(views) <= 8
    modes = set()
    for e in views:
        assert set(e) == {"scene", "view", "modes"}
        assert e["scene"] in EXPECTED, e
        assert e["view"] in EXPECTED[e["scene"]][1], e
        assert e["modes"] and set(e["modes"]) <= set(THREEJS_MODES), e
        modes |= set(e["modes"])
    assert {"direct", "probe"} <= modes
    groups = {EXPECTED[e["scene"]][0] for e in views}
    assert {"calibration", "targeted", "realworld"} <= groups
