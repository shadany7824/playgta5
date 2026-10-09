"""GLSL from the vendored three.js r186 sources, assembled by code the way WebGLProgram.js does it.

* ``shader_chunks()`` parses ``src/renderers/shaders/ShaderChunk.js`` (the ``ShaderChunk`` object) and extracts each
  referenced template literal from ``ShaderChunk/*.glsl.js`` and ``ShaderLib/*.glsl.js``.
* ``shader_lib(id)`` parses ``ShaderLib.js`` for the vertex/fragment chunk names of a built-in shader.
* ``resolve_includes``, ``unroll_loops``, ``replace_light_nums`` and ``replace_clipping_plane_nums`` are ports of the
  functions of the same names in ``src/renderers/webgl/WebGLProgram.js`` (lines 214-304).
* ``ltc_tables()`` parses ``LTC_MAT_1``/``LTC_MAT_2`` from ``examples/jsm/lights/RectAreaLightTexturesLib.js``.

Nothing here contains shader maths: every GLSL character comes from the vendored files.
"""

from __future__ import annotations

import functools
import hashlib
import re
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
THREE_DIR = REPO_ROOT / "web" / "vendor" / "three"
SHADERS_DIR = THREE_DIR / "src" / "renderers" / "shaders"
SHADER_CHUNK_JS = SHADERS_DIR / "ShaderChunk.js"
SHADER_LIB_JS = SHADERS_DIR / "ShaderLib.js"
WEBGL_PROGRAM_JS = THREE_DIR / "src" / "renderers" / "webgl" / "WebGLProgram.js"
LTC_LIB_JS = THREE_DIR / "examples" / "jsm" / "lights" / "RectAreaLightTexturesLib.js"

__all__ = ["shader_chunks", "shader_lib", "resolve_includes", "unroll_loops", "replace_light_nums",
           "replace_clipping_plane_nums", "ltc_tables", "template_literals", "vendored_sha256", "THREE_DIR"]

_LITERAL = re.compile(r"export\s+(?:default|const\s+(\w+)\s*=)\s*/\*\s*glsl\s*\*/\s*`([^`]*)`\s*;")


def template_literals(path: Path) -> dict[str, str]:
    """{'default'|export name: GLSL text} of a *.glsl.js module. The literals contain no `${}`/backslashes
    (checked), so the cooked string equals the raw text between the backticks."""
    text = Path(path).read_text(encoding="utf-8")
    out = {}
    for m in _LITERAL.finditer(text):
        body = m.group(2)
        if "${" in body or "\\" in body:
            raise ValueError(f"{path}: template literal needs JS evaluation (interpolation/escape)")
        out[m.group(1) or "default"] = body
    if not out:
        raise ValueError(f"{path}: no /* glsl */ template literal found")
    return out


@functools.lru_cache(maxsize=1)
def shader_chunks() -> dict[str, str]:
    """The ``ShaderChunk`` object of ShaderChunk.js: chunk name -> GLSL text."""
    js = SHADER_CHUNK_JS.read_text(encoding="utf-8")
    default_imports = dict(re.findall(r"^import\s+(\w+)\s+from\s+'(\./ShaderChunk/[\w.]+)';", js, re.M))
    ns_imports = dict(re.findall(r"^import\s+\*\s+as\s+(\w+)\s+from\s+'(\./ShaderLib/[\w.]+)';", js, re.M))
    body = js[js.index("export const ShaderChunk = {"):]
    body = body[:body.index("\n};")]
    chunks: dict[str, str] = {}
    for key, ref in re.findall(r"^\s*(\w+)\s*:\s*([\w.]+)\s*,?\s*$", body, re.M):
        if "." in ref:
            mod, export = ref.split(".", 1)
            chunks[key] = template_literals(SHADERS_DIR / ns_imports[mod])[export]
        else:
            chunks[key] = template_literals(SHADERS_DIR / default_imports[ref])["default"]
    return chunks


@functools.lru_cache(maxsize=None)
def shader_lib(shader_id: str) -> tuple[str, str]:
    """ShaderLib[shader_id] -> (vertexShader, fragmentShader) GLSL (ShaderLib.js entries reference ShaderChunk)."""
    js = SHADER_LIB_JS.read_text(encoding="utf-8")
    m = re.search(r"^\t" + re.escape(shader_id) + r":\s*\{.*?vertexShader:\s*ShaderChunk\.(\w+),\s*"
                  r"fragmentShader:\s*ShaderChunk\.(\w+)", js, re.M | re.S)
    if m is None:
        raise KeyError(f"ShaderLib has no entry {shader_id!r}")
    chunks = shader_chunks()
    return chunks[m.group(1)], chunks[m.group(2)]


# ------------------------------------------------------------------------------------------------ WebGLProgram.js

