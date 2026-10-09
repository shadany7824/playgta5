# Phase 0: the native port of three.js r186 lighting (`threejs-native`)

This document covers `native/`, the measured system of DESIGN §0. It is three.js r186's `WebGLRenderer` lighting
(`MeshLambertMaterial`, point/directional lights with `PCFShadowMap`, `RectAreaLight`, `HemisphereLight`, an SH9
`LightProbe` from a `CubeCamera`) running on Python + wgpu-py on **Vulkan**, offscreen, with linear HDR output. It
covers how the port is built, where every ported piece comes from, every line of shader code written by hand, every
WebGL-only workaround the native path drops or changes, and the three.js behaviours it reproduces on purpose. Paths
under `three/` mean `web/vendor/three/` (unmodified three@0.186.1).

## 1. Pipeline

```
bundle.json + arrays ──► SceneState (native/scene.py)          one Renderer per bundle (native/render.py)
                          materials, meshes, emitters,          per output frame k:
                          lights, cameras, timeline ops           1. timeline ops scheduled at k
                                                                  2. shadow maps (one pass per 2D map / cube face)
WebGLProgram parameters ─► webgl_sources()  (exact r186 GLSL)     3. probe: 6 CubeCamera faces -> HalfFloat cube,
                       ─► vulkanize()       (GLSL 450 for naga)      readback, LightProbeGenerator SH9 (numpy)
                                                                  4. main pass per SSAA sample (setViewOffset)
                                                                  5. resolve: fixed-order average (compute)
                                                                  6. readback (rows flipped to top-first), EXR/PNG
```

| Module | Role |
|---|---|
| `native/three_chunks.py` | Extracts GLSL from `ShaderChunk/*.glsl.js` and `ShaderLib/*.glsl.js` template literals by parsing `ShaderChunk.js` and `ShaderLib.js`; ports `resolveIncludes`, `unrollLoops`, `replaceLightNums` and `replaceClippingPlaneNums`; parses the LTC tables. |
| `native/program.py` | Ports the `WebGLProgram` prefix/defines generation (`webgl_sources`), then applies the mechanical WebGL2→Vulkan rewrite (`vulkanize`, rules R1–R14 below); std140 block layout and packing. |
| `native/three_math.py` | The JS-side maths in float64, operation for operation: `Matrix4`, `Matrix3`, `Quaternion`, `Vector3`, `Object3D.lookAt`, `Camera.updateMatrixWorld`, `PerspectiveCamera`, `OrthographicCamera`, `LinearToSRGB`, the colour-management matrix. |
| `native/scene.py` | Bundle → three.js-equivalent scene; timeline ops; `WebGLLights.setup` + `setupView` uniform packing; per-draw matrices. |
| `native/shadows.py` | `WebGLShadowMap` / `LightShadow` / `DirectionalLightShadow` / `PointLightShadow`: cameras, shadow matrices, map sizes, side rules. |
| `native/probe.py` | `CubeCamera` faces (fov −90, WebGL coordinate system) and `LightProbeGenerator.fromCubeRenderTarget`. |
| `native/render.py` | GPU resources, pipelines, the frame loop, SSAA, resolve, readback, parity output. |
| `native/device.py` | Adapter/device choice (Vulkan by default), GPU timestamps, allocation accounting, peak RSS. |
| `native/runner.py` | CLI and outputs of DESIGN §4.3 (receipt.json, timing.json, EXR/PNG). |

## 2. How the shaders are built

**Step 1: the exact WebGL source.** `program.webgl_sources(params)` reproduces `WebGLProgram`'s constructor (non-raw
path, GLSL 3 conversion) for a `WebGLPrograms.getParameters`-style parameter dict. That covers the precision block,
`#define SHADER_TYPE/NAME`, the feature defines, the built-in uniform and attribute declarations, the
`tonemapping_pars_fragment` and `colorspace_pars_fragment` chunks with the generated `toneMapping()` and
`linearToOutputTexel()`, `luminance()`, then the ShaderLib body with `#include`s resolved recursively, light counts
substituted and `#pragma unroll_loop` blocks unrolled.

*Verified:* `tests/test_native.py::test_webgl_sources_token_identical_to_real_threejs` captures the strings the
unmodified r186 build passes to `gl.shaderSource` in headless Chromium. It does this for the depth, distance, Lambert
(render target) and Lambert (canvas, ACES) programs of a scene with a shadowed point light, a shadowed directional
light, a rect light, a hemisphere light and a light probe. All 8 sources are token-identical to `webgl_sources`. Only
comments and whitespace are excluded from the comparison, because the build ships its chunks with them stripped.

