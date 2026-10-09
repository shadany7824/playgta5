# Scenes

The scene specs live in `scenes/<group>/<name>.json` (DESIGN §2). They are written by `scenes/generate.py`, which
computes the derived numbers: the handedness pixel positions, the world-coordinate survey OBJ, and the courtyard's
boxes and openings. Edit the generator, run `python scenes/generate.py`, and commit both. `tests/test_scenes.py`
fails when the JSON and the generator disagree. Validate with `python -m tools.spec scenes --check`.

Shared conventions. Every image is 256×192, and every albedo's brightest channel is between 0.5 and 0.8 (coloured
paints have dimmer channels). The one exception is `cal_handedness`'s dark floor (0.05), the background its coloured
quads are found against. Reference spp, always in 4 batches, depends on the group:

| Group | Reference spp |
|---|---|
| calibration | 1024 (`cal_furnace`: 4096) |
| targeted (timeline scenes included) | 4096 |
| realworld | 2048 |

At these sample counts, Mitsuba `llvm_ad_rgb` on a 4-CPU machine takes:

| Scenes | Time per view |
|---|---|
| calibration | 2–15 s |
| targeted | 35–70 s |
| realworld | 40–100 s |

Each wall that encloses a room is embedded about 5–10 cm into its neighbours, so walls never just touch along a seam
that light could slip through. Faces that coincide always point in opposite directions and are hidden, so no visible
surface z-fights. A ROI box is padded by 1 cm around the surface it selects. A ROI that only one station can see
lists that station under `views`.

Radiance levels are chosen to land between about 0.05 and 10 W·m⁻²·sr⁻¹. Interiors lit only by bounces come out
dimmer, around 0.01–0.3. Closed white rooms come out brighter: bounces amplify their direct light about 4×.

`display.exposure` is used only by parity mode and the sheets. Each scene's value maps the 99th percentile of its
reference `full` luminance to about 1.2, so the 8-bit parity images are neither saturated nor black.

## Calibration (oracle gates, DESIGN §8)

Each calibration scene has an `oracle` block and at least one ROI with role `oracle`. `tools/oracles.py` evaluates
the analytic image at every pixel from the reference AOVs (position and normal). `tools/gates.py` then compares the
images against it on the oracle ROIs:

| Subject | Images compared | Gate |
|---|---|---|
| Reference | `full` and `direct` | \|bias\| ≤ 0.5 %, rel_l1 ≤ 1 % |
| Every engine | `direct` mode | \|bias\| ≤ 1 %, rel_l1 ≤ 2 % |

The three.js engines do not claim `light:rect` (DESIGN §4.4): r186 `MeshLambertMaterial` ignores `RectAreaLight`
(docs/PHASE0.md §6). Their gates on `cal_rect_plane` and `cal_furnace` are therefore recorded as by-design skips
(`status: "skipped"`, `by_design: true`), not failures. Every other calibration scene runs on both engines:
`cal_point_plane`, `cal_sun_plane`, `cal_sky_plane`, `cal_handedness` (redesigned without rect lights for exactly
this reason) and `cal_survey_origin`.

Verification on this machine (2026-10-09): Mitsuba `llvm_ad_rgb` at the committed spp; `threejs-native` on llvmpipe
and `threejs-web` on SwiftShader, both in `direct` mode at the bundle defaults (16 SSAA, 2048² directional map) with
2 settle frames. Bias / rel_l1 against the oracle on each oracle ROI (reference: `full`; `direct` is as close):

| Scene, ROI | Reference | `threejs-native` | `threejs-web` |
|---|---|---|---|
| `cal_point_plane` `plane` | −0.0005 % / 0.0017 % | −0.0004 % / 0.0016 % | +0.0007 % / 0.0163 % |
| `cal_sun_plane` `plane` | −0.0000 % / 0.0000 % | −0.0000 % / 0.0000 % | −0.0000 % / 0.0000 % |
| `cal_sky_plane` `plane` | +0.0001 % / 0.0329 % | −0.0000 % / 0.0000 % | −0.0000 % / 0.0000 % |
| `cal_handedness` `quads` | +0.0002 % / 0.0002 % | +0.0000 % / 0.0000 % | +0.0000 % / 0.0000 % |
| `cal_survey_origin` `plane` | −0.0005 % / 0.0017 % | −0.0004 % / 0.0016 % | +0.0007 % / 0.0163 % |
| `cal_rect_plane` `plane`, `emitter` | +0.0006 % / 0.0491 %, 0 / 0 | skipped (lacks `light:rect`) | skipped |
| `cal_furnace` `box` | +0.0261 % / 0.4174 % | skipped (lacks `light:rect`) | skipped |

