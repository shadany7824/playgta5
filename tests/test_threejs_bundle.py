"""renderers/threejs.py: bundle format (§4.2) and three.js mappings (§5.2)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from renderers import get_engine
from renderers.base import ALL_CAPABILITIES, Unsupported, load_bundle, needs_capabilities
from renderers.threejs import (THREEJS_CAPABILITIES, THREEJS_MODES, ThreeJsBundleBuilder, caster_receiver_extent,
                               matrix_elements, quat_rotate, rect_quaternion, scene_bounds, shadow_footprints,
                               shadow_light_basis, split_color, ssaa_offsets)
from tools import oracles
from tools.spec import discover_scenes, expand_views, load_scene, parse_scene


def _build(tiny_scene, name, mode, tmp_path, capture=None, **options):
    """Bundle via the engine's builder: the bundle format still maps rect lights (mini_room has one), although the
    three.js engines do not claim 'light:rect' (build_bundle refuses such scenes, test_capabilities_*)."""
    s = tiny_scene(name)
    builder = ThreeJsBundleBuilder(**options) if options else get_engine("threejs-native").builder
    p = builder.build(s, mode, expand_views(s), capture or {}, tmp_path / name / mode)
    b, arrays = load_bundle(p)
    return s, p, b, arrays


def _light(b, name):
    return next(x for x in b["engine_data"]["lights"] if x["name"] == name)


def test_capabilities_exclude_rect_lights_and_limits_are_listed(tiny_scene, tmp_path):
    """r186 MeshLambertMaterial ignores RectAreaLight, so neither three.js engine claims 'light:rect'."""
    from renderers.threejs import VENDOR_DIR

    lambert = (VENDOR_DIR / "src/renderers/shaders/ShaderChunk/lights_lambert_pars_fragment.glsl.js").read_text("utf-8")
    assert "#define RE_Direct\t\t\t\tRE_Direct_Lambert" in lambert and "RE_Direct_RectArea" not in lambert
    assert "Only PBR materials are supported" in (VENDOR_DIR / "src/lights/RectAreaLight.js").read_text("utf-8")
    assert THREEJS_CAPABILITIES == ALL_CAPABILITIES - {"light:rect"}
    room = tiny_scene("mini_room")  # has a rect light
    for name in ("threejs-native", "threejs-web"):
        eng = get_engine(name)
        assert eng.capabilities() == set(THREEJS_CAPABILITIES)
        assert eng.missing_capabilities(room) == {"light:rect"}
        with pytest.raises(Unsupported) as e:
            eng.build_bundle(room, "direct", expand_views(room), {}, tmp_path / name)
        assert e.value.missing == ["light:rect"]
        limits = eng.known_limits()
        assert len(limits) == 5 and all(isinstance(x, str) and x for x in limits)
        text = " ".join(limits)
        for key in ("RectAreaLight", "HemisphereLight", "SH9", "background", "FrontSide"):
            assert key in text, key
    for sc in ("cal_point_plane", "cal_sun_plane", "cal_sky_plane", "cal_handedness", "cal_survey_origin"):
        assert needs_capabilities(load_scene(discover_scenes(sc)[0])) <= THREEJS_CAPABILITIES, sc
    for sc in ("cal_rect_plane", "cal_furnace"):
        assert "light:rect" in needs_capabilities(load_scene(discover_scenes(sc)[0])), sc


def test_engine_base_known_limits_default():
    from renderers import _UnavailableEngine

    assert _UnavailableEngine("x", "not here").known_limits() == []  # Engine's default


def test_modes_table():
    assert set(THREEJS_MODES) == {"direct", "probe", "probe_dynamic"}
    assert [m for m, i in THREEJS_MODES.items() if i.kind == "direct"] == ["direct"]
    assert THREEJS_MODES["probe_dynamic"].dynamic and not THREEJS_MODES["probe"].dynamic
    assert get_engine("threejs-web").direct_mode() == "direct"


def test_arrays_round_trip(tiny_scene, tmp_path):
    s, p, b, arrays = _build(tiny_scene, "mini_room", "direct", tmp_path)
    assert b["bundle_version"] == 1 and b["engine"] == "threejs" and b["kind"] == "stations"
    assert b["image"] == {"width": 64, "height": 48} and b["mode"] == "direct" and b["scene"] == "mini_room"
    for ob in s.objects:
        np.testing.assert_array_equal(arrays[f"{ob.name}.position"], ob.mesh.positions)
        np.testing.assert_array_equal(arrays[f"{ob.name}.normal"], ob.mesh.normals)
        np.testing.assert_array_equal(arrays[f"{ob.name}.index"], ob.mesh.indices)
    for name, spec in b["arrays"].items():
        f = p.parent / spec["file"]
        assert f.is_file() and spec["file"] == f"arrays/{name}.bin"
        assert f.stat().st_size == int(np.prod(spec["shape"])) * np.dtype(spec["dtype"]).itemsize
        assert spec["dtype"] in ("float32", "uint32")
    raw = (p.parent / b["arrays"]["crate.position"]["file"]).read_bytes()
    np.testing.assert_array_equal(np.frombuffer(raw, "<f4").reshape(-1, 3), s.object("crate").mesh.positions)
    mesh_names = [m["name"] for m in b["engine_data"]["meshes"]]
    assert mesh_names == ["house", "crate"]
    for m in b["engine_data"]["meshes"]:
        assert {m["position"], m["normal"], m["index"]} <= set(b["arrays"])


def test_colour_split(tiny_scene, tmp_path):
    assert split_color([4.0, 2.0, 1.0]) == ([1.0, 0.5, 0.25], 4.0)
    assert split_color([0.0, 0.0, 0.0]) == ([1.0, 1.0, 1.0], 0.0)
    _, _, b, _ = _build(tiny_scene, "mini_point_plane", "direct", tmp_path)
    lamp = _light(b, "lamp")
    assert lamp["type"] == "PointLight" and lamp["color"] == [1.0, 0.5, 0.25] and lamp["intensity"] == 4.0
    assert lamp["decay"] == 2 and lamp["distance"] == 0 and lamp["castShadow"] is True
    assert b["engine_data"]["materials"]["grey"] == {"type": "MeshLambertMaterial", "color": [0.5, 0.5, 0.5],
                                                     "emissive": [0.0, 0.0, 0.0], "side": "DoubleSide"}


@pytest.mark.parametrize("u,v", [([1, 0, 0], [0, -1, 0]), ([0, 2, 0], [0, 0, 1.5]), ([1, 1, 0], [-1, 1, 3]),
                                 ([0.3, -0.2, 0.9], None), ([-1, 0, 0], [0, 0, -1])])
def test_rect_quaternion_maps_minus_z_to_normal(u, v):
    u = np.asarray(u, float)
    if v is None:  # random perpendicular partner
        r = np.random.default_rng(5).normal(size=3)
        v = r - u * (r @ u) / (u @ u)
    v = np.asarray(v, float)
    q = rect_quaternion(u, v)
    n = np.cross(u, v) / np.linalg.norm(np.cross(u, v))
    assert np.linalg.norm(q) == pytest.approx(1.0)
    np.testing.assert_allclose(quat_rotate(q, [0, 0, -1]), n, atol=1e-12)
    np.testing.assert_allclose(quat_rotate(q, [1, 0, 0]), u / np.linalg.norm(u), atol=1e-12)
    np.testing.assert_allclose(abs(quat_rotate(q, [0, 1, 0]) @ (v / np.linalg.norm(v))), 1.0, atol=1e-12)


def test_rect_light_block_and_emitter(tiny_scene, tmp_path):
    s, _, b, arrays = _build(tiny_scene, "mini_room", "direct", tmp_path)
    panel = _light(b, "panel")
    lt = s.light("panel")
    assert panel["type"] == "RectAreaLight" and panel["width"] == 1.0 and panel["height"] == 1.0
    assert panel["color"] == [1.0, 1.0, 0.8] and panel["intensity"] == 5.0
    np.testing.assert_allclose(panel["position"], lt.params["origin"] + 0.5 * (lt.params["u"] + lt.params["v"]))
    np.testing.assert_allclose(quat_rotate(panel["quaternion"], [0, 0, -1]), [0, 0, -1], atol=1e-12)
    em = b["engine_data"]["emitters"]
    assert len(em) == 1 and em[0]["name"] == "panel" and em[0]["side"] == "FrontSide"
    assert em[0]["emissive"] == [5.0, 5.0, 4.0] and em[0]["color"] == [0.0, 0.0, 0.0]
    np.testing.assert_allclose(arrays["panel.normal"], np.tile([0, 0, -1.0], (4, 1)))
    np.testing.assert_allclose(arrays["panel.position"].min(0), [-0.5, -0.5, 2.45], atol=1e-6)


def test_hemisphere_pi_l_and_background(tiny_scene, tmp_path):
    _, _, b, _ = _build(tiny_scene, "mini_room", "direct", tmp_path)
    sky = _light(b, "sky")
    assert sky["type"] == "HemisphereLight" and sky["groundColor"] == [0.0, 0.0, 0.0] and sky["up"] == [0, 0, 1]
    assert sky["intensity"] == pytest.approx(math.pi * 0.3)
    np.testing.assert_allclose(sky["skyColor"], np.array([0.2, 0.25, 0.3]) / 0.3)
    assert b["engine_data"]["background"] == [0.2, 0.25, 0.3]
    _, _, b2, _ = _build(tiny_scene, "mini_point_plane", "direct", tmp_path)
    assert b2["engine_data"]["background"] == [0.0, 0.0, 0.0]


def test_column_major_matrices(tiny_scene, tmp_path):
    s, _, b, arrays = _build(tiny_scene, "mini_room", "direct", tmp_path)
    crate = next(m for m in b["engine_data"]["meshes"] if m["name"] == "crate")
    M = s.object("crate").transform
    e = crate["matrix"]
    assert len(e) == 16 and e[12:15] == M[:3, 3].tolist() and e[15] == 1.0  # translation in elements 12..14
    np.testing.assert_array_equal(np.array(e).reshape(4, 4).T, M)  # three.js Matrix4.elements is column-major
    assert matrix_elements(np.arange(16).reshape(4, 4))[:4] == [0, 4, 8, 12]
    p = arrays["crate.position"][0].astype(np.float64)
    world = np.array(e).reshape(4, 4).T @ np.append(p, 1.0)
    np.testing.assert_allclose(world[:3], M[:3, :3] @ p + M[:3, 3])


def test_timeline_ops(tiny_scene, tmp_path):
    s, _, b, _ = _build(tiny_scene, "mini_timeline", "probe_dynamic", tmp_path)
    assert b["kind"] == "timeline" and b["fps"] == 60
    assert b["capture"] == {"timeline": {"camera": "s0", "end_frame": 11, "frames": list(range(12))}}
    tl = b["engine_data"]["timeline"]
    assert tl["fps"] == 60 and [ev["frame"] for ev in tl["events"]] == [4, 8]
    assert tl["events"][0]["ops"] == [{"op": "light", "name": "lamp", "intensity": 0.0, "color": [1.0, 1.0, 1.0]}]
    ops = tl["events"][1]["ops"]
    assert ops[0]["op"] == "matrix" and ops[0]["mesh"] == "door"
    np.testing.assert_allclose(np.array(ops[0]["matrix"]).reshape(4, 4).T[:3, :3], [[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    assert ops[1] == {"op": "material", "name": "red", "color": [0.1, 0.8, 0.1]}
    assert ops[2] == {"op": "light", "name": "sun", "intensity": 2.0, "color": [1.0, 0.5, 0.25]}
    assert b["engine_data"]["probe"]["enabled"] and b["engine_data"]["probe"]["dynamic"]
    # base state in the bundle is state 0
    assert _light(b, "lamp")["intensity"] == 3.0


def test_timeline_env_and_rect_ops_carry_background_and_emissive(tiny_scene):
    import json
    from conftest import DATA
    d = json.loads((DATA / "mini_room.json").read_text(encoding="utf-8"))
    d["timeline"] = {"station": "inside", "end_frame": 5, "steps": [{"frame": 2, "actions": [
        {"op": "set_light", "light": "sky", "radiance": [0.5, 0.5, 1.0]},
        {"op": "set_light", "light": "panel", "radiance": [0.0, 0.0, 0.0]}]}]}
    d["rois"][1].pop("views")
    s = parse_scene(d)
    ops = ThreeJsBundleBuilder().timeline_block(s)["events"][0]["ops"]
    assert ops[0]["intensity"] == pytest.approx(math.pi) and ops[0]["color"] == [0.5, 0.5, 1.0]
    assert ops[0]["background"] == [0.5, 0.5, 1.0]
    assert ops[1] == {"op": "light", "name": "panel", "intensity": 0.0, "color": [1.0, 1.0, 1.0],
                      "emissive": [0.0, 0.0, 0.0]}


def test_ssaa_offsets(tiny_scene, tmp_path):
    off = ssaa_offsets(16)
    assert len(off) == 16 and off[0] == [-0.375, -0.375] and off[1] == [-0.125, -0.375]
    assert sorted({o[0] for o in off}) == [-0.375, -0.125, 0.125, 0.375]
    assert len({tuple(o) for o in off}) == 16 and np.allclose(np.mean(off, axis=0), 0)
    assert ssaa_offsets(1) == [[0.0, 0.0]]
    with pytest.raises(ValueError):
        ssaa_offsets(8)
    _, _, b, _ = _build(tiny_scene, "mini_point_plane", "direct", tmp_path)
    r = b["engine_data"]["renderer"]
    assert r["ssaa"] == 16 and r["ssaa_offsets"] == off and r["shadowMapType"] == "PCFShadowMap"
    assert r["parity"] == {"toneMapping": "ACESFilmicToneMapping", "exposure": 1.0, "outputColorSpace": "srgb"}
    _, _, b4, _ = _build(tiny_scene, "mini_point_plane", "probe", tmp_path, {"ssaa": 4})
    assert b4["engine_data"]["renderer"]["ssaa_offsets"] == [[-0.25, -0.25], [0.25, -0.25], [-0.25, 0.25], [0.25, 0.25]]


def _shadow_frame(sun):
    """Light-space axes of a bundle's DirectionalLight (as both runners build them) and its target."""
    pos, tgt = np.array(sun["position"]), np.array(sun["target"])
    X, Y = shadow_light_basis(pos, tgt)
    d = (tgt - pos) / np.linalg.norm(tgt - pos)
    return pos, tgt, X, Y, d


