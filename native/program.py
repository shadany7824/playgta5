"""WebGLProgram port + the thin, mechanical WebGL2 -> Vulkan GLSL 450 adapter (DESIGN §5.3).

Two steps, kept separate so the intermediate text can be compared with what three.js compiles:

1. ``webgl_sources(params)`` builds the exact GLSL ES 3.00 strings ``WebGLProgram`` (src/renderers/webgl/
   WebGLProgram.js:414-836, non-raw path) generates for a parameter set: precision block, defines prefix,
   built-in uniform/attribute declarations, tone-mapping/colour-space functions, then the ShaderLib body with
   #includes resolved, light counts substituted and loops unrolled (native/three_chunks.py).
2. ``vulkanize(vertex, fragment)`` rewrites both stages for naga's GLSL 450 frontend with the rules R1-R14 listed in
   docs/PHASE0.md (version line, preprocessor conditionals evaluated, precision statements dropped, uniforms gathered
   into two std140 blocks, bool uniforms as uint, combined samplers split into texture + sampler, explicit varying /
   attribute locations, 'const in' -> 'in', clip-space y and depth remap). No expression of three.js maths is
   touched; the only hand-written lines are the declarations and the two remap statements.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field

import numpy as np

from . import three_chunks
from .three_math import REC709_LUMINANCE_COEFFICIENTS, js_to_fixed, working_to_output_matrix

__all__ = ["CONSTANTS", "lambert_parameters", "depth_parameters", "distance_parameters", "webgl_sources",
           "vulkanize", "Program", "BlockLayout", "build_program", "Preprocessor", "OBJECT_UNIFORMS",
           "HAND_WRITTEN_LINES"]


@functools.lru_cache(maxsize=1)
def _constants() -> dict:
    js = (three_chunks.THREE_DIR / "src" / "constants.js").read_text(encoding="utf-8")
    out: dict = {}
    for name, val in re.findall(r"^export const (\w+) = (-?\d+|'[^']*');", js, re.M):
        out[name] = val.strip("'") if val.startswith("'") else int(val)
    return out


CONSTANTS = _constants()


# ------------------------------------------------------------------------------------------------ parameters

def _base_parameters() -> dict:
    """Defaults of WebGLPrograms.getParameters (WebGLPrograms.js:189-388) for a scene with no fog, no maps,
    no instancing/skinning/morphs, no clipping, highp precision (WebGL2), not a RawShaderMaterial."""
    return {
        "shaderID": None, "shaderType": "", "shaderName": "", "defines": None, "isRawShaderMaterial": False,
        "glslVersion": None, "precision": "highp",
        "outputColorSpace": CONSTANTS["LinearSRGBColorSpace"], "toneMapping": CONSTANTS["NoToneMapping"],
        "numSunLights": 0, "numDirLights": 0, "numPointLights": 0, "numSpotLights": 0, "numSpotLightMaps": 0,
        "numRectAreaLights": 0, "numHemiLights": 0, "numSunLightShadows": 0, "numDirLightShadows": 0,
        "numPointLightShadows": 0, "numSpotLightShadows": 0, "numSpotLightShadowsWithMaps": 0,
        "numLightProbes": 0, "numLightProbeGrids": 0, "numClippingPlanes": 0, "numClipIntersection": 0,
        "shadowMapEnabled": False, "shadowMapType": CONSTANTS["PCFShadowMap"],
        "vertexNormals": True, "doubleSided": False, "flipSided": False, "flatShading": False,
        "opaque": True, "premultipliedAlpha": False, "dithering": False,
        "useDepthPacking": False, "depthPacking": 0, "useFog": False, "fog": False,
    }


def _light_counts(lights: dict) -> dict:
    keys = ("numDirLights", "numPointLights", "numRectAreaLights", "numHemiLights", "numDirLightShadows",
            "numPointLightShadows", "numLightProbes")
    return {k: int(lights.get(k, 0)) for k in keys}


def lambert_parameters(lights: dict, *, double_sided: bool, tone_mapping: str = "NoToneMapping",
                       output_color_space: str = "srgb-linear", shadow_map_type: str = "PCFShadowMap") -> dict:
    """getParameters for MeshLambertMaterial. ``lights``: light/shadow/probe counts (JS names)."""
    p = _base_parameters()
    p.update(_light_counts(lights))
    p.update(shaderID="lambert", shaderType="MeshLambertMaterial", doubleSided=bool(double_sided),
             toneMapping=CONSTANTS[tone_mapping], outputColorSpace=output_color_space,
             shadowMapType=CONSTANTS[shadow_map_type], useFog=True,
             shadowMapEnabled=(p["numDirLightShadows"] + p["numPointLightShadows"]) > 0)
    return p


def _shadow_pass_counts(lights: dict) -> dict:
    """Light counts a depth/distance program is compiled with: WebGLShadowMap.render runs before
    currentRenderState.setupLights() (WebGLRenderer.js:1737 vs 1752), so on the first frame WebGLLights.state still
    has numLightProbes = 0, and those programs never need a light-state refresh (needsLights is false)."""
    c = _light_counts(lights)
    c["numLightProbes"] = 0
    return c


def depth_parameters(lights: dict, *, side: str = "DoubleSide") -> dict:
    """getParameters for WebGLShadowMap's MeshDepthMaterial (depthPacking = BasicDepthPacking)."""
    p = _base_parameters()
    p.update(_shadow_pass_counts(lights))
    p.update(shaderID="depth", shaderType="MeshDepthMaterial", useDepthPacking=True,
             depthPacking=CONSTANTS["BasicDepthPacking"], doubleSided=side == "DoubleSide",
             flipSided=side == "BackSide",
             shadowMapEnabled=(p["numDirLightShadows"] + p["numPointLightShadows"]) > 0)
    return p