**Step 2: the adapter.** `program.vulkanize(vertex, fragment)` makes the text acceptable to naga's GLSL 450
frontend (wgpu's `create_shader_module(label="vertex"|"fragment", code=...)`). Every rule is mechanical: it changes
declarations, qualifiers or how resources are reached, never an expression of three.js maths.

| Rule | Rewrite | Why |
|---|---|---|
| R1 | `#version 300 es` → `#version 450` | Vulkan GLSL. |
| R2 | Comments stripped; `#if/#ifdef/#ifndef/#elif/#else/#endif` evaluated by `program.Preprocessor` (with `defined()`, object-like macro expansion and integer arithmetic); active `#define`/`#undef` lines are kept, so naga still expands function-like macros such as `saturate()` | The later rules must see which declarations are live (e.g. a `struct` inside `#if NUM_POINT_LIGHTS > 0`). Comment stripping keeps `/* #if ... */` text out of the directive scan. |
| R3 | `precision <q> <type>;` statements dropped | GLSL ES only. Vulkan floats are IEEE binary32, the same as WebGL `highp` (three.js picks `highp` whenever the GPU supports it). |
| R4 | Every non-opaque `uniform T name[N];` moves into one of two `layout(std140)` blocks: `ThreeFrame` (set 0: camera, lights, shadows, probe, tone-mapping exposure) and `ThreeObject` (set 1: `modelMatrix`, `modelViewMatrix`, `normalMatrix`, `diffuse`, `emissive`, `opacity`, `receiveShadow`). Each block is the union of both stages' uniforms, and the struct types it uses are hoisted above it | naga accepts no free uniforms ("uniform/buffer blocks require layout(binding=X)"). Two sets match the update rates (per camera, per draw) and keep the binding count at 2 instead of ~20. |
| R5 | `uniform bool x;` → block member `uint x_b;` plus `#define x ( x_b != 0u )` | `bool` is not host-shareable in uniform buffers (naga: "Alignment requirements for address space Uniform are not met"). |
| R6 | Combined samplers become a texture plus a sampler: `uniform sampler2DShadow m[N]` → `texture2D m_i_tex` + `samplerShadow m_i_smp` (set 2), with constant-indexed arrays flattened (`m[ 0 ]` → `m_0`, valid because the loops are already unrolled). A function parameter `sampler2DShadow p` becomes `texture2D p_tex, samplerShadow p_smp`; its call arguments become `X_tex, X_smp`; inside the function `p` becomes `sampler2DShadow( p_tex, p_smp )`; other uses of a global sampler become `sampler2D( g_tex, g_smp )` | naga has no combined image samplers ("NotImplemented: variable qualifier") and rejects `sampler2DShadow` as a parameter type. |
| R7 | `varying T v[N];` → `layout(location = L) out/in T v[N];`, with locations taken from the vertex stage's declaration order and shared by name with the fragment stage | Vulkan needs explicit interface locations; GL linked them by name. |
| R8 | `attribute T a;` → `layout(location = K) in T a;` (position 0, normal 1). Attributes `main()` never reads are dropped, as GL's linker drops inactive attributes (`uv`, and `normal` in the depth programs) | Explicit vertex-input locations; wgpu requires a vertex buffer for every declared input. |
| R9/R10 | `#define attribute in` and `#define varying out/in` dropped | Replaced by R7/R8. |
| R10b | The GLSL3 compatibility macros (`#define texture2D texture`, `textureCube`, `texture2DLodEXT`, …, WebGLProgram.js:810-831) are applied textually (as the preprocessor would) and dropped | `texture2D`/`textureCube` are type names in Vulkan GLSL, so the macro would corrupt the R6 declarations. |
| R11 | `const in` → `in` in parameter lists | naga does not parse the `const` parameter qualifier (`InvalidToken(In, ...)`); it changes nothing at run time. |
| R12 | `gl_Position.y = - gl_Position.y;` appended to the vertex `main()` | Keeps WebGL's framebuffer memory layout (row 0 = bottom). §4 explains why this makes `gl_FragCoord`, shadow-map texel addressing and cube-face sampling identical to WebGL. |
| R13 | `gl_Position.z = ( gl_Position.z + gl_Position.w ) * 0.5;` appended | GL clip z ∈ [−w, w] → Vulkan [0, w]. The stored depth equals GL's window depth `0.5·z/w + 0.5`, which the shadow code assumes (`getPointShadow` computes `dp = far·(z−near)/(z·(far−near))`). |
| R14 | Shadow passes use only the vertex stage of the depth/distance programs (pipeline `fragment=None`) | r186 samples `shadow.map.depthTexture` for PCF (WebGLLights.js:257-269). The colour the depth/distance fragment shaders write is never read. naga also lacks `modf` (used by `packing.glsl.js`), so the unused depth fragment stage would not compile. |

`tests/test_native.py::test_vulkanized_program_adds_only_listed_hand_written_lines` checks that every line of the
Vulkan GLSL is either a three.js line (after undoing R6/R10b/R11) or one of the templates below. It runs for the
Lambert, Lambert-parity, depth and distance programs.

### Hand-written shader lines (complete list)

The templates are in `program.HAND_WRITTEN_LINES`. The `<...>` parts are filled in mechanically.

```glsl
#version 450
layout(std140, set = <0|1>, binding = 0) uniform <ThreeFrame|ThreeObject> {   // members = uniform declarations
};                                                                              //   moved verbatim (R4)
	uint <name>_b;                                     // R5, block member for a bool uniform
#define <name> ( <name>_b != 0u )                      // R5
layout(set = 2, binding = <2k>) uniform texture2D|textureCube <name>_tex;          // R6
layout(set = 2, binding = <2k+1>) uniform sampler|samplerShadow <name>_smp;        // R6
layout(location = <L>) out|in <type> <name>[<n>];      // R7, was: varying <type> <name>[<n>];
layout(location = <K>) in <type> <name>;               // R8, was: attribute <type> <name>;
	gl_Position.y = - gl_Position.y;                   // R12
	gl_Position.z = ( gl_Position.z + gl_Position.w ) * 0.5;   // R13
```

Two more pieces are hand-written but are harness code, not three.js shading:

* `render.RESOLVE_WGSL`, the SSAA average. It adds each sample times `1/N` into a float32 accumulator in a fixed
  order, so output is deterministic. The web runner must average the same offsets.
* `tests/test_native.py::test_std140_packing_matches_naga_layout` builds a throw-away compute shader. It reads
  every scalar of both blocks back so that `BlockLayout.pack` can be checked against naga's actual std140 offsets.

### Programs and variants

| Program | three.js counterpart | Variants |
|---|---|---|
| `lambert` | `MeshLambertMaterial` (ShaderLib `lambert`) | material side (`DOUBLE_SIDED` / `FLIP_SIDED`); `USE_LIGHT_PROBES` on or off; target (render target: `NoToneMapping` + `srgb-linear`; canvas/parity: `ACESFilmicToneMapping` + `srgb`) |
| `depth` | `MeshDepthMaterial`, `depthPacking = BasicDepthPacking` (directional shadow pass) | one program; the pipeline cull mode follows `shadowSide[material.side]` |
| `distance` | `MeshDistanceMaterial` (point-light cube shadow pass) | as for depth |

## 3. Provenance of every ported piece

| Native function | Ported from |
|---|---|
| `three_chunks.shader_chunks`, `shader_lib` | `three/src/renderers/shaders/ShaderChunk.js` (imports + `ShaderChunk` object), `ShaderLib.js` (`lambert` 27-, `depth` 177-187, `distance` 269-284) |
| `three_chunks.resolve_includes` | `WebGLProgram.js:245-278` (`includePattern`, `resolveIncludes`, `includeReplacer`; `shaderChunkMap` is empty in r186) |
| `three_chunks.unroll_loops` | `WebGLProgram.js:282-304` |
| `three_chunks.replace_light_nums`, `replace_clipping_plane_nums` | `WebGLProgram.js:214-241` (same replacement order) |
| `three_chunks.ltc_tables` | `examples/jsm/lights/RectAreaLightTexturesLib.js:41-52` (`LTC_MAT_1/2` → `Float32Array`) |
| `program.webgl_sources` | `WebGLProgram.js:414-836`; helpers `generatePrecision` 308-345, `generateShadowMapTypeDefine` 347-356, `generateDefines` 160-176, `getToneMappingFunction` 100-123, `getTexelEncodingFunction`/`getEncodingComponents` 36-98, `getLuminanceFunction` 127-147 |
| `program.lambert_parameters`, `depth_parameters`, `distance_parameters` | `WebGLPrograms.js:56-400` (`getParameters`: tone mapping only for the canvas 177-187, `outputColorSpace` 213, `opaque` 264, `doubleSided`/`flipSided` 373-374, `useDepthPacking` 376-377, `shadowMapEnabled` 363). Depth/distance programs use `numLightProbes = 0` because `shadowMap.render` runs before `setupLights()` (WebGLRenderer.js:1737 vs 1752) |
| `three_math.*` | `three/build/three.core.js`: `Matrix4.multiplyMatrices` 10570, `invert` 10743, `determinantAffine` 10669, `compose` 11030, `decompose` 11079, `lookAt` 10491, `extractRotation` 10297, `makeTranslation` 10841, `makePerspective` 11148, `makeOrthographic` 11208; `Matrix3.getNormalMatrix` 6406 (+ 6227, 6347, 6386), `multiplyMatrices` 6275; `Quaternion.setFromRotationMatrix` 4289; `Vector3.applyMatrix4` 5244, `transformDirection` 5319, `length` 5563, `normalize` 5586, `crossVectors` 5664; `Object3D.lookAt` 12585, `updateMatrix` 13035, `updateMatrixWorld` 13067; `LinearToSRGB` 6888; colour matrices 6682-6692 and `_getMatrix` 6803. Cameras: `src/cameras/Camera.js:112-130`, `PerspectiveCamera.js:304-381` (`setViewOffset`, `clearViewOffset`, `updateProjectionMatrix`), `OrthographicCamera.js:195-223` |
| `scene.light_uniforms` | `WebGLLights.js:221-643` (`setup`, `setupView`; light sort 153-157 and 245; shadow uniforms 334-352, 430-450; rect `halfWidth`/`halfHeight` 409-420, 600-619; hemisphere 456-466, 630-637; probe sum 279-287) |
| `scene.object_uniforms` | `WebGLRenderer.js:2160-2161` (`modelViewMatrix`, `normalMatrix`); `WebGLMaterials.js:138-152` (`refreshUniformsCommon`), 591-599 (`refreshUniformsDistance`) |
| `shadows.shadow_setups` | `WebGLShadowMap.js:21-29` (cube directions/ups), 51 (`shadowSide`), 172-198 (map-size clamp), 246-275 (depth textures, compare and filter), 293-325 (point faces); `LightShadow.js:213-268` (`updateMatrices`, `_updateMatrix` with the bias matrix); `DirectionalLightShadow.js:16`, `PointLightShadow.js:16` |
| `probe.cube_cameras` | `CubeCamera.js:5-6` (fov −90, aspect 1), 76-98, 115-133 (WebGL coordinate-system face ups/targets), 161-167 |
| `probe.sh_from_cube_faces` | `examples/jsm/lights/LightProbeGenerator.js:157-308` (pixel → cube coordinate 248-266, solid-angle weight 270-274, normalisation 296); `SphericalHarmonics3.getBasisAt` (three.core.js:48429) |
| `render.Renderer._create_ltc` | `RectAreaLightUniformsLib.init` + `RectAreaLightTexturesLib.js:51-52` (mag Linear, min Nearest, clamp); FLOAT/HALF choice `WebGLLights.js:471-485` |
| `render.Renderer._clear_color` | `WebGLBackground.js:46-86, 239-245`; `UniformsUtils.getUnlitUniformColorSpace` (UniformsUtils.js:128-148); `ColorManagement.convert` |
| `render.Renderer._cull`, `_front_face` | `WebGLRenderer.js:1200-1204` (`frontFaceCW` when `matrixWorld.determinantAffine() < 0`); `WebGLState.setMaterial` (side → cull face) |
| `render.Renderer.render_frame` order | `WebGLRenderer.render` 1640-1830: `shadowMap.render` (1737) → `setupLights` (1752) → background clear (1784) → `renderScene` (1978, `setupLightsView` 1982) |

## 4. Keeping WebGL's memory layout

Rather than adapting each place where WebGL's bottom-left framebuffer origin matters, the port renders every pass
with clip-space y negated (R12) and front faces set to `cw`. Rows in memory are then in exactly WebGL's order (row 0
= the bottom of the image), so all of the following equal WebGL without further edits:

* `gl_FragCoord`, including y measured from the bottom. PCF rotates its Vogel disk by
  `interleavedGradientNoise( gl_FragCoord.xy )`, so the noise pattern is identical.
* Shadow-map texel addressing (`shadowMatrix` maps v = 0 to the first row in memory).
* Cube-map face contents and sampling, both for point-light cube shadows and the probe cube. Vulkan and GL share the
  face-selection table and v = 0 → row 0.
* Readback: `LightProbeGenerator` reads the probe faces in GL row order exactly as `readRenderTargetPixels` returns
  them. Final images are flipped to top-row-first on readback, as the web runner flips `readPixels`.

This was verified with a probe shader: a triangle in GL's bottom-left lands in memory row 0, `gl_FragCoord.y = 0.5`
there, and a GL-counter-clockwise triangle is front-facing with `front_face="cw"`. The analytic tests then confirm
shading, shadow placement and image orientation end to end.

## 5. WebGL-only workarounds dropped or changed

The numbers come from llvmpipe 25.2.8 (Vulkan), using the measurement scripts summarised in §8.

| Workaround / WebGL constraint | Native path | Numerical change (measured) |
|---|---|---|
| **Clip-space depth range** GL [−1, 1] | R13 remap `(z + w)/2` in the vertex shader; three.js's GL projection matrices stay unchanged | Float32 emulation over 2·10⁵ depths (near 0.05, far 1000): max \|stored − exact\| is 1.48e-7 with the remap and 1.79e-7 with a native [0, 1] projection. They round to different 24-bit codes in 67% of samples (±1 code). No image effect: directional shadows have a 5e-4 depth bias; point shadows have none (bias 0, see DESIGN §5.2) but their 0.02 m normalBias is about 2e-5 in perspective depth at 3 m (near 0.01, normal incidence), some 300 codes; the main-pass depth only orders surfaces. |
| **Framebuffer origin / readback row order** | R12 y negation, front face `cw`, rows flipped on readback | None: same memory layout as WebGL (§4). |
| **Precision qualifiers** (`precision highp …`) | dropped (R3) | None: WebGL `highp` and Vulkan `float` are both binary32. three.js uses `mediump` only when `highp` is missing. |
| **Depth-texture vs packed-RGBA depth** | r186 PCF already samples a `DEPTH_COMPONENT24` depth texture with hardware compare; native uses `depth24plus` + a `less-equal` comparison sampler with linear filtering | Images were bit-identical between `depth24plus` and `depth32float` for mini_room (inside, outside) and mini_timeline at 16× SSAA, because on llvmpipe both resolve to the same storage. On GPUs with D24 support `depth24plus` is D24, like WebGL. For float formats Vulkan does not clamp the compare reference to [0, 1]; `getShadow` already discards z > 1. |
| **Shadow render target colour attachment** (`WebGLRenderTarget` always has an RGBA8 colour texture, and the depth/distance shaders write to it) | not allocated; depth-only pipelines (R14) | None (never read). Saves w·h·4 bytes per map and per cube face, plus the fragment work. |
| **Half-float cube target** (`HalfFloatType` for the probe; `readRenderTargetPixels` reads half floats) | kept: `rgba16float` cube, half→float widening is exact like `DataUtils.fromHalfFloat` | Half vs float cube: SH coefficients differ by at most 2.7e-4 (room inside) and 6.4e-4 (room outside, relative to the largest coefficient). The isolated probe component differs by 2.8e-4 and 3.3e-4 relative L1, max 1.6e-4 absolute. |
| **LTC tables FLOAT vs HALF** (`OES_texture_float_linear`) | `rgba32float` when the adapter has `float32-filterable` (it does here), otherwise `rgba16float`, mirroring WebGLLights.js:471-485 | None on Lambert surfaces: r186 Lambert never samples the LTC tables (§6). |
| **Texture-size limit** (`capabilities.maxTextureSize` clamps `shadow.mapSize`) | same clamp against wgpu `max-texture-dimension-2d` (16384 on llvmpipe; typically 8192–16384 on GPUs) | None at the bundle defaults (1024 cube faces, 2048 directional). |
| **Uniform-count limits** (`MAX_FRAGMENT_UNIFORM_VECTORS`, typically 1024 vec4 = 16 KiB on desktop) | two std140 uniform buffers (`maxUniformBufferBindingSize` ≥ 64 KiB) | No change in values (std140 packing checked against naga on the GPU). Frame-block size: 160 B base, +144 B per shadowed point light, +128 B per shadowed directional light, +64 B per rect light, +48 B per hemisphere light, +144 B for the probe, so about 400 lights fit in 64 KiB. Varyings are the tighter limit in both: one location per shadowed light, wgpu default 16 vs WebGL2 ≥ 15. |
| **Sampler state in texture objects** (GL) vs sampler objects (WebGPU) | explicit samplers with the same filter/compare/wrap state | None. |
| **Matrices in JS float64, uploaded as Float32Array** | ported operation-for-operation in float64 (`three_math.py`), cast to float32 when packed | Same values; `Math.tan` (V8 fdlibm) and the C libm `tan` may differ in the last float64 bit, which almost never survives the float32 cast. |
| **SH accumulation order** (`LightProbeGenerator` sums pixel by pixel in JS float64) | numpy (pairwise summation) | Max relative difference to a sequential float64 loop on a captured cube: 9.4e-14. 0% of the float32 uniform values differ. |
| **Shadow maps re-rendered in every `renderer.render()`** (`shadowMap.autoUpdate`), i.e. 6× per probe capture and N× for SSAA | rendered once per output frame and shared by the probe faces and every SSAA sample | None (nothing moves within a frame). Cost only. **The web runner should set `shadowMap.autoUpdate = false` and `needsUpdate = true` once per frame for a like-for-like performance comparison.** |
| **Opaque sort order** (`painterSortStable`: material id, z, id) | bundle order | Only for exactly coplanar overlapping surfaces (LessEqual depth test). None in the test scenes. |
| **GLSL compiler** (ANGLE → driver) vs naga → SPIR-V → driver | n/a | Floating-point contraction (fma) and transcendental precision belong to the driver. See §8: SwiftShader's `pow` is off by up to 2.6e-3 relative, while the native point light matches the analytic value to 3e-7 on llvmpipe. |

