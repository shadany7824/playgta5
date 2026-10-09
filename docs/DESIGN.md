# Lighting comparison harness: design contract

This file is the contract every module in the harness is written against. If code and this file disagree, fix
one of them in the same change. Section numbers are referenced from code comments as `DESIGN §n`.

## 0. Roles

| Role | What it is here | Where |
|---|---|---|
| **Reference** | Mitsuba 3 (`llvm_ad_rgb` on CPU, `cuda_ad_rgb` when present, `scalar_rgb` fallback). Converged ground truth plus AOVs. | `tools/reference.py` |
| **`<SYSTEM>` (the port)** | three.js r186 `WebGLRenderer` lighting, ported to a native runtime: Python orchestration + `wgpu-py` on **Vulkan**, offscreen, linear HDR. Engine name `threejs-native`. | `native/`, `renderers/threejs.py` |
| **The original (WebGL build)** | Pinned, unmodified three.js r186 in headless Chromium, driven by Playwright. Engine name `threejs-web`. Used for Phase 0 parity and as the performance baseline; never as the measured system. | `web/`, `renderers/threejs.py` |
| **Future engine** | Not wired. `NotWired` stub, reported as a skip reason. Contract in `docs/FUTURE_ADAPTER.md`. | `renderers/future.py` |
| **Fake engine** | `FakeRenderer`: a test engine whose runner perturbs the reference by known amounts, so tests can assert that every metric recovers them. | `renderers/future.py`, `renderers/fake_runner.py` |

The playgta5 files at the repo root (`serve_local.py`, `game.js`, `runtime/`, …) are unrelated to the harness and are
not touched or imported by it.

## 1. Conventions (shared by every engine and the reference)

- **Frame:** right-handed, **+Z up**, metres. A scene has a float64 **survey origin** (`origin`, e.g. UTM metres);
  every position in the spec is **local** (metres relative to `origin`) and every vertex handed to an engine is a
  float32 local coordinate. Mesh files may be given in world (survey) coordinates; the resolver subtracts the origin in
  float64 *before* casting to float32.
- **Units (linear, radiometric, linear-sRGB primaries):** radiance W·m⁻²·sr⁻¹ per channel; point-light
  `intensity` W·sr⁻¹; directional `irradiance` W·m⁻² on a surface perpendicular to the beam; rect-light and
  environment `radiance` W·m⁻²·sr⁻¹; material `albedo` in [0,1]. Lambertian BRDF = albedo/π. No exposure, no
  tonemapping, no gamma anywhere in measurement output.
- **Direct vs isolated:** `direct` = emitted radiance seen by the camera + single scattering from every source,
  environment included, with visibility (Mitsuba `path`, `max_depth=2`). `full` = all bounces (Mitsuba `path`,
  `max_depth=64`, `rr_depth=8`). The **isolated component** of a mode is `final(mode) − final(direct)` of the *same
  engine*; the reference's is `full − direct`.
- **Images:** EXR, row 0 = top of the image, column 0 = left. RGB channels `R,G,B`; single-channel AOVs use `Z`
  (depth) or `Y`. Station finals: FLOAT32 + ZIP. Timeline frames: HALF + ZIP.
- **Pixel filter:** box over the pixel. The reference uses Mitsuba's `box` rfilter. Engines approach it with a fixed
  set of subpixel offsets (SSAA) per output frame; the same offsets every frame, so a deterministic engine has zero
  flicker.
- **Time:** fixed timestep. Frame `k` is at `t = k / fps` (default fps 60), independent of wall time. Frame `k`
  applies the timeline actions scheduled at `k`, then draws.
- **Camera:** pinhole; `position`, `look_at`, `up` (default `[0,0,1]`), vertical FOV in degrees; aspect = width/height.
- **Luminance:** `Y = 0.2126 R + 0.7152 G + 0.0722 B`.

## 2. Scene spec (`scenes/<group>/<name>.json`)

Engine-neutral JSON. `tools/spec.py` validates it with path-qualified errors (`SpecError: objects[3].shape.size: ...`).