def test_directional_shadow_camera_covers_scene(tiny_scene, tmp_path):
    s, _, b, _ = _build(tiny_scene, "mini_room", "direct", tmp_path)
    sun = _light(b, "sun")
    lo, hi = scene_bounds(s)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    pos, tgt, X, Y, d = _shadow_frame(sun)
    np.testing.assert_allclose(d, s.light("sun").params["direction"] / np.linalg.norm(s.light("sun").params["direction"]))
    cam = sun["shadow"]["camera"]
    depth = (corners - pos) @ d
    assert np.all(depth > cam["near"]) and np.all(depth < cam["far"])  # depth range: the whole scene
    # laterally the camera covers every place a shadow can fall: the room (not convex) and the crate inside it
    assert sun["shadow"]["fit"] == "casters"
    boxes, convex, names = shadow_footprints(s, X, Y, tgt)
    assert names == ["house", "crate", "panel"] and convex.tolist() == [False, True, True]
    ext = caster_receiver_extent(boxes, convex)
    assert cam["left"] < ext[0] and cam["right"] > ext[1] and cam["bottom"] < ext[2] and cam["top"] > ext[3]
    assert sun["color"] == pytest.approx([1.0, 2.8 / 3, 2.5 / 3]) and sun["intensity"] == 3.0
    # fit "scene" (the pre-fit square around every scene corner) is kept for A/B measurements
    _, _, b2, _ = _build(tiny_scene, "mini_room", "direct", tmp_path / "scene", dir_shadow_fit="scene")
    sun2 = _light(b2, "sun")
    c2 = sun2["shadow"]["camera"]
    radial = np.linalg.norm((corners - pos) - depth[:, None] * d, axis=1)
    assert sun2["shadow"]["fit"] == "scene" and np.all(radial <= c2["right"])
    assert c2["left"] == -c2["right"] and c2["top"] == c2["right"] and c2["bottom"] == -c2["right"]
    assert (c2["near"], c2["far"], sun2["position"]) == (cam["near"], cam["far"], sun["position"])
    assert -c2["right"] <= cam["left"] and cam["right"] <= c2["right"] and cam["top"] <= c2["top"]
    lamp = _light(b, "lamp")
    assert lamp["shadow"]["far"] > np.max(np.linalg.norm(corners - lamp["position"], axis=1))
    assert 0 < lamp["shadow"]["near"] <= 0.05
    with pytest.raises(ValueError):
        ThreeJsBundleBuilder(dir_shadow_fit="tight").engine_data(s, "direct")