## 6. three.js r186 behaviours reproduced on purpose

The port reproduces behaviour, not appearance. These are properties of the original that the measurements will
show, not bugs in the port. Items 1–4, plus the `HemisphereLight`'s lack of occlusion, are what
`Engine.known_limits()` returns for both three.js engines (`renderers/threejs.py: THREEJS_KNOWN_LIMITS`), so the
report can print them:

1. **`RectAreaLight` does not light `MeshLambertMaterial`.** `lights_lambert_pars_fragment` defines only `RE_Direct`
   and `RE_IndirectDiffuse`. `lights_fragment_begin` evaluates rect lights only `#if ( NUM_RECT_AREA_LIGHTS > 0 ) &&
   defined( RE_Direct_RectArea )`, and `RectAreaLight.js` says "Only PBR materials are supported". The rect light's
   uniforms and LTC tables are declared and bound, but Lambert surfaces receive nothing from them. The emitter mesh
   still shows its radiance (emissive). The three.js engines therefore do not claim the `light:rect` capability
   (DESIGN §4.4): `cal_rect_plane`, `cal_furnace` and any other scene with a rect light are by-design skips for them,
   and their gates there are recorded as skipped, not failed. The bundle format still maps rect lights, so
   `test_rect_light_facing_and_lambert_receiver` (native) and `test_room_all_light_types_linear_output` (web) can pin
   the behaviour down.
2. **SH9 irradiance is not clamped.** `shGetIrradianceAt` can go negative from ringing; only the probe-grid path
   clamps. In mini_timeline (dark sky, lit floor below the probe), `probe` mode makes the floor 0.25% darker than
   `direct`, i.e. a negative isolated component.
3. **The probe also sees the background.** In outdoor scenes the sky reaches the surface twice in the probe modes:
   once through the `HemisphereLight` (direct) and again through the SH9 projection of the cube faces' background.
4. **One-sided emitters.** A rect light with zero albedo is `FrontSide`: it is invisible from behind (culled), and
   in the shadow pass it is drawn with `BackSide` (`shadowSide`). It occludes lights in front of its emitting face
   but not lights behind it.