_INCLUDE = re.compile(r"^[ \t]*#include +<([\w\d./]+)>", re.M | re.A)  # WebGLProgram.js:245


def resolve_includes(string: str, chunks: dict[str, str] | None = None) -> str:
    """WebGLProgram.resolveIncludes (WebGLProgram.js:247-278); shaderChunkMap is empty in r186."""
    chunks = shader_chunks() if chunks is None else chunks

    def replacer(m: re.Match) -> str:
        include = m.group(1)
        if include not in chunks:
            raise KeyError(f"THREE.WebGLProgram: Can not resolve #include <{include}>")
        return resolve_includes(chunks[include], chunks)

    return _INCLUDE.sub(replacer, string)


_UNROLL = re.compile(r"#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*"
                     r"\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end", re.A)  # WebGLProgram.js:282


def unroll_loops(string: str) -> str:
    """WebGLProgram.unrollLoops/loopReplacer (WebGLProgram.js:284-304)."""

    def replacer(m: re.Match) -> str:
        out = []
        for i in range(int(m.group(1)), int(m.group(2))):
            snippet = re.sub(r"\[\s*i\s*\]", f"[ {i} ]", m.group(3))
            out.append(snippet.replace("UNROLLED_LOOP_INDEX", str(i)))
        return "".join(out)

    return _UNROLL.sub(replacer, string)


def replace_light_nums(string: str, p: dict) -> str:
    """WebGLProgram.replaceLightNums (WebGLProgram.js:214-233); p uses the JS parameter names."""
    num_spot_light_coords = p["numSpotLightShadows"] + p["numSpotLightMaps"] - p["numSpotLightShadowsWithMaps"]
    for pat, val in (("NUM_SUN_LIGHTS", p["numSunLights"]), ("NUM_DIR_LIGHTS", p["numDirLights"]),
                     ("NUM_SPOT_LIGHTS", p["numSpotLights"]), ("NUM_SPOT_LIGHT_MAPS", p["numSpotLightMaps"]),
                     ("NUM_SPOT_LIGHT_COORDS", num_spot_light_coords),
                     ("NUM_RECT_AREA_LIGHTS", p["numRectAreaLights"]), ("NUM_POINT_LIGHTS", p["numPointLights"]),
                     ("NUM_HEMI_LIGHTS", p["numHemiLights"]), ("NUM_SUN_LIGHT_SHADOWS", p["numSunLightShadows"]),
                     ("NUM_DIR_LIGHT_SHADOWS", p["numDirLightShadows"]),
                     ("NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS", p["numSpotLightShadowsWithMaps"]),
                     ("NUM_SPOT_LIGHT_SHADOWS", p["numSpotLightShadows"]),
                     ("NUM_POINT_LIGHT_SHADOWS", p["numPointLightShadows"])):
        string = string.replace(pat, str(int(val)))
    return string


def replace_clipping_plane_nums(string: str, p: dict) -> str:
    """WebGLProgram.replaceClippingPlaneNums (WebGLProgram.js:235-241)."""
    string = string.replace("NUM_CLIPPING_PLANES", str(int(p["numClippingPlanes"])))
    return string.replace("UNION_CLIPPING_PLANES", str(int(p["numClippingPlanes"] - p["numClipIntersection"])))


# ------------------------------------------------------------------------------------------------ LTC tables

@functools.lru_cache(maxsize=1)
def ltc_tables() -> tuple[np.ndarray, np.ndarray]:
    """(LTC_MAT_1, LTC_MAT_2) as float32 (64, 64, 4): ``new Float32Array(LTC_MAT_n)`` of
    RectAreaLightTexturesLib.init (RectAreaLightTexturesLib.js:41-52)."""
    js = LTC_LIB_JS.read_text(encoding="utf-8")
    out = []
    for name in ("LTC_MAT_1", "LTC_MAT_2"):
        m = re.search(r"const\s+" + name + r"\s*=\s*\[([^\]]*)\]\s*;", js)
        if m is None:
            raise ValueError(f"{LTC_LIB_JS.name}: {name} not found")
        vals = [float(re.sub(r"\s+", "", v)) for v in m.group(1).split(",") if v.strip()]  # JS allows "- 4e-07"
        if len(vals) != 64 * 64 * 4:
            raise ValueError(f"{name}: expected {64 * 64 * 4} values, got {len(vals)}")
        out.append(np.asarray(vals, dtype=np.float64).astype(np.float32).reshape(64, 64, 4))
    return out[0], out[1]


def vendored_sha256(rel_paths) -> dict[str, str]:
    """sha256 of vendored files (paths relative to web/vendor/three) for receipts/provenance."""
    return {rel: hashlib.sha256((THREE_DIR / rel).read_bytes()).hexdigest() for rel in rel_paths}
