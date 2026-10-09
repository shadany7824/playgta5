"""Mitsuba reference (tools/reference.py, DESIGN §6): analytic checks, orientation, furnace, cache, timeline, noise."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from tools import reference as ref  # imports Mitsuba lazily
from tools.exr import read_exr, read_exr_header
from tools.layout import REFERENCE_FILES
from tools.spec import expand_views, parse_scene

try:
    import mitsuba as mi
except ImportError:  # settings/key tests still run; rendering tests skip
    mi = None

pytestmark = pytest.mark.reference
needs_mitsuba = pytest.mark.skipif(mi is None, reason="mitsuba not installed")

GREY = {"grey": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}}
TOP = {"name": "top", "position": [0.0, 0.0, 3.0], "look_at": [0.0, 0.0, 0.0], "up": [0.0, 1.0, 0.0], "vfov_deg": 60}
PLANE = {"name": "plane", "material": "grey",
         "shape": {"type": "quad", "origin": [-3.0, -3.0, 0.0], "u": [6.0, 0.0, 0.0], "v": [0.0, 6.0, 0.0]}}
FAST = {"spp": 64, "batches": 2, "aov_spp": 64}


def make_scene(name, objects, lights, station=TOP, materials=GREY, w=48, h=36, reference=None):
    d = {"spec_version": 1, "name": name, "group": "calibration", "image": {"width": w, "height": h},
         "materials": materials, "objects": objects, "lights": lights, "stations": [station],
         "oracle": {"type": "test"}, "reference": reference or FAST}
    return parse_scene(d)


@pytest.fixture(scope="module")
def cache(tmp_path_factory):
    return tmp_path_factory.mktemp("refcache")


def render(view, cache, **settings):
    s = ref.reference_settings(view.state, **settings)
    d, receipt = ref.ensure_reference(view, cache, s)
    imgs = {n[:-4]: read_exr(d / n) for n in ref.OUTPUT_FILES if n.endswith(".exr")}
    imgs["depth"] = imgs["depth"][..., 0]
    return d, receipt, imgs


def erode(m, n=1):
    for _ in range(n):
        e = m.copy()
        e[1:] &= m[:-1]
        e[:-1] &= m[1:]
        e[:, 1:] &= m[:, :-1]
        e[:, :-1] &= m[:, 1:]
        m = e
    return m


def interior(imgs, erode_px=1):
    """Valid pixels (DESIGN §6) eroded by ``erode_px`` pixels."""
    return erode(ref.valid_pixels(imgs["depth"], imgs["normal"]), erode_px)


def assert_rel(img, expected, mask, tol, what):
    rel = np.abs(img[mask].astype(np.float64) / expected[mask] - 1.0)
    assert mask.sum() > 50, f"{what}: too few interior pixels ({mask.sum()})"
    assert rel.max() <= tol, f"{what}: max relative error {rel.max():.4f} > {tol} (mean {rel.mean():.5f})"


def plane_hits(station, w, h, z0=0.0, k=8):
    """(H, W, k*k, 3) points where a k x k grid of rays per pixel meets the plane z = z0.

    An independent pinhole model (image right = -left of the look_at frame, row 0 = top): averaging an analytic
    formula over these points gives the box-filtered pixel value the reference estimates.
    """
    M = ref.look_at_matrix(station.position, station.look_at, station.up)
    left, up, fwd = M[:3, 0], M[:3, 1], M[:3, 2]
    ty = math.tan(math.radians(station.vfov_deg) / 2)
    tx = ty * w / h
    s = (np.arange(k) + 0.5) / k
    xs = (np.arange(w)[:, None] + s[None, :]).reshape(-1) / w * 2 - 1
    ys = 1 - (np.arange(h)[:, None] + s[None, :]).reshape(-1) / h * 2
    X, Y = np.meshgrid(xs, ys)
    d = (-X * tx)[..., None] * left + (Y * ty)[..., None] * up + fwd
    p = station.position + ((z0 - station.position[2]) / d[..., 2])[..., None] * d
    return p.reshape(h, k, w, k, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, k * k, 3)


# ------------------------------------------------------------------------------------------------ settings / keys

@needs_mitsuba
def test_variant_and_version():
    v = ref.select_variant()
    assert v in ref.VARIANTS and mi.variant() == v
    assert ref.mitsuba_version() == mi.__version__
    import drjit as dr
    if "llvm_ad_rgb" in mi.variants() and dr.has_backend(dr.JitBackend.LLVM):
        assert v != "scalar_rgb", f"auto-selection fell back to scalar: {ref._state['skipped']}"


def test_settings_defaults_overrides_and_scale(tiny_scene):
    s = ref.reference_settings()
    assert s == ref.REFERENCE_DEFAULTS
    scene = tiny_scene("mini_point_plane")  # reference: spp 64, batches 2, aov_spp 4
    s = ref.reference_settings(scene)
    assert (s["spp"], s["batches"], s["aov_spp"], s["max_depth"], s["rr_depth"]) == (64, 2, 4, 64, 8)
    assert ref.reference_settings(scene, spp_scale=0.25)["spp"] == 16
    assert ref.reference_settings(scene, spp_scale=0.001)["spp"] == 2  # never below batches
    assert ref.reference_settings(scene, aov_spp=9)["aov_spp"] == 9
    with pytest.raises(ref.ReferenceError):
        ref.reference_settings(scene, batches=1)
    with pytest.raises(ref.ReferenceError):
        ref.reference_settings(scene, bogus=3)


def test_cache_key_covers_inputs(tiny_scene):
    view = expand_views(tiny_scene("mini_point_plane"))[0]
    s = ref.reference_settings(view.state)
    k = ref.cache_key(view, s, "llvm_ad_rgb", "3.9.1")
    assert k == ref.cache_key(view, dict(s), "llvm_ad_rgb", "3.9.1")
    for change in ({"spp": 128}, {"batches": 4}, {"max_depth": 3}, {"rr_depth": 2}, {"aov_spp": 8}, {"seed": 1}):
        assert ref.cache_key(view, {**s, **change}, "llvm_ad_rgb", "3.9.1") != k, change
    assert ref.cache_key(view, s, "scalar_rgb", "3.9.1") != k
    assert ref.cache_key(view, s, "llvm_ad_rgb", "3.9.2") != k
    inputs = ref.receipt_inputs(view, s, "llvm_ad_rgb", "3.9.1")
    assert inputs["view_hash"] == view.hash and inputs["reference_version"] == ref.REFERENCE_VERSION


def test_rect_matrix_maps_unit_square_and_normal():
    o, u, v = np.array([1.0, 2.0, 3.0]), np.array([0.0, 2.0, 0.0]), np.array([0.0, 0.0, 0.5])
    M = ref.rect_matrix(o, u, v)
    for s, t in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)):
        p = M @ np.array([s, t, 0.0, 1.0])
        assert np.allclose(p[:3], o + (s + 1) / 2 * u + (t + 1) / 2 * v)
    n = np.linalg.inv(M[:3, :3]).T @ np.array([0.0, 0.0, 1.0])
    assert np.allclose(n / np.linalg.norm(n), [1.0, 0.0, 0.0])  # u x v = +x
    assert np.linalg.det(M[:3, :3]) > 0


# ------------------------------------------------------------------------------------------------ analytic planes

@needs_mitsuba
def test_point_plane_matches_inverse_square(cache, tiny_scene):
    view = expand_views(tiny_scene("mini_point_plane"))[0]
    _, receipt, imgs = render(view, cache, aov_spp=64)
    mask = interior(imgs)

    def oracle(p):  # L = rho/pi * I * cos(theta) / d^2
        to_light = np.array([0.0, 0.0, 1.0]) - p
        dist = np.linalg.norm(to_light, axis=-1)
        return 0.5 / math.pi * np.array([4.0, 2.0, 1.0]) * (to_light[..., 2] / dist ** 3)[..., None]

    p = imgs["position"].astype(np.float64)
    # at the AOV hit point (what tools/oracles.py does): within 2 %
    assert_rel(imgs["direct"], oracle(p), mask, 0.02, "point direct")
    assert_rel(imgs["full"], oracle(p), mask, 0.02, "point full")
    # averaged over the pixel footprint (the exact box-filtered value): within 0.5 %
    exact = oracle(plane_hits(view.station, view.state.width, view.state.height)).mean(axis=2)
    assert_rel(imgs["direct"], exact, mask, 0.005, "point direct (footprint)")
    assert_rel(imgs["full"], exact, mask, 0.005, "point full (footprint)")
    # AOVs: upward normals, position on z = 0 where the pinhole model puts it, depth = hit distance from the
    # camera (near-clip offset corrected)
    assert np.allclose(imgs["normal"][mask], [0.0, 0.0, 1.0], atol=1e-5)
    assert np.abs(p[mask][:, 2]).max() < 1e-5
    hits = plane_hits(view.station, view.state.width, view.state.height).mean(axis=2)
    assert np.abs(hits[mask] - p[mask]).max() < 2e-3
    cam_dist = np.linalg.norm(p - np.array([0.0, 0.0, 3.0]), axis=-1)
    assert np.abs(imgs["depth"][mask] - cam_dist[mask]).max() < 1e-3
    assert receipt["inputs"]["variant"] == ref.select_variant()
    assert set(receipt["timings"]) >= {"full_s", "direct_s", "aov_s", "total_s"}
    assert len(receipt["timings"]["full_s"]) == 2


@needs_mitsuba
def test_directional_plane(cache):
    direction = np.array([-0.3, 0.2, -1.0])
    sc = make_scene("sun_plane", [PLANE], [{"name": "sun", "type": "directional", "direction": direction.tolist(),
                                           "irradiance": [3.0, 2.0, 1.0]}])
    _, _, imgs = render(expand_views(sc)[0], cache)
    mask = interior(imgs)
    cos = -direction[2] / np.linalg.norm(direction)
    expected = np.broadcast_to(0.5 / math.pi * np.array([3.0, 2.0, 1.0]) * cos, imgs["full"].shape)
    assert_rel(imgs["direct"], expected, mask, 0.02, "sun direct")
    assert_rel(imgs["full"], expected, mask, 0.02, "sun full")
    # facing away from the light: the bottom side of a two-sided plane is dark
    sc2 = make_scene("sun_plane_below", [PLANE], [{"name": "sun", "type": "directional", "direction": [0.3, 0.2, 1.0],
                                                  "irradiance": [3.0, 2.0, 1.0]}])
    _, _, imgs2 = render(expand_views(sc2)[0], cache)
    assert imgs2["full"][interior(imgs2)].max() < 1e-6


@needs_mitsuba
def test_constant_environment_plane(cache):
    sky = np.array([0.4, 0.3, 0.2])
    sc = make_scene("sky_plane", [PLANE], [{"name": "sky", "type": "environment", "radiance": sky.tolist()}],
                    station={"name": "s", "position": [0.0, -4.0, 1.0], "look_at": [0.0, 0.0, 0.3], "vfov_deg": 60})
    _, receipt, imgs = render(expand_views(sc)[0], cache, spp=1024)  # environment sampling is noisier
    mask = interior(imgs)
    expected = np.broadcast_to(0.5 * sky, imgs["full"].shape)
    assert_rel(imgs["direct"], expected, mask, 0.02, "sky direct")
    assert_rel(imgs["full"], expected, mask, 0.02, "sky full")
    miss = imgs["depth"] == 0  # misses: depth, normal and position are 0
    assert miss.sum() > 20 and np.all(imgs["normal"][miss] == 0) and np.all(imgs["position"][miss] == 0)
    sky_px = erode(miss)  # away from the horizon, where beauty samples may still hit the plane
    assert sky_px.sum() > 20
    assert np.allclose(imgs["full"][sky_px], sky, rtol=1e-4)  # the camera sees the environment where nothing is hit
    assert np.allclose(imgs["direct"][sky_px], sky, rtol=1e-4)
    assert receipt["render"]["scene"]["emitters"] == ["light_sky"]


def _polygon_irradiance(x, n, corners):
    """E / L_e at points x (..., 3) with normal n for a polygon (DESIGN §8 cal_rect_plane form factor)."""
    total = np.zeros(x.shape[:-1])
    for i in range(len(corners)):
        a, b = corners[i] - x, corners[(i + 1) % len(corners)] - x
        a = a / np.linalg.norm(a, axis=-1, keepdims=True)
        b = b / np.linalg.norm(b, axis=-1, keepdims=True)
        theta = np.arccos(np.clip(np.sum(a * b, axis=-1), -1, 1))
        c = np.cross(a, b)
        c = c / np.linalg.norm(c, axis=-1, keepdims=True)
        total += theta * (c @ n)
    return 0.5 * np.abs(total)


@needs_mitsuba
@pytest.mark.parametrize("facing", ["down", "up"])
def test_rect_light_facing(cache, facing):
    o, u, v = [-0.5, -0.5, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]  # u x v = +z: faces up (away from the plane)
    if facing == "down":
        u, v = v, u
    radiance = np.array([5.0, 4.0, 3.0])
    sc = make_scene(f"rect_{facing}", [PLANE], [{"name": "panel", "type": "rect", "origin": o, "u": u, "v": v,
                                                "radiance": radiance.tolist()}],
                    station={"name": "s", "position": [0.0, -2.5, 3.0], "look_at": [0.0, 0.0, 0.0], "vfov_deg": 70})
    view = expand_views(sc)[0]
    _, _, imgs = render(view, cache, spp=1024, batches=4)
    on_plane = interior(imgs) & (np.abs(imgs["position"][..., 2]) < 1e-4)
    panel = interior(imgs) & (np.abs(imgs["position"][..., 2] - 1.0) < 1e-4)  # the camera is above the panel
    if facing == "up":  # panel and plane normals agree, so mixed edge pixels are "valid": erode them away
        panel = erode(panel)
    assert panel.sum() > 5
    if facing == "up":
        assert imgs["full"][on_plane].max() < 1e-6, "plane under an upward-facing rect light must be dark"
        assert np.allclose(imgs["full"][panel], radiance, rtol=1e-5), "emitting side shows its radiance"
        assert np.allclose(imgs["direct"][panel], radiance, rtol=1e-5)
        assert np.allclose(imgs["normal"][panel], [0.0, 0.0, 1.0], atol=1e-5)
        return
    assert imgs["full"][panel].max() < 1e-6, "back side of a rect light (albedo 0) is black"
    assert np.allclose(imgs["normal"][panel], [0.0, 0.0, -1.0], atol=1e-5)
    corners = np.array([o, np.add(o, u), np.add(np.add(o, u), v), np.add(o, v)])
    # The irradiance curves strongly at grazing pixels, so compare with the footprint average (the box-filtered
    # pixel value); at the mean hit point alone the far pixels differ by ~1.5 %.
    E = _polygon_irradiance(plane_hits(view.station, 48, 36), np.array([0.0, 0.0, 1.0]), corners).mean(axis=2)
    expected = 0.5 / math.pi * E[..., None] * radiance
    assert_rel(imgs["direct"], expected, on_plane, 0.02, "rect direct")
    assert_rel(imgs["full"], expected, on_plane, 0.02, "rect full")
    err = (imgs["direct"] - expected)[on_plane]  # the error is the noise the stderr image claims
    ratio = np.sqrt(np.mean(err ** 2)) / np.sqrt(np.mean(imgs["direct_stderr"][on_plane] ** 2))
    assert 0.5 < ratio < 2.0, ratio


# ------------------------------------------------------------------------------------------------ orientation

@needs_mitsuba
def test_handedness_and_orientation(cache):
    """Camera above the origin looking down -Z, up = +Y: +X on the right, +Y at the top, row 0 = top."""
    lights = [{"name": "red", "type": "rect", "origin": [0.8, -0.25, 0.0], "u": [0.5, 0.0, 0.0], "v": [0.0, 0.5, 0.0],
               "radiance": [1.0, 0.0, 0.0]},
              {"name": "green", "type": "rect", "origin": [-0.25, 0.8, 0.0], "u": [0.5, 0.0, 0.0],
               "v": [0.0, 0.5, 0.0], "radiance": [0.0, 1.0, 0.0]}]
    dummy = {"name": "dummy", "material": "grey", "shape": {"type": "box", "center": [0, 0, 50], "size": [1, 1, 1]}}
    sc = make_scene("handedness", [dummy], lights, w=64, h=48)
    _, _, imgs = render(expand_views(sc)[0], cache)
    H, W = imgs["full"].shape[:2]
    for img in (imgs["full"], imgs["direct"]):
        red = img[..., 0] > 0.5
        green = img[..., 1] > 0.5
        ry, rx = np.nonzero(red)
        gy, gx = np.nonzero(green)
        assert rx.mean() > W / 2 + 8 and abs(ry.mean() - (H - 1) / 2) < 1.5, "red (+x) must be on the right"
        assert gy.mean() < H / 2 - 8 and abs(gx.mean() - (W - 1) / 2) < 1.5, "green (+y) must be at the top"
        # fully covered emitter pixels equal their radiance (linear output, no exposure)
        full_red = interior({"depth": imgs["depth"], "normal": imgs["normal"]}) & red
        assert full_red.sum() > 4 and np.allclose(img[full_red], [1.0, 0.0, 0.0], atol=1e-6)
    # projection: the red panel centre (1.05, 0, 0) lands where a pinhole camera puts it
    tan_y = math.tan(math.radians(30))
    col = (1.05 / 3.0 / (tan_y * W / H) + 1) / 2 * W - 0.5
    ry, rx = np.nonzero(imgs["full"][..., 0] > 0.5)
    assert abs(rx.mean() - col) < 0.75


# ------------------------------------------------------------------------------------------------ furnace

def _furnace(rho, le, ext=0.01):
    a, s = -1.0 - ext, 2.0 + 2 * ext  # faces overlap slightly at the edges so no ray slips between them

    def face(name, o, u, v):
        return {"name": name, "type": "rect", "origin": o, "u": u, "v": v, "radiance": [le] * 3, "albedo": [rho] * 3}

    lights = [face("zm", [a, a, -1], [s, 0, 0], [0, s, 0]), face("zp", [a, a, 1], [0, s, 0], [s, 0, 0]),
              face("xm", [-1, a, a], [0, s, 0], [0, 0, s]), face("xp", [1, a, a], [0, 0, s], [0, s, 0]),
              face("ym", [a, -1, a], [0, 0, s], [s, 0, 0]), face("yp", [a, 1, a], [s, 0, 0], [0, 0, s])]
    dummy = {"name": "dummy", "material": "grey", "shape": {"type": "box", "center": [10, 10, 10], "size": [0.1] * 3}}
    return make_scene("furnace", [dummy], lights, w=32, h=24,
                      station={"name": "c", "position": [0, 0, 0], "look_at": [1, 0.3, 0.2], "vfov_deg": 90},
                      reference={"spp": 256, "batches": 4, "aov_spp": 16})


@needs_mitsuba
def test_furnace_closed_box(cache):
    rho, le = 0.5, 1.0
    sc = _furnace(rho, le)
    for lt in sc.lights:  # every face emits inward
        c = lt.params["origin"] + (lt.params["u"] + lt.params["v"]) / 2
        assert np.dot(np.cross(lt.params["u"], lt.params["v"]), -c) > 0
    _, receipt, imgs = render(expand_views(sc)[0], cache)
    full, direct = imgs["full"].astype(np.float64), imgs["direct"].astype(np.float64)
    assert abs(full.mean() / (le / (1 - rho)) - 1) < 0.005
    assert abs(direct.mean() / (le * (1 + rho)) - 1) < 0.005
    assert np.abs(full / (le / (1 - rho)) - 1).max() < 0.06
    assert np.abs(direct / (le * (1 + rho)) - 1).max() < 0.04
    iso = full - direct
    assert abs(iso.mean() / (le * rho ** 2 / (1 - rho)) - 1) < 0.01
    # the stderr images are consistent with the observed spread around the known answer
    ratio = np.sqrt(np.mean((full - le / (1 - rho)) ** 2)) / np.sqrt(np.mean(imgs["full_stderr"] ** 2))
    assert 0.5 < ratio < 2.0, ratio
    assert receipt["noise"]["isolated"]["rel_se_mean"] < 0.01


# ------------------------------------------------------------------------------------------------ cache / files

@needs_mitsuba
def test_files_cache_hit_and_materialize(tmp_path, tiny_scene, tmp_layout, monkeypatch):
    view = expand_views(tiny_scene("mini_point_plane"))[0]
    d1, r1 = ref.ensure_reference(view, tmp_path / "cache")
    assert r1["cache_hit"] is False
    assert d1 == tmp_path / "cache" / "reference" / r1["key"]
    assert r1["key"] == ref.cache_key(view, ref.reference_settings(view.state), ref.select_variant())
    for name in ref.OUTPUT_FILES:
        assert (d1 / name).is_file(), name
    hdr = read_exr_header(d1 / "full.exr")  # station finals: FLOAT32 + ZIP (DESIGN §1)
    assert hdr["compression"] == "zip" and {c["type"] for c in hdr["channels"]} == {2}
    assert [c["name"] for c in read_exr_header(d1 / "depth.exr")["channels"]] == ["Z"]
    assert read_exr(d1 / "depth.exr").shape == (48, 64, 1)
    assert read_exr(d1 / "full.exr").shape == (48, 64, 3)
    stored = json.loads((d1 / "receipt.json").read_text(encoding="utf-8"))
    for k in ("view_hash", "spp", "batches", "max_depth", "rr_depth", "aov_spp", "seed", "variant",
              "mitsuba_version"):
        assert k in stored["inputs"], k
    assert set(stored["noise"]) == {"full", "direct", "isolated"}
    assert stored["noise"]["full"]["pixels"] == stored["valid_pixels"] > 0

    def boom(*a, **k):
        raise AssertionError("cache hit must not render")

    monkeypatch.setattr(ref, "render_view", boom)
    d2, r2 = ref.ensure_reference(view, tmp_path / "cache")
    assert d2 == d1 and r2["cache_hit"] is True and r2["key"] == r1["key"]

    out = ref.materialize(tmp_layout, view, d2, r2)
    assert out == tmp_layout.reference_dir("mini_point_plane", "top")
    for name in REFERENCE_FILES:
        assert (out / name).is_file(), name
    rec = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert rec["cache"]["key"] == r1["key"] and rec["cache"]["hit"] is True
    assert np.array_equal(read_exr(out / "full.exr"), read_exr(d1 / "full.exr"))

    # a broken entry (missing file) is re-rendered, not served
    monkeypatch.undo()
    (d1 / "normal.exr").unlink()
    d3, r3 = ref.ensure_reference(view, tmp_path / "cache")
    assert r3["cache_hit"] is False and (d3 / "normal.exr").is_file()
    assert not [p for p in d3.parent.iterdir() if p.name.startswith(".")], "temporary dirs are cleaned up"


@needs_mitsuba
def test_stderr_shrinks_with_spp(cache):
    o, u, v = [-0.5, -0.5, 1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]
    sc = make_scene("noise", [PLANE], [{"name": "panel", "type": "rect", "origin": o, "u": u, "v": v,
                                       "radiance": [5.0, 5.0, 5.0]},
                                      {"name": "sky", "type": "environment", "radiance": [0.2, 0.2, 0.2]}],
                    w=32, h=24)
    view = expand_views(sc)[0]
    se = {}
    for spp in (16, 256):
        _, receipt, imgs = render(view, cache, spp=spp, batches=4, aov_spp=16)
        m = interior(imgs)
        se[spp] = float(imgs["full_stderr"][m].mean())
        assert receipt["render"]["spp_total"] >= spp
    assert se[256] < 0.5 * se[16], se
    assert se[256] > 0


# ------------------------------------------------------------------------------------------------ timeline

@needs_mitsuba
def test_timeline_states_follow_actions(cache, tiny_scene):
    scene = tiny_scene("mini_timeline")
    views = expand_views(scene)
    assert [v.id for v in views] == ["state0", "state1", "state2"]
    descs = [ref.describe_view(v) for v in views]
    em = [{e["light"]: e for e in d["emitters"]} for d in descs]
    assert set(em[0]) == {"lamp", "sun"} and set(em[1]) == {"sun"}  # lamp switched off at frame 4
    assert np.allclose(em[2]["sun"]["irradiance"], [2.0, 1.0, 0.5])
    door = [next(m for m in d["meshes"] if m["object"] == "door") for d in descs]
    assert np.allclose(door[1]["albedo"], [0.8, 0.1, 0.1]) and np.allclose(door[2]["albedo"], [0.1, 0.8, 0.1])
    lo2, hi2 = door[2]["positions"].min(0), door[2]["positions"].max(0)  # rotated 90 deg about the origin
    assert np.allclose(lo2[:2], [-0.05, 0.0], atol=1e-6) and np.allclose(hi2[:2], [0.05, 1.0], atol=1e-6)

    keys, imgs = set(), []
    for v in views:
        _, receipt, im = render(v, cache, spp=16, batches=2, aov_spp=16)
        keys.add(receipt["key"])
        assert receipt["view"] == v.id and receipt["capture_frame"] == v.capture_frame
        imgs.append(im)
    assert len(keys) == 3
    floor = [interior(im) & (np.abs(im["position"][..., 2]) < 1e-4) & (im["position"][..., 1] < 0) for im in imgs]
    y = [ref.luminance(im["full"])[m].mean() for im, m in zip(imgs, floor)]
    assert y[1] < 0.8 * y[0], f"floor must darken when the lamp switches off: {y}"

    def door_pixels(im, lo, hi):
        p = im["position"]
        return interior(im, erode_px=0) & np.all((p >= lo - 1e-3) & (p <= hi + 1e-3), axis=-1) & (p[..., 2] > 0.05)

    d1 = door_pixels(imgs[1], np.array([0.0, -0.05, 0.0]), np.array([1.0, 0.05, 2.0]))
    d2 = door_pixels(imgs[2], np.array([-0.05, 0.0, 0.0]), np.array([0.05, 1.0, 2.0]))  # nearly edge-on now
    assert d1.sum() > 10 and d2.sum() >= 1
    c1, c2 = imgs[1]["full"][d1].mean(0), imgs[2]["full"][d2].mean(0)
    assert c1[0] > 2 * c1[1], f"door is red in state1: {c1}"
    assert c2[1] > 2 * c2[0], f"door is green in state2: {c2}"
    f1, f2 = (im["full"][m].mean(0) for im, m in zip(imgs[1:], floor[1:]))
    assert f1[0] / f1[2] < 1.2 and f2[0] / f2[2] > 3.0, f"sun turns orange in state2: {f1} -> {f2}"


# ------------------------------------------------------------------------------------------------ CLI / variants

@needs_mitsuba
def test_cli_writes_views_and_references(tmp_path, data_dir):
    run = tmp_path / "runs" / "r1"
    rc = ref.main(["--run", str(run), "--scenes", str(data_dir / "mini_point_plane.json"),
                   "--cache", str(tmp_path / "cache"), "--spp-scale", "0.5"])
    assert rc == 0
    views = json.loads((run / "views" / "mini_point_plane.json").read_text(encoding="utf-8"))
    assert [v["id"] for v in views["views"]] == ["top"]
    rdir = run / "reference" / "mini_point_plane" / "top"
    rec = json.loads((rdir / "receipt.json").read_text(encoding="utf-8"))
    assert rec["inputs"]["spp"] == 32 and rec["cache"]["hit"] is False
    assert all((rdir / n).is_file() for n in REFERENCE_FILES)
    rc = ref.main(["--run", str(run), "--scenes", str(data_dir / "mini_point_plane.json"),
                   "--cache", str(tmp_path / "cache"), "--spp-scale", "0.5"])
    assert rc == 0
    assert json.loads((rdir / "receipt.json").read_text(encoding="utf-8"))["cache"]["hit"] is True


def test_cli_reports_bad_scene(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"spec_version": 1, "name": "bad"}), encoding="utf-8")
    rc = ref.main(["--run", str(tmp_path / "run"), "--scenes", str(bad), "--cache", str(tmp_path / "cache")])
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out


@needs_mitsuba
def test_scalar_variant_agrees(tmp_path, tiny_scene):
    """The scalar_rgb fallback renders the same point-plane image (different random streams)."""
    if "scalar_rgb" not in mi.variants():
        pytest.skip("scalar_rgb not built")
    view = expand_views(tiny_scene("mini_point_plane"))[0]
    prev = ref.select_variant()
    try:
        ref.select_variant("scalar_rgb")
        d_s, r_s = ref.ensure_reference(view, tmp_path / "cache")
        assert r_s["inputs"]["variant"] == "scalar_rgb"
    finally:
        ref.select_variant(prev)
    d_v, r_v = ref.ensure_reference(view, tmp_path / "cache")
    assert r_v["inputs"]["variant"] == prev and r_v["key"] != r_s["key"]
    a, b = read_exr(d_s / "full.exr"), read_exr(d_v / "full.exr")
    m = ref.valid_pixels(read_exr(d_v / "depth.exr"), read_exr(d_v / "normal.exr"))
    m &= ref.valid_pixels(read_exr(d_s / "depth.exr"), read_exr(d_s / "normal.exr"))
    assert np.abs(a[m] / b[m] - 1).max() < 0.05