```jsonc
{
  "spec_version": 1,
  "name": "thin_wall",                       // unique; must equal the file stem
  "group": "calibration" | "targeted" | "realworld",
  "description": "…",
  "failure_mode": "light leaking through a 5 cm wall",   // targeted scenes: the single failure mode
  "comparison": "exact" | "appearance",      // default exact; appearance => only perceptual metrics are reported
  "origin": [346000.0, 6297000.0, 570.0],    // float64 survey origin, default [0,0,0]
  "image": {"width": 256, "height": 192},
  "display": {"exposure": 1.0},              // used only by parity mode and sheets
  "materials": {
    "white": {"type": "diffuse", "albedo": [0.8, 0.8, 0.8]}
  },
  "objects": [
    {"name": "floor", "material": "white",
     "shape": {"type": "box", "min": [-3,-2,-0.1], "max": [3,2,0]},           // or {"center":…, "size":…}
     "transform": {"translate": [0,0,0], "rotate_z_deg": 0, "pivot": [0,0,0]}},  // optional, default identity
    {"name": "q", "material": "white", "shape": {"type": "quad", "origin": [..], "u": [..], "v": [..]}},
    {"name": "house", "material": "white",
     "shape": {"type": "room", "min": [..], "max": [..], "thickness": 0.2,      // interior box; slabs grow outward
               "omit": ["+z"],                                                  // faces left open, optional
               "openings": [{"wall": "+x", "u": [0.5, 1.5], "v": [0.0, 2.0]}]}}, // see below
    {"name": "m", "material": "white", "shape": {"type": "mesh", "file": "meshes/x.obj", "coords": "local" | "world"}}
  ],
  "lights": [
    {"name": "lamp", "type": "point", "position": [..], "intensity": [r,g,b]},
    {"name": "sun", "type": "directional", "direction": [..], "irradiance": [r,g,b]},   // direction light travels
    {"name": "panel", "type": "rect", "origin": [..], "u": [..], "v": [..], "radiance": [r,g,b],
     "albedo": [0,0,0]},                     // emits on the side of normalize(u × v); optional reflectance
    {"name": "sky", "type": "environment", "radiance": [r,g,b]}                          // constant, at most one
  ],
  "stations": [{"name": "s0", "position": [..], "look_at": [..], "up": [0,0,1], "vfov_deg": 60}],
  "rois": [
    {"name": "dark_floor", "role": "dark" | "lit" | "bleed" | "oracle" | "any",
     "box": {"min": [..], "max": [..]},       // local coords; pixel kept if its first-hit position is inside
     "normal": [0,0,1], "min_cos": 0.9,       // optional: keep pixels whose shading normal·normal >= min_cos
     "views": ["s0"]}                          // optional: restrict to these view ids
  ],
  "timeline": {                              // optional => timeline scene
    "station": "s0", "fps": 60, "end_frame": 359,
    "steps": [{"frame": 120, "actions": [
      {"op": "set_light", "light": "lamp", "intensity": [0,0,0]},          // field named as in the light type
      {"op": "set_transform", "object": "door", "transform": {"translate": [..], "rotate_z_deg": 90, "pivot": [..]}},
      {"op": "set_material", "material": "red", "albedo": [..]}
    ]}]
  },
  "reference": {"spp": 4096, "batches": 4, "max_depth": 64, "aov_spp": 64},   // optional overrides
  "oracle": {"type": "point_plane", "...": "..."}                             // calibration scenes only, §8
}
```

- **Shapes** resolve to flat-shaded triangle meshes in object space (`tools/geometry.py`): `box` = 12 triangles with
  outward normals; `quad` = 2 triangles, normal `normalize(u × v)`; `room` = six slabs of `thickness` around the
  interior box `[min,max]` (floor `-z`, ceiling `+z`, walls `±x`, `±y`), minus `omit`, with rectangular `openings`
  cut through a wall by splitting the slab into boxes. Opening coordinates are axis ranges in the wall plane:
  for `±x` walls `u` is the y range and `v` the z range; for `±y` walls `u` = x, `v` = z; for `±z` slabs `u` = x,
  `v` = y. `mesh` loads OBJ (`v`, `vn`, `f` with polygons fan-triangulated); without `vn` it is flat-shaded.
- All materials are **two-sided** diffuse in every engine. Rect lights are one-sided emitters; their back side is
  black unless `albedo` is given (then both sides reflect).
- `transform` = rotate by `rotate_z_deg` about `pivot`, then translate. The object's matrix maps object space to the
  local frame.
- Spot lights, textures, specular materials and emissive meshes are not in spec v1 (see `STATUS.md` for why).

### Views (`tools/spec.py: expand_views`)

- A scene **without** a timeline has one view per station: `view.id = station name`, `kind = "station"`.
- A scene **with** a timeline has one view per **state**: state 0 = frames `[0, f1)`, state *i* = frames
  `[f_i, f_{i+1})`, the last state ends at `end_frame` inclusive. `view.id = "state<i>"`, `kind = "state"`, the camera is
  the timeline station, and `capture_frame = f_{i+1} − 1` (the frame just before the next step; `end_frame` for the
  last state). `view.state` is the scene with every action up to and including state *i* applied.
- Every view has a stable `hash` (sha256 of the canonical JSON of the resolved state, camera, image size, plus the
  sha256 of every geometry array).

### Python API (`tools/spec.py`, `tools/geometry.py`)

```python
class SpecError(ValueError)
@dataclass class Mesh:      positions (N,3) f32, normals (N,3) f32, indices (M,3) u32
@dataclass class Material:  name, albedo: np.ndarray(3,) f64
@dataclass class Object:    name, material, mesh: Mesh, transform: np.ndarray (4,4) f64, shape: dict
@dataclass class Light:     name, type, params: dict          # params hold the spec fields as float64 arrays
@dataclass class Station:   name, position, look_at, up, vfov_deg
@dataclass class ROI:       name, role, box_min, box_max, normal|None, min_cos|None, views|None
@dataclass class Timeline:  station, fps, end_frame, steps: list[(frame, actions)]
@dataclass class Scene:     name, group, description, failure_mode, comparison, origin, width, height, display,
                            materials: dict, objects: list, lights: list, stations: dict, rois: list,
                            timeline|None, reference: dict, oracle|None, source: Path, hash
@dataclass class View:      id, scene: str, kind, station: Station, state_index|None, capture_frame|None,
                            state: Scene, hash
load_scene(path) -> Scene ; apply_actions(scene, actions) -> Scene ; state_at_frame(scene, k) -> Scene
expand_views(scene) -> list[View] ; discover_scenes(selector="all"|"calibration"|"targeted"|"realworld"|name,...) -> list[Path]
world_matrix(obj) -> (4,4) ; transformed_mesh(obj) -> Mesh   # vertices in the local frame
```