5. **`Object3D.DEFAULT_UP`.** The directional shadow camera's `up` is `Object3D.DEFAULT_UP` at construction time.
   Neither runner changes it, so it stays (0, 1, 0) (three.core.js:13578) even though the scenes are +Z-up. The shadow
   map's texel grid is therefore oriented by +Y. A sun travelling exactly along ±Y would hit `Matrix4.lookAt`'s
   degenerate branch (it nudges z by 1e-4), and the port reproduces that branch too. `engine_data.frame.up` only fills
   in a missing per-camera or hemisphere `up`.

### 6.1 Directional shadow camera fit (adapter, both runners)

Where the directional shadow camera points and how far it reaches is not three.js behaviour; the adapter
(`renderers/threejs.py: ThreeJsBundleBuilder.directional_shadow_camera`) chooses it, and both runners read it from the
bundle. The depth range (near/far) spans the whole scene. The lateral extent is fitted to the region where a shadow
can fall: the light-space AABB of the union, over every pair of objects, of `footprint(A) ∩ footprint(B)`, with A = B
only for non-convex objects (DESIGN §5.2). Points outside that region cannot be shadowed, and `getShadow` returns 1
outside the frustum (`frustumTest`), so the fit changes no shadow; it only buys resolution. The old fit, a square
around every scene corner, is `dir_shadow_fit = "scene"`.

The old fit let the 120 m ground slab of the outdoor scenes set the map's extent. A 2048² map then had 8 cm texels.
Under a sun 45° high, a flat receiver's light-space depth changes by about one texel width (8 cm) from one texel to
the next. That is more than the `bias · (far − near)` ≈ 7 cm plus the 2 cm normal offset can absorb, so the sunlit
ground and walls showed acne stripes. Their pattern depends on rasterization details, so SwiftShader and llvmpipe
disagreed on them.

| Scene | Fit | Shadow camera (m) | Texel (cm) |
|---|---|---|---|
| courtyard_simplified | scene (before) | 171.50 × 171.50 | 8.37 × 8.37 |
| courtyard_simplified | casters (after) | 25.04 × 29.77 | 1.22 × 1.45 |
| occluded_canyon | scene (before) | 167.92 × 167.92 | 8.20 × 8.20 |
| occluded_canyon | casters (after) | 45.11 × 72.80 | 2.20 × 3.55 |
| offscreen_source | scene (before) | 8.23 × 8.23 | 0.40 × 0.40 |
| offscreen_source | casters (after) | 6.72 × 5.49 | 0.33 × 0.27 |

The depth range, and so the bias in metres, is unchanged: 6.9 cm (courtyard) and 7.7 cm (canyon).

Measured on this machine (`threejs-native` on llvmpipe, `threejs-web` on SwiftShader; `direct` mode, bundle defaults:
16 SSAA, 2048² map, 2 settle frames). "Acne" is the share of sunlit pixels (ray cast toward the sun from the
reference's hit points, eroded 2 px from shadow edges) that are more than 1 % darker than the exact three.js value
`ρ·(E·cosθ/π + L_sky·(0.5·n_z + 0.5))`. The `HemisphereLight` has no occlusion, so that value is exact wherever the
sun is visible.

| View | Fit | web vs native, rel. L1 | px > 1 % apart | Acne native / web | Darkest sunlit px (native) |
|---|---|---|---|---|---|
| courtyard_simplified/courtyard | scene | 0.71 % | 18.4 % | 84.6 % / 85.9 % | 0.77 |
| courtyard_simplified/courtyard | casters | 0.14 % | 1.2 % | 0.05 % / 0.65 % | 0.94 |
| courtyard_simplified/window_room | scene | 0.31 % | 1.5 % | 83.3 % / 84.5 % | 0.54 |
| courtyard_simplified/window_room | casters | 0.11 % | 1.0 % | 1.0 % / 0.9 % | 0.87 |
| courtyard_simplified/deep_room | scene | 0.011 % | 0.10 % | 89 % / 89 % (27 px) | 0.95 |
| courtyard_simplified/deep_room | casters | 0.010 % | 0.10 % | 0 % / 0 % | 1.00 |
| occluded_canyon/street | scene | 0.0082 % | 0.02 % | 18 % / 18 % (11 px) | 0.98 |
| occluded_canyon/street | casters | 0.0058 % | 0.02 % | 0 % / 0 % | 1.00 |
| occluded_canyon/low_wall | scene / casters | 0.0017 % / 0.0010 % | 0.01 % / 0.00 % | no sunlit pixel in view | |

On the sunlit courtyard ground alone (13 359 px), acne falls from 81 % (native) and 83 % (web) to 0 %, and the mean
ratio to the exact value rises from 0.973 to 1.0000. The canyon's views look into the sun-shadowed street, so the
fit changes little there. These numbers come from one-off scripts run during the change (both fits rendered with
`ThreeJsNative/ThreeJsWeb(dir_shadow_fit=...)`), not from a harness command.

`tests/test_threejs_bundle.py` checks the fit: frustum ⊇ every caster/receiver intersection, depth range = whole
scene, ray casts that ground points outside the map cannot be shadowed, and the degenerate `lookAt` branch.
`test_shadow_maps_put_shadows_where_geometry_says` (native) renders a box over a plane with the fitted map and finds
the analytic lit value outside the shadow, including outside the frustum.

## 7. Runner behaviour (DESIGN §4.3)

* `python native/runner.py --bundle B --out O [--adapter S] [--power high-performance|low-power] [--parity]
  [--backend vulkan]`. The backend comes from `--backend`, else `$WGPU_BACKEND_TYPE`, else Vulkan.
  `--adapter` matches a substring of device/vendor/description; otherwise the first adapter by power preference
  (discrete before integrated before CPU for high-performance).
* **Stations:** every station is rendered for `settle_frames` frames, and each station bakes its own probe at its
  camera position. `final.exr` (FLOAT32, ZIP, R/G/B) is written from the last frame. `convergence[station] =
  {settle_frames, last_rel_change}`, where `last_rel_change` = mean\|F_n − F_{n−1}\| / mean\|F_n\|.
* **Timeline:** frames 0…end_frame are simulated. At frame k the timeline ops are applied first, then the frame is
  drawn. Every listed frame is written as `frames/<k:05d>.exr` (HALF, ZIP).
* **Probe schedule:** `probe` captures at frame 0 (per station) and right after every timeline event, with the probe
  disabled (a program without `USE_LIGHT_PROBES`). `probe_dynamic` captures every frame with the previous frame's
  probe active; on the first frame that probe is zero.
* **SSAA:** each `engine_data.renderer.ssaa_offsets` entry is applied through `PerspectiveCamera.setViewOffset(W, H,
  dx, dy, W, H)`. The samples are averaged in order with weight 1/N in float32.
* **Parity (`--parity`, DESIGN §5.1 "one sample, no offsets"):** every frame is drawn as three.js draws to a canvas.
  That means one sample with no view offset, to an `rgba8unorm` target, with the canvas program
  (`ACESFilmicToneMapping`, `toneMappingExposure = display.exposure`, `linearToOutputTexel` = sRGB OETF), and the
  clear colour is the background after `LinearToSRGB`. This render is what `timing.json` times as `main`. On capture
  frames the 8-bit image is written as `final.png` (or `frames/<k>.png`). The same single sample is then rendered
  linear (`rgba32float`, `NoToneMapping`) for `final.exr`, matching `web/runner.py`'s parity mode. The receipt says
  `ssaa: 1`.
* **timing.json:** `cpu_ms` is the frame's wall time minus time spent blocked on the GPU (probe readback, timestamp
  readback). `wall_ms` is also recorded. `passes` sums GPU timestamp durations per category: `shadow` (each 2D map
  or cube face), `probe` (6 faces), `main` (each SSAA sample), `resolve` (each accumulation). Ticks are scaled by
  `wgpuQueueGetTimestampPeriod`, recorded in the receipt as `device.timestamp_period_ns`. `memory` is the bytes of
  every texture and buffer the runner created plus peak RSS. `precompute` covers shader build, pipeline creation,
  set-up time and the LTC table bytes.
