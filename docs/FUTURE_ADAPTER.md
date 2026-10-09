# The future engine slot: adapter contract

`renderers/future.py: FutureEngine` (engine name `future`) is the place a later engine plugs into the harness. Until
it is wired, `check_available()` raises `NotWired("future engine not wired: see docs/FUTURE_ADAPTER.md")`, and
`tools/pairs.py` records one skipped result per scene with `by_design: true` and that reason. This file is the
contract the engine has to meet. `docs/DESIGN.md` is binding where the two differ; section numbers below (§n)
refer to it.

The test engine `fake` (`FakeRenderer` and `renderers/fake_runner.py`) is a complete, minimal example of everything
below: a bundle builder, a subprocess runner, receipt, timing and captures. `tests/test_pipeline_fake.py` runs the
whole loop with it.

## 1. Modes

An engine declares its modes in `modes()` as `ModeInfo(name, kind, dynamic, counterpart, description)`. Exactly one
mode has kind `direct`. Every `indirect` mode is measured as `final(mode) − final(direct)` of the same engine, against
the reference's `full − direct` (§1, §7), so the direct mode has to be the same renderer with indirect lighting
switched off, not a different pipeline.

Each row pairs an engine mode with its counterpart in the measured system, the three.js r186 port (§5.1). The
engine columns are placeholders in `FUTURE_MODES` until an engine is wired; fill them in here and in the code.

| Engine mode | Kind | Dynamic | What it is in the engine (to fill) | System counterpart (three.js r186 port) |
|---|---|---|---|---|
| `direct` | direct | no | | `direct`: `MeshLambertMaterial`; point/directional lights with `PCFShadowMap` shadows; environment → `HemisphereLight(sky = π·L, ground = 0)` + background `L`; no probe, no ambient |
| `indirect` | indirect | no | | `probe`: `direct` + one global SH9 `LightProbe` from a `CubeCamera` at the camera, one bounce, re-baked at frame 0 and after every timeline step |
| `indirect_dynamic` | indirect | yes | | `probe_dynamic`: `direct` + the probe re-captured every frame with the previous frame's probe active (multi-bounce feedback) |

Rename the rows to the engine's own terms, and add or remove indirect modes as needed. Two rules:

- A mode is `dynamic` when its indirect lighting changes over frames after the scene stops changing (temporal
  accumulation, progressive updates, feedback). Dynamic modes settle for 64 frames at a station and capture every
  timeline frame. Only dynamic modes get temporal metrics (`t90`, afterglow, flicker; §7).
- A static mode must give its final answer on the frame the scene changes. It captures only the state capture frames.

## 2. Mapping the spec onto the engine's API

The bundle builder (`build_bundle`) turns a resolved `tools.spec.Scene` into the engine's own terms in
`engine_data` (§4.2). Everything it needs is in the `Scene`, `View` and `Mesh` objects of `tools/spec.py` and
`tools/geometry.py` (§2 "Python API").

**Frame and handedness.** The spec frame is right-handed, +Z up, in metres (§1). Map it with one fixed basis change and
write that change down here:

- a right-handed Y-up engine: `(x, y, z)_engine = (x, z, −y)_spec`, a rotation, so triangle winding is unchanged;
- a left-handed engine: the basis change is a reflection, so reverse the winding of every triangle (or flip the
  cull mode) and transform normals with the same matrix;
- an engine in centimetres: scale positions by 100 and convert every unit that has length in it (§2 below).

`cal_handedness` catches a mirrored or rotated image: red must be on the right of the image, green at the top.

**Survey origin.** Every spec position is local: metres relative to the float64 `origin` (§1). The resolver has
already subtracted the origin in float64 and cast to float32, so `Mesh.positions` are float32 local vertices. Hand
those to the engine unchanged, with the object's matrix (`Object.transform`, object space → local frame, float64).
Never rebuild world coordinates in float32. If the engine has large-world coordinates (double-precision
transforms), it may place the scene at `origin`, but the measured images must be the same; `cal_survey_origin`
and its `survey_equivalence` gate check this.

**Units of each source** (linear, radiometric, per channel, linear-sRGB primaries):

