# STEP 3 — Fair A/B: Node + native Dawn vs Chrome (same settings)

## Goal
Answer the one question this whole harness exists for: **is native Dawn under Node faster than Chrome's WebGPU for this game on this PC, and by how much?** Plain number, no spin.

## Precondition
STEP 1 (world loads) and STEP 2 (real pixels confirmed) passed. **Screenshots OFF** (`WGPU_SHOT_EVERY` unset), because readbacks distort FPS.

## Why a gain is possible (from memory)
- Chrome bottleneck (memory 1080p-optimization/01, 14): the JS GPU worker is busy ~120 ms/frame at 1080p, with **GPU wait ≈ 0**. Time goes into the WebGPU wire / IPC (Chrome sends every call to a GPU process). Benchmarks said the wire is ~40% of per-dispatch cost.
- Native Dawn in Node has no wire/IPC, so the same draw calls should cost less CPU. But the CPU is only i3-7100U 2C/4T and the GPU is Intel HD 620 (memory 00). If the GPU becomes the limit, the gain disappears.

## Chrome baselines (already measured, memory 02/09/10/14)
| Preset | Chrome FPS | draws/frame |
|---|---|---|
| low 1024x576 (`?low=1&res=1024x576&fps=30&slots=5`) | ~30 (capped) | low |
| high-optimized 960x540, texture 2, shadow 0, reflection 1 | 16.5-16.8 | 1150-1250 |
| true 1920x1080 optimized | 4.4-8 | ~2700 |
| true MAX 1280x720 (all quality=2) | ~7 | high |
Re-measure at least ONE Chrome baseline today: the code changed since (shader/upscale patches), and so did the scene.

## Test matrix (minimum)
Run each in **Sandbox**, same spawn point, standing still for 60 s, then 60 s of the same camera movement if input exists (otherwise standing only, for both).
1. **A — matched to high-optimized:** Node args `-width=960 -height=540 -textureQuality=2 -shadowQuality=0 -reflectionQuality=1 -particleQuality=0 -grassQuality=0 -cityDensity=0 -lodScale=0 -frameLimit=0` vs Chrome URL with the same values in `args=` and `fps=0`.
2. **B — 1280x720 same quality.**
3. **C — 1920x1080 same quality.**
Use `-frameLimit=0` (uncapped) for both, otherwise both just hit the cap.

## How to set args in Node
Edit only the `arguments: [...]` array at `harness.js` line 102 (back up first: `harness.js.bak-step3`). Keep `-rootdir=/game/` and the browser base args. Also check whether the wgpu worker gets a `display=` size (memory 13: index.html sends `displayW/displayH`). Keep it equal to the render size for a fair test.

## What to record (from `[wgpu] fps:` lines, every 10 s)
- `fps`, `draws/frame`, `worker busy %` and `ms/frame`, `gpu wait` (from the stutter line), `validation errors`.
- Ignore the first 30 s (shader compiles: `pipelines +N`). Average at least 6 samples. Write the min and max too.
- Only compare runs where draws/frame are within ±15%. If they differ more, the scenes differ and the comparison is invalid.

## Result table (put in `02-performance-benchmarks.md` and ERROR-TRACE)
| Test | Chrome FPS | Node FPS | draws/f | Chrome worker ms | Node worker ms | Node gpu wait | Gain % |

## Decide (write one of these sentences, honestly)
- "Node/Dawn is X% faster at <res>. Worth making playable (STEP 5)."
- "No meaningful gain (<10%). Stop: the Chrome path stays the way to play." Then skip STEP 5 and go to STEP 6.
- If Node is faster but gpu wait > 0, write "now GPU-bound; HD 620 is the ceiling at this setting".

## Traps
- Don't compare Node uncapped with Chrome capped.
- Don't compare a loading screen with the world.
- Two Chrome game tabs double the load (memory 01); close extras.
- Background downloads or a Node process left running skew both. Check Task Manager / `tasklist` before each run.
- Rule U02: recompute the average from the raw lines a second way (e.g. a short script) before writing the number.

## Log it
`## Stage 19` in ERROR-TRACE with the table + verdict sentence. Also update the top of `CURRENT-PROBLEM.md`.
