"""native/: the three.js r186 port on wgpu (engine 'threejs-native', DESIGN §5.3).

Runner tests build bundles with renderers/threejs.py from tests/data or inline specs and run native/runner.py
through renderers.base.launch. Physics checks use the analytic formulas (geometry computed here), not a reference.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from renderers import get_engine
from renderers.base import NotWired, launch
from renderers.threejs import ThreeJsBundleBuilder
from tools.exr import read_exr, read_exr_header
from tools.png import load_png
from tools.spec import expand_views, load_scene, parse_scene

pytestmark = pytest.mark.native

DATA = Path(__file__).resolve().parent / "data"
SMALL = dict(point_shadow_map=256, dir_shadow_map=256, probe_cube_size=32)


# ------------------------------------------------------------------------------------------------ helpers

@pytest.fixture(scope="module")
def engine():
    eng = get_engine("threejs-native")
    try:
        eng.check_available()
    except NotWired as e:
        pytest.skip(f"threejs-native not available: {e.reason}")
    return eng


def _run(engine, scene, mode, root: Path, capture=None, extra=(), builder=None, expect="ok"):
    b = ThreeJsBundleBuilder(**(builder or SMALL)).build(scene, mode, expand_views(scene), capture or {},
                                                       root / "bundle" / mode)
    out = root / "out" / mode
    res = launch(engine, b, out, timeout_s=600, extra=list(extra))
    assert res.status == expect, "\n".join(res.log_tail)
    return out, res


def _inline(d: dict, root: Path):
    return parse_scene(d, source=root / f"{d['name']}.json")


def _rays(W, H, pos, look_at, up, vfov):
    """Pinhole rays through pixel centres (row 0 = top): (H, W, 3) directions."""
    f = np.asarray(look_at, float) - np.asarray(pos, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, np.asarray(up, float))
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    t = math.tan(math.radians(vfov) / 2)
    ii, jj = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    x = (ii / W * 2 - 1) * t * W / H
    y = (1 - jj / H * 2) * t
    return f[None, None] + x[..., None] * r[None, None] + y[..., None] * u[None, None]


def _hit_plane_z(pos, d, z):
    s = (z - pos[2]) / d[..., 2]
    return np.asarray(pos, float)[None, None] + d * s[..., None]


@pytest.fixture(scope="module")
def point_plane_run(engine, tmp_path_factory):
    root = tmp_path_factory.mktemp("pp")
    scene = load_scene(DATA / "mini_point_plane.json")
    # Shipped point-shadow resolution: with point bias 0 (DESIGN §5.2) a 256 cube map self-shadows the most grazing
    # interior pixels by up to 1.3 %; at 1024 the plane is acne-free (min ratio 0.999, as with the old bias).
    out, _ = _run(engine, scene, "direct", root, {"ssaa": 4, "settle_frames": 3},
                  builder=dict(SMALL, point_shadow_map=1024))
    return scene, out


# ------------------------------------------------------------------------------------------------ shader adapter

def test_webgl_sources_are_assembled_from_vendored_chunks():
    from native.program import lambert_parameters, webgl_sources
    counts = dict(numDirLights=1, numPointLights=2, numRectAreaLights=1, numHemiLights=1, numDirLightShadows=1,
                  numPointLightShadows=2, numLightProbes=1)
    vs, fs = webgl_sources(lambert_parameters(counts, double_sided=True))
    for src in (vs, fs):
        assert src.startswith("#version 300 es\n") and "#include" not in src
        assert "#pragma unroll_loop_start" not in src  # every light loop unrolled as WebGLProgram does
        assert "NUM_POINT_LIGHTS" not in src
    assert "#define DOUBLE_SIDED" in fs and "#define USE_SHADOWMAP" in fs and "#define SHADOWMAP_TYPE_PCF" in fs
    assert "#define USE_LIGHT_PROBES" in fs and "#define OPAQUE" in fs and "#define TONE_MAPPING" not in fs
    assert "pointLights[ 1 ]" in fs and "pointShadowMap[ 1 ]" in fs
    assert "return LinearTransferOETF( vec4( value.rgb * mat3( 1.0000," in fs
    _, fs2 = webgl_sources(lambert_parameters(counts, double_sided=False, tone_mapping="ACESFilmicToneMapping",
                                              output_color_space="srgb"))
    assert "#define TONE_MAPPING" in fs2 and "return ACESFilmicToneMapping( color );" in fs2
    assert "return sRGBTransferOETF(" in fs2 and "#define DOUBLE_SIDED" not in fs2


def _normalize_vulkan_line(line: str) -> str:
    """Undo the mechanical rewrites R6/R10b/R11 on one line so it can be looked up in the WebGL source."""
    line = re.sub(r"\b(sampler2DShadow|samplerCubeShadow|sampler2D|samplerCube)\( (\w+)_tex, \2_smp \)", r"\2", line)
    line = re.sub(r"\b(\w+)_tex, (\1)_smp\b", r"\1", line)
    line = re.sub(r"\btexture2D (\w+)_tex, samplerShadow \1_smp", r"sampler2DShadow \1", line)
    line = re.sub(r"\btextureCube (\w+)_tex, samplerShadow \1_smp", r"samplerCubeShadow \1", line)
    line = re.sub(r"\btexture2D (\w+)_tex, sampler \1_smp", r"sampler2D \1", line)
    line = re.sub(r"\b(directionalShadowMap|pointShadowMap)_(\d+)\b", r"\1[ \2 ]", line)
    return re.sub(r"\s+", "", line)


def _normalize_webgl_line(line: str) -> str:
    line = re.sub(r"\bconst\s+in\b", "in", line)
    line = re.sub(r"\btexture2D\b|\btextureCube\b", "texture", line)
    line = re.sub(r"^\s*(?:(?:highp|mediump|lowp)\s+)?uniform\s+(?:(?:highp|mediump|lowp)\s+)?", "", line)
    return re.sub(r"\s+", "", line)


@pytest.mark.parametrize("which", ["lambert", "lambert_parity", "depth", "distance"])
def test_vulkanized_program_adds_only_listed_hand_written_lines(which):
    """Every line of the Vulkan GLSL is either a three.js line (modulo the mechanical rewrites) or one of the
    hand-written templates listed in docs/PHASE0.md / program.HAND_WRITTEN_LINES."""
    from native.program import (build_program, depth_parameters, distance_parameters, lambert_parameters)
    counts = dict(numDirLights=1, numPointLights=1, numRectAreaLights=1, numHemiLights=1, numDirLightShadows=1,
                  numPointLightShadows=1, numLightProbes=1)
    params = {"lambert": lambert_parameters(counts, double_sided=True),
              "lambert_parity": lambert_parameters(counts, double_sided=False, tone_mapping="ACESFilmicToneMapping",
                                                   output_color_space="srgb"),
              "depth": depth_parameters(counts), "distance": distance_parameters(counts)}[which]
    prog = build_program(params)
    allowed = [r"#version 450", r"layout\(std140, set = \d, binding = 0\) uniform Three(Frame|Object) \{", r"\};",
               r"\tuint \w+_b;", r"#define (\w+) \( \1_b != 0u \)",
               r"layout\(set = 2, binding = \d+\) uniform (texture2D|textureCube|sampler|samplerShadow) \w+;",
               r"layout\(location = \d+\) (in|out) \w+ \w+(\[ \d+ \])?;",
               r"\tgl_Position\.y = - gl_Position\.y;",
               r"\tgl_Position\.z = \( gl_Position\.z \+ gl_Position\.w \) \* 0\.5;"]
    # the uniform blocks (and the structs they use) are the union of both stages, so look lines up in both
    from native.program import strip_comments  # R2 removes comments; compare comment-free text
    webgl = strip_comments(prog.webgl_vertex) + "\n" + strip_comments(prog.webgl_fragment)
    known = {_normalize_webgl_line(x) for x in webgl.split("\n")}
    for stage in ("vertex", "fragment"):
        for line in getattr(prog, stage).split("\n"):
            if not line.strip() or any(re.fullmatch(p, line) for p in allowed):
                continue
            assert _normalize_vulkan_line(line) in known, f"{which}/{stage}: line not from three.js: {line!r}"


def _leaves(fields, prefix=""):
    """(GLSL expression, kind) for every scalar of a block, in packing order."""
    for f in fields:
        names = [f"{prefix}{f.name}[{k}]" for k in range(f.array)] if f.array else [f"{prefix}{f.name}"]
        for n in names:
            if f.struct is not None:
                yield from _leaves(f.struct.fields, n + ".")
            elif f.type == "mat4":
                yield from ((f"{n}[{c}][{r}]", "f") for c in range(4) for r in range(4))
            elif f.type == "mat3":
                yield from ((f"{n}[{c}][{r}]", "f") for c in range(3) for r in range(3))
            elif f.type in ("vec2", "vec3", "vec4"):
                yield from ((f"{n}.{'xyzw'[i]}", "f") for i in range(int(f.type[-1])))
            else:
                yield (n, "u" if f.type == "uint" else "f")


def _one_value(f, counter):
    if f.struct is not None:
        return _values(f.struct.fields, counter)
    n = {"mat4": 16, "mat3": 9, "vec2": 2, "vec3": 3, "vec4": 4}.get(f.type, 1)
    vals = [next(counter) for _ in range(n)]
    return vals if n > 1 else vals[0]


def _values(fields, counter):
    """Distinct consecutive numbers for every scalar, nested like the values BlockLayout.pack expects."""
    return {f.name: [_one_value(f, counter) for _ in range(f.array)] if f.array else _one_value(f, counter)
            for f in fields}


def test_std140_packing_matches_naga_layout(engine):
    """Pack distinct numbers with BlockLayout and read every member back through naga's layout on the GPU."""
    import itertools

    from native.device import open_device
    from native.program import build_program, lambert_parameters
    counts = dict(numDirLights=2, numPointLights=2, numRectAreaLights=1, numHemiLights=1, numDirLightShadows=1,
                  numPointLightShadows=2, numLightProbes=1)
    prog = build_program(lambert_parameters(counts, double_sided=True, tone_mapping="ACESFilmicToneMapping",
                                            output_color_space="srgb"))
    header = prog.fragment.split("#define isOrthographic")[0]
    ctx = open_device()
    wgpu = ctx.wgpu
    for block in (prog.frame_block, prog.object_block):
        leaves = list(_leaves(block.fields))
        body = "\n".join(f"\toutv[{i}] = {'float(' + e + ')' if k == 'u' else e};" for i, (e, k) in enumerate(leaves))
        code = (header + f"layout(std430, set = 2, binding = 0) buffer OutBuf {{ float outv[{len(leaves)}]; }};\n"
                "layout(local_size_x = 1) in;\nvoid main() {\n" + body + "\n}\n")
        mod = ctx.device.create_shader_module(label="compute", code=code)
        counter = itertools.count(1)
        vals = {block.aliases.get(k, k): v for k, v in _values(block.fields, counter).items()}
        U = wgpu.BufferUsage
        ubufs = []
        for blk in (prog.frame_block, prog.object_block):
            data = blk.pack(vals) if blk is block else bytes(blk.size)
            ubufs.append(ctx.create_buffer("u", blk.size, U.UNIFORM, data))
        out = ctx.create_buffer("o", 4 * len(leaves), U.STORAGE | U.COPY_SRC)
        bgls, groups = [], []
        for gi, buf, kind in ((0, ubufs[0], "uniform"), (1, ubufs[1], "uniform"), (2, out, "storage")):
            bgl = ctx.device.create_bind_group_layout(entries=[
                {"binding": 0, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": {"type": kind}}])
            bgls.append(bgl)
            groups.append((gi, ctx.device.create_bind_group(layout=bgl, entries=[
                {"binding": 0, "resource": {"buffer": buf, "offset": 0, "size": buf.size}}])))
        pipe = ctx.device.create_compute_pipeline(layout=ctx.device.create_pipeline_layout(bind_group_layouts=bgls),
                                                  compute={"module": mod, "entry_point": "main"})
        enc = ctx.device.create_command_encoder()
        cp = enc.begin_compute_pass()
        cp.set_pipeline(pipe)
        for gi, g in groups:
            cp.set_bind_group(gi, g)
        cp.dispatch_workgroups(1)
        cp.end()
        ctx.queue.submit([enc.finish()])
        got = np.frombuffer(ctx.queue.read_buffer(out), dtype=np.float32)
        np.testing.assert_array_equal(got, np.arange(1, len(leaves) + 1, dtype=np.float32), err_msg=block.name)


# ------------------------------------------------------------------------------------------------ runner outputs

def test_runner_files_receipt_and_timing_schema(point_plane_run):
    _, out = point_plane_run
    assert (out / "top" / "final.exr").is_file() and (out / "runner.log").is_file()
    hdr = read_exr_header(out / "top" / "final.exr")
    assert hdr["compression"] == "zip" and sorted(c["name"] for c in hdr["channels"]) == ["B", "G", "R"]
    assert all(c["type"] == 2 for c in hdr["channels"])  # FLOAT32
    img = read_exr(out / "top" / "final.exr")
    assert img.shape == (48, 64, 3) and img.dtype == np.float32
    r = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    for k in ("receipt_version", "engine", "engine_version", "runner", "scene", "mode", "kind", "parity", "settings",
              "device", "frames", "seed", "convergence", "outputs", "started_utc", "finished_utc", "wall_seconds",
              "host"):
        assert k in r, k
    assert r["engine"] == "threejs-native" and r["runner"] == "native/runner.py" and r["kind"] == "stations"
    assert r["engine_version"].startswith("three.js r186 port @ ")
    assert r["device"]["backend"] == "Vulkan" and r["device"]["adapter"]
    assert r["device"]["adapter_type"] in ("DiscreteGPU", "IntegratedGPU", "CPU", "VirtualGPU", "Unknown")
    assert r["frames"] == {"fps": 60, "rendered": 3, "timestep": "fixed"}
    assert r["outputs"] == ["top/final.exr"] and r["convergence"]["top"]["settle_frames"] == 3
    assert r["convergence"]["top"]["last_rel_change"] == 0.0  # static mode, deterministic frames
    s = r["settings"]
    assert s["ssaa"] == 4 and s["shadow_map_type"] == "PCFShadowMap" and s["formats"]["measurement"] == "rgba32float"
    assert s["shadow_maps"][0]["mapSize"] == [1024, 1024] and s["measurement"]["toneMapping"] == "NoToneMapping"
    t = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    assert t["timing_version"] == 1 and t["units"] == "ms" and len(t["frames"]) == 3
    for k in ("memory", "precompute", "warmup_frames", "gpu_timestamps"):
        assert k in t
    assert t["memory"]["gpu_texture_bytes"] > 256 * 256 * 6 * 4 and t["memory"]["gpu_buffer_bytes"] > 0
    assert t["memory"]["peak_rss_bytes"] > 0 and t["precompute"]["bytes"] > 0
    f0 = t["frames"][0]
    assert f0["frame"] == 0 and f0["station"] == "top" and f0["warmup"] is True and f0["cpu_ms"] > 0


def test_gpu_timestamps_present(point_plane_run):
    _, out = point_plane_run
    t = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    assert t["gpu_timestamps"] is True
    for f in t["frames"]:
        assert f["gpu_ms"] > 0 and set(f["passes"]) == {"shadow", "probe", "main", "resolve"}
        assert f["passes"]["shadow"] > 0 and f["passes"]["main"] > 0 and f["passes"]["resolve"] > 0
        assert f["passes"]["probe"] == 0  # direct mode has no probe
        assert abs(sum(f["passes"].values()) - f["gpu_ms"]) < 1e-3


def test_point_plane_matches_inverse_square_lambert(point_plane_run):
    """L = rho/pi * I * cos(theta) / d^2 on interior pixels within 1 %."""
    scene, out = point_plane_run
    img = read_exr(out / "top" / "final.exr")
    st = scene.stations["top"]
    d = _rays(64, 48, st.position, st.look_at, st.up, st.vfov_deg)
    p = _hit_plane_z(st.position, d, 0.0)
    lamp = scene.light("lamp").params
    lv = lamp["position"][None, None] - p
    d2 = np.sum(lv * lv, -1)
    cos = lv[..., 2] / np.sqrt(d2)
    rho = scene.material("grey").albedo
    expect = (rho / math.pi)[None, None] * lamp["intensity"][None, None] * (cos / d2)[..., None]
    interior = (np.abs(p[..., 0]) < 1.9) & (np.abs(p[..., 1]) < 1.4)
    ratio = img[interior] / expect[interior]
    assert interior.sum() > 1000
    assert np.all(np.abs(ratio - 1) < 0.01), (ratio.min(), ratio.max())


def test_survey_origin_world_obj_matches_point_formula(engine, tmp_path):
    scene = load_scene(DATA / "mini_survey.json")
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 4, "settle_frames": 1})
    img = read_exr(out / "top" / "final.exr")
    st = scene.stations["top"]
    z = float(scene.object("ground").mesh.positions[:, 2].mean())
    d = _rays(64, 48, st.position, st.look_at, st.up, st.vfov_deg)
    p = _hit_plane_z(st.position, d, z)
    lamp = scene.light("lamp").params
    lv = lamp["position"][None, None] - p
    d2 = np.sum(lv * lv, -1)
    expect = 0.5 / math.pi * lamp["intensity"][0] * (lv[..., 2] / np.sqrt(d2)) / d2
    lo, hi = scene.object("ground").mesh.bbox()
    interior = (p[..., 0] > lo[0] + 0.1) & (p[..., 0] < hi[0] - 0.1) & (p[..., 1] > lo[1] + 0.1) & \
               (p[..., 1] < hi[1] - 0.1)
    assert interior.sum() > 500
    np.testing.assert_allclose(img[..., 0][interior], expect[interior], rtol=0.01)


def _sky_scene(root):
    return _inline({
        "spec_version": 1, "name": "sky_plane", "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 64, "height": 48},
        "materials": {"g": {"type": "diffuse", "albedo": [0.5, 0.6, 0.7]}},
        "objects": [{"name": "plane", "material": "g",
                     "shape": {"type": "quad", "origin": [-1, -1, 0], "u": [2, 0, 0], "v": [0, 2, 0]}}],
        "lights": [{"name": "sky", "type": "environment", "radiance": [0.2, 0.3, 0.4]}],
        "stations": [{"name": "top", "position": [0, 0, 3], "look_at": [0, 0, 0], "up": [0, 1, 0], "vfov_deg": 60}]},
        root)


def test_hemisphere_sky_irradiance_and_background(engine, tmp_path):
    """environment -> HemisphereLight(sky = pi L): an up-facing plane shows rho * L, the background shows L."""
    scene = _sky_scene(tmp_path)
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 1, "settle_frames": 1})
    img = read_exr(out / "top" / "final.exr")
    st = scene.stations["top"]
    p = _hit_plane_z(st.position, _rays(64, 48, st.position, st.look_at, st.up, st.vfov_deg), 0.0)
    on = (np.abs(p[..., 0]) < 0.95) & (np.abs(p[..., 1]) < 0.95)
    off = (np.abs(p[..., 0]) > 1.05) | (np.abs(p[..., 1]) > 1.05)
    L = np.array([0.2, 0.3, 0.4])
    np.testing.assert_allclose(img[on], np.broadcast_to(L * [0.5, 0.6, 0.7], img[on].shape), rtol=1e-5)
    np.testing.assert_allclose(img[off], np.broadcast_to(L, img[off].shape), rtol=1e-6)


