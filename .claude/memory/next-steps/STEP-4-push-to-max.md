# STEP 4 — Push to MAX, one lever per run

## Goal
Find the highest resolution + quality the Node/Dawn path can run at a playable FPS, with a measured number for every setting. The owner wants the **true MAX** preset improved, not low mode dressed up as max (mistake U23).

## Precondition
STEP 3 is done, the verdict is written, and you have a Node baseline at 960x540 high-optimized.
If STEP 3 said "no gain", still do this step briefly (3-4 runs) to document the Node ceiling, then stop.

## The true MAX definition (memory 01, verified recipe)
Chrome URL:
`?low=0&res=1280x720&fps=60&shadows=1&slots=5&log=1&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2,-vehicleVariety=2`
→ Chrome measured **~7 FPS**. At 1920x1080 max: **5.6 FPS**.
In Node these become entries in the `arguments` array at `harness.js` line 102 (e.g. `'-textureQuality=2'`). `-width/-height` set the resolution. Keep `-rootdir=/game/` and the base args.

## Order of runs (change ONE thing each run)
Start from the Node high-optimized baseline (960x540, texture 2, shadow 0, reflection 1, rest 0).
1. Resolution: 960x540 → **1280x720** → **1920x1080**. Pick the highest that stays ≥ 25 FPS as the base for the quality runs. If none does, use 1280x720 and note it.
2. Quality levers, add ONE per run in this order (cheapest look gain first):
   1. `-textureQuality=2` (already in baseline; confirm)
   2. `-lodScale=1`, then `-lodScale=2` (draw distance; LOD drives draw count, see memory 15 / engine-code-map LOD globals)
   3. `-reflectionQuality=2`
   4. `-shadowQuality=1`, then `2` (shadows were the biggest cost in Chrome: memory 09, shadow 0 gave 13-15 → 16.5 FPS)
   5. `-particleQuality=2`, `-grassQuality=1/2`
   6. `-cityDensity=1/2`, `-pedVariety=2`, `-vehicleVariety=2` (these add CPU work: peds/cars)
3. Run each lever with `-frameLimit=0` to measure the ceiling, then confirm the chosen final preset with `-frameLimit=1` (60 cap) or `2` (30 cap).

## Per-run procedure
1. Back up harness.js once (`harness.js.bak-step4`). After that, edit only the args line.
2. Run 120-180 s in Sandbox, same spot. Ignore the first 30 s (pipeline compiles).
3. Record: FPS avg/min, draws/frame, worker busy %, gpu wait, validation errors. Any new warning in the log, write it down.
4. Optional: one screenshot per new preset (STEP 2 env vars) to prove the setting really changed the image, e.g. shadows visible. Take it in a separate short run, not during the FPS sample.

## How to read the numbers
- **Worker busy high, gpu wait 0:** CPU/JS-bound. Fewer draw calls help (lower lodScale/cityDensity); GPU settings are nearly free.
- **Gpu wait > 0 and rising:** GPU-bound (HD 620 is the limit). Resolution and shadows are now the expensive levers.
- **validation errors > 0:** a setting broke something in the WebGPU path. Revert that lever and log the exact error text.
- A crash on a lever: record the stack, revert, and mark that lever "unsafe on Node" in the table.

## Output
Write a table to `02-performance-benchmarks.md` (section "Node/Dawn MAX ladder"):
| Run | Res | Change | FPS avg/min | draws/f | busy % | gpu wait | Notes |
Then name two presets with numbers:
- **Node-Balanced:** best look at ≥ 30 FPS.
- **Node-Max:** all quality=2 at the chosen resolution, with its real FPS, even if low.
Compare each with the Chrome numbers at identical settings.

## Hard truths to keep (memory 00/10/11)
- i3-7100U 2C/4T + HD 620 has a hardware floor. True 1080p max was 4.4-8 FPS in Chrome. Don't promise 60.
- Post-FX args (`-postFX=0,-fxaa=0,...`) made things worse in Chrome (memory 11). Don't repeat them blindly.
- Never present a number from a lower preset as "max".

## Log it
`## Stage 20` in ERROR-TRACE + update CURRENT-PROBLEM with the two named presets.
