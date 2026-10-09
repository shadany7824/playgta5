"""web/runner.py + web/harness.js: the original three.js r186 WebGL build in headless Chromium (engine 'threejs-web').

Browser tests are marked ``web`` and skip when Playwright/Chromium are missing. Bundles are tiny (64x48, few frames,
small shadow/probe maps) so the whole module runs in well under a minute on SwiftShader.
"""

from __future__ import annotations

import importlib.util
import json
import math
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from renderers.base import NotWired, launch
from renderers.threejs import CHROMIUM_SOFTWARE_ARGS, ThreeJsWeb
from tools.exr import read_exr, read_exr_header
from tools.png import load_png
from tools.spec import expand_views, parse_scene

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("web_runner", REPO / "web" / "runner.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

FAST = {"ssaa": 4, "probe_cube_size": 32, "point_shadow_map": 256, "dir_shadow_map": 512}
CLOSED_ROOM = {
    "spec_version": 1, "name": "closed_room", "group": "targeted",
    "description": "Closed room lit by one point light; camera inside.", "failure_mode": "missing indirect light",
    "image": {"width": 64, "height": 48},
    "materials": {"white": {"type": "diffuse", "albedo": [0.8, 0.8, 0.8]}},
    "objects": [{"name": "house", "material": "white",
                 "shape": {"type": "room", "min": [-2.0, -1.5, 0.0], "max": [2.0, 1.5, 2.5], "thickness": 0.1}}],
    "lights": [{"name": "lamp", "type": "point", "position": [0.0, 0.0, 2.0], "intensity": [4.0, 4.0, 4.0]}],
    "stations": [{"name": "inside", "position": [-1.6, 0.0, 1.2], "look_at": [2.0, 0.0, 1.0], "vfov_deg": 70}],
    "rois": [],
}


# ------------------------------------------------------------------------------------------------ helpers

def _require_web():
    try:
        ThreeJsWeb().check_available()
    except NotWired as e:
        pytest.skip(f"threejs-web not available: {e.reason}")


def _run(scene, mode, root: Path, options=None, capture=None, extra=()):
    """Build a bundle with renderers/threejs.py and run web/runner.py on it through renderers.base.launch."""
    eng = ThreeJsWeb(**{**FAST, **(options or {})})
    # the builder, not eng.build_bundle: mini_room's rect light is outside the engine's capabilities (DESIGN §4.4)
    # but the runner still draws it, which test_room_all_light_types_linear_output pins
    bundle = eng.builder.build(scene, mode, expand_views(scene), capture or {}, root / "bundle" / mode)
    out = root / "out" / mode
    res = launch(eng, bundle, out, timeout_s=300, extra=list(extra))
    assert res.ok, f"{res.status}: {res.reason}\n" + "\n".join(res.log_tail)
    return out


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pixel_ray_hits(width, height, pos, look_at, up, vfov_deg, plane_z=0.0):
    """Pixel-centre rays of a pinhole camera hitting the plane z = plane_z: (H, W, 3) local points."""
    pos, look_at, up = (np.asarray(v, float) for v in (pos, look_at, up))
    f = look_at - pos
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    th = math.tan(math.radians(vfov_deg) / 2)
    j, i = np.meshgrid(np.arange(width), np.arange(height))
    x = ((j + 0.5) / width) * 2 - 1
    y = 1 - ((i + 0.5) / height) * 2
    d = f + (x * th * width / height)[..., None] * r + (y * th)[..., None] * u
    t = (plane_z - pos[2]) / d[..., 2]
    return pos + t[..., None] * d


def _aces_srgb8(lin, exposure=1.0):
    """three.js r186 ACESFilmicToneMapping + sRGBTransferOETF, quantised to 8 bit (tonemapping/colorspace chunks)."""
    m_in = np.array([[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]])
    m_out = np.array([[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]])
    c = (np.asarray(lin, np.float64) * exposure / 0.6) @ m_in.T
    c = (c * (c + 0.0245786) - 0.000090537) / (c * (0.983729 * c + 0.4329510) + 0.238081)
    c = np.clip(c @ m_out.T, 0.0, 1.0)
    s = np.where(c <= 0.0031308, c * 12.92, np.power(c, 0.41666) * 1.055 - 0.055)
    return np.round(s * 255.0)


# ------------------------------------------------------------------------------------------------ no browser

def test_http_server_routes_mime_and_containment(tmp_path):
    bdir = tmp_path / "bundle"
    (bdir / "arrays").mkdir(parents=True)
    (bdir / "bundle.json").write_text("{}", encoding="utf-8")
    (bdir / "arrays" / "a.bin").write_bytes(b"\x01\x02")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    with runner.serve({"/bundle/": bdir, "/": runner.WEB_DIR}) as base:
        def get(path):
            try:
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    return r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.headers, b""

        st, h, body = get("/harness.html")
        assert st == 200 and h["Content-Type"].startswith("text/html") and b"importmap" in body
        assert h["Cross-Origin-Opener-Policy"] == "same-origin" and h["Cross-Origin-Embedder-Policy"] == "require-corp"
        assert get("/harness.js")[1]["Content-Type"].startswith("text/javascript")
        assert get("/vendor/three/build/three.module.js")[1]["Content-Type"].startswith("text/javascript")
        assert get("/bundle/bundle.json")[1]["Content-Type"].startswith("application/json")
        st, h, body = get("/bundle/arrays/a.bin")
        assert st == 200 and body == b"\x01\x02" and h["Content-Type"] == "application/octet-stream"
        for bad in ("/bundle/../secret.txt", "/bundle/%2e%2e/secret.txt", "/bundle/..%2fsecret.txt", "/bundle/",
                    "/vendor/", "/missing.js"):
            assert get(bad)[0] == 404, bad


def test_chromium_flags_and_device_heuristics(monkeypatch):
    monkeypatch.delenv("HARNESS_CHROMIUM_ARGS", raising=False)
    flags, notes = runner.chromium_flags("vulkan", "high-performance", "RTX", software=True, software_reason="x")
    assert flags == list(CHROMIUM_SOFTWARE_ARGS) and "ignored" in notes["backend"] and "not enforced" in notes["adapter"]
    flags, notes = runner.chromium_flags("vulkan", "high-performance", None, software=False)
    assert "--use-angle=vulkan" in flags and "--force_high_performance_gpu" in flags
    flags, _ = runner.chromium_flags(None, "low-power", None, software=False)
    assert not any(f.startswith("--use-angle") for f in flags)
    with pytest.raises(SystemExit):
        runner.chromium_flags("directx13", None, None, software=False)
    monkeypatch.setenv("HARNESS_CHROMIUM_ARGS", "--foo --bar=1")
    assert runner.chromium_flags(None, None, None, software=False)[0][-2:] == ["--foo", "--bar=1"]
    monkeypatch.setenv("HARNESS_WEB_SOFTWARE", "1")
    assert runner.software_required()[0] is True
    monkeypatch.setenv("HARNESS_WEB_SOFTWARE", "0")
    assert runner.software_required()[0] is False

    sw = "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)"
    nv = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 (0x00002206) Direct3D11 vs_5_0 ps_5_0, D3D11)"
    intel = "ANGLE (Intel, Intel(R) UHD Graphics 630 (0x00003E92) Direct3D11 vs_5_0 ps_5_0, D3D11)"
    arc = "ANGLE (Intel, Intel(R) Arc(TM) A770 Graphics (0x000056A0) Direct3D11 vs_5_0 ps_5_0, D3D11)"
    amd = "ANGLE (AMD, AMD Radeon RX 6800 XT (0x000073BF) Direct3D11 vs_5_0 ps_5_0, D3D11)"
    assert [runner.adapter_type(s) for s in (sw, nv, intel, arc, amd, "Mystery GPU")] == \
        ["CPU", "DiscreteGPU", "IntegratedGPU", "DiscreteGPU", "DiscreteGPU", "Unknown"]
    assert runner.angle_backend(nv) == "D3D11" and runner.angle_backend(sw) == "Vulkan"