def test_rect_light_facing_and_lambert_receiver(engine, tmp_path):
    """Rect emitters are one-sided (FrontSide): the face along normalize(u x v) shows its radiance exactly, the
    back face is culled. r186's MeshLambertMaterial defines no RE_Direct_RectArea (lights_lambert_pars_fragment),
    so a Lambert receiver gets nothing from a RectAreaLight; the port reproduces that."""
    spec = {
        "spec_version": 1, "name": "rect_facing", "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 64, "height": 48},
        "materials": {"g": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}},
        "objects": [{"name": "ground", "material": "g",
                     "shape": {"type": "quad", "origin": [-3, -3, 0], "u": [6, 0, 0], "v": [0, 6, 0]}}],
        "lights": [{"name": "up_panel", "type": "rect", "origin": [-1.5, -0.5, 0.5], "u": [1, 0, 0], "v": [0, 1, 0],
                    "radiance": [3.0, 2.0, 1.0]},
                   {"name": "down_panel", "type": "rect", "origin": [0.5, 0.5, 0.5], "u": [1, 0, 0],
                    "v": [0, -1, 0], "radiance": [7.0, 7.0, 7.0]},
                   {"name": "sun", "type": "directional", "direction": [0, 0, -1], "irradiance": [1.0, 1.0, 1.0]}],
        "stations": [{"name": "top", "position": [0, 0, 4], "look_at": [0, 0, 0], "up": [0, 1, 0], "vfov_deg": 60}]}
    scene = _inline(spec, tmp_path)
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 1, "settle_frames": 1})
    img = read_exr(out / "top" / "final.exr")
    st = scene.stations["top"]
    d = _rays(64, 48, st.position, st.look_at, st.up, st.vfov_deg)
    p5 = _hit_plane_z(st.position, d, 0.5)
    p0 = _hit_plane_z(st.position, d, 0.0)
    up_px = (p5[..., 0] > -1.4) & (p5[..., 0] < -0.6) & (np.abs(p5[..., 1]) < 0.4)
    down_px = (p5[..., 0] > 0.6) & (p5[..., 0] < 1.25) & (np.abs(p5[..., 1]) < 0.4)  # ground seen there: in shadow
    assert up_px.sum() > 20 and down_px.sum() > 20
    np.testing.assert_allclose(img[up_px], np.broadcast_to([3.0, 2.0, 1.0], img[up_px].shape), rtol=1e-6)
    assert img[down_px].max() < 0.01 * 7.0  # back face culled: we see the ground in the panel's shadow
    ground = (np.abs(p0[..., 1]) > 0.7) & (np.abs(p0[..., 0]) < 2.5) & (np.abs(p0[..., 1]) < 2.5)
    np.testing.assert_allclose(img[ground], 0.5 / math.pi, rtol=1e-5)  # sun only: rect lights add nothing


