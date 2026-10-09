"""tools/spec.py: validation paths, views and capture frames, actions per state, survey origin, CLI."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal

import numpy as np
import pytest

from tools import spec
from tools.spec import SpecError, apply_actions, expand_views, load_scene, parse_scene, state_at_frame

from conftest import DATA, TINY_SCENES


def _raw(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TINY_SCENES)
def test_tiny_scenes_load(tiny_scene, name):
    s = tiny_scene(name)
    assert s.name == name and len(s.hash) == 64
    for o in s.objects:
        assert o.mesh.positions.dtype == np.float32 and o.transform.shape == (4, 4)
    assert s.width == 64 and s.height == 48


def _err(d, source=None) -> SpecError:
    with pytest.raises(SpecError) as e:
        parse_scene(d, source)
    return e.value


@pytest.mark.parametrize("mutate,path", [
    (lambda d: d["objects"][1]["shape"].update(size=[0.5, -1, 0.5]), "objects[1].shape.size"),
    (lambda d: d["materials"]["white"].update(albedo=[0.8, 1.5, 0.8]), "materials.white.albedo[1]"),
    (lambda d: d["objects"][0]["shape"].update(sise=1), "objects[0].shape.sise"),
    (lambda d: d["objects"][0]["shape"]["openings"][0].update(u=[1.0, 2.0]), "objects[0].shape.openings[0].u"),
    (lambda d: d["objects"][0]["shape"].update(thickness=0), "objects[0].shape.thickness"),
    (lambda d: d["objects"][1].update(material="steel"), "objects[1].material"),
    (lambda d: d["lights"][0].pop("intensity"), "lights[0].intensity"),
    (lambda d: d["lights"][2].update(v=[0.3, -1.0, 0.0]), "lights[2].v"),
    (lambda d: d["lights"].append({"name": "sky2", "type": "environment", "radiance": [1, 1, 1]}), "lights[4]"),
    (lambda d: d["lights"][1].update(name="house"), "lights[1].name"),
    (lambda d: d["stations"][0].update(look_at=[-1.6, 0.0, 1.2]), "stations[0].look_at"),
    (lambda d: d["rois"][1].update(views=["state0"]), "rois[1].views[0]"),
    (lambda d: d["rois"][0].update(name="all"), "rois[0].name"),
    (lambda d: d["rois"][0].update(role="glow"), "rois[0].role"),
    (lambda d: d.update(group="targetted"), "group"),
    (lambda d: d.pop("failure_mode"), "failure_mode"),
    (lambda d: d.update(image={"width": 64, "height": 0}), "image.height"),
    (lambda d: d.update(reference={"spp": 64, "batches": 2.5}), "reference.batches"),
    (lambda d: d.update(oracle={"type": "point_plane"}), "oracle"),
    (lambda d: d.update(colour=1), "colour"),
])
def test_errors_are_path_qualified(mutate, path):
    d = _raw("mini_room")
    mutate(d)
    e = _err(d)
    assert e.path == path, str(e)
    assert str(e).startswith(path + ":")


@pytest.mark.parametrize("mutate,path", [
    (lambda t: t["steps"][1].update(frame=4), "timeline.steps[1].frame"),
    (lambda t: t["steps"][1].update(frame=12), "timeline.steps[1].frame"),
    (lambda t: t["steps"][0].update(frame=0), "timeline.steps[0].frame"),
    (lambda t: t["steps"][0]["actions"][0].update(op="toggle"), "timeline.steps[0].actions[0].op"),
    (lambda t: t["steps"][0]["actions"][0].update(light="moon"), "timeline.steps[0].actions[0].light"),
    (lambda t: t["steps"][1]["actions"][2].update(intensity=[1, 1, 1]), "timeline.steps[1].actions[2].intensity"),
    (lambda t: t["steps"][1]["actions"][0]["transform"].update(rotate_z_deg="90"),
     "timeline.steps[1].actions[0].transform.rotate_z_deg"),
    (lambda t: t["steps"][1]["actions"][1].update(albedo=[0.1, 0.8]), "timeline.steps[1].actions[1].albedo"),
    (lambda t: t.update(station="s9"), "timeline.station"),
])
def test_timeline_errors_are_path_qualified(mutate, path):
    d = _raw("mini_timeline")
    mutate(d["timeline"])
    assert _err(d).path == path


def test_error_names_file_and_stem(tmp_path):
    d = _raw("mini_point_plane")
    d["objects"][0]["shape"]["u"] = [4.0, 0.0]
    f = tmp_path / "mini_point_plane.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SpecError) as e:
        load_scene(f)
    assert e.value.path == "objects[0].shape.u" and str(f.resolve()) in str(e.value)
    g = tmp_path / "other_name.json"
    shutil.copy(DATA / "mini_point_plane.json", g)
    with pytest.raises(SpecError) as e:
        load_scene(g)
    assert e.value.path == "name"


def test_station_views(tiny_scene):
    s = tiny_scene("mini_room")
    views = expand_views(s)
    assert [v.id for v in views] == ["inside", "outside"]
    assert all(v.kind == "station" and v.capture_frame is None and v.state_index is None for v in views)
    assert views[0].state is s and views[0].station.name == "inside"
    assert len({v.hash for v in views}) == 2
    np.testing.assert_allclose(views[0].station.up, [0, 0, 1])  # default up
    assert s.stations["outside"].vfov_deg == 60.0  # default fov


def test_timeline_views_capture_frames_and_states(tiny_scene):
    s = tiny_scene("mini_timeline")
    views = expand_views(s)
    assert [v.id for v in views] == ["state0", "state1", "state2"]
    assert [v.capture_frame for v in views] == [3, 7, 11]
    assert [v.frame_range for v in views] == [(0, 3), (4, 7), (8, 11)]
    assert all(v.kind == "state" and v.station.name == "s0" for v in views)
    lamp = [v.state.light("lamp").params["intensity"].tolist() for v in views]
    assert lamp == [[3, 3, 3], [0, 0, 0], [0, 0, 0]]
    door = [v.state.object("door").transform for v in views]
    np.testing.assert_array_equal(door[0], np.eye(4))
    np.testing.assert_array_equal(door[1], np.eye(4))
    np.testing.assert_allclose(door[2][:3, :3], [[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    assert views[2].state.materials["red"].albedo.tolist() == [0.1, 0.8, 0.1]
    assert views[2].state.light("sun").params["irradiance"].tolist() == [2, 1, 0.5]
    assert views[1].state.materials["red"].albedo.tolist() == [0.8, 0.1, 0.1]
    # the base scene is untouched
    assert s.light("lamp").params["intensity"].tolist() == [3, 3, 3]
    assert len({v.hash for v in views}) == 3
    assert spec.timeline_states(s) == [(0, 3), (4, 7), (8, 11)]


def test_state_at_frame(tiny_scene):
    s = tiny_scene("mini_timeline")
    assert state_at_frame(s, 3).light("lamp").params["intensity"].tolist() == [3, 3, 3]
    assert state_at_frame(s, 4).light("lamp").params["intensity"].tolist() == [0, 0, 0]  # applied, then drawn
    assert state_at_frame(s, 7).object("door").transform[0, 0] == 1.0
    assert state_at_frame(s, 8).object("door").transform[0, 0] == 0.0
    views = expand_views(s)
    for v in views:
        assert state_at_frame(s, v.capture_frame).hash == v.state.hash
    np_scene = tiny_scene("mini_room")
    assert state_at_frame(np_scene, 100) is np_scene


def test_apply_actions_raw_and_validation(tiny_scene):
    s = tiny_scene("mini_room")
    out = apply_actions(s, [{"op": "set_light", "light": "panel", "radiance": [1, 2, 3]},
                            {"op": "set_material", "material": "red", "albedo": [0.5, 0.5, 0.5]},
                            {"op": "set_transform", "object": "crate", "transform": {"translate": [0, 0, 1]}}])
    assert out.light("panel").params["radiance"].tolist() == [1, 2, 3]
    assert s.light("panel").params["radiance"].tolist() == [5, 5, 4]
    assert out.object("crate").transform[2, 3] == 1.0 and out.hash != s.hash
    with pytest.raises(SpecError) as e:
        apply_actions(s, [{"op": "set_light", "light": "sun", "intensity": [1, 1, 1]}])
    assert e.value.path == "actions[0].intensity"


def test_hashes_stable_and_location_independent(tmp_path, tiny_scene):
    a = tiny_scene("mini_room")
    b = tiny_scene("mini_room")
    assert a.hash == b.hash
    assert [v.hash for v in expand_views(a)] == [v.hash for v in expand_views(b)]
    shutil.copy(DATA / "mini_room.json", tmp_path / "mini_room.json")
    assert load_scene(tmp_path / "mini_room.json").hash == a.hash
    d = _raw("mini_room")
    d["description"] = "changed text"
    c = parse_scene(d)
    assert c.hash != a.hash
    assert [v.hash for v in expand_views(c)] == [v.hash for v in expand_views(a)]  # views: render inputs only
    d["materials"]["white"]["albedo"] = [0.7, 0.8, 0.8]
    assert expand_views(parse_scene(d))[0].hash != expand_views(a)[0].hash


def test_survey_origin_precision(tiny_scene):
    s = tiny_scene("mini_survey")
    assert s.origin.dtype == np.float64 and s.origin.tolist() == [346000.0, 6297000.0, 570.0]
    pos = s.objects[0].mesh.positions
    assert pos.dtype == np.float32
    lines = (DATA / "meshes" / "mini_survey_plane.obj").read_text(encoding="utf-8").splitlines()
    world = [[Decimal(t) for t in ln.split()[1:4]] for ln in lines if ln.startswith("v ")]
    origin = [Decimal("346000.0"), Decimal("6297000.0"), Decimal("570.0")]
    exact = np.array([[float(w - o) for w, o in zip(v, origin)] for v in world])
    got = {tuple(np.round(p, 6)) for p in pos.astype(np.float64)}
    assert len(got) == 4
    err = max(np.min(np.max(np.abs(pos.astype(np.float64) - e), axis=1)) for e in exact)
    assert err < 1e-4  # sub-millimetre (float32 near 1 m: ~6e-8)
    naive = np.array([[float(np.float32(float(c))) for c in v] for v in world]) - [float(o) for o in origin]
    assert np.max(np.abs(naive - exact)) > 0.01  # casting world coords to float32 first would be cm-off
    assert s.objects[0].shape == {"type": "mesh", "file": "meshes/mini_survey_plane.obj", "coords": "world"}


def test_discover_scenes(tmp_path):
    root = tmp_path / "scenes"
    for grp, name in [("calibration", "mini_point_plane"), ("targeted", "mini_room"), ("targeted", "mini_timeline")]:
        (root / grp).mkdir(parents=True, exist_ok=True)
        shutil.copy(DATA / f"{name}.json", root / grp / f"{name}.json")
    (root / "phase0_parity.json").write_text("{}", encoding="utf-8")
    names = lambda ps: [p.stem for p in ps]  # noqa: E731
    assert names(spec.discover_scenes("all", root)) == ["mini_point_plane", "mini_room", "mini_timeline"]
    assert names(spec.discover_scenes("targeted", root)) == ["mini_room", "mini_timeline"]
    assert names(spec.discover_scenes("mini_room,calibration", root)) == ["mini_room", "mini_point_plane"]
    assert names(spec.discover_scenes(["mini_timeline"], root)) == ["mini_timeline"]
    assert spec.discover_scenes("realworld", root) == []
    with pytest.raises(SpecError):
        spec.discover_scenes("nope", root)
    for p in spec.discover_scenes("all", root):
        load_scene(p)  # group matches directory


def test_group_must_match_directory(tmp_path):
    (tmp_path / "realworld").mkdir()
    shutil.copy(DATA / "mini_room.json", tmp_path / "realworld" / "mini_room.json")
    with pytest.raises(SpecError) as e:
        load_scene(tmp_path / "realworld" / "mini_room.json")
    assert e.value.path == "group"


def test_views_summary(tiny_scene):
    s = tiny_scene("mini_timeline")
    j = spec.views_summary(s)
    json.dumps(j)
    assert j["kind"] == "timeline" and j["end_frame"] == 11 and j["steps"] == [4, 8]
    assert [(v["id"], v["capture_frame"], v["frames"]) for v in j["views"]] == [
        ("state0", 3, [0, 3]), ("state1", 7, [4, 7]), ("state2", 11, [8, 11])]


def test_cli_check(capsys, tmp_path):
    assert spec.main([str(DATA), "--check"]) == 0
    out = capsys.readouterr().out
    for name in TINY_SCENES:
        assert f"ok   {name}" in out
    assert "state2" in out and "capture_frame=11" in out and "4 ok, 0 failed" in out
    d = _raw("mini_room")
    d["objects"][1]["shape"]["size"] = [1, 1, -1]
    (tmp_path / "mini_room.json").write_text(json.dumps(d), encoding="utf-8")
    assert spec.main([str(tmp_path / "mini_room.json"), "--check"]) == 1
    assert "objects[1].shape.size" in capsys.readouterr().out


def test_canonical_json():
    assert spec.canonical_json({"b": np.float32(0.5), "a": [-0.0, np.int64(3)]}) == '{"a":[0.0,3],"b":0.5}'
    with pytest.raises(ValueError):
        spec.canonical_json({"x": float("nan")})
