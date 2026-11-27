# 11 — Read the whole function, not just its name

## The lesson
A function or variable name tells you what someone **meant**. The body tells you what it **does**. Small details in the body (a flag bit, a clamp, a "max" instead of "set") decide whether your change works.

## What happened here (three times)
1. **LOD scale:** an earlier experiment wrote the LOD scale value to address `23318984` and saw no effect. Reading the engine's own setter `CLodScale_SetGlobalScaleFromScript` showed it does **two** things:
   ```
   23318984L[0]:float = a;        // the value
   23319072L[0]:byte |= 1;        // a flag: "script override active"
   ```
   The experiment never set the flag. That's a likely reason it did nothing (to be confirmed by the agent).
2. **Vehicle density:** `CommandSetRandomVehicleDensityMultiplierThisFrame` doesn't set the value. It sets `max(current, a)`. So a script can only **raise** density per frame, and writing a lower value from outside won't work unless you write after the engine's reset.
3. **ApplyLodScaleModifiers** computes `1.0 - lodScale`, so a value above 1.0 makes a negative modifier, which explains why 1.5 "did nothing visible".

## How to apply
- Before writing to a global or calling a function, read **its setter and its reader**: `grep -n "<address>L" game.dcmp`.
- Note every side effect: flags, counters, "ThisFrame" resets, clamps, min/max.
- Note who resets the value and when (per frame? per level load?).
- Write these down in memory next to the address, so the next agent doesn't repeat the experiment.

## One-line rule
**Names are promises. Bodies are facts.**