def _occluder_scene(light, root, name):
    return _inline({
        "spec_version": 1, "name": name, "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 96, "height": 96},
        "materials": {"w": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}},
        "objects": [{"name": "ground", "material": "w",
                     "shape": {"type": "quad", "origin": [-3, -3, 0], "u": [6, 0, 0], "v": [0, 6, 0]}},
                    {"name": "occ", "material": "w", "shape": {"type": "box", "min": [-0.5, -0.5, 1.0],
                                                               "max": [0.5, 0.5, 1.2]}}],
        "lights": [light],
        "stations": [{"name": "top", "position": [0, 0, 6], "look_at": [0, 0, 0], "up": [0, 1, 0], "vfov_deg": 50}]},
        root)


@pytest.mark.parametrize("kind", ["directional", "point"])
def test_shadow_maps_put_shadows_where_geometry_says(engine, tmp_path, kind):
    if kind == "directional":
        light = {"name": "sun", "type": "directional", "direction": [0.6, 0, -1], "irradiance": [2, 2, 2]}
    else:
        light = {"name": "lamp", "type": "point", "position": [0, 0, 2], "intensity": [4, 4, 4]}
    scene = _occluder_scene(light, tmp_path, f"occ_{kind}")
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 1, "settle_frames": 1},
                  builder=dict(SMALL, point_shadow_map=512, dir_shadow_map=512))
    img = read_exr(out / "top" / "final.exr")[..., 0]
    st = scene.stations["top"]
    p = _hit_plane_z(st.position, _rays(96, 96, st.position, st.look_at, st.up, st.vfov_deg), 0.0)
    x, y = p[..., 0], p[..., 1]
    occ = (np.abs(x) <= 0.5 * 6 / 4.8 + 0.05) & (np.abs(y) <= 0.5 * 6 / 4.8 + 0.05)  # occluder top in view
    if kind == "directional":  # shadow of the box: x in [0.1, 1.22], |y| <= 0.5
        inner = (x > 0.18) & (x < 1.14) & (np.abs(y) < 0.42) & ~occ
        outer = ((x < 0.02) | (x > 1.3) | (np.abs(y) > 0.58)) & ~occ & (np.abs(x) < 2.5) & (np.abs(y) < 2.5)
        lit = 0.5 / math.pi * 2 / math.sqrt(1.36)
        np.testing.assert_allclose(img[outer], lit, rtol=1e-5)
    else:  # top face edges at z = 1.2 project to |x|,|y| <= 1.25
        inner = (np.abs(x) < 1.17) & (np.abs(y) < 1.17) & ~occ
        outer = ((np.abs(x) > 1.33) | (np.abs(y) > 1.33)) & (np.abs(x) < 2.5) & (np.abs(y) < 2.5)
        assert img[outer].min() > 0.01
    assert inner.sum() > 50 and img[inner].max() == 0.0


