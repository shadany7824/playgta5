# `web/`: the original three.js r186 WebGL build (engine `threejs-web`)

This directory runs the pinned, **unmodified** three.js r186 (`vendor/three`, see `vendor/three/VENDOR.md`) in
headless Chromium, driven by Playwright. It serves as the Phase 0 parity reference and as the performance baseline for
the native port. It is never the system being measured (DESIGN §0). It reads the same bundle as `native/runner.py`
(DESIGN §4.2, §5.2) and writes the same outputs (§4.3).

| File | Role |
|---|---|
| `harness.html` | Page with an import map (`three` → `./vendor/three/build/three.module.js`, `three/addons/` → `./vendor/three/examples/jsm/`) |
| `harness.js` | Builds the three.js scene from `bundle.json` and its arrays, and exposes `H.init / beginView / frame / finish` |
| `runner.py` | Runner CLI (§4.3): a local HTTP server, Chromium via Playwright, the frame loop, and EXR, PNG, receipt and timing output |
| `vendor/three/` | three@0.186.1 from npm, byte for byte. **Never edit it** (§5.3) |

## Running

```
python web/runner.py --bundle <bundle dir>/bundle.json --out <capture dir>
        [--parity] [--backend vulkan|d3d11|gl|gles|metal|swiftshader] [--power high-performance|low-power]
        [--adapter <substring>] [--chromium <exe>] [--cpu-resolve] [--headful] [--verbose]
```

Normally `renderers.base.launch(ThreeJsWeb(), bundle_json, out_dir, timeout_s)` starts the runner and maps its exit
code: `0` means ok; `2` means a by-design skip, printed as one line `{"skip": "..."}`, for example when Playwright,
Chromium, WebGL2 or float render targets are missing; anything else is a failure.

**Chromium** is found by `renderers.threejs.find_chromium()`, which tries `$HARNESS_CHROMIUM`, then
`$PLAYWRIGHT_BROWSERS_PATH/chromium-*/chrome-linux/chrome` (or `chrome-win/chrome.exe`), then Playwright's default
browser directory, then Playwright itself. Setup: `pip install -r requirements.txt` and `python -m playwright install
chromium`.

**GPU selection.**
- On Linux without `/dev/dri`, the runner uses SwiftShader (`--use-angle=swiftshader --enable-unsafe-swiftshader
  --ignore-gpu-blocklist`). `HARNESS_WEB_SOFTWARE=1` forces SwiftShader and `=0` forbids it.
- If no WebGL2 context can be created without SwiftShader, the runner retries once with it and records
  `settings.chromium.notes.software_fallback`.
- `--backend` maps to ANGLE (`--use-angle=...`). With no `--backend`, Chromium picks: D3D11 on Windows, Metal on
  macOS, GL or Vulkan on Linux. The native runner's `--backend vulkan` therefore means ANGLE Vulkan here.
- `--power` sets the WebGL `powerPreference`; `high-performance` also adds `--force_high_performance_gpu`.
- `--adapter` cannot be mapped, because Chromium has no adapter-by-name switch. It is recorded and compared with the
  WebGL renderer string (`device.adapter_matches`), not enforced.
- `HARNESS_CHROMIUM_ARGS` appends extra flags. On Windows with a GPU, nothing is needed: headless Chromium uses the
  GPU through ANGLE D3D11.

## What a run does

1. `runner.py` serves `web/` at `/` and the bundle directory at `/bundle/` from a `ThreadingHTTPServer` on
   `127.0.0.1` with a random port. It sets explicit MIME types, because on Windows the registry can map `.js` to
   `text/plain`, and COOP/COEP headers, so the page is cross-origin isolated and `performance.now()` has finer
   resolution.
2. Chromium opens `harness.html`, and `H.init(cfg)` builds the scene exactly as §5.2 describes:
   - `MeshLambertMaterial` with `Color.setRGB(r, g, b, LinearSRGBColorSpace)`.
   - `BufferGeometry` with position, normal and index (uint32).
   - `mesh.matrix` from the column-major array, with `matrixAutoUpdate = false`.
   - `PointLight` and `DirectionalLight` (with target), with shadows: `mapSize`, `bias`, `normalBias`, `radius`,
     near/far and the ortho camera from the bundle.
   - `RectAreaLight` after `RectAreaLightUniformsLib.init()`.
   - `HemisphereLight`, whose sky direction is its `position`, set to `up`.
   - `scene.background`, emitter meshes, and a `PerspectiveCamera` per station with `up` set before `lookAt`.

   Shaders are compiled up front with `compileAsync`, and that time is reported as precompute.
3. **Frame loop (Python).** For each station, `settle_frames` frames are rendered and the last one is written. The
   last two are read back so the receipt can report `convergence.last_rel_change`. For a timeline, frames `0..end_frame`
   are all drawn, and the frames listed in `capture.timeline.frames` are written. Frame *k* applies the timeline ops
   scheduled at *k* first, then draws, with a fixed timestep.