* **Exit codes:** 0 ok; 2 by-design skip with `{"skip": reason}` (no matching adapter or backend, bundle feature the
  port does not have); 1 failure with a traceback in runner.log.

## 8. Pre-checks against real three.js (informal, this machine)

These are not the Phase 0 gates. They were run once during development, with a scratch page that builds the bundle's
scene with the vendored three.js in headless Chromium/SwiftShader (the same JS mapping as DESIGN §5.2). The results
were compared with the port on llvmpipe:

| Check | Result |
|---|---|
| GLSL passed to `gl.shaderSource` (depth, distance, lambert, lambert-parity) | token-identical (now a test) |
| Directional shadow occluder scene, float output, 1 spp | 99.61% of values bit-identical; the rest are 36 PCF-edge pixels (max 8.8%) |
| Point light over a plane (no occluder), float, 1 spp | relative diff median 6.6e-4, max 2.8e-3. Against the analytic L = ρ/π·I·cosθ/d², **native** is within 9.4e-7 and **SwiftShader** within 2.6e-3, so the difference is SwiftShader's `pow()` approximation in `getDistanceAttenuation` |
| Point shadow occluder scene | shadow masks identical (0 pixels disagree on lit vs dark) |
| Hemisphere light, float | identical except `+0` vs `−0` |
| Probe SH9 (`LightProbeGenerator.fromCubeRenderTarget` vs `probe.sh_from_cube_faces`), mini_room inside/outside, mini_timeline | max \|Δ\| / max\|c\| = 4.6e-4, 6.4e-4, 7.4e-4, with every sign and magnitude matching (orientation conventions confirmed) |
| 8-bit parity, mini_room `direct` (16 SSAA in the bundle; parity is 1 spp) | inside: p99.9 5 LSB, mean 0.105 LSB; outside: p99.9 3 LSB, mean 0.151 LSB. The outliers are isolated edge/T-junction pixels where SwiftShader and llvmpipe rasterize differently, plus the `pow()` difference |

Then, once `web/runner.py` existed, both real runners were run on the same bundles (64×48, 2×2 SSAA, 256² shadow
maps, 32² probe cube, 6 settle frames; SwiftShader vs llvmpipe):

| Bundle | `--parity` 8-bit \|web − native\| (inside / outside) | Measurement EXR (SSAA), relative L1 (inside / outside) |
|---|---|---|
| mini_room `direct` | p99.9 3 / 3 LSB, mean 0.101 / 0.152 LSB | 1.9e-3 / 1.9e-3 (median per-pixel 4.5e-4 / 0) |
| mini_room `probe` | p99.9 1 / 2 LSB, mean 0.045 / 0.070 LSB | 1.2e-3 / 1.7e-3 |
| mini_room `probe_dynamic` | p99.9 1 / 2 LSB, mean 0.018 / 0.069 LSB | 6.8e-4 / 1.7e-3 |
| mini_timeline `direct`, `probe_dynamic` (12 HALF frames) | n/a | 2.0e-3 (frames 0–3), 2.7e-3 (4–7), 3.0e-3 (8–11), so the events land on the same frames |

The single 211 / 95 LSB outlier pixel in each outside view is a T-junction crack in the room's slab geometry that
SwiftShader rasterizes open and llvmpipe closed.

On this machine both sides are software rasterizers with different edge rules and transcendental precision, so the
DESIGN §5.4 parity gate (p99.9 ≤ 1 LSB, mean ≤ 0.1 LSB) is not expected to pass here. The real-GPU run is what counts.

## Parity results

**How to run.** `tools/parity.py` runs the DESIGN §5.4 parity gate:

```
python -m tools.parity --run runs/<id>                     # the views of scenes/phase0_parity.json
python -m tools.parity --run runs/<id> --power high-performance --adapter "<GPU name part>" --strict
```

For each (scene, mode) of `scenes/phase0_parity.json` it builds both three.js bundles for the listed views only
(`phase0/bundles/<engine>/<scene>/<mode>/`). It then runs `web/runner.py` and `native/runner.py` with `--parity`
(one sample, ACES + sRGB, the 8-bit canvas, DESIGN §5.1) into `phase0/captures/<engine>/<scene>/<mode>/`, so the
measurement bundles and captures of the run are never overwritten. Station views settle for 2 frames (64 in dynamic
modes; `--settle-frames`, `--dynamic-settle-frames`). The static probe is baked on frame 0 on both sides. A timeline
state view runs its timeline up to the state's capture frame. `--adapter` and `--power` go to both runners.
`--strict` also exits 1 when the gate does not pass; without it the exit code only reports launch or comparison
failures.