def test_outdoor_sun_has_no_acne_with_the_caster_fit(engine, tmp_path):
    """A tower on a 120 m ground under a 45 deg sun (the courtyard's geometry in miniature). With the shadow camera
    fitted to where shadows can fall (DESIGN §5.2) every sunlit ground pixel is exactly rho/pi E cos; the old
    whole-scene square (8 cm texels at 2048^2) shows acne on most of them."""
    from tools import oracles
    from tools.masks import erode

    d = np.array([math.sin(math.radians(45)) * math.cos(math.radians(-60)),
                  math.sin(math.radians(45)) * math.sin(math.radians(-60)), -math.cos(math.radians(45))])
    scene = _inline({
        "spec_version": 1, "name": "tower", "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 64, "height": 48},
        "materials": {"w": {"type": "diffuse", "albedo": [0.6, 0.6, 0.6]}},
        "objects": [{"name": "ground", "material": "w", "shape": {"type": "box", "min": [-60, -60, -0.5],
                                                                  "max": [60, 60, 0]}},
                    {"name": "tower", "material": "w", "shape": {"type": "box", "min": [-3, -3, -0.1],
                                                                 "max": [3, 3, 7]}}],
        "lights": [{"name": "sun", "type": "directional", "direction": d.tolist(), "irradiance": [5, 5, 5]}],
        "stations": [{"name": "s", "position": [9, -14, 5], "look_at": [3, -4, 0], "vfov_deg": 60}]}, tmp_path)
    tris = oracles.scene_triangles(scene)[0]
    aux = oracles.raycast_aux(scene, "s", 64, 48, tris=(tris, oracles.scene_triangles(scene)[1]))
    p = aux["position"]
    ground = oracles.valid_aux(aux) & (np.abs(p[..., 2]) < 1e-6) & (aux["normal"][..., 2] > 0.999)
    t, _ = oracles.raycast(tris, p.reshape(-1, 3) + [0, 0, 1e-3], np.broadcast_to(-d, (64 * 48, 3)))
    lit = erode(ground & ~np.isfinite(t).reshape(48, 64), 2)  # sunlit ground, 2 px from shadow edges
    assert lit.sum() > 500
    want = 0.6 / math.pi * 5 * float(-d[2])
    acne = {}
    for fit in ("casters", "scene"):
        out, _ = _run(engine, scene, "direct", tmp_path / fit, {"ssaa": 1, "settle_frames": 1},
                      builder=dict(SMALL, dir_shadow_map=2048, dir_shadow_fit=fit))
        img = read_exr(out / "s" / "final.exr")[..., 0]
        acne[fit] = float(np.mean(img[lit] < 0.99 * want))
        if fit == "casters":
            np.testing.assert_allclose(img[lit], want, rtol=1e-4)
    assert acne["casters"] == 0.0 and acne["scene"] > 0.1, acne