def distance_parameters(lights: dict, *, side: str = "DoubleSide") -> dict:
    """getParameters for WebGLShadowMap's MeshDistanceMaterial (point-light cube shadows)."""
    p = _base_parameters()
    p.update(_shadow_pass_counts(lights))
    p.update(shaderID="distance", shaderType="MeshDistanceMaterial", doubleSided=side == "DoubleSide",
             flipSided=side == "BackSide",
             shadowMapEnabled=(p["numDirLightShadows"] + p["numPointLightShadows"]) > 0)
    return p


# ------------------------------------------------------------------------------------------------ WebGLProgram

def _generate_precision(p: dict) -> str:
    """WebGLProgram.generatePrecision (WebGLProgram.js:308-345), whitespace included."""
    q = p["precision"]
    s = (f"precision {q} float;\n\tprecision {q} int;\n\tprecision {q} sampler2D;\n\tprecision {q} samplerCube;\n"
         f"\tprecision {q} sampler3D;\n\tprecision {q} sampler2DArray;\n\tprecision {q} sampler2DShadow;\n"
         f"\tprecision {q} samplerCubeShadow;\n\tprecision {q} sampler2DArrayShadow;\n\tprecision {q} isampler2D;\n"
         f"\tprecision {q} isampler3D;\n\tprecision {q} isamplerCube;\n\tprecision {q} isampler2DArray;\n"
         f"\tprecision {q} usampler2D;\n\tprecision {q} usampler3D;\n\tprecision {q} usamplerCube;\n"
         f"\tprecision {q} usampler2DArray;\n\t")
    s += {"highp": "\n#define HIGH_PRECISION", "mediump": "\n#define MEDIUM_PRECISION",
          "lowp": "\n#define LOW_PRECISION"}.get(q, "")
    return s


def _shadow_map_type_define(p: dict) -> str:
    """WebGLProgram.generateShadowMapTypeDefine (WebGLProgram.js:347-356)."""
    return {CONSTANTS["PCFShadowMap"]: "SHADOWMAP_TYPE_PCF",
            CONSTANTS["VSMShadowMap"]: "SHADOWMAP_TYPE_VSM"}.get(p["shadowMapType"], "SHADOWMAP_TYPE_BASIC")


def _generate_defines(defines) -> str:
    """WebGLProgram.generateDefines (WebGLProgram.js:160-176)."""
    if not defines:
        return ""
    return "\n".join(f"#define {k} {v}" for k, v in defines.items() if v is not False)


_TONE_MAPPING_NAMES = {CONSTANTS["LinearToneMapping"]: "Linear", CONSTANTS["ReinhardToneMapping"]: "Reinhard",
                       CONSTANTS["CineonToneMapping"]: "Cineon", CONSTANTS["ACESFilmicToneMapping"]: "ACESFilmic",
                       CONSTANTS["AgXToneMapping"]: "AgX", CONSTANTS["NeutralToneMapping"]: "Neutral",
                       CONSTANTS["CustomToneMapping"]: "Custom"}  # WebGLProgram.js:100-108


def _tone_mapping_function(name: str, tone_mapping: int) -> str:
    """WebGLProgram.getToneMappingFunction (WebGLProgram.js:110-123)."""
    tm = _TONE_MAPPING_NAMES.get(tone_mapping)
    if tm is None:
        return "vec3 " + name + "( vec3 color ) { return LinearToneMapping( color ); }"
    return "vec3 " + name + "( vec3 color ) { return " + tm + "ToneMapping( color ); }"


def _texel_encoding_function(name: str, color_space: str) -> str:
    """WebGLProgram.getTexelEncodingFunction + getEncodingComponents (WebGLProgram.js:36-98)."""
    m = working_to_output_matrix()
    matrix = "mat3( " + ",".join(js_to_fixed(v, 4) for v in m) + " )"
    transfer = {"srgb": "sRGBTransferOETF", "srgb-linear": "LinearTransferOETF", "": "LinearTransferOETF"}[color_space]
    return "\n".join([f"vec4 {name}( vec4 value ) {{",
                      f"\treturn {transfer}( vec4( value.rgb * {matrix}, value.a ) );", "}"])


def _luminance_function() -> str:
    """WebGLProgram.getLuminanceFunction (WebGLProgram.js:127-147)."""
    r, g, b = (js_to_fixed(v, 4) for v in REC709_LUMINANCE_COEFFICIENTS)
    return "\n".join(["float luminance( const in vec3 rgb ) {", f"\tconst vec3 weights = vec3( {r}, {g}, {b} );",
                      "\treturn dot( weights, rgb );", "}"])


