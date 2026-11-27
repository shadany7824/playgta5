# Deep semantic reads — the big functions of region 1 (2026-11-23)

Companion to `semantic-304-functions.md`. I read the actual opcode-level bodies of the largest/most important functions in the verified 30k region:

## `CTaskVehicleFSM_ComputeRemainingAnimTransform` (762 lines, func76183, line 5001239)
**What it does:** computes the remaining animation transform for a ped in a vehicle, per mover track.
- Inputs: a struct `a` with arrays — `a.a` (floats, weights at `a.a + p*4`), `a.c` (float weights), `a.e` (array of mover-track pointers at `a.e + p*8`), `a.b` = track count, `a.f`/`a.d` = bounds. Outputs `b[0]`, `c[0]` as SIMD (`simd_ptr`).
- Loop over tracks `p`: for each with weight `> 0`, calls `rage_fwAnimHelpers_GetMoverTrackTranslationDiff(out, track, weight, 1.0f)` and `GetMoverTrackRotation(out, track, 0.0f)` to get the delta transform of the mover track from the animation.
- Then a large block of **SIMD quaternion math** (`f32x4_mul`, `f32x4_sub`, `SimdShuffleOp`, `f32x4_div`, `f32x4_sqrt`): normalizes a quaternion (`q / sqrt(dot(q,q))`), composes rotations, and blends them. The pattern `1/sqrt(x²+y²+z²)` + cross-product shuffle structure = quaternion normalization / spherical interpolation of animation transforms.
- Uses `i32x4_bitmask(f32x4_abs(...) < eps)` to test convergence (==15 means all 4 lanes inside epsilon), then iterates.
- **Semantic summary:** computes a weighted blend of remaining vehicle-animation transforms using quaternion math (Slerp-like), so the ped's animation stays correct when animation states change. Pure math — no rendering, no globals that matter for FPS. This is why this 30k region has no FPS lever.

## `CVehicleHullAI_LiesInside` (32 lines, func76230) — already read
Point-in-convex-polygon test over 8-byte `{float,float}` hull vertices (a[130] count, vertices at a+i*8); computes normalized edge normals (`1/sqrt`) and half-plane tests. Used by vehicle navigation.

## `CTaskMoveGoToVehicleDoor_HasCarMoved` (44 lines, func76225) — already read
Checks vehicle state (`[40]==3`, `[772]` state bits), loops child vehicles at `b[387]`, then squared-distance vs threshold globals `7736376L`/`25446584L`. Semantics: abort entering a car that drove away.

## `CTaskVehicleFSM_GetGenericClipBlendParams` (47 lines, func76182) — already read
Loops 5 animation layers; reads clip handles + blend weights from a move network (`CMoveNetworkHelper_GetClip/GetFloat`), clamps 0..1, grows 3 arrays. Semantics: configure 5-layer animation blend.

## `CTaskExitVehicleSeat_GetGroundFixupHeight` (13 lines, func76185) — already read
Checks vehicle state flags then returns one of 3 global float height constants (`25445500/25445512/25445516`).

## Overall semantic verdict for region 1
All 304 functions are **vehicle/ped TASK AI**: animation state machines, vehicle hull pathfinding, enter/exit/jack tasks, mounted weapon tasks. The dominant math is SIMD animation blending and geometry. **No draw generation, no renderer calls, no WebGPU.** Zero FPS patch value; the region is correctly classified as AI/task logic.