# ------------------------------------------------------------------------------------------------ determinism

def test_two_runs_bit_identical(engine, tmp_path):
    scene = load_scene(DATA / "mini_room.json")
    cap = {"ssaa": 4, "settle_frames": 3}
    a, _ = _run(engine, scene, "probe_dynamic", tmp_path / "a", cap)
    b, _ = _run(engine, scene, "probe_dynamic", tmp_path / "b", cap)
    for st in ("inside", "outside"):
        ia, ib = read_exr(a / st / "final.exr"), read_exr(b / st / "final.exr")
        assert ia.tobytes() == ib.tobytes(), st
        assert np.isfinite(ia).all() and ia.max() > 0


# ------------------------------------------------------------------------------------------------ timeline

def test_timeline_ops_change_the_image_at_their_frame(engine, tmp_path):
    scene = load_scene(DATA / "mini_timeline.json")  # steps at frames 4 and 8, end_frame 11
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 1})
    frames = [read_exr(out / "frames" / f"{k:05d}.exr") for k in range(12)]
    hdr = read_exr_header(out / "frames" / "00000.exr")
    assert hdr["compression"] == "zip" and all(c["type"] == 1 for c in hdr["channels"])  # HALF
    for k in range(1, 12):
        same = frames[k].tobytes() == frames[k - 1].tobytes()
        assert same == (k not in (4, 8)), k
    r = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert r["kind"] == "timeline" and r["frames"]["rendered"] == 12 and len(r["outputs"]) == 12
    # frame 4 switches the lamp off: darker; frame 8 makes the sun orange: red/blue ratio rises
    m = [f.reshape(-1, 3).mean(0) for f in frames]
    assert m[4].sum() < m[3].sum()
    assert m[8][0] / m[8][2] > 2 * m[7][0] / m[7][2]