4. **Measurement pass.** Each of `engine_data.renderer.ssaa_offsets` is rendered with
   `camera.setViewOffset(W, H, dx, dy, W, H)` into an `RGBA` `FloatType` `WebGLRenderTarget`
   (`LinearSRGBColorSpace`, `NoToneMapping`). Each sample is added with weight 1/n into a second float target, using
   a fullscreen quad with `ONE, ONE` blending (`EXT_float_blend`; without it the samples are read back and averaged
   on the CPU). The result is read with `readRenderTargetPixels`, rows are flipped so row 0 is the top, and it goes
   to Python as base64 Float32 RGB. Stations are written as `<out>/<station>/final.exr` (FLOAT32, ZIP); timeline
   frames as `<out>/frames/<frame:05d>.exr` (HALF, ZIP).
5. **Parity pass (`--parity`, or `measure.parity`).** One sample with no view offset is rendered to the canvas, the
   way three.js draws to a canvas: `WebGLRenderer({antialias: false, alpha: false, preserveDrawingBuffer: true})`,
   `ACESFilmicToneMapping`, `toneMappingExposure = display.exposure`, `outputColorSpace = srgb`. It is read with
   `gl.readPixels` as RGBA8, flipped, and written as `final.png` (timeline: `frames/<frame>.png`). The same single
   sample is also rendered linear into the float target for `final.exr`. The PNG equals ACES then sRGB OETF of that
   EXR to within 1 LSB, which `tests/test_web_runner.py` checks.
6. **Probe modes (§5.1).** `CubeCamera(near, far, WebGLCubeRenderTarget(cubeSize, {type: HalfFloatType}))` is placed
   at the camera position, `await LightProbeGenerator.fromCubeRenderTarget(renderer, cubeRT)` computes the SH, and
   one `LightProbe` is in the scene.
   - `probe` captures on the first frame of each view and right after each timeline event, with the probe's
     intensity at 0 during capture (one bounce).
   - `probe_dynamic` recaptures every frame with the previous probe active.
   - Each view starts from a zero probe.
7. **Timing (`timing.json`, §4.3).** `EXT_disjoint_timer_query_webgl2` `TIME_ELAPSED` queries wrap the `main` pass
   and the `probe` pass (`CubeCamera.update`). Results are collected asynchronously and `GPU_DISJOINT` is honoured.
   `cpu_ms` is `performance.now()` around the frame (ops, probe and main submission); `readback_ms` is separate.
   Memory is computed from what the page allocated: SSAA targets, the cube target, shadow maps, LTC tables, canvas
   and geometry buffers. `peak_rss_bytes` is the peak sampled sum of the Chromium processes' RSS (psutil, or `/proc`
   on Linux; otherwise `null`).
8. **`receipt.json` (§4.3)** records every setting in effect. Under `device` it records the browser version, the
   WebGL `UNMASKED_RENDERER` string (`adapter`), the ANGLE backend, `adapter_type` (CPU for
   SwiftShader/llvmpipe, otherwise guessed from the renderer string), the Chromium flags and the relevant extensions.

## Behaviour to know when comparing

- **Shadow maps are updated once per frame.** The runner sets `shadowMap.autoUpdate = false` and
  `needsUpdate = true` at the start of each frame. Without this, three.js would redraw every shadow map in every
  `render()` call: 16 SSAA samples plus 6 cube faces per frame, which no real three.js app does per displayed frame.
  three.js draws shadows inside `render()`, so there is no separate `shadow` pass. They are counted in whichever pass
  renders first in the frame: `probe` on probe-capture frames, otherwise `main`. The receipt says so.
- **`main` includes the SSAA resolve** (the additive quad per sample). In parity mode, `main` is the single canvas
  render.
- **The probe capture sees `scene.background`**, because `CubeCamera.update` renders the scene as it is. With an
  environment light, the sky is therefore in the probe as well as in the `HemisphereLight`. This is three.js
  behaviour and is recorded as `settings.probe.capture_sees_background`.
- **SH9 ringing is not clamped** (`getLightProbeIrradiance`). A probe that sees a bright floor under a black sky can
  *subtract* light from upward-facing surfaces, so the isolated component can be negative in open scenes. That is the
  measured system's behaviour, not a harness error.
- **`probe_dynamic` runs `LightProbeGenerator`'s JavaScript SH projection every frame.** For a 128² HalfFloat cube
  that is about 150–200 ms of CPU per frame on SwiftShader, and it is part of `cpu_ms`.
- **The frame loop costs one Playwright round trip per frame** (about 1 ms). It is outside both `cpu_ms` and
  `gpu_ms`.

## Tests

`pytest tests/test_web_runner.py` takes about 15 s on SwiftShader. Browser tests are marked `web` and skip when
Chromium or Playwright are missing. They cover:
- EXR, receipt and timing output;
- the point-plane `direct` capture against `ρ/π·I·cosθ/d²` (within 1 % per interior pixel);
- the parity PNG against ACES/sRGB of the linear EXR;
- emitter radiance and background passing through unchanged in mini_room (all four light types);
- timeline frames switching exactly at the scheduled frames, with zero flicker between them;
- `probe` and `probe_dynamic` adding positive light in a closed lit room.
