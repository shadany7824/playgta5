# Vendored three.js r186 (unmodified)

| | |
|---|---|
| Package | `three` |
| Version | `0.186.1` (revision **186**) |
| Tarball | <https://registry.npmjs.org/three/-/three-0.186.1.tgz> |
| Tarball sha256 | `8cd068708ea44f2c73c944b1cead2ba2f0d5c15c8fc194e5700f4e4f4a033fe7` |
| Tarball sha1 (npm `shasum`) | `6d50f70c2c437f844179bbb56d6f5b774e1ca38a` |
| npm integrity | `sha512-blFeqb49wRCSGUGj7gtpfnSGHy2lwDk94RhUmS1c/hTby70kvChbWpkJ4Pm1390LqzzvTmzgXKHPEafJwCb8jA==` |
| Obtained with | `npm pack three@0.186.1` |

Every file below is a byte-for-byte copy of the file at the same relative path inside the tarball's `package/`
directory. `manifest.json` lists the sha256 of each one; `tests/test_vendor.py` checks them. **Never edit these
files** (DESIGN §5.3): `web/harness.js` drives the WebGL build, and the native port reads the sources.

## What is vendored and why

| Path | Why |
|---|---|
| `build/three.module.js`, `build/three.core.js` | The WebGL build the original (`threejs-web`) runs in headless Chromium. `three.module.js` imports `three.core.js`. |
| `examples/jsm/lights/LightProbeGenerator.js` | `LightProbeGenerator.fromCubeRenderTarget` for the `probe` modes (web runner imports it; native port ports its SH projection). |
| `examples/jsm/lights/RectAreaLightUniformsLib.js`, `RectAreaLightTexturesLib.js` | LTC tables for `RectAreaLight` (web runner calls `RectAreaLightUniformsLib.init()`; native port uploads the same tables). |
| `src/renderers/shaders/**` | `ShaderChunk/*.glsl.js` and `ShaderLib/*.glsl.js`: the native port extracts the GLSL from these template literals and resolves `#include`s by code (`native/three_chunks.py`), so no three.js shader maths is re-typed. |
| `src/renderers/webgl/**` | `WebGLProgram` (prefix/defines/include resolution), `WebGLLights` (uniform packing), `WebGLShadowMap`, `WebGLUniforms`, … ported as written, with file/line references. |
| `src/renderers/WebGLRenderer.js`, `WebGLRenderTarget.js`, `WebGLCubeRenderTarget.js` | Render-loop order, tone-mapping/output-colour-space handling, cube-target face setup for the probe capture. |
| `src/cameras/**` | `CubeCamera` face orientation, `PerspectiveCamera.setViewOffset` (SSAA offsets) and projection matrices. |
| `src/lights/**` | Light, shadow-camera and `LightProbe` behaviour (`PointLightShadow` cube faces, `DirectionalLightShadow` ortho camera, `RectAreaLight`, `HemisphereLight`). |
| `src/constants.js` | Enum values (`PCFShadowMap`, `ACESFilmicToneMapping`, `HalfFloatType`, …) referenced by the bundle and the port. |
| `LICENSE`, `package.json` | MIT licence (required for redistribution) and the exact version metadata. |

`src/lights/webgpu/` is included only because `src/lights/**` is copied whole; the harness does not use it.