**Pass criteria.** For each view and mode, `d = |web − native|` is taken per channel on the 8-bit `final.png`
values, over all pixels. The view passes when the 99.9th percentile of d is ≤ 1 LSB **and** the mean of d is ≤ 0.1
LSB. The percentile is the inverted-CDF one: the smallest observed d with at least 99.9 % of the (pixel, channel)
values at or below it, so it is always a whole number of LSB. The gate passes when every listed view and mode
passes. One failure fails it. A view that could not be compared (a runner missing or a launch failing) leaves the gate
`incomplete` (`passed: null`).

The following are reported but not gated:

* max d;
* the count and fraction of pixels with any channel more than 1 LSB off;
* the per-channel statistics;
* the same statistics on the **valid** pixels only: ROI `all` of DESIGN §7 (`|normal| > 0.99`, `depth > 0`, eroded
  by 1 pixel), taken from the view's reference AOVs in the run, or else from a reference-cache entry with the same
  view hash;
* the relative L1 difference of the linear `final.exr` that the same launches write (the same single sample,
  NoToneMapping).

`representative` is false, with the reason, when either side runs on a software rasterizer: SwiftShader, llvmpipe,
lavapipe, softpipe, WARP, or `adapter_type` CPU. The tool writes `phase0/parity.json` and one contact sheet per view
and mode, `phase0/sheets/<scene>__<view>__<mode>.png`, showing web | native | per-channel d × 32.

**This machine: not representative (both sides are software rasterizers).** Run on 2026-10-09 at commit `a3bad03`
with uncommitted harness changes. The host is a 4-vCPU Intel Xeon VM with no GPU.

* threejs-web: headless Chromium 141.0.7390.37, ANGLE Vulkan on SwiftShader (Subzero).
* threejs-native: wgpu 0.32 on Vulkan, `llvmpipe (LLVM 20.1.2, 256 bits)`, Mesa 25.2.8.