def test_timeline_probe_rebaked_after_each_step(engine, tmp_path):
    scene = load_scene(DATA / "mini_timeline.json")
    out, _ = _run(engine, scene, "probe", tmp_path, {"ssaa": 1, "frames": [0, 4, 8]})
    t = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    assert [f["frame"] for f in t["frames"] if f["probe_captured"]] == [0, 4, 8]
    assert all(f["passes"]["probe"] > 0 for f in t["frames"] if f["probe_captured"])
    assert sorted(p.name for p in (out / "frames").iterdir()) == ["00000.exr", "00004.exr", "00008.exr"]


# ------------------------------------------------------------------------------------------------ probes

def _closed_room(root):
    return _inline({
        "spec_version": 1, "name": "closed_room", "group": "targeted", "failure_mode": "test", "description": "t",
        "image": {"width": 64, "height": 48},
        "materials": {"w": {"type": "diffuse", "albedo": [0.8, 0.8, 0.8]}},
        "objects": [{"name": "room", "material": "w",
                     "shape": {"type": "room", "min": [-2, -1.5, 0], "max": [2, 1.5, 2.5], "thickness": 0.1}}],
        "lights": [{"name": "lamp", "type": "point", "position": [0.5, 0.3, 2.0], "intensity": [3, 3, 3]}],
        "stations": [{"name": "in", "position": [-1.5, -1.0, 1.2], "look_at": [2, 1.5, 0.8], "vfov_deg": 75}]},
        root)


@pytest.fixture(scope="module")
def closed_room_runs(engine, tmp_path_factory):
    root = tmp_path_factory.mktemp("room")
    scene = _closed_room(root)
    outs = {}
    for mode, n in (("direct", 1), ("probe", 2), ("probe_dynamic", 4), ("probe_dynamic", 16)):
        out, _ = _run(engine, scene, mode, root / f"{mode}{n}", {"ssaa": 1, "settle_frames": n})
        outs[(mode, n)] = out
    return outs


def test_probe_modes_add_positive_isolated_light_in_closed_room(closed_room_runs):
    direct = read_exr(closed_room_runs[("direct", 1)] / "in" / "final.exr")
    probe = read_exr(closed_room_runs[("probe", 2)] / "in" / "final.exr")
    dyn = read_exr(closed_room_runs[("probe_dynamic", 16)] / "in" / "final.exr")
    iso_probe = probe - direct
    iso_dyn = dyn - direct
    assert iso_probe.mean() > 0.02 * direct.mean() and (iso_probe > 0).mean() > 0.95
    assert iso_dyn.mean() > 1.2 * iso_probe.mean()  # feedback adds further bounces


def test_probe_dynamic_converges(closed_room_runs):
    r4 = json.loads((closed_room_runs[("probe_dynamic", 4)] / "receipt.json").read_text(encoding="utf-8"))
    r16 = json.loads((closed_room_runs[("probe_dynamic", 16)] / "receipt.json").read_text(encoding="utf-8"))
    c4, c16 = r4["convergence"]["in"]["last_rel_change"], r16["convergence"]["in"]["last_rel_change"]
    assert c4 > 0 and c16 < 0.5 * c4
    t = json.loads((closed_room_runs[("probe_dynamic", 16)] / "timing.json").read_text(encoding="utf-8"))
    assert all(f["probe_captured"] for f in t["frames"])


def test_probe_sh_orientation(engine):
    """LightProbeGenerator port: light from below the probe gives a negative z (band-1) coefficient."""
    from renderers.base import load_bundle  # noqa: F401
    from native.device import GpuTimer, open_device
    from native.render import Renderer
    from native.scene import SceneState
    scene = load_scene(DATA / "mini_point_plane.json")
    bundle, arrays = ThreeJsBundleBuilder(**SMALL).bundle(scene, "probe", expand_views(scene), {"ssaa": 1})
    ctx = open_device()
    sc = SceneState(bundle, arrays)
    r = Renderer(ctx, sc, 64, 48, timer=GpuTimer(ctx))
    r.render_frame(bundle["engine_data"]["cameras"]["top"], offsets=[[0, 0]], capture_probe=True,
                   probe_feedback=False, with_probe=True, readback=False)
    sh = sc.probe_sh  # probe at z = 3 above the lit plane: all light comes from -z
    assert sh.shape == (9, 3) and np.all(sh[0] > 0) and np.all(sh[2] < 0)
    assert np.all(np.abs(sh[1]) < 0.05 * sh[0]) and np.all(np.abs(sh[3]) < 0.05 * sh[0])  # symmetric in x, y


# ------------------------------------------------------------------------------------------------ parity

def test_parity_png_and_linear_exr(engine, tmp_path):
    scene = load_scene(DATA / "mini_room.json")
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 4, "settle_frames": 1}, extra=["--parity"])
    for st in ("inside", "outside"):
        png = load_png(out / st / "final.png")
        assert png.shape[:2] == (48, 64) and png.dtype == np.uint8 and png.max() > 0
        assert (out / st / "final.exr").is_file()
    r = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert r["parity"] is True and r["settings"]["parity"]["toneMapping"] == "ACESFilmicToneMapping"
    assert r["settings"]["ssaa"] == 1 and r["settings"]["measurement"] is None
    assert "inside/final.png" in r["outputs"] and "inside/final.exr" in r["outputs"]
    # parity mode = one sample, no view offset: the linear EXR equals a 1-sample measurement render bit for bit
    one, _ = _run(engine, scene, "direct", tmp_path / "one", {"ssaa": 1, "settle_frames": 1})
    for st in ("inside", "outside"):
        assert read_exr(out / st / "final.exr").tobytes() == read_exr(one / st / "final.exr").tobytes()
    # background pixels: canvas clear colour = sRGB-encoded L, no tone mapping (WebGLBackground)
    png = load_png(out / "outside" / "final.png")
    exr = read_exr(out / "outside" / "final.exr")
    bg = np.all(np.abs(exr - np.array([0.2, 0.25, 0.3], np.float32)) < 1e-6, axis=-1)
    assert bg.sum() > 100
    L = np.array([0.2, 0.25, 0.3])
    enc = np.where(L < 0.0031308, L * 12.92, 1.055 * L ** 0.41666 - 0.055)
    assert np.all(np.abs(png[bg][:, :3].astype(int) - np.round(enc * 255).astype(int)) <= 1)