def test_rel_change_and_decode():
    a = np.ones((2, 3, 3), np.float32)
    assert runner.rel_change(None, a) is None
    assert runner.rel_change(a, a) == 0.0
    assert runner.rel_change(a, 2 * a) == pytest.approx(0.5)
    import base64
    raw = np.arange(18, dtype="<f4")
    img = runner.decode_rgb(base64.b64encode(raw.tobytes()).decode(), 3, 2)
    assert img.shape == (2, 3, 3) and img[1, 0, 0] == 9.0


def test_skip_without_browser(tiny_scene, tmp_path):
    s = tiny_scene("mini_point_plane")
    eng = ThreeJsWeb(**FAST)
    bundle = eng.build_bundle(s, "direct", expand_views(s), {"settle_frames": 1}, tmp_path / "b")
    res = launch(eng, bundle, tmp_path / "out", timeout_s=120, extra=["--chromium", str(tmp_path / "no_chrome")])
    assert res.status == "skipped" and res.by_design and res.returncode == 2
    assert "Chromium" in res.reason or "playwright" in res.reason


# ------------------------------------------------------------------------------------------------ browser

@pytest.mark.web
def test_engine_available():
    try:
        ThreeJsWeb().check_available()
    except NotWired as e:  # a missing browser is a skip; a missing runner is a bug
        assert "runner.py" not in e.reason, e.reason
        pytest.skip(e.reason)


