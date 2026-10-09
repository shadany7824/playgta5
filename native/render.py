"""The native three.js r186 frame: shadow maps -> (probe capture) -> main passes (SSAA) -> resolve -> readback.

Render-loop order follows WebGLRenderer.render (WebGLRenderer.js:1640-1830): shadow maps first (shadowMap.render),
then lights set up for the camera, background clear, opaque objects. Everything is drawn in WebGL's memory layout
(clip-space y negated in the vertex stage, front faces clockwise, rows bottom-up) so that gl_FragCoord, shadow-map
texel addressing and cube-face sampling equal WebGL's; images are flipped to top-row-first on readback, exactly
like the web runner's readPixels. See docs/PHASE0.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from . import three_math as tm
from .device import GpuContext, GpuTimer
from .probe import cube_cameras, sh_from_cube_faces
from .program import (FRAME_SET, OBJECT_SET, TEXTURE_SET, Program, build_program, depth_parameters,
                      distance_parameters, lambert_parameters)
from .scene import Drawable, SceneState, light_counts, light_uniforms, object_uniforms
from .shadows import DEPTH_FORMAT, SHADOW_SIDE, ShadowSetup, shadow_setups
from .three_chunks import ltc_tables

__all__ = ["Renderer", "FrameResult", "MEASURE_FORMAT", "PARITY_FORMAT", "PROBE_FORMAT", "RESOLVE_WGSL"]

MEASURE_FORMAT = "rgba32float"  # FloatType RGBA render target (DESIGN §5.1 measurement mode)
PARITY_FORMAT = "rgba8unorm"  # the 8-bit canvas drawing buffer
PROBE_FORMAT = "rgba16float"  # WebGLCubeRenderTarget type HalfFloatType
_FORMAT_FOR_TYPE = {"HalfFloatType": "rgba16float", "FloatType": "rgba32float", "UnsignedByteType": "rgba8unorm"}

# Harness-side SSAA averaging (not three.js maths): acc = sum_s sample_s * (1/N), in a fixed order.
RESOLVE_WGSL = """
struct Params { width: u32, height: u32, weight: f32, first: u32 };
@group(0) @binding(0) var src: texture_2d<f32>;
@group(0) @binding(1) var<storage, read_write> acc: array<vec4<f32>>;
@group(0) @binding(2) var<uniform> params: Params;
@compute @workgroup_size(8, 8)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    if (id.x >= params.width || id.y >= params.height) { return; }
    let c = textureLoad(src, vec2<i32>(i32(id.x), i32(id.y)), 0) * params.weight;
    let i = id.y * params.width + id.x;
    if (params.first == 1u) { acc[i] = c; } else { acc[i] = acc[i] + c; }
}
"""


def _align(x: int, a: int) -> int:
    return (x + a - 1) // a * a


class UniformArena:
    """One dynamic-offset uniform buffer per frame segment; slots are 256-byte aligned."""

    def __init__(self, ctx: GpuContext, capacity: int = 1 << 20):
        self.ctx = ctx
        self.align = max(256, int(ctx.device.limits.get("min-uniform-buffer-offset-alignment", 256)))
        self.capacity = 0
        self.generation = 0
        self.data = bytearray()
        self.buffer = None
        self._ensure(capacity)

    def _ensure(self, size: int) -> None:
        if size <= self.capacity:
            return
        cap = max(size, 2 * self.capacity, 1 << 16)
        wgpu = self.ctx.wgpu
        self.buffer = self.ctx.create_buffer(f"uniform-arena.{self.generation + 1}", cap,
                                             wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
        self.capacity = cap
        self.generation += 1

    def reset(self) -> None:
        self.data = bytearray()
        self._base = 0

    def begin_segment(self) -> None:
        self._base = len(self.data)

    def alloc(self, payload: bytes) -> int:
        off = _align(len(self.data), self.align)
        self.data.extend(b"\0" * (off - len(self.data)))
        self.data.extend(payload)
        return off

    def upload_segment(self) -> bool:
        """Write the current segment; returns True when the buffer had to grow (bind groups must be rebuilt)."""
        grew = False
        if len(self.data) + 256 > self.capacity:
            self._ensure(len(self.data) + 256)
            grew = True
            self.ctx.queue.write_buffer(self.buffer, 0, bytes(self.data))
        elif len(self.data) > self._base:
            self.ctx.queue.write_buffer(self.buffer, self._base, bytes(self.data[self._base:]))
        return grew


@dataclass
class FrameResult:
    cpu_ms: float
    wall_ms: float
    gpu_passes: dict
    image: np.ndarray | None = None  # (H, W, 4) float32, top row first
    probe_captured: bool = False


@dataclass
class _ProgramState:
    program: Program
    pipeline_layout: object
    bgl: list
    bind_groups: dict = field(default_factory=dict)
    pipelines: dict = field(default_factory=dict)


class Renderer:
    """Owns GPU resources for one bundle and renders frames."""

    def __init__(self, ctx: GpuContext, scene: SceneState, width: int, height: int, *, timer: GpuTimer,
                 exposure: float = 1.0):
        self.ctx = ctx
        self.wgpu = ctx.wgpu
        self.device = ctx.device
        self.scene = scene
        self.width, self.height = int(width), int(height)
        self.timer = timer
        self.exposure = float(exposure)
        self.arena = UniformArena(ctx)
        self.precompute: dict[str, float] = {"shader_build_s": 0.0, "pipeline_s": 0.0}
        self.max_texture_size = int(ctx.device.limits.get("max-texture-dimension-2d", 8192))
        self._programs: dict[tuple, _ProgramState] = {}
        self._upload_geometry()
        self._create_ltc()
        self._create_shadow_maps()
        self._create_targets()
        self._create_resolve()

    # ------------------------------------------------------------------------------------------- resources
    def _upload_geometry(self) -> None:
        U = self.wgpu.BufferUsage
        for d in self.scene.drawables:
            pos = np.ascontiguousarray(d.positions, dtype=np.float32)
            nrm = np.ascontiguousarray(d.normals, dtype=np.float32)
            idx = np.ascontiguousarray(d.indices, dtype=np.uint32).reshape(-1)
            d.gpu = {"position": self.ctx.create_buffer(f"{d.name}.position", pos.nbytes, U.VERTEX, pos.tobytes()),
                     "normal": self.ctx.create_buffer(f"{d.name}.normal", nrm.nbytes, U.VERTEX, nrm.tobytes()),
                     "index": self.ctx.create_buffer(f"{d.name}.index", idx.nbytes, U.INDEX, idx.tobytes()),
                     "count": int(idx.size)}

    def _create_ltc(self) -> None:
        """RectAreaLightUniformsLib.init textures; WebGLLights.js:471-483 picks FLOAT when float-linear filtering
        exists (OES_texture_float_linear <-> float32-filterable), else the HALF copies."""
        t1, t2 = ltc_tables()
        T = self.wgpu.TextureUsage
        use_float = "float32-filterable" in self.ctx.features
        self.ltc_format = "rgba32float" if use_float else "rgba16float"
        self.ltc = []
        for i, t in enumerate((t1, t2)):
            tex = self.ctx.create_texture(f"ltc_{i + 1}", (64, 64, 1), self.ltc_format, T.TEXTURE_BINDING | T.COPY_DST)
            data = t if use_float else t.astype(np.float16)
            self.ctx.queue.write_texture({"texture": tex}, np.ascontiguousarray(data).tobytes(),
                                         {"bytes_per_row": 64 * data.itemsize * 4}, (64, 64, 1))
            self.ltc.append(tex.create_view())
        self.precompute_bytes = int(t1.nbytes + t2.nbytes) if use_float else int(t1.nbytes + t2.nbytes) // 2
        # DataTexture( ..., ClampToEdgeWrapping, ClampToEdgeWrapping, LinearFilter (mag), NearestFilter (min) )
        self.ltc_sampler = self.device.create_sampler(mag_filter="linear", min_filter="nearest")
        # PCFShadowMap depth textures: compareFunction LessEqualCompare, Linear filters (WebGLShadowMap.js:261-265)
        self.shadow_sampler = self.device.create_sampler(mag_filter="linear", min_filter="linear",
                                                         compare="less-equal")

    def _create_shadow_maps(self) -> None:
        T = self.wgpu.TextureUsage
        self.shadow_maps: dict[str, dict] = {}
        for s in shadow_setups(self.scene, self.max_texture_size):
            w, h = s.map_size
            if s.kind == "point":
                tex = self.ctx.create_texture(f"{s.light}.shadowMap", (w, w, 6), DEPTH_FORMAT,
                                              T.RENDER_ATTACHMENT | T.TEXTURE_BINDING)
                faces = [tex.create_view(dimension="2d", base_array_layer=i, array_layer_count=1) for i in range(6)]
                sample = tex.create_view(dimension="cube")
            else:
                tex = self.ctx.create_texture(f"{s.light}.shadowMap", (w, h, 1), DEPTH_FORMAT,
                                              T.RENDER_ATTACHMENT | T.TEXTURE_BINDING)
                faces = [tex.create_view()]
                sample = faces[0]
            self.shadow_maps[s.light] = {"texture": tex, "faces": faces, "sample": sample, "kind": s.kind}

    def _create_targets(self) -> None:
        T = self.wgpu.TextureUsage
        W, H = self.width, self.height
        self.color = self.ctx.create_texture("main.color", (W, H, 1), MEASURE_FORMAT,
                                             T.RENDER_ATTACHMENT | T.TEXTURE_BINDING | T.COPY_SRC)
        self.color_view = self.color.create_view()
        self.depth = self.ctx.create_texture("main.depth", (W, H, 1), DEPTH_FORMAT, T.RENDER_ATTACHMENT)
        self.depth_view = self.depth.create_view()
        self.parity_target = None
        cfg = self.scene.probe_cfg
        self.probe_size = int(cfg.get("cubeSize", 128))
        self.probe_format = _FORMAT_FOR_TYPE.get(cfg.get("type", "HalfFloatType"), PROBE_FORMAT)
        self.probe_target = None
        if cfg.get("enabled"):
            S = self.probe_size
            self.probe_target = self.ctx.create_texture("probe.cube", (S, S, 6), self.probe_format,
                                                        T.RENDER_ATTACHMENT | T.COPY_SRC)
            self.probe_faces = [self.probe_target.create_view(dimension="2d", base_array_layer=i, array_layer_count=1)
                                for i in range(6)]
            self.probe_depth = self.ctx.create_texture("probe.depth", (S, S, 1), DEPTH_FORMAT, T.RENDER_ATTACHMENT)
            self.probe_depth_view = self.probe_depth.create_view()
            bpp = 8 if self.probe_format == "rgba16float" else (16 if self.probe_format == "rgba32float" else 4)
            self.probe_bpr = _align(S * bpp, 256)
            U = self.wgpu.BufferUsage
            self.probe_readback = self.ctx.create_buffer("probe.readback", self.probe_bpr * S * 6,
                                                         U.COPY_DST | U.MAP_READ)

    def _ensure_parity_target(self) -> None:
        if self.parity_target is None:
            T = self.wgpu.TextureUsage
            self.parity_target = self.ctx.create_texture("parity.color", (self.width, self.height, 1), PARITY_FORMAT,
                                                         T.RENDER_ATTACHMENT | T.COPY_SRC)
            self.parity_view = self.parity_target.create_view()

    def _create_resolve(self) -> None:
        U = self.wgpu.BufferUsage
        W, H = self.width, self.height
        self.acc = self.ctx.create_buffer("resolve.acc", W * H * 16, U.STORAGE | U.COPY_SRC)
        self.resolve_params = self.ctx.create_buffer("resolve.params", 512, U.UNIFORM | U.COPY_DST)
        mod = self.device.create_shader_module(label="resolve", code=RESOLVE_WGSL)
        S = self.wgpu.ShaderStage
        bgl = self.device.create_bind_group_layout(entries=[
            {"binding": 0, "visibility": S.COMPUTE, "texture": {"sample_type": "unfilterable-float"}},
            {"binding": 1, "visibility": S.COMPUTE, "buffer": {"type": "storage"}},
            {"binding": 2, "visibility": S.COMPUTE, "buffer": {"type": "uniform", "has_dynamic_offset": True,
                                                               "min_binding_size": 16}}])
        self.resolve_pipeline = self.device.create_compute_pipeline(
            layout=self.device.create_pipeline_layout(bind_group_layouts=[bgl]),
            compute={"module": mod, "entry_point": "main"})
        self.resolve_bg = self.device.create_bind_group(layout=bgl, entries=[
            {"binding": 0, "resource": self.color_view},
            {"binding": 1, "resource": {"buffer": self.acc, "offset": 0, "size": W * H * 16}},
            {"binding": 2, "resource": {"buffer": self.resolve_params, "offset": 0, "size": 16}}])
        self._resolve_n = None

    def _set_resolve_weight(self, n: int) -> None:
        if self._resolve_n == n:
            return
        p0 = np.array([self.width, self.height, 0, 1], dtype=np.uint32)
        p1 = np.array([self.width, self.height, 0, 0], dtype=np.uint32)
        w = np.float32(1.0 / n)
        p0.view(np.float32)[2] = w
        p1.view(np.float32)[2] = w
        data = bytearray(512)
        data[0:16] = p0.tobytes()
        data[256:272] = p1.tobytes()
        self.ctx.queue.write_buffer(self.resolve_params, 0, bytes(data))
        self._resolve_n = n

    # ------------------------------------------------------------------------------------------- programs
    def _program_state(self, key: tuple, params: dict) -> _ProgramState:
        st = self._programs.get(key)
        if st is not None:
            return st
        t0 = time.perf_counter()
        prog = build_program(params)
        S = self.wgpu.ShaderStage
        entries0 = [{"binding": 0, "visibility": S.VERTEX | S.FRAGMENT,
                     "buffer": {"type": "uniform", "has_dynamic_offset": True,
                                "min_binding_size": prog.frame_block.size}}]
        entries1 = [{"binding": 0, "visibility": S.VERTEX | S.FRAGMENT,
                     "buffer": {"type": "uniform", "has_dynamic_offset": True,
                                "min_binding_size": prog.object_block.size}}]
        entries2 = []
        for tb in prog.textures:
            entries2.append({"binding": tb.tex_binding, "visibility": S.FRAGMENT,
                             "texture": {"sample_type": tb.sample_type, "view_dimension": tb.dimension}})
            entries2.append({"binding": tb.smp_binding, "visibility": S.FRAGMENT,
                             "sampler": {"type": "comparison" if tb.sample_type == "depth" else "filtering"}})
        bgl = [self.device.create_bind_group_layout(entries=entries0),
               self.device.create_bind_group_layout(entries=entries1),
               self.device.create_bind_group_layout(entries=entries2)]
        layout = self.device.create_pipeline_layout(bind_group_layouts=bgl)
        st = _ProgramState(prog, layout, bgl)
        st.vertex_module = self.device.create_shader_module(label="vertex", code=prog.vertex)
        st.fragment_module = None
        self._programs[key] = st
        self.precompute["shader_build_s"] += time.perf_counter() - t0
        return st

    def _fragment_module(self, st: _ProgramState):
        if st.fragment_module is None:
            t0 = time.perf_counter()
            st.fragment_module = self.device.create_shader_module(label="fragment", code=st.program.fragment)
            self.precompute["shader_build_s"] += time.perf_counter() - t0
        return st.fragment_module

    def lambert(self, *, side: str, with_probe: bool, parity: bool) -> _ProgramState:
        """MeshLambertMaterial program for a material side; parity = drawing to the canvas (ACES + sRGB),
        otherwise a render target (NoToneMapping, working colour space) as WebGLPrograms.js:177-213 decides."""
        counts = light_counts(self.scene, with_probe)
        tmap = "ACESFilmicToneMapping" if parity else "NoToneMapping"
        ocs = "srgb" if parity else "srgb-linear"
        params = lambert_parameters(counts, double_sided=side == "DoubleSide", tone_mapping=tmap,
                                    output_color_space=ocs,
                                    shadow_map_type=self.scene.renderer_cfg.get("shadowMapType", "PCFShadowMap"))
        params["flipSided"] = side == "BackSide"
        return self._program_state(("lambert", side, with_probe, parity), params)

    def depth_program(self, point: bool) -> _ProgramState:
        counts = light_counts(self.scene, False)
        params = distance_parameters(counts) if point else depth_parameters(counts)
        return self._program_state(("distance" if point else "depth",), params)

    def _bind_groups(self, st: _ProgramState) -> tuple:
        gen = self.arena.generation
        bg = st.bind_groups.get(gen)
        if bg is None:
            prog = st.program
            g0 = self.device.create_bind_group(layout=st.bgl[0], entries=[
                {"binding": 0, "resource": {"buffer": self.arena.buffer, "offset": 0, "size": prog.frame_block.size}}])
            g1 = self.device.create_bind_group(layout=st.bgl[1], entries=[
                {"binding": 0, "resource": {"buffer": self.arena.buffer, "offset": 0,
                                            "size": prog.object_block.size}}])
            entries = []
            for tb in prog.textures:
                view, smp = self._texture_for(tb.name)
                entries.append({"binding": tb.tex_binding, "resource": view})
                entries.append({"binding": tb.smp_binding, "resource": smp})
            g2 = self.device.create_bind_group(layout=st.bgl[2], entries=entries)
            bg = (g0, g1, g2)
            st.bind_groups = {gen: bg}
        return bg

    def _texture_for(self, name: str):
        if name in ("ltc_1", "ltc_2"):
            return self.ltc[int(name[-1]) - 1], self.ltc_sampler
        # directionalShadowMap_i / pointShadowMap_i follow WebGLLights order (shadow casters first, bundle order)
        kind, i = name.rsplit("_", 1)
        want = "directional" if kind == "directionalShadowMap" else "point"
        maps = [m for m in self.shadow_maps.values() if m["kind"] == want]
        return maps[int(i)]["sample"], self.shadow_sampler

    def _pipeline(self, st: _ProgramState, color_format: str | None, cull: str, front_face: str):
        key = (color_format, cull, front_face)
        p = st.pipelines.get(key)
        if p is not None:
            return p
        t0 = time.perf_counter()
        prog = st.program
        buffers = [{"array_stride": 12, "step_mode": "vertex",
                    "attributes": [{"format": "float32x3", "offset": 0, "shader_location": loc}]}
                   for name, loc in sorted(prog.attributes.items(), key=lambda kv: kv[1])]
        desc = {"layout": st.pipeline_layout,
                "vertex": {"module": st.vertex_module, "entry_point": "main", "buffers": buffers},
                "primitive": {"topology": "triangle-list", "front_face": front_face, "cull_mode": cull},
                "depth_stencil": {"format": DEPTH_FORMAT, "depth_write_enabled": True,
                                  "depth_compare": "less-equal"}}  # material.depthFunc = LessEqualDepth
        if color_format is not None:
            desc["fragment"] = {"module": self._fragment_module(st), "entry_point": "main",
                                "targets": [{"format": color_format}]}  # NoBlending for opaque materials
        p = self.device.create_render_pipeline(**desc)
        st.pipelines[key] = p
        self.precompute["pipeline_s"] += time.perf_counter() - t0
        return p

    # ------------------------------------------------------------------------------------------- drawing
    @staticmethod
    def _cull(side: str) -> str:
        """WebGLState.setMaterial: FrontSide culls back faces, BackSide front faces, DoubleSide none."""
        return {"FrontSide": "back", "BackSide": "front", "DoubleSide": "none"}[side]

    @staticmethod
    def _front_face(d: Drawable) -> str:
        """GL frontFace(CCW), flipped to CW when matrixWorld.determinant() < 0 (WebGLRenderer renderBufferDirect).
        The clip-space y negation mirrors the winding again, hence 'cw' for the ordinary case."""
        det = tm.m4_determinant_affine(d.matrix)
        return "ccw" if det < 0 else "cw"

    def _draw(self, rpass, by_side: dict, slots: "_ViewSlots", sample: int, color_format: str | None,
              drawables: list[Drawable], shadow: bool = False) -> None:
        for d in drawables:
            side = d.material.side
            st = by_side[side]
            cull = self._cull(SHADOW_SIDE[side] if shadow else side)
            rpass.set_pipeline(self._pipeline(st, color_format, cull, self._front_face(d)))
            g0, g1, g2 = self._bind_groups(st)
            rpass.set_bind_group(FRAME_SET, g0, [slots.frame[sample][id(st)]])
            rpass.set_bind_group(OBJECT_SET, g1, [slots.objects[d.name]])
            rpass.set_bind_group(TEXTURE_SET, g2)  # may be empty; WebGPU wants every layout slot bound
            for name, loc in st.program.attributes.items():
                rpass.set_vertex_buffer(loc, d.gpu[name])
            rpass.set_index_buffer(d.gpu["index"], "uint32")
            rpass.draw_indexed(d.gpu["count"])

    def _frame_values(self, camera, base: dict, projection) -> dict:
        v = dict(base)
        v["projectionMatrix"] = projection
        v["viewMatrix"] = camera.matrix_world_inverse
        v["cameraPosition"] = tm.v3_from_matrix_position(camera.matrix_world)
        v["isOrthographic"] = isinstance(camera, tm.OrthographicCamera)
        return v

    def _alloc_view(self, by_side: dict, camera, base: dict, drawables: list[Drawable],
                    projections: list | None = None) -> "_ViewSlots":
        """Pack this camera's uniform blocks into the arena: one frame slot per (projection, program) and one
        object slot per drawable (its material side's program)."""
        view = camera.matrix_world_inverse
        used = []
        for d in drawables:
            st = by_side[d.material.side]
            if st not in used:
                used.append(st)
        frame = []
        for proj in (projections or [camera.projection_matrix]):
            vals = self._frame_values(camera, base, proj)
            frame.append({id(st): self.arena.alloc(st.program.frame_block.pack(vals)) for st in used})
        objects = {d.name: self.arena.alloc(by_side[d.material.side].program.object_block.pack(
            object_uniforms(d, view))) for d in drawables}
        return _ViewSlots(frame, objects)

    # ------------------------------------------------------------------------------------------- passes
    def _plan_shadows(self, setups: list[ShadowSetup]) -> list:
        casters = [d for d in self.scene.drawables if d.cast_shadow]
        plan = []
        for s in setups:
            st = self.depth_program(s.kind == "point")
            by_side = {"FrontSide": st, "BackSide": st, "DoubleSide": st}
            base = {}
            if s.kind == "point":  # MeshDistanceMaterial uniforms (WebGLMaterials.js:591-599)
                lt = self.scene.light(s.light)
                base = {"referencePosition": tm.v3_from_matrix_position(lt.matrix_world), "nearDistance": s.near,
                        "farDistance": s.far}
            for face_i, face in enumerate(s.faces):
                plan.append((self.shadow_maps[s.light]["faces"][face_i], by_side,
                             self._alloc_view(by_side, face.camera, base, casters), casters))
        return plan

    def _encode_shadows(self, enc, plan: list) -> None:
        for view, by_side, slots, casters in plan:
            rp = enc.begin_render_pass(
                color_attachments=[],
                depth_stencil_attachment={"view": view, "depth_clear_value": 1.0, "depth_load_op": "clear",
                                          "depth_store_op": "store"},
                timestamp_writes=self.timer.pass_writes("shadow"))
            self._draw(rp, by_side, slots, 0, None, casters, shadow=True)
            rp.end()

    def _lambert_states(self, with_probe: bool, parity: bool) -> dict:
        sides = {d.material.side for d in self.scene.drawables}
        return {side: self.lambert(side=side, with_probe=with_probe, parity=parity) for side in sorted(sides)}

    def _base_frame_values(self, camera, shadow_info: dict, with_probe: bool, parity: bool) -> dict:
        u = light_uniforms(self.scene, camera.matrix_world_inverse, shadow_info, with_probe)
        u["toneMappingExposure"] = self.exposure if parity else 1.0
        return u

    def _clear_color(self, parity: bool) -> tuple:
        """WebGLBackground: scene.background Color -> setClear( background, 1 ) in getUnlitUniformColorSpace:
        the canvas' outputColorSpace (sRGB) in parity mode, the working space (linear) for render targets."""
        bg = self.scene.background
        if bg is None:
            return (0.0, 0.0, 0.0, 1.0)
        if parity:
            return tuple(tm.srgb_transfer_oetf(c) for c in bg) + (1.0,)
        return (bg[0], bg[1], bg[2], 1.0)

    def _plan_probe(self, position, shadow_info: dict, with_probe: bool) -> list:
        cfg = self.scene.probe_cfg
        by_side = self._lambert_states(with_probe, parity=False)
        plan = []
        for face_i, cam in enumerate(cube_cameras(position, float(cfg.get("near", 0.05)),
                                                  float(cfg.get("far", 1000)))):
            base = self._base_frame_values(cam, shadow_info, with_probe, parity=False)
            plan.append((face_i, by_side, self._alloc_view(by_side, cam, base, self.scene.drawables)))
        return plan

    def _encode_probe(self, enc, plan: list) -> None:
        clear = self._clear_color(False)
        for face_i, by_side, slots in plan:
            rp = enc.begin_render_pass(
                color_attachments=[{"view": self.probe_faces[face_i], "load_op": "clear", "store_op": "store",
                                    "clear_value": clear}],
                depth_stencil_attachment={"view": self.probe_depth_view, "depth_clear_value": 1.0,
                                          "depth_load_op": "clear", "depth_store_op": "discard"},
                timestamp_writes=self.timer.pass_writes("probe"))
            self._draw(rp, by_side, slots, 0, self.probe_format, self.scene.drawables)
            rp.end()
        S = self.probe_size
        enc.copy_texture_to_buffer({"texture": self.probe_target, "origin": (0, 0, 0)},
                                   {"buffer": self.probe_readback, "offset": 0, "bytes_per_row": self.probe_bpr,
                                    "rows_per_image": S}, (S, S, 6))

    def _read_probe(self) -> list[np.ndarray]:
        """readRenderTargetPixels of the six faces (rows in GL memory order), widened to float64."""
        S = self.probe_size
        self.probe_readback.map_sync(self.wgpu.MapMode.READ)
        raw = np.frombuffer(self.probe_readback.read_mapped(), dtype=np.uint8).copy()
        self.probe_readback.unmap()
        dt = {"rgba16float": np.float16, "rgba32float": np.float32, "rgba8unorm": np.uint8}[self.probe_format]
        bpp = np.dtype(dt).itemsize * 4
        faces = []
        for i in range(6):
            block = raw[i * self.probe_bpr * S:(i + 1) * self.probe_bpr * S].reshape(S, self.probe_bpr)[:, :S * bpp]
            px = np.frombuffer(block.tobytes(), dtype=dt).reshape(S, S, 4)
            faces.append(px.astype(np.float64) / 255.0 if dt == np.uint8 else px.astype(np.float64))
        return faces

    # ------------------------------------------------------------------------------------------- frame
    def make_camera(self, cam_cfg: dict) -> tm.PerspectiveCamera:
        """PerspectiveCamera(fov, W/H, near, far) at position, up, lookAt (as the web runner builds it)."""
        cam = tm.PerspectiveCamera(cam_cfg["fov"], self.width / self.height, cam_cfg["near"], cam_cfg["far"],
                                   up=cam_cfg.get("up", self.scene.frame_up))
        cam.position = tm.v3(cam_cfg["position"])
        cam.look_at(cam_cfg["lookAt"])
        cam.update_matrix_world()
        return cam

    def render_frame(self, cam_cfg: dict, *, offsets: list, capture_probe: bool, probe_feedback: bool,
                     with_probe: bool, readback: bool, parity: bool = False) -> FrameResult:
        """One output frame: shadows, optional probe capture (with or without the current probe active), then
        the main passes. ``offsets``: SSAA subpixel offsets (pixels) applied through setViewOffset and averaged
        (None = one sample without a view offset); ``parity``: one sample without offsets on the 8-bit target with
        ACES + sRGB, as drawn to a canvas (image is uint8 RGBA)."""
        t_start = time.perf_counter()
        wait = 0.0
        self.timer.reset()
        self.arena.reset()
        cam = self.make_camera(cam_cfg)
        setups = shadow_setups(self.scene, self.max_texture_size)
        shadow_info = {s.light: s.info() for s in setups}

        # segment A: shadow maps (+ probe capture), then read the cube back and project it (LightProbeGenerator)
        self.arena.begin_segment()
        shadow_plan = self._plan_shadows(setups)
        probe_plan = self._plan_probe(cam_cfg["position"], shadow_info, probe_feedback) if capture_probe else None
        self.arena.upload_segment()
        enc = self.device.create_command_encoder()
        self._encode_shadows(enc, shadow_plan)
        if probe_plan is not None:
            self._encode_probe(enc, probe_plan)
        self.ctx.queue.submit([enc.finish()])
        if capture_probe:
            tw = time.perf_counter()
            faces = self._read_probe()
            wait += time.perf_counter() - tw
            self.scene.probe_sh = sh_from_cube_faces(faces)

        # segment B: main passes (+ resolve)
        self.arena.begin_segment()
        by_side = self._lambert_states(with_probe, parity)
        base = self._base_frame_values(cam, shadow_info, with_probe, parity)
        drawables = self.scene.drawables
        W, H = self.width, self.height
        if parity or offsets is None:
            cam.clear_view_offset()
            projections = [cam.projection_matrix]
        else:
            projections = []
            for dx, dy in offsets:
                cam.set_view_offset(W, H, float(dx), float(dy), W, H)  # PerspectiveCamera.setViewOffset
                projections.append(cam.projection_matrix)
        slots = self._alloc_view(by_side, cam, base, drawables, projections)
        self.arena.upload_segment()
        enc = self.device.create_command_encoder()
        clear = self._clear_color(parity)
        if parity:
            self._ensure_parity_target()
            rp = enc.begin_render_pass(
                color_attachments=[{"view": self.parity_view, "load_op": "clear", "store_op": "store",
                                    "clear_value": clear}],
                depth_stencil_attachment={"view": self.depth_view, "depth_clear_value": 1.0, "depth_load_op": "clear",
                                          "depth_store_op": "discard"},
                timestamp_writes=self.timer.pass_writes("main"))
            self._draw(rp, by_side, slots, 0, PARITY_FORMAT, drawables)
            rp.end()
        else:
            self._set_resolve_weight(len(projections))
            for s in range(len(projections)):
                rp = enc.begin_render_pass(
                    color_attachments=[{"view": self.color_view, "load_op": "clear", "store_op": "store",
                                        "clear_value": clear}],
                    depth_stencil_attachment={"view": self.depth_view, "depth_clear_value": 1.0,
                                              "depth_load_op": "clear", "depth_store_op": "discard"},
                    timestamp_writes=self.timer.pass_writes("main"))
                self._draw(rp, by_side, slots, s, MEASURE_FORMAT, drawables)
                rp.end()
                cp = enc.begin_compute_pass(timestamp_writes=self.timer.pass_writes("resolve"))
                cp.set_pipeline(self.resolve_pipeline)
                cp.set_bind_group(0, self.resolve_bg, [0 if s == 0 else 256])
                cp.dispatch_workgroups((W + 7) // 8, (H + 7) // 8, 1)
                cp.end()
        self.timer.resolve(enc)
        self.ctx.queue.submit([enc.finish()])
        tw = time.perf_counter()
        image = None
        if readback:
            if parity:
                raw = self.ctx.queue.read_texture({"texture": self.parity_target}, {"bytes_per_row": W * 4}, (W, H, 1))
                image = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)[::-1].copy()  # GL rows -> top first
            else:
                raw = self.ctx.queue.read_buffer(self.acc)
                image = np.frombuffer(raw, dtype=np.float32).reshape(H, W, 4)[::-1].copy()
        passes = self.timer.read()
        if not readback and not passes:
            self.ctx.queue.on_submitted_work_done_sync()
        wait += time.perf_counter() - tw
        wall = (time.perf_counter() - t_start) * 1000.0
        return FrameResult(cpu_ms=wall - wait * 1000.0, wall_ms=wall, gpu_passes=passes, image=image,
                           probe_captured=capture_probe)


@dataclass
class _ViewSlots:
    frame: list  # per projection: {id(program state): arena offset}
    objects: dict  # drawable name -> arena offset
