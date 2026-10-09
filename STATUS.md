# Status

System under study: three.js r186 `WebGLRenderer` lighting, ported to Python + `wgpu-py` on Vulkan (`threejs-native`).
Reference: Mitsuba 3. Original WebGL build (`threejs-web`) kept unmodified for Phase 0 parity and the perf baseline.
Contract: `docs/DESIGN.md`. Next steps on a GPU machine: `HANDOFF.md`.

## Where it stands

| Item | State |
|---|---|
| Spec, geometry, reference, adapters, metrics, pairs, temporal, perf, parity, report, inspector | Built; 382 tests pass |
| Calibration gates (units, conventions) | Pass for reference and `threejs-native` (by-design skips only) |
| End-to-end run (all steps, all outputs) | Done at reduced reference quality (0.05× spp), container without GPU |
| Phase 0 parity and performance gates | Measured on software rasterizers only, **not representative**; must run on a GPU |
| Full-quality run | Not done here (stopped to save budget); run `Run-Harness.cmd --phase0 --perf` on Windows |
| Future engine | `NotWired` slot + `FakeRenderer` test; contract in `docs/FUTURE_ADAPTER.md` |
| Unity_LSD_GI conventions | Not cross-checked (repository not accessible from here); spec follows the stated conventions |

## Findings and causes

**Harness bugs found and fixed at their source**
- Point-light shadow bias was in the wrong units. r186 point shadows compare perspective depth, so a bias of
  −0.0005 meant about 0.5 m at 3 m and leaked light through walls. Now 0 (three.js's default).
  Effect: `opening` door_floor rel_l1 2.43 % → 0.26 %; `dyn_light_switch` 1.49 % → 0.27 %; `dyn_material` 102 % → 11.8 %.
- The sun's shadow camera covered the 120 m ground (8 cm texels, acne stripes). It is now fitted to where shadows
  can fall (2.2 × 3.6 cm texels in `occluded_canyon`).
- Isolated metrics against a reference that is zero within noise produced absurd ratios; they now report the
  absolute difference and mark "reference ≈ 0 within noise".

**Conventions verified** (both engines, calibration scenes): point-light units and inverse square, Lambert 1/π,
sun direction sign (tilted plane), sky units, image orientation and handedness, survey origin (identical to the
non-survey scene). Native and web agree with the analytic oracles to ~1e-5–1e-4 relative.

**Behaviour of the system (three.js), measured, by design**
- `MeshLambertMaterial` ignores `RectAreaLight` (r186: "Only PBR materials are supported"). Rect-light scenes
  (`cal_rect_plane`, `cal_furnace`) are by-design skips for three.js.
- `HemisphereLight` sky has no occlusion: `occluded_canyon` direct +540 % to +1550 % per ROI; courtyard deep room
  +7780 %.
- Static probe at the camera underestimates indoor indirect light by 70–97 % (`thin_wall` −91 %). Probe units were
  checked independently: SH irradiance at the probe point 0.02531 (native) vs 0.02533 predicted from Mitsuba.
- Outdoors the probe counts the sky twice (cube capture sees the background, plus the HemisphereLight).
- SH9 is not clamped, so the probe can subtract light in open scenes.
- `probe_dynamic`: t90 5–11 frames on the timeline scenes (`dyn_light_switch` 7 frames, afterglow r(0.1 s) = 0.038).

**Phase 0 on this machine (not representative: SwiftShader vs llvmpipe)**
- Parity: 5 of 9 view/mode entries pass. Failures: `opening` p99.9 4–5 LSB (PCF shadow-edge texels),
  `courtyard_simplified` p99.9 43–80 LSB (one-pixel cracks at wall/ground T-junctions). Linear images differ by
  0.01–0.2 % relative L1.
- Performance: native GPU time 0.3–0.46× web at p50 and p95 (CPU rasterizers; says nothing about a GPU).

## Scenes cut or changed, and why

- Spot lights: three.js uses smoothstep in cosine, Mitsuba linear in angle, and a hard cone is undefined in
  three.js; no exact comparison possible in spec v1.
- Textures, specular materials, emissive meshes: three.js emissive surfaces do not light other surfaces; out of
  scope for a diffuse lighting comparison in v1.
- Ambient and lightmap modes: no principled ambient value; three.js's ProgressiveLightMap accumulates direct light
  only.
- Real-world sample: procedural courtyard (simplified = exact, authored = appearance) with a survey origin, because
  no real model was available here. OBJ meshes in world coordinates are supported to drop one in.
- `cal_handedness` uses diffuse quads under a sun (not rect lights) so three.js can run it.
- `cal_furnace` albedo 0.8, so one bounce (0.8 Lₑ) and full GI (3.2 Lₑ) differ.

## Run times (container: 4 CPUs, no GPU)

| Step | Seconds (reduced run, 0.05× spp) |
|---|---|
| spec | 0.1 |
| references | 74 (all scenes; full quality is ~26 min here: calibration ~2, targeted ~17, real-world ~7) |
| parity | 37 |
| pairs (45 native launches) | 448–465 |
| temporal | 7 |
| perf (reduced rounds) | 101–163 |
| report | < 0.1 |
| **total** | **~655–683** |

Inspector build: 3 s, 93 MB. Full-quality references measured here: 8 views in 402 s before the run was stopped.