## 3. Run layout

```
runs/<run_id>/                                   # one run; runs/LATEST holds the newest run dir (text file)
  run.json                                       # config, git sha, host, engines, scenes, start/end, durations
  views/<scene>.json                             # expanded views (ids, kinds, capture frames, hashes)
  reference/<scene>/<view>/                      # copied from the cache
      full.exr direct.exr full_stderr.exr direct_stderr.exr depth.exr normal.exr position.exr receipt.json
  <engine>/                                      # == "<run>" in the adapter contract below
    <scene>/bundles/<mode>/bundle.json + arrays/*.bin
    <scene>/stations/<mode>/<station>/final.exr        # station captures
    <scene>/timeline/<mode>/frames/<frame:05d>.exr     # timeline captures
    <scene>/{stations|timeline}/<mode>/receipt.json, timing.json, runner.log
  metrics.json gates.json temporal.json perf.json report.md
  sheets/<scene>/<view>.png   temporal/<scene>__<engine>__<mode>.png
  phase0/parity.json phase0/sheets/*.png phase0/perf.json
  phase0/{bundles,captures}/<engine>/<scene>/<mode>/          # parity launches (tools/parity.py, --parity)
  perf/{bundles,captures}/<engine>/<scene>/<mode>[/round<k>]/ # timed launches (tools/perf.py; phase0/perf/ with --phase0)
  inspect/                                       # built by tools/inspector.py
cache/reference/<key>/                           # reference cache, key = sha256 of the reference receipt inputs
```

`tools/layout.py: RunLayout(run_dir)` is the only place these paths are spelled out. Methods: `reference_dir(scene,
view)`, `engine_root(engine)`, `bundle_dir(engine, scene, mode)`, `capture_dir(engine, scene, kind, mode)`,
`station_capture(engine, scene, mode, station)`, `timeline_frame(engine, scene, mode, frame)`,
`view_capture(engine, scene, mode, view)`, `views_json(scene)`, and properties `metrics_json`, `gates_json`,
`temporal_json`, `perf_json`, `report_md`, `sheets_dir`, `temporal_dir`, `phase0_dir`, `inspect_dir`. Phase 0 and
perf launches never write into the measurement tree: `parity_bundle_dir/parity_capture_dir(engine, scene, mode)`,
`parity_capture(engine, scene, mode, view, ext)`, `phase0_sheet_png(scene, view, mode)`,
`perf_bundle_dir(engine, scene, mode, phase0)`, `perf_capture_dir(engine, scene, mode, round, phase0)`.

## 4. Adapter interface (every engine, now and later)

An **adapter** (Python, this project's interpreter) turns a resolved scene + mode + views into a **bundle**: a JSON
plus raw arrays in the engine's own terms. A **runner** (the engine's own interpreter or binary) draws the bundle as
a subprocess.

### 4.1 Engine class (`renderers/base.py`)

```python
class NotWired(Exception):            # .reason: str — reported by pairs.py as the skip reason
class Unsupported(Exception):         # .reason — scene needs a capability the engine lacks (by-design skip)
@dataclass class ModeInfo:
    name: str; kind: "direct" | "indirect"; dynamic: bool; counterpart: str; description: str
class Engine(ABC):
    name: str
    def modes(self) -> dict[str, ModeInfo]              # must contain exactly one mode of kind "direct"
    def capabilities(self) -> set[str]                  # see 4.4
    def check_available(self) -> None                   # raise NotWired(reason) when it cannot run here
    def build_bundle(self, scene: Scene, mode: str, views: list[View], capture: dict, out_dir: Path) -> Path
    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]
    def version(self) -> str
    def known_limits(self) -> list[str]                 # by-design limits of the engine's lighting, one sentence
                                                        # each, printed by the report (default [])
def launch(engine, bundle_json, out_dir, timeout_s, extra=()) -> LaunchResult   # runs the subprocess, keeps
                                                        # runner.log, maps exit codes (4.3), never raises on failure
def get_engine(name) -> Engine                          # registry in renderers/__init__.py
```

### 4.2 Bundle (`bundle.json`)

```jsonc
{
  "bundle_version": 1,
  "engine": "threejs", "mode": "probe", "scene": "thin_wall",
  "kind": "stations" | "timeline",
  "image": {"width": 256, "height": 192},
  "fps": 60, "seed": 1,
  "capture": {
    "stations": [{"name": "s0", "camera": "s0", "settle_frames": 32}],        // kind == stations
    "timeline": {"camera": "s0", "end_frame": 359, "frames": [0, 1, 2, ...]}   // kind == timeline
  },
  "measure": {"timing": true, "warmup_frames": 8, "parity": false},
  "arrays": {"floor.position": {"file": "arrays/floor.position.bin", "dtype": "float32", "shape": [24, 3]}, ...},
  "engine_data": { ... }                                                       // engine's own terms (5.2)
}
```

Arrays are little-endian raw binary, C order. `capture.timeline.frames` lists every frame to write; frames not
listed are still simulated and drawn.

### 4.3 Runner CLI and outputs

```
<engine interpreter> <runner> --bundle <dir>/bundle.json --out <capture dir>
        [--adapter <substring>] [--power high-performance|low-power] [--parity] [--backend vulkan]
```

`--out` is `RunLayout.capture_dir(...)`. The runner writes:

- stations: `<out>/<station>/final.exr` (FLOAT32, linear). With `--parity` also `<out>/<station>/final.png`
  (8-bit sRGB after the original's tonemap, §6).
- timeline: `<out>/frames/<frame:05d>.exr` (HALF, linear) for each listed frame.
- `<out>/receipt.json`:
  ```jsonc
  {"receipt_version": 1, "engine": "threejs-native", "engine_version": "three.js r186 port @ <git sha>",
   "runner": "native/runner.py", "scene": "...", "mode": "...", "kind": "...", "parity": false,
   "settings": { /* everything in effect: ssaa, shadow map type/size/bias, probe cube size, formats, tonemap, ... */ },
   "device": {"adapter": "...", "backend": "Vulkan", "adapter_type": "DiscreteGPU|IntegratedGPU|CPU", "vendor": "...",
              "driver": "...", "browser": "(web runner only)"},
   "frames": {"fps": 60, "rendered": 392, "timestep": "fixed"},
   "seed": 1,
   "convergence": {"s0": {"settle_frames": 32, "last_rel_change": 0.0}},
   "outputs": ["s0/final.exr"],
   "started_utc": "...", "finished_utc": "...", "wall_seconds": 3.2,
   "host": {"os": "...", "python": "...", "cpu": "..."}}
  ```
- `<out>/timing.json`:
  ```jsonc
  {"timing_version": 1, "units": "ms", "gpu_timestamps": true, "warmup_frames": 8,
   "frames": [{"frame": 0, "station": "s0", "warmup": true, "cpu_ms": 4.1, "gpu_ms": 2.0,
               "passes": {"shadow": 0.4, "probe": 0.0, "main": 1.5, "resolve": 0.1}}],
   "memory": {"gpu_texture_bytes": 0, "gpu_buffer_bytes": 0, "peak_rss_bytes": 0},
   "precompute": {"seconds": 0.0, "bytes": 0, "items": {}}}
  ```
  `gpu_ms` is null when GPU timestamps are unavailable (then `gpu_timestamps` is false).

Exit codes: `0` success; `2` by-design skip (the runner prints one JSON line `{"skip": "<reason>"}` to stdout);
anything else is a failure (pairs records the last 40 lines of `runner.log`).

### 4.4 Capabilities

`light:point`, `light:directional`, `light:rect`, `light:environment`, `shape:mesh`, `timeline`,
`op:set_light`, `op:set_transform`, `op:set_material`. `pairs.py` derives a scene's needs from its spec and
skips (by design) engines that lack one, naming the missing capability. `tools/gates.py` records the gates of such
a (scene, engine) as by-design skips, never as failures (§9).

The three.js engines claim every capability **except `light:rect`** (`renderers/threejs.py:
THREEJS_CAPABILITIES`): r186 `MeshLambertMaterial` ignores `RectAreaLight` (`lights_lambert_pars_fragment` defines
only `RE_Direct` and `RE_IndirectDiffuse`, `lights_fragment_begin` evaluates rect lights only when
`RE_Direct_RectArea` is defined, and `RectAreaLight.js` says "Only PBR materials are supported"). Scenes with rect
lights (`cal_rect_plane`, `cal_furnace`) are therefore by-design skips for them. Their `known_limits()` lists this
and the other by-design limits (HemisphereLight has no occlusion; the probe's SH9 is unclamped; the probe cube sees
`scene.background`, so outdoor probe modes count the sky twice; one-sided rect emitters are see-through from
behind).

## 5. The system: three.js r186, original and port

### 5.1 Modes (`renderers/threejs.py: THREEJS_MODES`)

| mode | kind | dynamic | three.js counterpart |
|---|---|---|---|
| `direct` | direct | no | `MeshLambertMaterial`; `PointLight`/`DirectionalLight` with `PCFShadowMap` shadows; environment → `HemisphereLight(sky = π·L, ground = 0)` + `scene.background = L`. No light probe, no ambient. (The bundle still maps rect lights to `RectAreaLight` + an emitter mesh, but Lambert ignores them, so the engines do not claim `light:rect`, §4.4.) |
| `probe` | indirect | no | `direct` + one global `LightProbe` (SH9) from `CubeCamera` at the camera position via `LightProbeGenerator.fromCubeRenderTarget`, captured with the probe disabled (one bounce). Re-baked at frame 0 and immediately after every timeline step. |
| `probe_dynamic` | indirect | yes | `direct` + the same probe re-captured **every frame** with the previous frame's probe active (progressive multi-bounce feedback). |

Measurement mode: render to an `RGBA32F` target with `NoToneMapping` and linear output; `ssaa` (default 16) fixed
subpixel offsets via `camera.setViewOffset`, averaged. Parity mode (`--parity`): one sample, no offsets, render to an
8-bit target with `ACESFilmicToneMapping`, `toneMappingExposure = display.exposure`, `outputColorSpace = srgb`,
exactly as three.js draws to a canvas.

### 5.2 `engine_data` for three.js (one format, read by both runners)

```jsonc
{
  "three_revision": "186",
  "frame": {"up": [0,0,1], "origin_world": [..]},
  "materials": {"white": {"type": "MeshLambertMaterial", "color": [r,g,b], "emissive": [0,0,0], "side": "DoubleSide"}},
  "meshes": [{"name": "floor", "material": "white", "position": "floor.position", "normal": "floor.normal",
              "index": "floor.index", "matrix": [16 floats, column-major = Matrix4.elements],
              "castShadow": true, "receiveShadow": true}],
  "emitters": [{"name": "panel", "position": "...", "normal": "...", "index": "...", "matrix": [...],
                "emissive": [r,g,b], "side": "FrontSide" | "DoubleSide", "color": [r,g,b]}],   // visible rect lights
  "lights": [
    {"name": "lamp", "type": "PointLight", "color": [..], "intensity": I, "distance": 0, "decay": 2,
     "position": [..], "castShadow": true,
     "shadow": {"mapSize": [1024,1024], "bias": 0.0, "normalBias": 0.02, "radius": 1, "near": 0.05, "far": 100}},
                                             // bias 0: r186 point shadows compare perspective depth, see below
    {"name": "sun", "type": "DirectionalLight", "color": [..], "intensity": E, "position": [..], "target": [..],
     "castShadow": true, "shadow": {"mapSize": [2048,2048], "bias": -0.0005, "normalBias": 0.02, "radius": 1,
     "camera": {"left": .., "right": .., "top": .., "bottom": .., "near": .., "far": ..},
     "fit": "casters" | "scene"}},                // how the camera was fitted (below); runners ignore it
    {"name": "panel", "type": "RectAreaLight", "color": [..], "intensity": L, "width": w, "height": h,
     "position": [center], "quaternion": [x,y,z,w]},
    {"name": "sky", "type": "HemisphereLight", "skyColor": [..], "groundColor": [0,0,0], "intensity": πL,
     "up": [0,0,1]}],
  "background": [r,g,b],
  "cameras": {"s0": {"position": [..], "lookAt": [..], "up": [0,0,1], "fov": 60, "near": 0.05, "far": 1000}},
  "probe": {"enabled": false, "dynamic": false, "cubeSize": 128, "near": 0.05, "far": 1000,
            "type": "HalfFloatType"},                       // WebGLCubeRenderTarget texture type
  "timeline": {"fps": 60, "events": [{"frame": 120, "ops": [
     {"op": "light", "name": "lamp", "intensity": 0.0, "color": [..]},
     {"op": "matrix", "mesh": "door", "matrix": [..]},
     {"op": "material", "name": "red", "color": [..]}]}]},
  "renderer": {"shadowMapType": "PCFShadowMap", "ssaa": 16,
               "ssaa_offsets": [[-0.375, -0.375], ...],    // pixels; 4x4 grid ((i+0.5)/4 - 0.5); both runners use these
               "parity": {"toneMapping": "ACESFilmicToneMapping", "exposure": 1.0, "outputColorSpace": "srgb"}}
}
```

Colours are linear-sRGB; a light's RGB value `v` is split as `color = v / max(v)`, `intensity = max(v)`
(`color = [1,1,1]`, `intensity = 0` when `v = 0`). Colours are set with `Color.setRGB(r, g, b,
LinearSRGBColorSpace)` so three.js colour management never converts them. Three.js lights and cameras look down
their local −Z, so `RectAreaLight` emits along its local −Z; the adapter computes the quaternion so that −Z equals
the spec's `normalize(u × v)`. The calibration gates (§8) confirm every one of these mappings.

**Directional shadow camera.** The light sits up-beam of the scene's AABB and looks at its centre (`up` =
`Object3D.DEFAULT_UP`, docs/PHASE0.md §6). `near`/`far` span the whole scene, so every caster between the light and
a receiver is in the map. Laterally (shadow-camera x/y) the camera is fitted to where a shadow can fall
(`dir_shadow_fit = "casters"`, the default): a point is shadowed only by geometry between it and the light, and the
two share light-space (x, y), so a shadow cast by object A on object B lies in `footprint(A) ∩ footprint(B)`, with
A = B only when B is not convex (`box` and `quad` shapes and rect emitters are convex; a convex solid cannot shadow
its own lit faces). The camera covers the AABB of the union of those intersections over every pair (each object is
both caster and receiver, over every timeline transform), padded by 1 % of its size plus 2 `normalBias`.
`left/right/top/bottom` may be asymmetric. This is exact: points outside cannot be shadowed, and three.js treats
points outside the shadow frustum as lit (`getShadow`: `frustumTest`). A ground slab therefore no longer sets the
map's extent: on `courtyard_simplified` a texel shrinks from 8.37 cm to 1.22 × 1.45 cm, which removes the acne
stripes of the outdoor scenes (numbers in docs/PHASE0.md §6.1). When no pair can cast a shadow, and with
`dir_shadow_fit = "scene"` (kept for A/B measurements), the camera is the square around every scene corner.

