# 07 — Population density: fewer peds and cars

## Why
Each ped/vehicle = several draws (body, head, clothes, wheels, shadows) plus AI, physics and animation CPU on the engine threads. On a 2-core CPU this hits both the engine and the worker. `-cityDensity=0` is already set; these engine globals go further and work per frame.

## Engine code (verified in `game.dcmp`)
| Command / function | Writes | Notes |
|---|---|---|
| `vehicle_commands_CommandSetRandomVehicleDensityMultiplierThisFrame(a)` (func 61299, line 4165688) | `7813544:float = max(current, a)` | random (moving) traffic |
| `vehicle_commands_CommandSetParkedVehicleDensityMultiplierThisFrame(a)` (61300) | `7813548:float = max(current, a)` | parked cars |
| `vehicle_commands_CommandSetVehicleDensityMultiplierThisFrame(a)` (61298) | both of the above | |
| `CPedPopulation_SetAmbientPedDensityMultiplier(a)` (41513, line 3295508) | `7155636:float = a` | ambient pedestrians (plain set, not "ThisFrame") |
| `CPedPopulation_SetScenarioPedDensityMultipliers(a,b)` (41471, line 3288453) | `7155640 = a`, `7155644 = b` | scenario peds (sitting, working...) |
| `CVehiclePopulation_GetParkedCarDensityMultiplier` (80421) / `GetLowPrioParkedCarDensityMultiplier` (80422) | read path | read these to see how the final multiplier is computed |

**Important:** the vehicle "ThisFrame" setters use **max(current, a)**. So the engine resets these globals each frame (probably to 0 or to the default), and scripts can only raise them in that frame. Writing a low value from JS works only if it lands **after** the reset and **before** the read, or if you write the *final* computed multiplier instead.

## Steps
1. **Read where `7813544`/`7813548` are reset and read**: `grep -n "7813544L\|7813548L" game.dcmp`. Find the reset value and the consumer (likely `CVehiclePopulation_*` per-frame update). Same for `7155636/40/44`.
2. **Peds first (simplest):** `7155636` is a plain set. Write 0.5, then 0.25 (one per run) via the JS memory-write method (fresh DataView, `setFloat32(addr, v, true)`), from the worker `present()` hook or once after the world loads. Check that the engine doesn't overwrite it each frame (log the value back every 10 s).
3. **Vehicles:** per step 1, either write after the reset (timing hook) or WAT-patch the consumer so it multiplies by a constant (e.g. 0.5). The WAT route is deterministic; prefer it if the timing is racy.
4. Keep player-related and mission vehicles alone. These multipliers only affect ambient population.

## Values (one per run)
Peds: 1.0 (baseline) → 0.5 → 0.25. Vehicles random: 0.5 → 0.25. Parked: 0.5 → 0.

## Measure
Draws/frame, FPS, engine wait % (file 02), and a count of peds/cars visible in screenshots at the same spot. Sandbox mode is the most stable spawn for this (mission scripts may force their own density in story mode).

## Pass
Draws and/or engine CPU drop with the world still looking alive (owner decides how empty is OK; show screenshots). Record the chosen values for the final preset.