Every handedness quad lands within 0.01 px of its expected pixel for all three subjects, with radiance errors of
2.4e-6 (reference) and 4.2e-8 (both engines). `survey_equivalence` passes for all three. Summary: reference 19
passed; each engine 7 passed, 0 failed, 5 skipped by design. The worst reference case is `cal_furnace` `full`, at
rel_l1 0.42 % (gate 1 %).

**cal_point_plane.** A point light, `I = [6, 5, 4]` W/sr, hangs 1.25 m above a plane with albedo [0.8, 0.65, 0.5].
It is deliberately off centre, at (0.375, −0.25), and the camera looks straight down from 3.5 m with up = +Y.
The oracle is `L = ρ/π · I · cosθ / d²`. It checks:

- point-light units;
- the inverse-square law;
- the Lambert 1/π;
- the light's position, because an x or y sign error moves the hot spot and fails the gate.

The plane, x ∈ [−4.25, 4.25] and y ∈ [−3.125, 3.125], fills the whole view, so the `plane` ROI covers all 49 152
pixels. Values run from about 0.03 at the image corners to 0.98 below the light. All coordinates are binary fractions,
so `cal_survey_origin` can reproduce them exactly.

**cal_sun_plane.** A directional light 30° from the zenith shines on a plane with albedo [0.7, 0.75, 0.8] and
`E = [3, 2.6, 2.2]` W/m². The light travels toward azimuth −60°, i.e. +x and −y. The plane is tilted about 19.5° about
an oblique axis, with normal ∝ (−0.2, 0.3, 1), so every component of the direction shows in the result:

| Direction | cos(n, −dir) |
|---|---|
| as specified | 0.984 |
| x flipped | 0.890 |
| y flipped | 0.740 |
| reversed | 0 (the lit face goes black) |

The oracle is `L = ρ/π · E · max(0, n·(−dir))`, a uniform image, and the camera looks down from 4 m. The test pins the
30° zenith angle and the > 5 % sensitivity to sign errors.

**cal_sky_plane.** A constant environment, `L_sky = [0.4, 0.5, 0.7]`, lights a lone horizontal plane with albedo
[0.6, 0.7, 0.8], 40 m deep. Nothing else is in the scene, so every point sees the full upper hemisphere and
`L = ρ · L_sky`, with `full = direct`. The camera, at (0, −5, 2.2), sees the horizon: the sky pixels show the background
`L_sky`, but they are invalid in the masks and not gated. The `plane` ROI stops at y = 12 m to avoid the most grazing
pixels.

**cal_rect_plane.** A rect light, 1.2 × 0.6 m with `L_e = [9, 8, 7]`, faces down 1.6 m above a plane with albedo
[0.75, 0.7, 0.65]. It lies entirely above the plane, so it never crosses a receiver's horizon. The oracle is the
polygon form factor `E/L_e = ½ |Σ θ_i n·normalize(r_i × r_{i+1})|`, clipped to the receiver's hemisphere (the clip is
exact even though this scene never needs it) and zero behind the one-sided emitter. The camera, at (0.4, −3, 0.7),
is below the light, so it also sees the emitting face. There are two oracle ROIs:

- `plane` (|x|, |y| ≤ 3 m) checks rect radiance units and facing on a receiver.
- `emitter` (about 490 px) checks the emitted radiance seen directly.

Known property of the system: three.js r186 `MeshLambertMaterial` ignores `RectAreaLight` (docs/PHASE0.md §6), so
the three.js engines do not run this scene; their gates are by-design skips.

**cal_handedness.** The camera is at (0, 0, 4), looking down −Z with up +Y. A sun from straight above,
`E = [3, 3, 3]` W/m² travelling −Z, lights three 0.6 m square diffuse quads that sit 1 cm above a dark floor
(albedo 0.05). There are no rect lights, so every engine can run it. (The earlier design used rect emitters, which
the three.js engines do not claim.)