@pytest.mark.web
def test_point_plane_direct_matches_oracle(tiny_scene, tmp_path):
    _require_web()
    s = tiny_scene("mini_point_plane")
    out = _run(s, "direct", tmp_path, options={"ssaa": 16, "point_shadow_map": 1024}, capture={"settle_frames": 2})

    exr = out / "top" / "final.exr"
    hdr = read_exr_header(exr)
    assert {c["name"]: c["type"] for c in hdr["channels"]} == {"R": 2, "G": 2, "B": 2}  # FLOAT32
    img = read_exr(exr).astype(np.float64)
    assert img.shape == (48, 64, 3) and np.isfinite(img).all()

    st = s.stations["top"]
    P = _pixel_ray_hits(64, 48, st.position, st.look_at, st.up, st.vfov_deg)
    lamp = s.light("lamp").params
    v = lamp["position"] - P
    d2 = (v ** 2).sum(-1)
    oracle = 0.5 / math.pi * lamp["intensity"] * (v[..., 2] / np.sqrt(d2) / d2)[..., None]
    interior = (np.abs(P[..., 0]) < 1.9) & (np.abs(P[..., 1]) < 1.4)
    rel = img[interior] / oracle[interior] - 1.0
    assert interior.sum() > 1500
    assert np.abs(rel).max() < 0.01, f"max |rel| {np.abs(rel).max():.4f}"
    assert abs(rel.mean()) < 0.002

    rec = _json(out / "receipt.json")
    assert rec["receipt_version"] == 1 and rec["engine"] == "threejs-web" and rec["runner"] == "web/runner.py"
    assert (rec["scene"], rec["mode"], rec["kind"], rec["parity"]) == ("mini_point_plane", "direct", "stations", False)
    assert rec["outputs"] == ["top/final.exr"] and rec["frames"]["rendered"] == 2 and rec["frames"]["timestep"] == "fixed"
    assert rec["convergence"]["top"]["settle_frames"] == 2 and rec["convergence"]["top"]["last_rel_change"] == 0.0
    dev = rec["device"]
    assert dev["browser"].startswith("Chromium") and dev["adapter"] and dev["adapter_type"] in (
        "CPU", "DiscreteGPU", "IntegratedGPU", "Unknown") and dev["flags"] is not None
    st_ = rec["settings"]
    assert st_["measurement"]["ssaa"] == 16 and len(st_["measurement"]["ssaa_offsets"]) == 16
    assert st_["shadow_maps"]["type"] == "PCFShadowMap" and st_["shadow_maps"]["lights"]["lamp"]["mapSize"] == [1024, 1024]

    tm = _json(out / "timing.json")
    assert tm["timing_version"] == 1 and tm["units"] == "ms" and len(tm["frames"]) == 2
    assert {"gpu_texture_bytes", "gpu_buffer_bytes", "peak_rss_bytes"} <= set(tm["memory"])
    assert tm["memory"]["gpu_texture_bytes"] > 6 * 1024 * 1024 * 4  # the point light's cube shadow map at least
    assert {"seconds", "bytes", "items"} <= set(tm["precompute"])
    for f in tm["frames"]:
        assert f["station"] == "top" and f["warmup"] is True and f["cpu_ms"] >= 0
        if tm["gpu_timestamps"] and f["gpu_ms"] is not None:
            assert f["gpu_ms"] >= 0 and set(f["passes"]) == {"main", "probe"} and f["passes"]["probe"] == 0.0


@pytest.mark.web
def test_parity_png_is_aces_srgb_of_linear(tiny_scene, tmp_path):
    _require_web()
    s = tiny_scene("mini_point_plane")
    out = _run(s, "direct", tmp_path, capture={"settle_frames": 1}, extra=["--parity"])
    png = load_png(out / "top" / "final.png")
    lin = read_exr(out / "top" / "final.exr")
    assert png.shape == (48, 64, 3) and png.dtype == np.uint8
    diff = np.abs(_aces_srgb8(lin, s.display.get("exposure", 1.0)) - png)
    assert diff.max() <= 1 and diff.mean() < 0.05
    rec = _json(out / "receipt.json")
    assert rec["parity"] is True and rec["settings"]["parity"]["toneMapping"] == "ACESFilmicToneMapping"
    assert set(rec["outputs"]) == {"top/final.exr", "top/final.png"}