Shadow `bias` is in shadow-map depth units. Directional maps are orthographic, so depth is linear and the bias is
`bias · (far − near)` metres. r186 point lights compare **perspective** depth (`getPointShadow`:
`dp = far·(z − near) / (z·(far − near)) + bias`), so a constant bias is `bias · z²·(far − near)/(far·near)` metres
and grows with distance (−0.0005 with near 0.01 is about 0.5 m at 3.2 m: light passes through walls). Point lights
therefore get `bias = 0` and rely on the world-unit `normalBias`.

### 5.3 Phase 0 port rules (`native/`)

- **Port behaviour, not appearance.** GLSL comes from the vendored `web/vendor/three/src/renderers/shaders`
  (`ShaderChunk/*.glsl.js`, `ShaderLib/meshlambert.glsl.js`, …), extracted from the JS template literals and
  `#include`-resolved by code (`native/three_chunks.py`), the way `WebGLProgram` does it. A thin adapter adds
  `#version 450`, uniform blocks with set/binding layouts, varying locations and output declarations, and the
  WebGL→Vulkan clip-space depth remap. **No three.js maths is re-typed by hand.** Every hand-written shader line
  is listed in `docs/PHASE0.md`. JS-side behaviour (`WebGLLights` uniform packing, `WebGLShadowMap`,
  `CubeCamera` face orientation, `LightProbeGenerator` SH projection, `RectAreaLightUniformsLib` LTC tables) is
  ported from the vendored sources with file/line references in comments.