| Source | Spec field | Unit | Notes |
|---|---|---|---|
| point light | `intensity` | W·sr⁻¹ | isotropic, inverse square, no range cutoff (three.js: `distance 0`, `decay 2`) |
| directional light | `irradiance` | W·m⁻² on a surface perpendicular to the beam | `direction` is where the light travels |
| rect light | `radiance` | W·m⁻²·sr⁻¹ | one-sided, emits on the side of `normalize(u × v)`; visible to the camera; back side black unless `albedo` is given |
| environment | `radiance` | W·m⁻²·sr⁻¹ | constant over the sphere, at most one; seen as the background |
| material | `albedo` | [0, 1] | Lambertian, BRDF = albedo/π, two-sided |

An engine with photometric or "artist" units (lux, candela, nits, EV100, a physical camera, intensity × π
conventions) has to be set up so that the pixel values equal the radiance above. Switch off exposure and auto
exposure, or fix exposure to 1. Derive each conversion factor, write it in this file, and let the calibration gates
(§8) confirm it. Never fit a factor to make a gate pass.

**Encodings.** Colours are linear sRGB with no colour-space conversion: set the engine's working and output colour
spaces to linear, or bypass them. If the engine splits a light into colour and intensity, use the three.js split:
`color = v / max(v)`, `intensity = max(v)`, and `color = [1, 1, 1]`, `intensity = 0` when `v = 0` (§5.2).

**Cameras.** Pinhole camera with `position`, `look_at`, `up` and a vertical FOV in degrees; aspect = width/height
(§1). No depth of field, motion blur, lens distortion or vignetting. Pick near and far planes that clip nothing in
the scene. The reference uses a box pixel filter. Approximate it with a fixed set of subpixel offsets, the same on
every frame (three.js uses a 4×4 grid, `((i + 0.5)/4 − 0.5)` pixels), so a deterministic engine has no flicker. Any
temporal jitter the engine adds on its own counts as part of its result and shows up as flicker.

**Timeline semantics.** Time steps are fixed at `1/fps` (default 60), independent of wall-clock time. Frame `k` is
at `t = k/fps`. **Frame `k` applies the actions scheduled at `k`, then draws.** Actions (§2):

- `set_light`: sets the light's radiometric field (`intensity`, `irradiance` or `radiance`);
- `set_transform`: replaces the object's transform (rotate by `rotate_z_deg` about `pivot`, then translate);
- `set_material`: sets a material's `albedo`.

Every frame from 0 to `end_frame` is simulated and drawn, including the frames that are not written. Drive the
engine's own clock and any temporal accumulation from the fixed step (`dt = 1/fps`), never from wall time. If
something in the engine depends on wall time, the temporal metrics measure it and its receipt has to say so.

## 3. Reading back linear, high-precision output

- Render to a float target (RGBA32F; RGBA16F only when the engine cannot do 32-bit, and say so in the receipt) with
  **no tonemapping, no exposure, no gamma/OETF, no bloom, AO, fog, sharpening or other post effects**. The value
  written is linear radiance.
- Station captures are written as FLOAT32 EXR and timeline frames as HALF EXR, both ZIP, with channels `R`, `G`
  and `B` (§1). `tools/exr.py: write_exr(path, img, pixel_type="float"|"half", compression="zip")` does this.
- Row 0 is the **top** of the image and column 0 the left. APIs that read back bottom-up (OpenGL `glReadPixels`)
  must be flipped.
- NaN or inf in a capture makes the result fail (`tools.metrics`).

## 4. Bundle, runner, receipt, timing and capture layout

The contract is DESIGN §3 (run layout) and §4 (adapter interface). In short:

- **Engine class** (`renderers/base.py: Engine`): `name`, `modes()`, `capabilities()` (§4.4: `light:*`,
  `shape:mesh`, `timeline`, `op:*`), `check_available()`, `build_bundle(scene, mode, views, capture, out_dir)`,
  `runner_argv(bundle_json, out_dir, extra)`, `version()`, and optionally `runner_env()` and `known_limits()`.
  - `check_available()` raises `NotWired(reason)` when the engine cannot run on this machine (no runtime, no
    licence, no GPU). That is a by-design skip.
  - A scene that needs a capability the engine does not declare is skipped by design too (`Unsupported`, naming
    the missing capability).