| Quad | Centre | Albedo | Radiance ρ/π·E·cosθ | Expected pixel (x, y) | Expected place in image |
|---|---|---|---|---|---|
| red | (1.5, 0) | [0.8, 0, 0] | [0.764, 0, 0] | (190.51, 96.0) | right |
| green | (0, 1.2) | [0, 0.8, 0] | [0, 0.764, 0] | (128.0, 45.99) | top |
| white | origin | [0.8, 0.8, 0.8] | [0.764, 0.764, 0.764] | (128.0, 96.0) | centre |

The oracle block (`type: handedness`, `light: sun`, `object: floor`) stores each quad's expected pixel and radiance.
The pixel is computed with `oracles.project_point`: a quad parallel to the image plane projects without distortion,
so its centroid is the projection of its centre. Pixel coordinates are measured from the top-left corner and pixel
centres sit at +0.5.

For the gate, `oracles.handedness_checks` finds each quad by colour, takes its centroid, and compares it with the
expected position within `tolerance_px = 1`. It also compares the mean colour of the quad's core with its radiance,
within the subject's bias tolerance. It names a left-right or top-bottom mirror when it sees one. The floor, at
0.05/π·E = 0.048, is under a quarter of the white quad's brightness, so it is never taken for a quad. The `quads`
oracle ROI (the three top faces) gates every pixel against `L = ρ/π · E · max(0, n·(−dir))`, each pixel taking the
albedo of the quad it lies on. The quads face an empty upper hemisphere, so `full = direct` on them, and the sun
casts their shadows straight down, under the quads.

**cal_furnace.** A closed 2 m box whose six inner faces are rect lights, each with `L_e = [1, 0.9, 0.8]` and albedo
ρ = 0.8. Each face overlaps its neighbours by 1 mm beyond the edges, so the box has no cracks. The camera is inside,
with a 75° field of view. Every valid pixel has the same oracle values:

| Component | Formula | Value |
|---|---|---|
| `full` | L_e/(1−ρ) | 5 L_e |
| `direct` | L_e(1+ρ) | 1.8 L_e |
| `isolated` | L_e ρ²/(1−ρ) | 3.2 L_e |

The scene checks energy conservation. Spec v1 needs at least one object, so a 10 cm `anchor` box sits 5 m below the
furnace, out of sight.

The albedo is 0.8 so that one bounce and full GI differ. A method that adds exactly one bounce adds ρ L_e = 0.8 L_e,
a quarter of the isolated 3.2 L_e. At the earlier ρ = 0.5, ρ²/(1−ρ) = ρ, so one bounce landed exactly on the oracle
(the three.js `probe` mode measured −0.01 %).

At ρ = 0.8 a path averages five bounces, and Russian roulette (from depth 8) carries 0.8⁸/0.2 = 0.84 L_e, 17 % of
`full`. That noise is why the reference uses 4096 spp here. The measured `full` rel_l1 does not depend on the image
size: 1.65 % at 256 spp, 0.81 % at 1024 and 0.42 % at 4096 (64×48, Mitsuba `llvm_ad_rgb`; the gate is 1 %).
At 256×192 and 4096 spp the reference passes with `full` bias +0.026 %, rel_l1 0.42 % and `direct` bias +0.015 %,
rel_l1 0.026 %, in 78 s on 4 CPUs.

The engines' indirect modes are reported as `furnace_isolated` measurements with `passed: null`, not gates. The
three.js engines do not run this scene (rect lights, DESIGN §4.4), so their gates and measurements are by-design
skips.

**cal_survey_origin.** This is cal_point_plane with the same lights, stations, ROIs and materials, but with the survey
origin [346000, 6297000, 570] (UTM 19S, Santiago). The plane is `scenes/meshes/survey_plane.obj` in world
coordinates, for example y = 6296996.875. float32 cannot represent that value (its spacing there is 0.5), so a
resolver that casts to float32 before subtracting the origin moves the plane by up to 0.25 m.

The oracle type `survey_origin` evaluates the point-light formula. Its `equivalent: cal_point_plane` adds a
`survey_equivalence` gate, which requires the image to equal cal_point_plane's, for the reference and for each
engine. The test checks that the OBJ resolves to cal_point_plane's local triangles exactly.

## Targeted (one failure mode each)

Each targeted scene has two stations, or a timeline. Its ROIs carry roles:

- `dark`: black in the reference, so leak is measured there;
- `lit`: relative metrics;
- `bleed`: chromaticity of the isolated component.

`tools/gates.py` requires the reference noise in every ROI, including `all`, to be ≤ 1 % relative standard error, for
both measured components: `direct` and `isolated`. Two details:

- For `dark` ROIs the error is relative to the leak normaliser (DESIGN §7): the largest mean over `all` among the
  scene's views, for the same component.
- A component that is exactly zero, with zero error, passes.

At 4096 spp the largest error over all 19 targeted views is 0.19 %, for the isolated component of `opening`'s
`far_corner`. Every targeted reference gate passes.

`tests/test_scenes.py` checks each scene's light-path claims by ray casting. It also checks that every ROI covers
pixels in its views.

**sealed_room.** Two closed 4 × 4 × 2.5 m rooms with 0.25 m walls, 1.5 m apart, with no openings. A 12 W/sr point
light hangs in `room_lit`. In the reference every surface of `room_dark` is exactly black. The test casts 400 random
rays from inside each room and checks that all of them hit the room's own interior.

| Station | ROI | Role |
|---|---|---|
| `lit` | `lit_floor` | lit |
| `dark` | `dark_room` (every interior surface) | dark |

Failure mode: any light in the dark room (shadow-map range or bias, or probe leakage).

**thin_wall.** A 6 × 4 × 2.5 m room is split by a 5 cm wall. The wall is embedded into the floor, the ceiling and the
side walls, so the unlit half is sealed: rays cast from it never cross x = −0.025. A 2 W/sr point light sits 0.3 m from
the wall's lit face. That makes about 5 W·m⁻²·sr⁻¹ on the wall and 0.5 on the floor below.

| Station | ROI | Role | What it covers |
|---|---|---|---|
| `lit` | `lit_floor` | lit | floor next to the wall on the lit side |
| `dark` | `base_floor` | dark | floor within 0.6 m of the wall, unlit side |
| `dark` | `base_wall` | dark | lowest 0.6 m of the wall's unlit face |
| `dark` | `dark_half` | dark | the whole unlit half |

Failure mode: light leaking through the wall at its base, where shadow-map bias, normal offset and PCF filtering
matter most.

**opening.** Two 4 × 4 m rooms joined by a 1 × 2 m doorway in a 0.2 m wall. A 10 W/sr point light near the ceiling of
room A, at (−1.5, −1.2, 2.2), is placed so that its direct beam through the doorway falls on room B's floor near the
door and on the far wall's +y end. It never reaches room B's −y far corner, as shadow rays confirm. Both stations are
in room B:

| Station | ROI | Role | Direct light |
|---|---|---|---|
| `toward_door` | `door_floor` (floor just past the doorway) | lit | about 60 % of its pixels |
| `far_corner` | `far_corner` (floor and both walls of the corner) | lit | none: bounces only |

Failure mode: too little or too much bounce light through the doorway.

**offscreen_source.** A 6 × 4 × 2.7 m white room, open only through a 1.6 × 1.4 m window in its −x wall. Its +y wall
is red, with albedo [0.8, 0.12, 0.1]. A sun 40° high, `E = [6, 5.6, 5]`, travelling +x, makes a bright patch on the
floor at x ≈ 1–2.6 m. Both cameras sit at x ≈ 3 m looking toward +x, so the patch is always behind them: no visible
pixel receives direct sun (ray-cast test), and everything the cameras see is indirect.

| Station | ROI | Role |
|---|---|---|
| `s0` | `bleed_floor` (white floor next to the red wall) | bleed |
| `s1` | `bleed_ceiling` (white ceiling next to the red wall) | bleed |
| both | `far_wall` | lit |

Failure mode: a source outside the view (screen-space methods miss it) and its colour bleeding.

**occluded_canyon.** Two 20 m tall, 60 m long blocks 6 m apart stand on open ground. A sun 35° high, crossing the
street at 20°, shines with `E = [8, 7.6, 7]`, and there is a sky of `[0.3, 0.4, 0.6]`. A shadow ray from any point of
the street (|y| < 27 m) or of the walls below about 15 m hits the west block, so no sunlight reaches them (ray-cast
test). They see a narrow slot of sky and the sunlit upper part of the east block's facade.

| Station | Sees | ROIs (all lit) |
|---|---|---|
| `street` | along the street | `street`, `low_wall_w`, `low_wall_e` |
| `low_wall` | the east block's lower facade | `street`, `low_wall_e` |

Every ROI covers the lowest 3 m or the street surface. Failure mode: an unoccluded sky (three.js `HemisphereLight`
has no visibility) over-lights the street; missing bounce from the sunlit facade under-lights it.

## Timeline scenes (targeted, DESIGN §2 views)

