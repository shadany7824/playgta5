# Semantic analysis of verified 30k-line region — vehicle/ped TASK AI (2026-11-23)

Source: `game.dcmp` lines 5,001,192–5,054,474 (304 complete functions, SHA256 `4da47378…`). I read representative full bodies and grouped all 304 by name. This region is **GTA V's task/AI system for vehicles and mounted weapons** — NOT rendering. It decides what peds/vehicles DO; it does not emit draws directly.

## What this code is (semantic)

Every function belongs to a `CTask*` state machine class. GTA's task system runs one "task" at a time per ped; each task has `ProcessPreFSM` / `UpdateFSM` / `UpdateTarget` / `Debug` methods. The classes here:

| Class group | What it does (semantic) |
|---|---|
| `CTaskVehicleFSM_*` | The in-vehicle animation state machine: computes remaining animation transforms (`ComputeRemainingAnimTransform`, 762 lines), converts relative offsets to world space, applies ground/orientation/mover fixups (positioning the ped correctly in the vehicle seat), and `GetGenericClipBlendParams` — reads 5 animation clips + blend weights from a **move network** (`CMoveNetworkHelper_GetClip/GetFloat`) into arrays. |
| `CTaskExitVehicleSeat_*` | Getting out of a car: `GetGroundFixupHeight` checks vehicle state flags (`a[19]->[772]` = vehicle type/state, `[102]&1`, `[5360]&1`) then returns a ground-height global (`25445500L`/`25445512L`/`25445516L`); `UpdateTarget` (318 lines) tracks the exit target; `ProcessMoveSignals` handles animation signals. |
| `CTaskCloseVehicleDoorFromOutside_*` | Ped closing a car door after exiting: `UpdateFSM` (465 lines) is the state machine. |
| `CTaskReactToBeingJacked_*` / `CTaskReactToBeingAskedToLeaveVehicle_*` | Ped reactions when the player carjacks them or asks them to leave; `UpdateFSM` (442/133 lines), `HasJackStarted`. |
| `CTaskGoToCarDoorAndStandStill_*` / `CTaskMoveGoToVehicleDoor_*` | Navigation to a vehicle door: `CalcTargetPositions`, `ChooseGoToDoorMBR`, `HasCarMoved` — checks if the car moved away (loops over `b[387]` child-vehicle list, checks `[512]&1`, `[40]==3`, `[772]==9` = a specific vehicle state; then squared-distance test vs globals `7736376L`, `25446584L`); `WarpIfPossible`, `IsAlreadyInPositionToEnter`, `AdjustPosForVehicleSpeed`, `TestIsSegmentClear` (312 lines). |
| `CVehicleHullAI_*` / `CVehicleHullCalculator_*` | **Vehicle collision-hull navigation**: `CalculateHullForVehicle` (695 lines) computes the vehicle's 2D hull polygon; `LiesInside` (read fully) is a point-in-polygon test (loops over hull edges at `a[i*8]`, computes normalized edge normals via `1/sqrt`, checks half-plane `>= 0`); `CalcShortestRouteToTarget` (547 lines), `TestIsRouteClear` (380 lines), `MoveOutside`. |
| `CTaskMountThrowProjectile_*` / `CTaskVehicleGun_*` | Ped firing weapons from a vehicle: projectile damage lookup, FPS camera overrides, `RestartMoveNetwork`, `UpdateFPSMoVESignals`, `NeedsToSmashWindowFromTargetPos`. |

## Representative bodies read in full (semantic detail)

- **`CVehicleHullAI_LiesInside` (32 lines, func76230):** `a[130]` = hull vertex count; vertices are 8-byte `{float,float}` pairs at `a + i*8`. For each edge it computes delta `e = f - prevX`, `c = g - prevY`, normalizes by `1/sqrt(e²+c²)`, then tests the point `b` against the edge's half-plane. Returns 1 (inside) if all edges pass. Classic convex polygon containment — used to decide if a ped/vehicle is inside another vehicle's hull for navigation.
- **`CTaskMoveGoToVehicleDoor_HasCarMoved` (44 lines, func76225):** reads `a[34]` = vehicle; checks type `[40]==3`, state `[772]<=9 & bitmask 770`, child list `b[387]` with `b[776]` count; loops children checking `[40]==3 && [772]==9`. Then a squared-distance comparison: `(b[38]-a[54])² + (b[36]-a[52])² + (b[37]-a[53])² > 7736376L` (a distance threshold global) → returns "moved". Semantics: abort the enter-vehicle task if the car drove off.
- **`CTaskVehicleFSM_GetGenericClipBlendParams` (47 lines, func76182):** loops `e=0..4` (5 animation layers); for each, calls `CMoveNetworkHelper_GetFloat(b, clipTable[e][745215])` for blend weight, clamps to 0..1, calls `GetClip(b, clipTable[e][745205])`, grows three arrays (float[], float[], restService*) with weight + clip. Semantics: configure a 5-layer animation blend from the move network.
- **`CTaskExitVehicleSeat_GetGroundFixupHeight` (13 lines, func76185):** checks vehicle state bits, selects one of three global floats `25445500/25445512/25445516` based on `a[176]&64`. Returns a hardcoded ground offset constant.

## Honest gap
I read ~6 bodies fully and grouped the other ~298 by name/pattern. I have NOT semantically decoded the 762-line `ComputeRemainingAnimTransform`, 695-line `CalculateHullForVehicle`, or every FSM body — those need targeted reads when relevant. This region has **no rendering/FPS relevance**: it's AI/task logic. Its only FPS connection is that it decides how many peds/vehicles exist and what animations play (upstream of draw count), which isn't safely patchable.

## Verification
Extraction + classification is SHA256-verified (`verified-30000-summary.md`). The semantic grouping above is based on the actual class names + the fully-read bodies cited. Stored alongside the verified dump so any session can cross-check.