def webgl_sources(p: dict) -> tuple[str, str]:
    """(vertexGlsl, fragmentGlsl) exactly as WebGLProgram builds them for WebGL2 (WebGLProgram.js:414-836).
    Only the parameters the harness can produce are honoured; every other feature flag is false."""
    chunks = three_chunks.shader_chunks()
    vertex_shader, fragment_shader = three_chunks.shader_lib(p["shaderID"])
    custom_defines = _generate_defines(p["defines"])
    smt = _shadow_map_type_define(p)
    f = p.get
    prefix_vertex = "\n".join(s for s in [
        _generate_precision(p),
        "#define SHADER_TYPE " + p["shaderType"],
        "#define SHADER_NAME " + p["shaderName"],
        custom_defines,
        "#define USE_FOG" if f("useFog") and f("fog") else "",
        "#define HAS_NORMAL" if f("vertexNormals") else "",
        "#define FLAT_SHADED" if f("flatShading") else "",
        "#define DOUBLE_SIDED" if f("doubleSided") else "",
        "#define FLIP_SIDED" if f("flipSided") else "",
        "#define USE_SHADOWMAP" if f("shadowMapEnabled") else "",
        "#define " + smt if f("shadowMapEnabled") else "",
        "#define USE_LIGHT_PROBES" if f("numLightProbes") > 0 else "",
        "uniform mat4 modelMatrix;",
        "uniform mat4 modelViewMatrix;",
        "uniform mat4 projectionMatrix;",
        "uniform mat4 viewMatrix;",
        "uniform mat3 normalMatrix;",
        "uniform vec3 cameraPosition;",
        "uniform bool isOrthographic;",
        "#ifdef USE_INSTANCING", "\tattribute mat4 instanceMatrix;", "#endif",
        "#ifdef USE_INSTANCING_COLOR", "\tattribute vec3 instanceColor;", "#endif",
        "#ifdef USE_INSTANCING_MORPH", "\tuniform sampler2D morphTexture;", "#endif",
        "attribute vec3 position;",
        "attribute vec3 normal;",
        "attribute vec2 uv;",
        "#ifdef USE_UV1", "\tattribute vec2 uv1;", "#endif",
        "#ifdef USE_UV2", "\tattribute vec2 uv2;", "#endif",
        "#ifdef USE_UV3", "\tattribute vec2 uv3;", "#endif",
        "#ifdef USE_TANGENT", "\tattribute vec4 tangent;", "#endif",
        "#if defined( USE_COLOR_ALPHA )", "\tattribute vec4 color;", "#elif defined( USE_COLOR )",
        "\tattribute vec3 color;", "#endif",
        "#ifdef USE_SKINNING", "\tattribute vec4 skinIndex;", "\tattribute vec4 skinWeight;", "#endif",
        "\n",
    ] if s != "")
    tm = p["toneMapping"] != CONSTANTS["NoToneMapping"]
    prefix_fragment = "\n".join(s for s in [
        _generate_precision(p),
        "#define SHADER_TYPE " + p["shaderType"],
        "#define SHADER_NAME " + p["shaderName"],
        custom_defines,
        "#define USE_FOG" if f("useFog") and f("fog") else "",
        "#define FLAT_SHADED" if f("flatShading") else "",
        "#define DOUBLE_SIDED" if f("doubleSided") else "",
        "#define FLIP_SIDED" if f("flipSided") else "",
        "#define USE_SHADOWMAP" if f("shadowMapEnabled") else "",
        "#define " + smt if f("shadowMapEnabled") else "",
        "#define PREMULTIPLIED_ALPHA" if f("premultipliedAlpha") else "",
        "#define USE_LIGHT_PROBES" if f("numLightProbes") > 0 else "",
        "#define USE_LIGHT_PROBES_GRID" if f("numLightProbeGrids") > 0 else "",
        "uniform mat4 viewMatrix;",
        "uniform vec3 cameraPosition;",
        "uniform bool isOrthographic;",
        "#define TONE_MAPPING" if tm else "",
        chunks["tonemapping_pars_fragment"] if tm else "",
        _tone_mapping_function("toneMapping", p["toneMapping"]) if tm else "",
        "#define DITHERING" if f("dithering") else "",
        "#define OPAQUE" if f("opaque") else "",
        chunks["colorspace_pars_fragment"],
        _texel_encoding_function("linearToOutputTexel", p["outputColorSpace"]),
        _luminance_function(),
        "#define DEPTH_PACKING " + str(p["depthPacking"]) if f("useDepthPacking") else "",
        "\n",
    ] if s != "")
    vs = three_chunks.resolve_includes(vertex_shader, chunks)
    vs = three_chunks.replace_light_nums(vs, p)
    vs = three_chunks.replace_clipping_plane_nums(vs, p)
    fs = three_chunks.resolve_includes(fragment_shader, chunks)
    fs = three_chunks.replace_light_nums(fs, p)
    fs = three_chunks.replace_clipping_plane_nums(fs, p)
    vs = three_chunks.unroll_loops(vs)
    fs = three_chunks.unroll_loops(fs)
    version = "#version 300 es\n"
    prefix_vertex = "\n".join(["", "#define attribute in", "#define varying out",
                               "#define texture2D texture"]) + "\n" + prefix_vertex
    prefix_fragment = "\n".join(["#define varying in", "layout(location = 0) out highp vec4 pc_fragColor;",
                                 "#define gl_FragColor pc_fragColor", "#define gl_FragDepthEXT gl_FragDepth",
                                 "#define texture2D texture", "#define textureCube texture",
                                 "#define texture2DProj textureProj", "#define texture2DLodEXT textureLod",
                                 "#define texture2DProjLodEXT textureProjLod", "#define textureCubeLodEXT textureLod",
                                 "#define texture2DGradEXT textureGrad", "#define texture2DProjGradEXT textureProjGrad",
                                 "#define textureCubeGradEXT textureGrad"]) + "\n" + prefix_fragment
    return version + prefix_vertex + vs, version + prefix_fragment + fs


# ------------------------------------------------------------------------------------------------ preprocessor