def test_caster_receiver_extent_pairs():
    B = np.array([[-50, 50, -50, 50], [0, 2, 0, 1], [10, 12, 5, 6], [1, 3, 0.5, 4]], dtype=float)
    # ground (convex) + three convex boxes: each box overlaps the ground; boxes 1 and 3 overlap each other
    assert caster_receiver_extent(B, np.array([True] * 4)).tolist() == [0, 12, 0, 6]
    assert caster_receiver_extent(B[:1], np.array([True])) is None  # one convex object cannot shadow itself
    assert caster_receiver_extent(B[:1], np.array([False])).tolist() == [-50, 50, -50, 50]  # non-convex: itself
    assert caster_receiver_extent(B[1:3], np.array([True, True])) is None  # disjoint footprints
    assert caster_receiver_extent(np.zeros((0, 4)), np.zeros(0, bool)) is None


def _outdoor(root, direction=(0.5, -0.3, -1.0)):
    return parse_scene({
        "spec_version": 1, "name": "outdoor", "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 32, "height": 24},
        "materials": {"w": {"type": "diffuse", "albedo": [0.6, 0.6, 0.6]}},
        "objects": [{"name": "ground", "material": "w", "shape": {"type": "box", "min": [-60, -60, -0.5],
                                                                  "max": [60, 60, 0]}},
                    {"name": "tower", "material": "w", "shape": {"type": "box", "min": [-2, -1, -0.1],
                                                                 "max": [2, 1, 10]}}],
        "lights": [{"name": "sun", "type": "directional", "direction": list(direction), "irradiance": [5, 5, 5]}],
        "stations": [{"name": "s", "position": [8, -8, 2], "look_at": [0, 0, 1]}]}, root / "outdoor.json")