# ------------------------------------------------------------------------------------------------ exit codes

def test_unavailable_backend_is_a_by_design_skip(engine, tmp_path):
    scene = load_scene(DATA / "mini_point_plane.json")
    _, res = _run(engine, scene, "direct", tmp_path, {"ssaa": 1, "settle_frames": 1},
                  extra=["--backend", "metal" if not __import__("sys").platform == "darwin" else "d3d12"],
                  expect="skipped")
    assert res.returncode == 2 and "adapter" in res.reason


def test_adapter_substring_selection(engine, tmp_path):
    ads = engine.adapters()
    name = str(ads[0].get("device", ""))
    scene = load_scene(DATA / "mini_point_plane.json")
    out, _ = _run(engine, scene, "direct", tmp_path, {"ssaa": 1, "settle_frames": 1},
                  extra=["--adapter", name[:6], "--power", "low-power"])
    r = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert r["device"]["adapter"] == name
    _, res = _run(engine, scene, "direct", tmp_path / "x", {"ssaa": 1, "settle_frames": 1},
                  extra=["--adapter", "no-such-adapter-xyz"], expect="skipped")
    assert "no-such-adapter-xyz" in res.reason


# ------------------------------------------------------------------------------------------------ vs real three.js

_CAPTURE_PAGE = """<!doctype html><html><body><script type="importmap">{"imports": {"three": "/build/three.module.js"}}
</script><script type="module">
import * as THREE from 'three';
import { RectAreaLightUniformsLib } from '/examples/jsm/lights/RectAreaLightUniformsLib.js';
RectAreaLightUniformsLib.init();
const renderer = new THREE.WebGLRenderer({ canvas: document.createElement('canvas') });
renderer.setSize(64, 48, false);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
const gl = renderer.getContext(); const srcs = []; const orig = gl.shaderSource.bind(gl);
gl.shaderSource = (s, src) => { srcs.push(src); orig(s, src); };
const scene = new THREE.Scene();
const sun = new THREE.DirectionalLight(0xffffff, 1); sun.castShadow = true; sun.position.set(1, 2, 3);
scene.add(sun); scene.add(sun.target);
const lamp = new THREE.PointLight(0xffffff, 1, 0, 2); lamp.castShadow = true; lamp.position.set(0, 0, 2);
scene.add(lamp);
scene.add(new THREE.HemisphereLight(0xffffff, 0x000000, 1));
const rect = new THREE.RectAreaLight(0xffffff, 1, 1, 1); rect.position.set(0, 0, 2); scene.add(rect);
scene.add(new THREE.LightProbe());
const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0,0,0, 1,0,0, 0,1,0]), 3));
geo.setAttribute('normal', new THREE.BufferAttribute(new Float32Array([0,0,1, 0,0,1, 0,0,1]), 3));
const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ side: THREE.DoubleSide }));
mesh.castShadow = mesh.receiveShadow = true; scene.add(mesh);
const cam = new THREE.PerspectiveCamera(60, 64 / 48, 0.05, 1000); cam.position.set(0, -3, 2); cam.lookAt(0, 0, 0);
renderer.setRenderTarget(new THREE.WebGLRenderTarget(64, 48, { type: THREE.FloatType }));
renderer.render(scene, cam);
const n1 = srcs.length;
renderer.setRenderTarget(null); renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.render(scene, cam);
window.__out = { srcs, n1 };
</script></body></html>"""


def _capture_threejs_glsl() -> dict:
    """GLSL strings real three.js r186 (the vendored build) passes to gl.shaderSource in headless Chromium."""
    import functools
    import http.server
    import socketserver
    import threading

    pw = pytest.importorskip("playwright.sync_api")
    from renderers.threejs import CHROMIUM_SOFTWARE_ARGS, VENDOR_DIR, find_chromium
    exe = find_chromium()
    if exe is None:
        pytest.skip("no Chromium for the three.js reference")

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/capture.html":
                body = _CAPTURE_PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(VENDOR_DIR)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pw.sync_playwright() as p:
            browser = p.chromium.launch(executable_path=str(exe), args=list(CHROMIUM_SOFTWARE_ARGS))
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/capture.html")
            page.wait_for_function("window.__out !== undefined", timeout=120000)
            out = page.evaluate("window.__out")
            browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
    return out


def _tokens(text: str) -> list[str]:
    from native.program import strip_comments
    return re.findall(r"[A-Za-z_]\w*|\d+\.\d*(?:e[+-]?\d+)?|\.\d+(?:e[+-]?\d+)?|\d+(?:e[+-]?\d+)?|\S",
                      strip_comments(text))