The command was `python -m tools.parity --run <run>` with every default: the 5 views and 9 (view, mode) pairs of
`scenes/phase0_parity.json`, 256×192, 2 settle frames, and the bundle defaults (`PCFShadowMap`, 1024² point and
2048² directional shadow maps, 128² HalfFloat probe cube, each scene's `display.exposure`). The valid-pixel masks
came from the reference cache for cal_point_plane and thin_wall. For opening, offscreen_source and
courtyard_simplified they came from `python -m tools.reference --run <run> --scenes
opening,offscreen_source,courtyard_simplified --views toward_door,s0,courtyard --spp-scale 0.0625`; the AOVs are
rendered at `aov_spp` 64 whatever the spp. All 18 launches took 1.7–2.5 s each, 40 s in total.

| View | Mode | p99.9 | mean | max | px > 1 LSB | valid px: p99.9 / mean / px > 1 LSB | linear rel. L1 | gate |
|---|---|---|---|---|---|---|---|---|
| cal_point_plane/s0 | direct | 1 | 0.010 | 1 | 0 (0.00 %) | 1 / 0.010 / 0 | 1.3e-4 | pass |
| thin_wall/lit | direct | 1 | 0.024 | 68 | 35 (0.07 %) | 1 / 0.017 / 0 | 8.2e-4 | pass |
| thin_wall/lit | probe | 1 | 0.020 | 62 | 32 (0.07 %) | 1 / 0.013 / 0 | 6.7e-4 | pass |
| opening/toward_door | direct | 4 | 0.025 | 177 | 94 (0.19 %) | 4 / 0.020 / 83 | 1.8e-3 | **fail** |
| opening/toward_door | probe | 5 | 0.025 | 161 | 100 (0.20 %) | 4 / 0.020 / 85 | 1.6e-3 | **fail** |
| offscreen_source/s0 | direct | 0 | 0.000 | 0 | 0 (0.00 %) | 0 / 0.000 / 0 | n/a (black image) | pass |
| offscreen_source/s0 | probe | 1 | 0.019 | 155 | 4 (0.01 %) | 1 / 0.009 / 0 | 1.4e-3 | pass |
| courtyard_simplified/courtyard | direct | 80 | 0.187 | 221 | 178 (0.36 %) | 78 / 0.159 / 97 | 1.7e-3 | **fail** |
| courtyard_simplified/courtyard | probe | 43 | 0.183 | 96 | 179 (0.36 %) | 40 / 0.163 / 92 | 2.1e-3 | **fail** |

Gate: **failed** (5 of 9 pass). The result is recorded but not representative. All the large differences come
from the two CPU rasterizers covering pixels, or shadow-map texels, differently. None comes from shading maths:

* **thin_wall:** the 35 off pixels are all isolated silhouette pixels; none is a valid pixel.
* **opening:** 83 of the 94 off pixels are valid pixels on the doorway's shadow edge on the floor, where SwiftShader
  and llvmpipe rasterize the shadow map's edge texels differently, so PCF gives different penumbra values.
* **courtyard:** 68 of the 178 off pixels are isolated single pixels where one side shows the wall colour and the
  other black or sky. These are T-junction cracks between the room slabs that the two rasterizers close
  differently (the dark specks on the web image's walls in the sheet). Most of the rest lie on the lines where the
  walls meet the ground, where one side shows the sky through a one-pixel gap.

Away from edges the two sides agree to 1 LSB. The linear images differ by 0.01–0.2 % relative L1, which matches §8.
The gate has to be run on the target GPU (Windows, the same adapter for both runners) before it means anything.

## Performance gate

**How to run.** `tools/perf.py --phase0` runs the DESIGN §5.4 performance gate. Without `--phase0` it measures cost
(DESIGN §7) for any engines, modes and scenes:

```
python -m tools.perf --run runs/<id> --phase0      # 5 rounds x (30 warm-up + 120 timed frames), web vs native
python -m tools.perf --run runs/<id> --phase0 --power high-performance --adapter "<GPU name part>" --strict
python -m tools.perf --run runs/<id>               # every threejs-native mode on thin_wall, opening, courtyard_simplified
```

**Method.**

* A **configuration** is (engine, scene, mode) on the station view that `scenes/phase0_parity.json` lists for the
  scene: thin_wall/lit, opening/toward_door and courtyard_simplified/courtyard by default. `--scenes all` uses every
  scene of the file.
* A **measurement** is one runner launch in measurement mode, with the bundle defaults: 16× SSAA into a linear float
  target, the same shadow maps and probe cube as above, and 256×192. The station settles for `warmup + frames`
  frames, with `measure.warmup_frames = warmup` and captures only at the end.
* **Rounds are interleaved round-robin.** Every configuration runs once per round in the order (scene, mode, web,
  native), so the launch order is web, native, web, native, …. Machine drift (clocks, heat, background load) then
  spreads over both sides instead of biasing one.
* **Statistics per configuration:**
  * p50 and p95 of GPU ms and CPU ms over the non-warm-up frames of every round pooled, using numpy linear
    interpolation;
  * the per-round p50s and their spread;
  * memory and precompute from `timing.json`, and the device from `receipt.json`.
* **GPU ms** is the frame total. Web: `EXT_disjoint_timer_query_webgl2` around its `main` and `probe` passes, with
  shadow maps rendered inside them. Native: wgpu timestamp queries summed over `shadow`, `probe`, `main` and
  `resolve`. The passes split a frame differently, so only totals are compared.
* **Outputs:** `perf.json`, merged with earlier `tools.perf` runs of the same run directory, and `phase0/perf.json`
  for this `--phase0` run alone. Each launch writes to `phase0/perf/captures/<engine>/<scene>/<mode>/round<k>/`.

**Pass criteria.** For every (scene, mode) of thin_wall, opening and courtyard_simplified × direct and probe, both
must hold:

* native GPU p50 ≤ web GPU p50;
* native GPU p95 ≤ web GPU p95.

One failing pair fails the gate. When a side has no GPU timestamps (for example a browser without the timer-query
extension), the gate is `not_measurable` and the reason is given. When a side was not measured, the gate is
`incomplete`. CPU ms are reported next to the gate but are not gated. The two runners define CPU time differently:

* web: JavaScript time from the start of the frame to its submission;
* native: frame wall time minus the time spent blocked on the GPU.

`representative` is false on software adapters.

The web runner cannot pick an adapter by name, because Chromium has no such flag. `--adapter` is therefore recorded
and checked against the WebGL renderer string (`device.adapter_matches` in the web receipt). On a machine with two
GPUs, pass `--power high-performance` and check that both `adapter` fields in `phase0/perf.json` name the same GPU.

In the static `probe` mode, the probe is baked on frame 0, which is a warm-up frame. The timed frames therefore
measure direct lighting plus the SH9 evaluation. The capture cost shows up only in `probe_dynamic`, which
`tools.perf` without `--phase0` measures.

**This machine: not representative.** The devices are the same as for parity (SwiftShader vs llvmpipe, both
`adapter_type` CPU). The command was `python -m tools.perf --run <run> --phase0 --rounds 3 --frames 30 --warmup 10`,
with defaults otherwise. That makes 12 configurations × 3 rounds = 36 launches in 5 min 19 s, with 90 timed frames
per configuration. Times are in ms.

| Scene / mode | web GPU p50 / p95 | native GPU p50 / p95 | native / web (p50, p95) | web CPU p50 / p95 | native CPU p50 / p95 | round-p50 spread, GPU (web / native) | pair |
|---|---|---|---|---|---|---|---|
| thin_wall / direct | 233.5 / 288.8 | 84.7 / 93.7 | 0.36, 0.32 | 0.5 / 3.0 | 22.9 / 29.0 | 12.1 / 0.4 | passed |
| thin_wall / probe | 258.9 / 309.0 | 96.5 / 141.7 | 0.37, 0.46 | 0.7 / 2.9 | 24.9 / 33.9 | 20.9 / 18.3 | passed |
| opening / direct | 205.7 / 256.2 | 73.4 / 85.4 | 0.36, 0.33 | 0.7 / 2.1 | 22.2 / 26.1 | 49.8 / 5.2 | passed |
| opening / probe | 234.2 / 285.0 | 76.3 / 90.5 | 0.33, 0.32 | 0.8 / 3.5 | 21.3 / 26.8 | 36.3 / 5.3 | passed |
| courtyard_simplified / direct | 255.1 / 312.5 | 89.0 / 99.8 | 0.35, 0.32 | 1.2 / 4.2 | 27.1 / 33.4 | 7.9 / 6.2 | passed |
| courtyard_simplified / probe | 294.5 / 366.8 | 89.1 / 105.4 | 0.30, 0.29 | 1.2 / 3.9 | 26.7 / 32.4 | 30.5 / 8.7 | passed |

Gate: **passed**, recorded as **not representative**. On these CPU rasterizers, the GPU timer measures how fast
SwiftShader and llvmpipe execute the work on 4 vCPUs. That says nothing about a real GPU.

The native GPU time splits as follows: shadow ≈ 18–25 ms, main ≈ 48–68 ms, resolve ≈ 6 ms.

Other results (memory is a property of the configuration, not of the machine):

* **Web round-to-round spread:** the web p50 varies by up to 24 % between rounds (opening/direct), while native
  varies by 0.5–18 %. At the default 5 rounds × 120 frames the spread should shrink.
* **Peak RSS:** about 0.89 GB for the Chromium processes, against 0.19 GB for the native runner.
* **GPU texture bytes:** 52 MB web vs 26 MB native on thin_wall. Native allocates no colour attachments for its
  shadow maps (§5).

## Tests

`tests/test_native.py` (marker `native`; the browser comparison is also `slow` and `web`):

* Shader assembly checks for the WebGL sources, the hand-written-lines whitelist, std140 packing against naga, and
  token identity with real three.js.
* Runner outputs, receipt/timing schema and GPU timestamps.
* Physics against analytic values: point-plane inverse square (1%), survey-origin OBJ plane, hemisphere sky
  (ρ·L) and background, rect-light facing (plus Lambert ignoring rect lights), and directional and point shadow
  placement. An outdoor sun on a 120 m ground is acne-free with the fitted directional map (§6.1) and shows acne on
  69 % of the sunlit ground with the old whole-scene square.
* Determinism (two runs bit-identical).
* Timeline: ops change the image at exactly their frame, and the probe is re-baked after each step.
* Probe: a positive isolated component in a closed room; `probe_dynamic` converges; SH orientation.
* Parity PNG plus clear colour, with the parity EXR equal to a 1-sample render; skip exit code; adapter selection.

`tests/test_parity.py` and `tests/test_perf.py` cover `tools/parity.py` and `tools/perf.py`:

* Synthetic parity comparisons with known answers: identical PNGs pass, +2 LSB fails, and both thresholds are
  checked exactly at their boundaries.
* Valid-pixel masks, software-adapter detection and the gate cases.
* Percentile maths on synthetic `timing.json` files.
* Both drivers end to end on a stub engine (`tests/phase0_stub.py`), which checks the interleaved launch order
  and that measurement captures are never touched.
* One real-runner run each, on a 64×48 view (markers `web`, `native`).