def test_casters_fit_is_exact_and_shrinks_texels(tmp_path):
    """A tower on a 120 m ground: the map covers the tower's light-space footprint (where its shadow falls),
    not the ground; ground points outside the map cannot be shadowed (ray cast toward the sun)."""
    s = _outdoor(tmp_path)
    ed_fit, _ = ThreeJsBundleBuilder().engine_data(s, "direct")
    ed_old, _ = ThreeJsBundleBuilder(dir_shadow_fit="scene").engine_data(s, "direct")
    sun, old = _light({"engine_data": ed_fit}, "sun"), _light({"engine_data": ed_old}, "sun")
    c, o = sun["shadow"]["camera"], old["shadow"]["camera"]
    w, h = c["right"] - c["left"], c["top"] - c["bottom"]
    assert w * h < 0.02 * (o["right"] - o["left"]) * (o["top"] - o["bottom"])  # >= 50x fewer m^2 per map
    assert (c["near"], c["far"]) == (o["near"], o["far"])
    pos, tgt, X, Y, d = _shadow_frame(sun)
    rng = np.random.default_rng(1)
    P = np.c_[rng.uniform(-40, 40, size=(4000, 2)), np.zeros(4000)]  # ground top
    lx, ly = (P - tgt) @ X, (P - tgt) @ Y
    outside = (lx < c["left"]) | (lx > c["right"]) | (ly < c["bottom"]) | (ly > c["top"])
    assert 100 < outside.sum() < len(P)
    tris = oracles.scene_triangles(s)[0]
    t, _ = oracles.raycast(tris, P[outside] - 1e-4 * d, np.broadcast_to(-d, P[outside].shape))
    assert not np.isfinite(t).any(), "a ground point outside the shadow camera is in shadow"
    t, _ = oracles.raycast(tris, P[~outside] - 1e-4 * d, np.broadcast_to(-d, P[~outside].shape))
    assert np.isfinite(t).sum() >= 10  # the tower's shadow lies inside
    # every corner of the tower is inside the frustum laterally
    T = np.array([[x, y, z] for x in (-2, 2) for y in (-1, 1) for z in (-0.1, 10)])
    tx, ty = (T - tgt) @ X, (T - tgt) @ Y
    assert np.all((tx > c["left"]) & (tx < c["right"]) & (ty > c["bottom"]) & (ty < c["top"]))