All three timelines run at 60 fps with steps at frames 120 and 240 and end at frame 359. Each state therefore lasts
120 frames (2 s), well over the 90-frame minimum. That leaves the temporal metrics their settle window (W = 10) and a
full second for afterglow. The views are `state0`, `state1` and `state2`, captured at frames 119, 239 and 359.

**dyn_light_switch.** A 6 × 4 m room with a 10 W/sr lamp that switches off at frame 120 and back on at 240. A
1.8 m wooden shelf shadows part of the floor from the lamp. Two lit ROIs:

- `lit_floor`: directly lit.
- `behind_shelf`: lit only by bounces (ray-cast test). It is the cleanest view of afterglow when the light goes off and
  of re-convergence when it comes back.

States 0 and 2 are identical, so they share a reference cache entry.

**dyn_door.** The `opening` layout with a door. The door overlaps the jambs, lintel and floor, so with it closed
room B is sealed and exactly black (ray-cast test). At frame 120 it swings 90° into room A, about a hinge at
(0, 0.5), and it closes again at 240. The lamp is in room A and the camera in room B. ROIs:

- `door_floor` (lit): direct light only while the door is open.
- `room_b` (any): the whole room.

Failure mode: indirect light that lags or lingers after the door opens or closes.

**dyn_material.** A white 6 × 4 m room with a fixed 9 W/sr lamp. A 5.2 × 2.4 m panel on the +y wall changes albedo
from red [0.8, 0.1, 0.08] to green [0.1, 0.7, 0.12] at frame 120, then to white at frame 240. ROIs:

- `bleed_floor` (bleed): the white floor in front of the panel, which picks up its colour.
- `panel` (any).

Failure mode: stale colour bleeding after a material change.

## Realworld (survey origin, sun + sky)

**courtyard_simplified** (`comparison: exact`) and **courtyard_authored** (`comparison: appearance`, so only FLIP is
reported). Both are a two-storey courtyard building at the Santiago survey origin [346000, 6297000, 570].

The building is 24 × 24 m with a 12 × 12 m courtyard and 0.3 m walls. Each wing storey is a `room` shape with window
and door openings; upper storeys omit their floor and use the ceiling slab below. The ground floor is raised 0.15 m on
a plinth above the paving, so floors never coincide with the ground.

The sun is 45° high from the north-west and travels toward azimuth −60°: `E = [7.5, 7.1, 6.5]`, plus a sky of
`[0.32, 0.42, 0.62]`. It reaches the north-facing (courtyard) side of the south wing and casts sun patches through its
windows. In the south wing's ground storey, partitions with an internal doorway form two rooms:

- a 7.85 × 2.6 m window room facing the courtyard;
- a windowless deep room behind it. Ray casting confirms that light leaves it only through the doorway.

The stations are `courtyard`, `window_room` (near the courtyard windows, looking at the sun patches and the internal
door) and `deep_room` (looking back at that door). The ROIs are `courtyard_ground`, `window_room_floor` and
`deep_room`.

`courtyard_simplified` uses one plaster albedo, [0.75, 0.72, 0.68]. `courtyard_authored` keeps every object and
station of the simplified scene and adds detail:

- mullions and transoms in every window;
- a balcony with railing and balusters in front of the upper French windows;
- terracotta roof coverings;
- a lawn, benches and planters in the courtyard;
- furniture in both rooms;
- per-wing plaster colours;
- a 2.2 W/sr pendant lamp in the deep room.

That makes 187 objects and 4152 triangles. The numbers are ordinary for a Santiago autumn afternoon, at a ~5:1 sun to
sky irradiance ratio.

## Phase 0 views (`scenes/phase0_parity.json`)

`{"parity_version": 1, "description", "views": [{"scene", "view", "modes"}]}` lists the views that `tools/parity.py`
(8-bit web vs native, DESIGN §5.4) and `tools/perf.py --phase0` use:

| Scene | View | Modes | What it covers |
|---|---|---|---|
| cal_point_plane | s0 | direct | point light |
| thin_wall | lit | direct, probe | point shadow next to a thin occluder |
| opening | toward_door | direct, probe | doorway |
| offscreen_source | s0 | direct, probe | directional light through a window, coloured bounce |
| courtyard_simplified | courtyard | direct, probe | sun + sky + hemisphere, 2000 triangles |

Together they cover every light type the port draws, both shadow kinds, the probe, and a realistic triangle count.