def strip_comments(src: str) -> str:
    """Remove // and /* */ comments (block comments keep their newlines). GLSL has no string literals."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * src.count("\n", i, j))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


_TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\d*\.\d+|\d+)[uU]?|([A-Za-z_]\w*)|(&&|\|\||==|!=|<=|>=|[()!<>+\-*/%]))")


class Preprocessor:
    """C-preprocessor subset: #define/#undef tracking, #if/#ifdef/#ifndef/#elif/#else/#endif evaluation with
    defined(), integer arithmetic and comparisons. Active #define/#undef lines are kept for naga's own
    preprocessor (function-like macros such as saturate() are expanded there)."""

    def __init__(self):
        self.macros: dict[str, tuple[list[str] | None, str]] = {}

    def run(self, src: str) -> str:
        src = strip_comments(src)
        out: list[str] = []
        stack: list[list[bool]] = []  # [parent_active, taken]
        active = True
        for line in src.split("\n"):
            s = line.strip()
            if s.startswith("#"):
                m = re.match(r"#\s*(\w+)\s*(.*)$", s)
                d, rest = (m.group(1), m.group(2).strip()) if m else ("", "")
                if d in ("if", "ifdef", "ifndef"):
                    if d == "ifdef":
                        cond = rest.split()[0] in self.macros if active else False
                    elif d == "ifndef":
                        cond = rest.split()[0] not in self.macros if active else False
                    else:
                        cond = bool(self.eval(rest)) if active else False
                    stack.append([active, cond])
                    active = active and cond
                elif d == "elif":
                    parent, taken = stack[-1]
                    cond = (not taken) and parent and bool(self.eval(rest))
                    stack[-1][1] = taken or cond
                    active = cond
                elif d == "else":
                    parent, taken = stack[-1]
                    active = parent and not taken
                    stack[-1][1] = True
                elif d == "endif":
                    active = stack.pop()[0]
                elif active:
                    if d == "define":
                        self._define(rest)
                    elif d == "undef":
                        self.macros.pop(rest.split()[0], None)
                    out.append(line)
                continue
            if active:
                out.append(line)
        if stack:
            raise ValueError("unterminated #if")
        return "\n".join(out)

    def _define(self, rest: str) -> None:
        m = re.match(r"([A-Za-z_]\w*)(\(([^)]*)\))?\s*(.*)$", rest)
        if not m:
            raise ValueError(f"bad #define {rest!r}")
        params = [a.strip() for a in m.group(3).split(",")] if m.group(2) else None
        self.macros[m.group(1)] = (params, m.group(4).strip())

    # -- expressions
    def expand(self, expr: str, depth: int = 0) -> str:
        """Replace defined(X) by 0/1 and object-like macros by their bodies (recursively); unknown names -> 0."""
        if depth > 32:
            raise ValueError("macro recursion")
        expr = re.sub(r"\bdefined\s*\(\s*(\w+)\s*\)", lambda m: "1" if m.group(1) in self.macros else "0", expr)
        expr = re.sub(r"\bdefined\s+(\w+)", lambda m: "1" if m.group(1) in self.macros else "0", expr)

        def sub(m):
            name = m.group(0)
            if name in self.macros and self.macros[name][0] is None:
                return "(" + self.expand(self.macros[name][1], depth + 1) + ")"
            return "0"

        return re.sub(r"\b[A-Za-z_]\w*\b", sub, expr)

    def eval(self, expr: str):
        toks = []
        s = self.expand(expr)
        pos = 0
        while pos < len(s):
            if s[pos:].strip() == "":
                break
            m = _TOKEN.match(s, pos)
            if not m:
                raise ValueError(f"cannot parse #if expression {expr!r}")
            toks.append(m.group(1) or m.group(2) or m.group(3))
            pos = m.end()
        val, i = self._expr(toks, 0, 0)
        if i != len(toks):
            raise ValueError(f"trailing tokens in #if {expr!r}")
        return val

    _PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, ">": 4, "<=": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6,
             "%": 6}

    def _atom(self, t, i):
        tok = t[i]
        if tok == "(":
            v, i = self._expr(t, i + 1, 0)
            if t[i] != ")":
                raise ValueError("missing )")
            return v, i + 1
        if tok == "!":
            v, i = self._atom(t, i + 1)
            return int(not v), i
        if tok == "-":
            v, i = self._atom(t, i + 1)
            return -v, i
        if tok == "+":
            return self._atom(t, i + 1)
        return (float(tok) if "." in tok else int(tok)), i + 1

    def _expr(self, t, i, min_prec):
        lhs, i = self._atom(t, i)
        while i < len(t) and t[i] in self._PREC and self._PREC[t[i]] >= min_prec:
            op = t[i]
            rhs, i = self._expr(t, i + 1, self._PREC[op] + 1)
            lhs = {"||": lambda a, b: int(bool(a) or bool(b)), "&&": lambda a, b: int(bool(a) and bool(b)),
                   "==": lambda a, b: int(a == b), "!=": lambda a, b: int(a != b), "<": lambda a, b: int(a < b),
                   ">": lambda a, b: int(a > b), "<=": lambda a, b: int(a <= b), ">=": lambda a, b: int(a >= b),
                   "+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
                   "/": lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b,
                   "%": lambda a, b: a % b}[op](lhs, rhs)
        return lhs, i


# ------------------------------------------------------------------------------------------------ std140 blocks

_SCALAR = {"float": ("f", 1), "int": ("i", 1), "uint": ("u", 1), "bool": ("u", 1)}
_VEC = {"vec2": 2, "vec3": 3, "vec4": 4, "ivec2": 2, "ivec3": 3, "ivec4": 4}


@dataclass
class FieldLayout:
    name: str
    type: str
    array: int | None
    offset: int
    size: int  # of one element
    align: int
    stride: int  # array stride (== rounded size for std140 arrays)
    struct: "StructLayout | None" = None


@dataclass
class StructLayout:
    name: str
    fields: list[FieldLayout]
    size: int
    align: int


def _round(x: int, a: int) -> int:
    return (x + a - 1) // a * a


def _type_layout(t: str, structs: dict[str, StructLayout]) -> tuple[int, int]:
    """(size, align) of one element under std140."""
    if t in _SCALAR:
        return 4, 4
    if t in _VEC:
        n = _VEC[t]
        return 4 * n, (8 if n == 2 else 16)
    if t == "mat3":
        return 48, 16
    if t == "mat4":
        return 64, 16
    if t in structs:
        return structs[t].size, structs[t].align
    raise ValueError(f"unsupported uniform type {t!r}")


def layout_fields(members: list[tuple[str, str, int | None]], structs: dict[str, StructLayout]) \
        -> tuple[list[FieldLayout], int, int]:
    """std140 offsets for (type, name, array) members -> (fields, size, align)."""
    off = 0
    fields = []
    align_max = 16
    for t, name, arr in members:
        size, align = _type_layout(t, structs)
        if arr is not None:
            align = max(align, 16)
            stride = _round(size, 16)
            total = stride * arr
        else:
            stride = size
            total = size
        off = _round(off, align)
        fields.append(FieldLayout(name, t, arr, off, size, align, stride, structs.get(t)))
        off += total
        align_max = max(align_max, align)
    return fields, _round(off, 16), align_max


class BlockLayout:
    """A std140 uniform block (one per set). ``pack(values)`` -> bytes; mat3/mat4 values are three.js
    column-major ``elements``; structs are dicts; arrays are sequences; bools become uint 0/1."""

    def __init__(self, name: str, set_index: int, members: list[tuple[str, str, int | None]],
                 structs: dict[str, StructLayout], aliases: dict[str, str] | None = None):
        self.name = name
        self.set = set_index
        self.members = members
        self.fields, self.size, _ = layout_fields(members, structs)
        self.size = max(self.size, 16)
        self.by_name = {f.name: f for f in self.fields}
        self.aliases = dict(aliases or {})  # block member name -> uniform name (bool 'x_b' -> 'x')

    def pack(self, values: dict, strict: bool = False) -> bytes:
        buf = np.zeros(self.size // 4, dtype=np.float32)
        u = buf.view(np.uint32)
        i32 = buf.view(np.int32)
        if strict:
            missing = {n for n in self.by_name if self.aliases.get(n, n) not in values}
            if missing:
                raise KeyError(f"{self.name}: no value for {sorted(missing)}")
        for f in self.fields:
            key = self.aliases.get(f.name, f.name)
            if key in values:
                self._write(buf, u, i32, f, values[key], f.offset)
        return buf.tobytes()

    def _write(self, buf, u, i32, f: FieldLayout, v, off: int) -> None:
        if f.array is not None:
            single = FieldLayout(f.name, f.type, None, 0, f.size, f.align, f.size, f.struct)
            for k, item in enumerate(v):
                if k >= f.array:
                    raise ValueError(f"{f.name}: more than {f.array} elements")
                self._write(buf, u, i32, single, item, off + k * f.stride)
            return
        o = off // 4
        t = f.type
        if f.struct is not None:
            for sf in f.struct.fields:
                if sf.name in v:
                    self._write(buf, u, i32, sf, v[sf.name], off + sf.offset)
        elif t == "float":
            buf[o] = v
        elif t in ("uint", "bool"):
            u[o] = int(bool(v)) if t == "bool" else int(v)
        elif t == "int":
            i32[o] = int(v)
        elif t in _VEC:
            n = _VEC[t]
            buf[o:o + n] = np.asarray(v, dtype=np.float64).reshape(n)
        elif t == "mat3":
            m = np.asarray(v, dtype=np.float64).reshape(3, 3)  # rows of the column-major list = columns
            for c in range(3):
                buf[o + 4 * c:o + 4 * c + 3] = m[c]
        elif t == "mat4":
            buf[o:o + 16] = np.asarray(v, dtype=np.float64).reshape(16)
        else:
            raise ValueError(t)


# ------------------------------------------------------------------------------------------------ Vulkan adapter

OBJECT_UNIFORMS = ("modelMatrix", "modelViewMatrix", "normalMatrix", "diffuse", "emissive", "opacity",
                   "receiveShadow")  # per-draw block (set 1); everything else is per-camera (set 0)
FRAME_SET, OBJECT_SET, TEXTURE_SET = 0, 1, 2
ATTRIBUTE_LOCATIONS = {"position": 0, "normal": 1, "uv": 2}
_SAMPLER_TYPES = {"sampler2D": ("texture2D", "sampler", "2d", "float"),
                  "sampler2DShadow": ("texture2D", "samplerShadow", "2d", "depth"),
                  "samplerCube": ("textureCube", "sampler", "cube", "float"),
                  "samplerCubeShadow": ("textureCube", "samplerShadow", "cube", "depth")}
_PRECISION_Q = r"(?:(?:highp|mediump|lowp)\s+)?"
_UNIFORM_RE = re.compile(r"^[ \t]*" + _PRECISION_Q + r"uniform\s+" + _PRECISION_Q +
                         r"(\w+)\s+(\w+)\s*(?:\[\s*([^\]]+?)\s*\])?\s*;[ \t]*$", re.M)
_VARYING_RE = re.compile(r"^[ \t]*varying\s+" + _PRECISION_Q + r"(\w+)\s+(\w+)\s*(?:\[\s*([^\]]+?)\s*\])?\s*;[ \t]*$",
                         re.M)
_ATTRIBUTE_RE = re.compile(r"^[ \t]*attribute\s+" + _PRECISION_Q + r"(\w+)\s+(\w+)\s*;[ \t]*$", re.M)
_STRUCT_RE = re.compile(r"^[ \t]*struct\s+(\w+)\s*\{([^{}]*)\}\s*;[ \t]*\n?", re.M)
_PRECISION_STMT_RE = re.compile(r"^[ \t]*precision\s+\w+\s+\w+\s*;[ \t]*$", re.M)

# Every line the adapter writes itself (templates; docs/PHASE0.md lists them with the reason).
HAND_WRITTEN_LINES = {
    "version": "#version 450",
    "block": "layout(std140, set = <S>, binding = 0) uniform <Block> { <uniform declarations moved verbatim> };",
    "bool": "#define <name> ( <name>_b != 0u )   // block member declared as 'uint <name>_b'",
    "texture": "layout(set = 2, binding = <2k>) uniform texture2D|textureCube <name>_tex;",
    "sampler": "layout(set = 2, binding = <2k+1>) uniform sampler|samplerShadow <name>_smp;",
    "varying": "layout(location = <L>) out|in <type> <name>[<n>];   // was 'varying <type> <name>[<n>];'",
    "attribute": "layout(location = <L>) in <type> <name>;   // was 'attribute <type> <name>;'",
    "clip_y": "gl_Position.y = - gl_Position.y;",
    "clip_z": "gl_Position.z = ( gl_Position.z + gl_Position.w ) * 0.5;",
}


@dataclass
class TextureBinding:
    name: str  # flattened uniform name (array element i -> name_i)
    glsl_type: str  # sampler2D | sampler2DShadow | samplerCube | samplerCubeShadow
    dimension: str  # 2d | cube
    sample_type: str  # float | depth
    tex_binding: int
    smp_binding: int


@dataclass
class Program:
    """A vulkanized program: GLSL 450 per stage + everything the pipeline layout needs."""
    label: str
    vertex: str
    fragment: str
    frame_block: BlockLayout
    object_block: BlockLayout
    textures: list[TextureBinding]
    attributes: dict[str, int]  # name -> location (only referenced attributes)
    varyings: dict[str, int]
    webgl_vertex: str = ""
    webgl_fragment: str = ""
    rewrites: dict = field(default_factory=dict)


def _depth_map(text: str) -> list[int]:
    """Brace depth at every character (depth before the char)."""
    d = 0
    out = [0] * (len(text) + 1)
    for i, c in enumerate(text):
        out[i] = d
        if c == "{":
            d += 1
        elif c == "}":
            d -= 1
    out[len(text)] = d
    return out


def _matching(text: str, i: int, open_c: str, close_c: str) -> int:
    d = 0
    for j in range(i, len(text)):
        if text[j] == open_c:
            d += 1
        elif text[j] == close_c:
            d -= 1
            if d == 0:
                return j
    raise ValueError(f"unbalanced {open_c}{close_c}")


_FUNC_RE = re.compile(r"(?:\b(?:highp|mediump|lowp)\s+)?\b(\w+)\s+(\w+)\s*\(([^()]*)\)\s*\{")


def _functions(text: str) -> list[tuple[str, int, int, int, int]]:
    """Top-level function definitions: (name, params_start, params_end, body_open, body_close)."""
    depth = _depth_map(text)
    out = []
    for m in _FUNC_RE.finditer(text):
        if depth[m.start()] != 0 or m.group(1) in ("else", "return"):
            continue
        open_brace = m.end() - 1
        out.append((m.group(2), m.start(3), m.end(3), open_brace, _matching(text, open_brace, "{", "}")))
    return out


def _split_args(s: str) -> list[str]:
    args, d, cur = [], 0, []
    for c in s:
        if c in "([":
            d += 1
        elif c in ")]":
            d -= 1
        if c == "," and d == 0:
            args.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    args.append("".join(cur))
    return args


def _count(pp: Preprocessor, expr: str | None) -> int | None:
    return None if expr is None else int(pp.eval(expr))


def _locations(t: str, arr: int | None) -> int:
    per = {"mat3": 3, "mat4": 4}.get(t, 1)
    return per * (arr or 1)


def vulkanize(vertex_glsl: str, fragment_glsl: str, label: str = "program") -> Program:
    """Apply the mechanical rewrite rules (docs/PHASE0.md R1-R14) to a WebGLProgram vertex/fragment pair."""
    stages = {}
    structs_src: dict[str, str] = {}
    struct_members: dict[str, list[tuple[str, str, int | None]]] = {}
    uniforms: list[tuple[str, str, int | None]] = []  # (type, name, array) in first-seen order
    seen_uniforms: set[str] = set()
    varyings: dict[str, tuple[str, int | None]] = {}
    for stage, src in (("vertex", vertex_glsl), ("fragment", fragment_glsl)):
        pp = Preprocessor()
        text = pp.run(src)  # R2: conditionals evaluated, comments removed
        text = re.sub(r"^[ \t]*#version[^\n]*\n", "", text, flags=re.M)  # R1 (re-added below)
        text = _PRECISION_STMT_RE.sub("", text)  # R3
        text = re.sub(r"^[ \t]*#define (attribute|varying) (in|out)[ \t]*$", "", text, flags=re.M)  # R9/R10
        text = re.sub(r"\bconst\s+in\b", "in", text)  # R11
        text = _apply_compat_macros(text)  # R10b
        for m in _STRUCT_RE.finditer(text):
            name, body = m.group(1), m.group(2)
            members = []
            for line in body.split(";"):
                mm = re.match(r"\s*" + _PRECISION_Q + r"(\w+)\s+(\w+)\s*(?:\[\s*([^\]]+?)\s*\])?\s*$", line)
                if mm:
                    members.append((mm.group(1), mm.group(2), _count(pp, mm.group(3))))
            if name in struct_members and struct_members[name] != members:
                raise ValueError(f"struct {name} differs between stages")
            struct_members[name] = members
            structs_src[name] = m.group(0).strip()
        for m in _UNIFORM_RE.finditer(text):
            t, name, arr = m.group(1), m.group(2), _count(pp, m.group(3))
            if name not in seen_uniforms:
                seen_uniforms.add(name)
                uniforms.append((t, name, arr))
        text = _UNIFORM_RE.sub("", text)  # R4: moved into blocks
        if stage == "vertex":
            for m in _VARYING_RE.finditer(text):
                varyings.setdefault(m.group(2), (m.group(1), _count(pp, m.group(3))))
        stages[stage] = (text, pp)

    # R4: std140 blocks. Struct types used by uniforms are hoisted above the blocks.
    opaque = [(t, n, a) for t, n, a in uniforms if t in _SAMPLER_TYPES]
    plain = [(t, n, a) for t, n, a in uniforms if t not in _SAMPLER_TYPES]
    needed: list[str] = []

    def need(t):
        if t in struct_members and t not in needed:
            for mt, _, _ in struct_members[t]:
                need(mt)
            needed.append(t)

    for t, _, _ in plain:
        need(t)
    layouts: dict[str, StructLayout] = {}
    for sname in needed:
        flds, size, align = layout_fields(struct_members[sname], layouts)
        layouts[sname] = StructLayout(sname, flds, size, align)

    def member(t, n, a):  # R5: bool -> uint
        return ("uint", n + "_b", a) if t == "bool" else (t, n, a)

    frame_members = [member(t, n, a) for t, n, a in plain if n not in OBJECT_UNIFORMS]
    object_members = [member(t, n, a) for t, n, a in plain if n in OBJECT_UNIFORMS]
    bool_names = [n for t, n, _ in plain if t == "bool"]
    aliases = {n + "_b": n for n in bool_names}
    frame_block = BlockLayout("ThreeFrame", FRAME_SET, frame_members, layouts, aliases)
    object_block = BlockLayout("ThreeObject", OBJECT_SET, object_members, layouts, aliases)

    textures: list[TextureBinding] = []
    for t, n, a in opaque:  # R6: combined samplers -> texture + sampler, arrays flattened
        names = [f"{n}_{i}" for i in range(a)] if a is not None else [n]
        for fn in names:
            k = len(textures)
            textures.append(TextureBinding(fn, t, _SAMPLER_TYPES[t][2], _SAMPLER_TYPES[t][3], 2 * k, 2 * k + 1))
    array_samplers = {n for t, n, a in opaque if a is not None}

    def decl_member(t, n, a):
        return f"\t{t} {n}" + (f"[ {a} ]" if a is not None else "") + ";"

    header = ["#version 450"]
    header += [structs_src[s] for s in needed]
    for blk in (frame_block, object_block):
        if blk.members:
            header.append(f"layout(std140, set = {blk.set}, binding = 0) uniform {blk.name} {{")
            header += [decl_member(*m) for m in blk.members]
            header.append("};")
    header += [f"#define {n} ( {n}_b != 0u )" for n in bool_names]
    for tb in textures:
        ttype, stype, _, _ = _SAMPLER_TYPES[tb.glsl_type]
        header.append(f"layout(set = {TEXTURE_SET}, binding = {tb.tex_binding}) uniform {ttype} {tb.name}_tex;")
        header.append(f"layout(set = {TEXTURE_SET}, binding = {tb.smp_binding}) uniform {stype} {tb.name}_smp;")

    # R7: varying locations from the vertex declaration order
    var_loc: dict[str, int] = {}
    loc = 0
    for name, (t, a) in varyings.items():
        var_loc[name] = loc
        loc += _locations(t, a)

    out = {}
    attributes: dict[str, int] = {}
    for stage in ("vertex", "fragment"):
        text, pp = stages[stage]
        # R7: varyings
        declared: set[str] = set()

        def var_sub(m, stage=stage, declared=declared):
            t, name, arr = m.group(1), m.group(2), m.group(3)
            if name not in var_loc:
                raise ValueError(f"{label}: fragment varying {name!r} is not written by the vertex shader")
            if name in declared:
                return ""
            declared.add(name)
            q = "out" if stage == "vertex" else "in"
            return f"layout(location = {var_loc[name]}) {q} {t} {name}" + (f"[ {arr} ]" if arr else "") + ";"

        text = _VARYING_RE.sub(var_sub, text)
        # R8: attributes (only the referenced ones; GL drops inactive attributes too)
        if stage == "vertex":
            mm = re.search(r"\bvoid\s+main\s*\(\s*\)\s*\{", text)
            main_body = text[mm.end() - 1:_matching(text, mm.end() - 1, "{", "}") + 1] if mm else ""

            def attr_sub(m, main_body=main_body):
                t, name = m.group(1), m.group(2)
                if not re.search(r"\b" + re.escape(name) + r"\b", main_body):
                    return ""  # inactive attribute (not read by main), as GL's linker drops it
                attributes[name] = ATTRIBUTE_LOCATIONS[name]
                return f"layout(location = {ATTRIBUTE_LOCATIONS[name]}) in {t} {name};"

            text = _ATTRIBUTE_RE.sub(attr_sub, text)
        text = _rewrite_samplers(text, opaque, array_samplers)  # R6
        if stage == "vertex":
            text = _append_clip_remap(text)  # R12/R13
        out[stage] = "\n".join(header) + "\n" + text
    return Program(label, out["vertex"], out["fragment"], frame_block, object_block, textures, attributes, var_loc,
                   vertex_glsl, fragment_glsl)


# WebGL2 compatibility macros of WebGLProgram.js:810-831 whose names are Vulkan GLSL type names (texture2D,
# textureCube) or that only rename builtins; applied textually, as the preprocessor would, then dropped (R10b).
_COMPAT_MACROS = ("texture2D", "textureCube", "texture2DProj", "texture2DLodEXT", "texture2DProjLodEXT",
                  "textureCubeLodEXT", "texture2DGradEXT", "texture2DProjGradEXT", "textureCubeGradEXT")


def _apply_compat_macros(text: str) -> str:
    for name in _COMPAT_MACROS:
        m = re.search(r"^[ \t]*#define " + name + r" (\w+)[ \t]*$", text, re.M)
        if m:
            target = m.group(1)
            text = text[:m.start()] + text[m.end():]
            text = re.sub(r"\b" + name + r"\b", target, text)
    return text


def _rewrite_samplers(text: str, opaque, array_samplers: set[str]) -> str:
    """R6: combined-sampler uniforms and parameters -> separate texture/sampler objects for naga."""
    # flatten constant-indexed sampler arrays: name[ 3 ] -> name_3 (loops are unrolled, indices are literals)
    for n in array_samplers:
        text = re.sub(r"\b" + re.escape(n) + r"\s*\[\s*(\d+)\s*\]", lambda m, n=n: f"{n}_{m.group(1)}", text)
    flat_types = {}
    for t, n, a in opaque:
        for i in range(a or 0):
            flat_types[f"{n}_{i}"] = t
        if a is None:
            flat_types[n] = t
    # functions with sampler parameters
    split: dict[str, list[int]] = {}
    param_types: dict[str, dict[str, str]] = {}
    for name, ps, pe, _, _ in _functions(text):
        params = _split_args(text[ps:pe]) if text[ps:pe].strip() else []
        idx = []
        for k, p in enumerate(params):
            mm = re.match(r"\s*(?:in\s+)?" + _PRECISION_Q + r"(sampler2DShadow|samplerCubeShadow|sampler2D|samplerCube)"
                          r"\s+(\w+)\s*$", p)
            if mm:
                idx.append(k)
                param_types.setdefault(name, {})[mm.group(2)] = mm.group(1)
        if idx:
            split[name] = idx
    # call sites: sampler argument X -> X_tex, X_smp
    for fname, idx in split.items():
        pos = 0
        pat = re.compile(r"\b" + re.escape(fname) + r"\s*\(")
        while True:
            m = pat.search(text, pos)
            if not m:
                break
            open_p = m.end() - 1
            close_p = _matching(text, open_p, "(", ")")
            args = _split_args(text[open_p + 1:close_p])
            is_def = re.match(r"\s*(?:" + "|".join(_SAMPLER_TYPES) + r")\b", args[idx[0]] if args else "")
            if not is_def:
                for k in idx:
                    a = args[k].strip()
                    if not re.fullmatch(r"\w+", a):
                        raise ValueError(f"sampler argument {a!r} of {fname} is not an identifier")
                    args[k] = f" {a}_tex, {a}_smp "
                new = ",".join(args)
                text = text[:open_p + 1] + new + text[close_p:]
                close_p = open_p + 1 + len(new)
            pos = close_p + 1
    # signatures and bodies
    for fname in split:
        for name, ps, pe, bo, bc in _functions(text):
            if name != fname:
                continue
            ptypes = param_types[fname]
            body = text[bo:bc + 1]
            for pname, ptype in ptypes.items():
                body = re.sub(r"\b" + re.escape(pname) + r"\b",
                              f"{ptype}( {pname}_tex, {pname}_smp )", body)
            params = text[ps:pe]
            for pname, ptype in ptypes.items():
                ttype, stype, _, _ = _SAMPLER_TYPES[ptype]
                params = re.sub(r"(?:\bin\s+)?" + _PRECISION_Q + re.escape(ptype) + r"\s+" + re.escape(pname) + r"\b",
                                f"{ttype} {pname}_tex, {stype} {pname}_smp", params)
            text = text[:ps] + params + text[pe:bo] + body + text[bc + 1:]
            break
    # remaining uses of global samplers (builtin texture calls)
    for fn, t in flat_types.items():
        text = re.sub(r"\b" + re.escape(fn) + r"\b(?!_)", f"{t}( {fn}_tex, {fn}_smp )", text)
    return text


def _append_clip_remap(text: str) -> str:
    """R12/R13: WebGL clip space -> Vulkan framebuffer with GL memory layout (y negated, z from [-w,w] to [0,w])."""
    m = re.search(r"\bvoid\s+main\s*\(\s*\)\s*\{", text)
    if not m:
        raise ValueError("vertex shader has no main()")
    close = _matching(text, m.end() - 1, "{", "}")
    remap = ("\n\t" + HAND_WRITTEN_LINES["clip_y"] + "\n\t" + HAND_WRITTEN_LINES["clip_z"] + "\n")
    return text[:close] + remap + text[close:]


@functools.lru_cache(maxsize=64)
def _build_cached(key: tuple) -> Program:
    p = dict(key)
    vs, fs = webgl_sources(p)
    label = f"{p['shaderID']}"
    return vulkanize(vs, fs, label)


def build_program(params: dict) -> Program:
    """WebGLProgram parameters -> vulkanized Program (cached by parameter values)."""
    key = tuple(sorted((k, v if not isinstance(v, dict) else tuple(sorted(v.items()))) for k, v in params.items()))
    return _build_cached(key)