- **Parity mode** reproduces the WebGL output (same tonemap, same 8-bit encoding). **Measurement mode** writes
  linear float output with the fixed timestep, no post effects, and records its settings in the receipt.
- Every WebGL-only workaround the native path drops (precision qualifiers, packed-depth or half-float fallbacks,
  texture-size limits, clip-space conventions, uniform-array limits) is listed in `docs/PHASE0.md` with what changed
  numerically and the measured effect.
- **Backend:** Vulkan by default (`WGPU_BACKEND_TYPE=Vulkan`, overridable with `--backend`). Adapter choice by
  `--power` or `--adapter <substring>`; the chosen adapter is in the receipt. No window, no surface.
- **GPU timestamps** per pass (`shadow`, `probe`, `main`, `resolve`) when the adapter supports `timestamp-query`;
  memory = bytes of every texture/buffer the runner allocated, plus peak RSS.
- The WebGL build (`web/vendor/three`) is never edited. `web/harness.js` only drives it.

### 5.4 Phase 0 gates

- **Parity** (`tools/parity.py`): on the views in `scenes/phase0_parity.json`, both runners in `--parity`; per channel
  `|web − native|` on 8-bit values. Pass when the 99.9th percentile ≤ 1 LSB and the mean ≤ 0.1 LSB. Writes
  `phase0/parity.json` and contact sheets `web | native | |diff|×32`.
- **Performance** (`tools/perf.py --phase0`): same scenes, same adapter, interleaved runs (web, native, web, native, …;
  5 rounds × 120 frames after 30 warm-up frames). Pass when native p50 ≤ web p50 and native p95 ≤ web p95 for GPU
  ms. Both are reported. On a machine without a real GPU the result is recorded but marked not representative.

## 6. Reference (`tools/reference.py`)

- One Mitsuba scene per view state, built in Python (`mi.load_dict`, meshes from the resolved arrays with the
  object's world matrix, `twosided(diffuse)`; rect lights as `rectangle` shapes with an `area` emitter and a
  `diffuse` BSDF of their `albedo`; `point`, `directional`, `constant` emitters; `perspective` sensor with
  `fov_axis="y"`, `box` rfilter, `hdrfilm` RGB float32).
- Renders `full` and `direct` as `batches` (default 4) independent passes of `spp / batches` with different seeds; the
  estimate is the mean and `*_stderr.exr` the per-pixel standard error of the mean.
- AOVs with the `aov` integrator at `aov_spp`: `depth.exr` (`Z`, hit distance), `normal.exr` (shading normal),
  `position.exr` (local-frame hit point). A pixel is **valid** when `|normal| > 0.99` (silhouette pixels average to a
  shorter normal) and `depth > 0`.
- Cache key = sha256 of the canonical JSON of `{view hash, spp, batches, max_depth, rr_depth, aov_spp, seed, variant,
  mitsuba version}`. `cache/reference/<key>/receipt.json` records those inputs, timings, and a whole-image noise
  summary. Per-ROI noise (relative standard error of the ROI mean of `full`, `direct`, `full − direct`) is computed
  from the `*_stderr.exr` images by `tools/metrics.py` / `tools/gates.py`, which own the masks.
- CLI: `python -m tools.reference --run <run_dir> [--scenes …] [--spp-scale 0.25]`.

## 7. Metrics (`tools/masks.py`, `tools/metrics.py`, `tools/temporal.py`)

Masks come from the reference AOVs of the same view, so they are engine-neutral. Every view has ROI `all` (all valid
pixels); spec ROIs are intersected with `all`; every mask is eroded by 1 pixel.

For a ROI with pixel set P, engine image E and reference T of the same component, `ΔY = Y(E) − Y(T)`,
`ε = 0.01 · mean_P Y(T)`:

| metric | definition |
|---|---|
| `bias` | `Σ_P ΔY / Σ_P Y(T)` (signed, relative) and `bias_rgb` per channel; `bias_abs = mean_P ΔY` |
| `rel_l1` | `mean_P |ΔY| / (Y(T) + ε)` |
| `rel_mse` | `mean_P ΔY² / (Y(T)² + ε²)` |
| `leak` (dark ROIs) | `leak_abs = mean_P Y(E_iso)`; `leak_rel = leak_abs / N_iso`; also the reference's own `leak_rel` (its floor). For the `direct` mode the same on the direct component with `N_direct`. Relative metrics are not computed on dark ROIs. |
| `bleed` (bleed ROIs) | chromaticity `c = Σ_P rgb / Σ_P (r+g+b)` of the isolated component; report `c_eng`, `c_ref`, `‖c_eng − c_ref‖₂` |
| `energy` | `Σ_all Y(E_iso) / Σ_all Y(T_iso) − 1` (gain > 0, loss < 0); direct mode: on the direct component |
| `flip` | HDR-FLIP (`flip_evaluator`, `"HDR"`) of engine `final` vs reference `full`: mean over the image and per ROI |
| reference noise | relative standard error of the reference ROI mean (from `*_stderr`); reported next to every ROI so a metric below the noise floor reads as such |