def test_casters_fit_sun_along_y_uses_the_degenerate_lookat_branch(tmp_path):
    s = _outdoor(tmp_path, direction=(0.0, 1.0, 0.0))  # Matrix4.lookAt nudges z by 1e-4 (up = +Y)
    ed, _ = ThreeJsBundleBuilder().engine_data(s, "direct")
    c = _light({"engine_data": ed}, "sun")["shadow"]["camera"]
    assert all(np.isfinite([c["left"], c["right"], c["top"], c["bottom"]])) and c["right"] > c["left"]


def test_point_shadow_bias_is_zero_because_r186_compares_perspective_depth(tiny_scene, tmp_path):
    """A constant depth bias on a perspective cube map is bias*z^2*(f-n)/(f*n) metres: it must not be used."""
    from renderers.threejs import VENDOR_DIR

    chunk = (VENDOR_DIR / "src/renderers/shaders/ShaderChunk/shadowmap_pars_fragment.glsl.js").read_text("utf-8")
    assert ("float dp = ( shadowCameraFar * ( viewSpaceZ - shadowCameraNear ) ) / "
            "( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );\n\t\t\t\tdp += shadowBias;") in chunk
    _, _, b, _ = _build(tiny_scene, "mini_room", "direct", tmp_path)
    lamp, sun = _light(b, "lamp"), _light(b, "sun")
    assert lamp["shadow"]["bias"] == 0.0 and lamp["shadow"]["normalBias"] == 0.02
    assert sun["shadow"]["bias"] == -0.0005  # orthographic: linear depth, bias * (far - near) metres
    n, f, z = lamp["shadow"]["near"], lamp["shadow"]["far"], 3.0
    assert 0.0005 * z * z * (f - n) / (f * n) > 0.1  # what the old -0.0005 would have meant at 3 m