@pytest.mark.slow
@pytest.mark.web
def test_webgl_sources_token_identical_to_real_threejs():
    """program.webgl_sources == what the unmodified r186 build compiles, token for token (the build ships its GLSL
    with comments/blank lines stripped, so comments and whitespace are not compared)."""
    from native.program import depth_parameters, distance_parameters, lambert_parameters, webgl_sources
    out = _capture_threejs_glsl()
    srcs = out["srcs"]
    counts = dict(numDirLights=1, numPointLights=1, numRectAreaLights=1, numHemiLights=1, numDirLightShadows=1,
                  numPointLightShadows=1, numLightProbes=1)
    ours = {"depth": webgl_sources(depth_parameters(counts)), "distance": webgl_sources(distance_parameters(counts)),
            "lambert": webgl_sources(lambert_parameters(counts, double_sided=True)),
            "lambert_parity": webgl_sources(lambert_parameters(counts, double_sided=True,
                                                               tone_mapping="ACESFilmicToneMapping",
                                                               output_color_space="srgb"))}
    seen = set()
    assert len(srcs) == 8
    for i in range(0, len(srcs), 2):
        st = re.search(r"#define SHADER_TYPE (\w+)", srcs[i]).group(1)
        key = {"MeshDepthMaterial": "depth", "MeshDistanceMaterial": "distance"}.get(
            st, "lambert" if i < out["n1"] else "lambert_parity")
        seen.add(key)
        for stage, theirs, mine in (("vertex", srcs[i], ours[key][0]), ("fragment", srcs[i + 1], ours[key][1])):
            assert _tokens(theirs) == _tokens(mine), f"{key}/{stage} differs from three.js"
    assert seen == set(ours)


# ------------------------------------------------------------------------------------------------ JS-side ports

def test_three_math_matches_linear_algebra():
    from native import three_math as tm
    rng = np.random.default_rng(3)
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    M = tm.m4_compose((1.5, -2.0, 0.25), tuple(q), (1.0, 2.0, 0.5))
    A = np.asarray(M).reshape(4, 4).T  # column-major elements -> row-major maths matrix
    np.testing.assert_allclose(np.asarray(tm.m4_invert(M)).reshape(4, 4).T, np.linalg.inv(A), atol=1e-12)
    np.testing.assert_allclose(np.asarray(tm.m4_multiply(M, tm.m4_invert(M))).reshape(4, 4), np.eye(4), atol=1e-12)
    N = np.asarray(tm.m3_normal_matrix(M)).reshape(3, 3).T
    np.testing.assert_allclose(N, np.linalg.inv(A[:3, :3]).T, atol=1e-12)
    pos, q2, s = tm.m4_decompose(M)
    np.testing.assert_allclose(s, (1.0, 2.0, 0.5), atol=1e-12)
    assert np.allclose(q2, q, atol=1e-12) or np.allclose(q2, -q, atol=1e-12)


def test_camera_view_offset_shifts_by_pixels():
    """setViewOffset(W, H, dx, dy, W, H) moves the projected image by -dx, +dy pixels (y measured downwards)."""
    from native import three_math as tm
    W, H = 64, 48
    cam = tm.PerspectiveCamera(60, W / H, 0.05, 100, up=(0, 0, 1))
    cam.position = (0.0, -3.0, 1.0)
    cam.look_at((0.3, 0.0, 0.8))
    cam.update_matrix_world()

    def pix():  # pixel position (x right, y down) of a fixed world point
        P = np.asarray(cam.projection_matrix).reshape(4, 4).T
        V = np.asarray(cam.matrix_world_inverse).reshape(4, 4).T
        clip = P @ V @ np.array([0.2, 0.5, 0.9, 1.0])
        ndc = clip[:2] / clip[3]
        return np.array([(ndc[0] + 1) / 2 * W, (1 - ndc[1]) / 2 * H])

    p0 = pix()
    cam.set_view_offset(W, H, 0.25, -0.375, W, H)
    np.testing.assert_allclose(pix() - p0, [-0.25, 0.375], atol=1e-9)
    cam.clear_view_offset()
    np.testing.assert_allclose(pix(), p0, atol=1e-12)


def test_cube_cameras_look_along_the_six_axes():
    from native.probe import cube_cameras
    cams = cube_cameras((1.0, 2.0, 3.0), 0.05, 100)
    expect = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    for cam, e in zip(cams, expect, strict=True):
        w = np.asarray(cam.matrix_world).reshape(4, 4).T
        np.testing.assert_allclose(w[:3, 3], (1.0, 2.0, 3.0), atol=1e-12)
        np.testing.assert_allclose(-w[:3, 2], e, atol=1e-12)  # cameras look down local -Z
        assert cam.projection_matrix[5] < 0 and cam.projection_matrix[0] < 0  # fov = -90 flips x and y


def test_rect_and_environment_timeline_ops_update_emitter_and_background(tmp_path):
    from native.scene import SceneState
    spec = {"spec_version": 1, "name": "ops", "group": "targeted", "failure_mode": "t", "description": "t",
            "image": {"width": 16, "height": 12},
            "materials": {"g": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}},
            "objects": [{"name": "q", "material": "g",
                         "shape": {"type": "quad", "origin": [-1, -1, 0], "u": [2, 0, 0], "v": [0, 2, 0]}}],
            "lights": [{"name": "panel", "type": "rect", "origin": [0, 0, 1], "u": [1, 0, 0], "v": [0, -1, 0],
                        "radiance": [2, 2, 2]},
                       {"name": "sky", "type": "environment", "radiance": [0.1, 0.2, 0.3]}],
            "stations": [{"name": "s0", "position": [0, 0, 3], "look_at": [0, 0, 0], "up": [0, 1, 0]}],
            "timeline": {"station": "s0", "end_frame": 3, "steps": [{"frame": 2, "actions": [
                {"op": "set_light", "light": "panel", "radiance": [4, 0, 0]},
                {"op": "set_light", "light": "sky", "radiance": [0.5, 0.5, 0.5]}]}]}}
    scene = _inline(spec, tmp_path)
    bundle, arrays = ThreeJsBundleBuilder(**SMALL).bundle(scene, "direct", expand_views(scene), {})
    sc = SceneState(bundle, arrays)
    assert sc.apply_events(1) is False
    assert sc.apply_events(2) is True
    emitter = sc.drawable("panel")
    assert emitter.emitter and emitter.material.emissive == [4.0, 0.0, 0.0] and emitter.material.side == "FrontSide"
    assert sc.light("panel").intensity == 4.0 and sc.light("panel").color == [1.0, 0.0, 0.0]
    assert sc.background == [0.5, 0.5, 0.5] and sc.light("sky").intensity == pytest.approx(math.pi * 0.5)