@pytest.mark.web
def test_room_all_light_types_linear_output(tiny_scene, tmp_path):
    _require_web()
    s = tiny_scene("mini_room")  # point + directional + rect (visible emitter) + environment
    out = _run(s, "direct", tmp_path, capture={"settle_frames": 1})
    inside, outside = read_exr(out / "inside" / "final.exr"), read_exr(out / "outside" / "final.exr")
    assert np.isfinite(inside).all() and np.isfinite(outside).all() and inside.min() >= 0
    # the rect light's emitter mesh shows its radiance unchanged (linear, no tone mapping)
    np.testing.assert_allclose(inside.reshape(-1, 3)[np.argmax(inside[..., 0])], [5.0, 5.0, 4.0], rtol=1e-4)
    # scene.background = environment radiance, seen in the outside view's top-left corner
    np.testing.assert_allclose(outside[0, 0], [0.2, 0.25, 0.3], rtol=1e-5)
    rec = _json(out / "receipt.json")
    assert rec["outputs"] == ["inside/final.exr", "outside/final.exr"]
    assert rec["settings"]["rect_area_lights"] and set(rec["settings"]["shadow_maps"]["lights"]) == {"lamp", "sun"}
    assert _json(out / "timing.json")["precompute"]["bytes"] > 0  # LTC tables


@pytest.mark.web
def test_timeline_frames_written(tiny_scene, tmp_path):
    _require_web()
    s = tiny_scene("mini_timeline")  # lamp off at frame 4; door, material and sun change at frame 8
    out = _run(s, "direct", tmp_path)
    frames = [out / "frames" / f"{k:05d}.exr" for k in range(12)]
    assert all(f.is_file() for f in frames)
    assert {c["type"] for c in read_exr_header(frames[0])["channels"]} == {1}  # HALF
    imgs = [read_exr(f) for f in frames]
    for k in (1, 2, 3):
        np.testing.assert_array_equal(imgs[k], imgs[0])  # fixed offsets, deterministic: no flicker
    assert imgs[4].mean() < 0.8 * imgs[3].mean()  # the ops of frame 4 apply before frame 4 draws
    np.testing.assert_array_equal(imgs[7], imgs[4])
    assert not np.array_equal(imgs[8], imgs[7])
    rec = _json(out / "receipt.json")
    assert rec["kind"] == "timeline" and rec["frames"]["rendered"] == 12 and len(rec["outputs"]) == 12
    tm = _json(out / "timing.json")
    assert [f["frame"] for f in tm["frames"]] == list(range(12))
    assert [f["warmup"] for f in tm["frames"]] == [True] * 8 + [False] * 4


@pytest.mark.web
def test_probe_modes_add_light_in_closed_room(tmp_path):
    _require_web()
    s = parse_scene(CLOSED_ROOM)
    cap = {"settle_frames": 3}
    direct = read_exr(_run(s, "direct", tmp_path, capture=cap) / "inside" / "final.exr").astype(np.float64)
    out_p = _run(s, "probe", tmp_path, capture=cap)
    out_d = _run(s, "probe_dynamic", tmp_path, capture=cap)
    iso_p = read_exr(out_p / "inside" / "final.exr") - direct
    iso_d = read_exr(out_d / "inside" / "final.exr") - direct
    y = np.array([0.2126, 0.7152, 0.0722])
    assert (iso_p @ y).mean() > 0.05 * (direct @ y).mean() and ((iso_p @ y) > 0).mean() > 0.99
    assert (iso_d @ y).mean() > (iso_p @ y).mean()  # multi-bounce feedback adds more than one bounce
    rp, rd = _json(out_p / "receipt.json"), _json(out_d / "receipt.json")
    assert rp["frames"]["probe_captures"] == 1 and rd["frames"]["probe_captures"] == 3
    assert rp["convergence"]["inside"]["last_rel_change"] == 0.0 and rd["convergence"]["inside"]["last_rel_change"] > 0
    tm = _json(out_p / "timing.json")
    assert [f["probe_captured"] for f in tm["frames"]] == [True, False, False]
    assert "probe_cube_target" in tm["memory"]["texture_items"]