def test_probe_block_per_mode(tiny_scene, tmp_path):
    for mode, enabled, dynamic in [("direct", False, False), ("probe", True, False), ("probe_dynamic", True, True)]:
        _, _, b, _ = _build(tiny_scene, "mini_room", mode, tmp_path)
        pr = b["engine_data"]["probe"]
        assert (pr["enabled"], pr["dynamic"], pr["cubeSize"], pr["type"]) == (enabled, dynamic, 128, "HalfFloatType")


def test_capture_and_measure_blocks(tiny_scene, tmp_path):
    _, _, b, _ = _build(tiny_scene, "mini_room", "probe", tmp_path,
                        {"settle_frames": 3, "measure": {"warmup_frames": 2}, "seed": 7})
    assert b["capture"] == {"stations": [{"name": "inside", "camera": "inside", "settle_frames": 3},
                                         {"name": "outside", "camera": "outside", "settle_frames": 3}]}
    assert b["measure"] == {"timing": True, "warmup_frames": 2, "parity": False} and b["seed"] == 7
    _, _, b2, _ = _build(tiny_scene, "mini_timeline", "direct", tmp_path, {"frames": [11, 3, 7, 3]})
    assert b2["capture"]["timeline"]["frames"] == [3, 7, 11]
    cams = b["engine_data"]["cameras"]
    assert set(cams) == {"inside", "outside"} and cams["inside"]["fov"] == 70.0 and cams["inside"]["up"] == [0, 0, 1]
    assert b["engine_data"]["frame"] == {"up": [0.0, 0.0, 1.0], "origin_world": [0.0, 0.0, 0.0]}
    with pytest.raises(ValueError):
        _build(tiny_scene, "mini_timeline", "direct", tmp_path, {"frames": [12]})
    with pytest.raises(ValueError):
        _build(tiny_scene, "mini_room", "ssgi", tmp_path)


def test_survey_bundle_is_local(tiny_scene, tmp_path):
    s, _, b, arrays = _build(tiny_scene, "mini_survey", "direct", tmp_path)
    assert b["engine_data"]["frame"]["origin_world"] == [346000.0, 6297000.0, 570.0]
    assert np.max(np.abs(arrays["ground.position"])) < 2.0  # local float32 coordinates only