- **Bundle** (`<run>/<engine>/<scene>/bundles/<mode>/bundle.json` + `arrays/*.bin`, §4.2): the common header
  (`bundle_version`, `engine`, `mode`, `scene`, `kind`, `image`, `fps`, `seed`, `capture`, `measure`, `arrays`)
  plus `engine_data` in the engine's own terms. `renderers.base.write_bundle` writes it.
  - `capture` comes from `tools.pairs` (`capture_request`): stations with `settle_frames` (4, or 64 for dynamic
    modes), or a timeline with every frame (direct and dynamic modes) or only the state capture frames (static
    modes).
- **Runner** (§4.3): `<interpreter> <runner> --bundle <bundle.json> --out <capture dir> [--adapter S]
  [--power high-performance|low-power] [--parity] [--backend B]`. It writes:
  - stations: `<out>/<station>/final.exr`;
  - timeline: `<out>/frames/<frame:05d>.exr` for every listed frame;
  - `receipt.json`: every setting in effect, the device, frames rendered, seed, `convergence`
    (`last_rel_change` per station; `tools.pairs` warns above 1e-3), outputs, times and host;
  - `timing.json`: per-frame `cpu_ms`, `gpu_ms` (null without GPU timestamps) and `passes`, plus `memory` and
    `precompute`.

  Exit codes: 0 = ok; 2 = by-design skip, after printing one JSON line `{"skip": "<reason>"}` to stdout; anything
  else = failure. `tools.pairs` records the last 40 lines of `runner.log` for a failure and goes on with the run.

## 5. Gates the engine must pass (DESIGN §8)

The engine's `direct` mode must match the analytic oracles of every calibration scene at **|bias| ≤ 1 %** and
**rel_l1 ≤ 2 %** on the oracle ROIs (`tools/gates.py`, written to `gates.json`):

| Scene | What it proves |
|---|---|
| `cal_point_plane` | point-light units, inverse square, Lambert 1/π, light position |
| `cal_sun_plane` | directional units and the sign of every direction component |
| `cal_sky_plane` | environment units |
| `cal_rect_plane` | rect-light units and facing; the emitter's radiance seen directly |
| `cal_handedness` | handedness, image orientation, linear output (emitters at the right pixels with their radiance) |
| `cal_furnace` | energy conservation (direct `= 1.5 L_e`) |
| `cal_survey_origin` | float64 → float32 local resolution; the image equals `cal_point_plane`'s (`survey_equivalence`) |

The indirect modes' `cal_furnace` results are reported as measurements (`furnace_isolated`, `passed: null`), not
gates. A calibration scene the engine skips by design, for lack of a capability, has no engine gate. The skip and
its reason appear in `metrics.json` and in the report.

## 6. How to wire it

1. **Engine class.** Replace `FutureEngine` in `renderers/future.py` (or add a module), keeping the name `future`
   or registering a new one. Fill in `modes()` (section 1), `capabilities()`, `check_available()`, `version()`,
   `known_limits()` and a bundle builder that maps the spec as in section 2.
2. **Runner.** Write it in the engine's own interpreter or binary: it reads the bundle, draws with the fixed
   timestep and writes the outputs of section 4. Start from `renderers/fake_runner.py` for the file and exit-code
   plumbing.
3. **Register.** Add the engine to `ENGINES` in `renderers/__init__.py` (`name → (module, class)`).
4. **Run.**
   - `python -m tools.pairs --run runs/<id> --engines <name> --scenes calibration`, then read `gates.json` until
     every applicable calibration gate passes.
   - Then `--scenes targeted` and `realworld`, `python -m tools.temporal --run runs/<id>` and
     `python -m tools.report --run runs/<id>`, or everything at once with
     `python -m tools.run_all --engines threejs-native,<name>`.
5. **Fix bugs at their source, measured before and after.** When a gate or metric shows a bug (wrong unit, mirrored
   axis, missing visibility, light leaks), fix it where it lives: in the engine, its configuration or the adapter's
   mapping. Never fix it by scaling or patching the output images. Keep the run from before the fix and the run from
   after, with the same reference cache and settings, and record both numbers next to the fix, in this file or the
   commit message. A fix with no measured before and after is not done.
6. **Fill in** the mode table (section 1) and the known-limits list (section 7).

## 7. Known limits

By-design properties of the wired engine that the measurements will show (one line each, with the evidence: source
file/line or a measured value). Empty until an engine is wired.

-