When a ROI's reference mean is within 2 of its standard errors of zero (`metrics.REF_ZERO_K`; the component is zero up
to the reference's own noise, e.g. `full − direct` of a lone plane is ~1e-13), every ratio to it is noise: `bias`,
`bias_rgb`, `rel_l1`, `rel_mse` (and `energy` when the ROI is `all`) are null, `bias_abs` is kept and the ROI carries
`ref_within_noise: true`.

**Leak normaliser.** `leak_rel` is relative to the scene's brightest view of the same component c (`direct` or
`isolated`): `N_c = max over the scene's views v of mean_all Y(T_c(v))` (`metrics.scene_leak_normalisers(ref_means:
{view_id: {component: mean_all Y}}) -> {component: N_c}`, passed to `metrics.view_metrics(..., leak_norm=...)`, and
recorded in the result as `leak_norm`). A view whose whole reference is black (`thin_wall/dark`, `sealed_room/dark`,
a timeline state with the light off) then still has a defined `leak_rel`. `N_c` is None (and `leak_rel` undefined)
only when the component is black in every view. `leak_noise_rel` (reference standard error of a dark ROI's mean) and
the `ref_noise` gate on dark ROIs use the same `N_c`.

Rows of kind `indirect` measure the isolated component; the `direct` row measures the direct component against
reference `direct`. Scenes with `comparison: "appearance"` report only `flip`. There is no blended score.

**Temporal** (dynamic modes on timeline scenes). For ROI mean series `y(k)` of the isolated component (engine
timeline frame of the mode minus its own `direct` timeline frame), states as in §2, and `W = min(10, len(state)/4)`:

- `pre` / `post` = mean of `y` over the last `W` frames of the previous / current state (the engine's own settled
  values); `Δ = post − pre`; no-change steps (`|Δ| < 1e-3 · max(|pre|, |post|)`) are not timed.
- `t90` = the smallest `n ≥ 0` such that `|y(k) − post| ≤ 0.1 |Δ|` for every frame `k ≥ f_s + n` of the state;
  reported in frames and seconds.
- `afterglow` (steps where the reference isolated ROI mean falls): `r(k) = (y(k) − ref_post) / (ref_pre −
  ref_post)` using the reference state views; report `r` at 0.1, 0.25, 0.5 and 1.0 s after the step, the time until
  `r ≤ 0.05`, and the settled residual `(post − ref_post) / (ref_pre − ref_post)`.
- `flicker`: over the last `W` frames of each state, per-pixel temporal std / mean, averaged over the ROI
  (`temporal_cv`), and `mean |y(k) − y(k−1)| / mean y` (`f2f`).

**Cost** (`tools/perf.py`): per engine, mode, scene and adapter: GPU and CPU ms p50/p95 after warm-up from
`timing.json`; runs interleaved A/B (round-robin over the compared configurations, 5 rounds by default); memory and
precompute bytes/seconds from `timing.json`. Records whether the machine is representative (real GPU, not a
software rasterizer).

## 8. Scenes and gates

Calibration scenes carry an `oracle`; `tools/oracles.py` turns it into per-pixel analytic images from the reference
AOVs (position, normal):

| scene | oracle | checks |
|---|---|---|
| `cal_point_plane` | `L = ρ/π · I · cosθ / d²` | point-light units, inverse square, Lambert 1/π |
| `cal_sun_plane` | `L = ρ/π · E · max(0, n·(−dir))` | directional units and direction sign |
| `cal_sky_plane` | `L = ρ · L_sky` (unoccluded upward plane) | environment units |
| `cal_rect_plane` | polygon form factor: `E = L_e · ½ Σ_i θ_i (n · normalize(r_i × r_{i+1}))` | rect-light units and facing |
| `cal_handedness` | dark floor; diffuse red quad at +x on the image's right, green at +y on the image's top, white at the centre, lit by a sun from straight above: centroids within `tolerance_px`, each quad `L = ρ/π · E · cosθ` | handedness, image orientation, linear output (no rect lights, so every engine runs it) |
| `cal_furnace` | closed box, all six faces rect lights with radiance `L_e` and albedo ρ = 0.8: `full = L_e/(1−ρ) = 5 L_e`, `direct = L_e(1+ρ) = 1.8 L_e`, isolated `= L_e ρ²/(1−ρ) = 3.2 L_e` (one bounce would give 0.8 L_e); reference at 4096 spp | energy conservation |
| `cal_survey_origin` | as `cal_point_plane`, with a survey origin and a world-coordinate OBJ | float64 → float32 local resolution |

**Gates** (`tools/gates.py`, written to `gates.json`): for the reference, `full` and `direct` of every calibration
scene match the oracle (|bias| ≤ 0.5 %, rel_l1 ≤ 1 % on the oracle ROI) and the reference noise in every targeted ROI is
≤ 1 % relative standard error (dark ROIs relative to the leak normaliser, §7). For each engine, its `direct` mode passes
the same oracles at |bias| ≤ 1 %, rel_l1 ≤ 2 % (`cal_furnace` and `cal_handedness` included). Indirect-mode results on
`cal_furnace` are reported as measurements, not gates. An engine that lacks a capability a scene needs (§4.4; the
three.js engines on `cal_rect_plane` and `cal_furnace`) gets its gates on that scene recorded as by-design skips
(`status: "skipped"`, `by_design: true`, `reason`), which are not failures.

**Targeted scenes** (one failure mode each): `sealed_room`, `thin_wall`, `opening`, `offscreen_source`,
`occluded_canyon`, and timeline scenes `dyn_light_switch`, `dyn_door`, `dyn_material`. **Real-world sample:**
`courtyard_simplified` (`comparison: exact`) and `courtyard_authored` (`comparison: appearance`), three stations each,
with a survey origin.

## 9. Outputs read by other tools

- `metrics.json`: `{"metrics_version": 1, "run", "created_utc", "git", "engines": {name: {"status": "ok"|"skipped",
  "reason", "modes": {...}, "version"}}, "scenes": {name: {"group", "failure_mode", "comparison", "views": [...]}},
  "results": [{"scene", "view", "engine", "mode", "kind", "status": "ok"|"skipped"|"failed", "reason",
  "by_design": bool, "component": "direct"|"isolated", "rois": {roi: {...§7 metrics..., "role", "pixels",
  "ref_noise_rel"}}, "leak_norm", "energy", "bleed": {roi: {...}}, "flip": {"mean", "rois": {...}}, "convergence",
  "files": {"capture", "direct_capture", "sheet"}}], "durations": {...}}`.
- `gates.json`: `{"gates_version": 1, "gates": [{"name", "subject", "scene", "view", "component", "roi"?, "values",
  "tolerance", "passed": true|false|null, "detail", "status": "passed"|"failed"|"not_applicable"|"skipped",
  "by_design": bool, "reason": str|null}], "summary": {subject: {"passed", "failed", "not_applicable", "skipped"}},
  "tolerances", "engines", "scenes", "warnings"}`. By-design skips have `passed: null`, `status: "skipped"` and the
  skip `reason`; they are counted under `skipped`, never under `failed`.
- `temporal.json`: `{"temporal_version": 1, "results": [{"scene", "engine", "mode", "roi", "steps": [{"frame", "pre",
  "post", "t90_frames", "t90_s", "afterglow": {...}|null}], "flicker": [{"state", "temporal_cv", "f2f"}]}],
  "skipped": [...]}`.
- `perf.json`: `{"perf_version": 1, "representative": bool, "reason", "entries": [{"engine", "mode", "scene",
  "adapter", "rounds", "gpu_ms": {"p50", "p95"}, "cpu_ms": {"p50", "p95"}, "memory", "precompute"}],
  "phase0_gate": {...}|null}`. Entries also carry `view`, `status`, `reason`, `device`, `gpu_timestamps` and, in
  `gpu_ms`/`cpu_ms`, `mean`, `n`, `round_p50`, `round_p50_spread`. `phase0_gate`: `{"status": "passed"|"failed"|
  "not_measurable"|"incomplete", "passed": bool|null, "reason", "representative", "pairs": [{"scene", "mode",
  "status", "baseline": {"gpu_ms", "cpu_ms", "adapter"}, "system": {...}, "gpu_p50_ratio", "gpu_p95_ratio"}]}`.
  `phase0/perf.json` is the document of the last `--phase0` run alone.
- `phase0/parity.json`: `{"parity_version": 1, "gate": {"passed": bool|null, "status": "passed"|"failed"|
  "incomplete", "failed_entries", "not_compared"}, "representative": bool, "reason", "devices": {engine: {"adapter",
  "adapter_type", "software", ...}}, "entries": [{"scene", "view", "mode", "status", "reason", "gate": {"passed",
  "p99_9", "mean"}, "all": {"max", "mean", "p99_9", "pixels_gt1", "fraction_gt1", "channels"}, "valid": {...}|null,
  "linear": {"all": {"rel_l1", "bias", "max_abs"}, "valid"}|null, "files": {"web_png", "native_png", "sheet"}}]}`.

## 10. Commands

```
python -m tools.spec scenes --check                     # validate every scene, list views
python -m tools.reference --run runs/<id>               # references (cached)
python -m tools.parity --run runs/<id>                  # Phase 0 parity (web vs native)
python -m tools.pairs --run runs/<id> [--engines threejs-native,future] [--scenes all]
python -m tools.temporal --run runs/<id>
python -m tools.perf --run runs/<id> [--phase0]
python -m tools.report --run runs/<id>
python -m tools.run_all --run runs/<id>                 # all of the above in order
        [--scenes …] [--engines …] [--spp-scale f] [--phase0] [--perf] [--skip-references] [--timeout S]
        [--settle-frames N] [--dynamic-settle-frames N]       # passed to pairs (dynamic also to parity)
        [--perf-rounds N] [--perf-frames N] [--perf-warmup N] # passed to perf as --rounds/--frames/--warmup
python -m tools.inspector [scene] [--run runs/<id>|LATEST] [--no-open] [--port N] [--no-serve]
                                                        # build <run>/inspect/ and serve it on 127.0.0.1
Inspect.cmd [scene]                                     # Windows: build and open the viewer for runs/LATEST
Run-Harness.cmd [options]                               # Windows: python -m tools.run_all, pauses at the end
```

Setup: `Setup.cmd` (Windows) or `pip install -r requirements.txt`; the web runner needs Chromium
(`python -m playwright install chromium`, or `PLAYWRIGHT_BROWSERS_PATH` pointing at an existing install).
