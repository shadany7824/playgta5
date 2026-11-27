# 04 — Pipeline pre-compile (removes the big hitches)

## Why
In the 1080p run, `pipelines +6 (638 ms)` and worst frames of 125-266 ms show up whenever a new render pipeline is compiled mid-game. Node compiles pipelines **synchronously** by default (worker line ~1319-1321), so a new pipeline freezes the frame. This doesn't change average FPS much, but it is what makes 20 FPS feel bad.

## What already exists in the worker (`mirror\...\wgpu_worker.js` ~lines 1384-1403)
- `WGPU_RECORD_PIPELINES=<file.jsonl>`: appends every new pipeline "recipe" seen during the run.
- `WGPU_PIPELINE_SEED=<file.json>`: at startup, compiles all recipes from a seed file before they are needed.
- Comment mentions `pipeline_seed.py`, which turns the recorded jsonl into a seed json. **Find it** (`dir /s pipeline_seed.py` under `E:\gta\playgta5` and `E:\Malik`). If it's missing, write a small converter: read the jsonl, dedup by recipe key, write the JSON format the seed loader expects (read the loader code at ~1403 to get the exact shape).
- `WGPU_ASYNC_PIPELINES=1`: compile asynchronously on Node too (draws using a not-yet-ready pipeline are skipped or wait, see the `draws waiting for a compiling pipeline` counter).

## Steps
1. **Record:** run 2-3 normal sessions (300 s each, moving around if input exists, otherwise a few different spawns/modes) with `set WGPU_RECORD_PIPELINES=E:/gta/playgta5/node-webgpu/pipelines.jsonl`. Check that the file grows and the count of unique recipes levels off.
2. **Build the seed:** jsonl → `pipeline-seed.json`.
3. **Use it:** `set WGPU_PIPELINE_SEED=E:/gta/playgta5/node-webgpu/pipeline-seed.json`. Expect a longer startup (all pipelines compiled up front) and then `pipelines +0` in steady play.
4. **Separately**, as its own run: `WGPU_ASYNC_PIPELINES=1` without a seed. Check `draws waiting for a compiling pipeline` (objects may pop in for a moment) vs hitch size.

## Measure
- Worst-frame ms and count of frames > 100 ms over 300 s, before and after.
- Startup time to first world frame (the seed adds compile time).
- Average FPS should stay the same. If it drops, report it.

## Pass
- Steady play shows `pipelines +0` almost always. Frames > 100 ms drop by ≥ 80%.
- No validation errors, screenshot OK.

## Notes
- File 03's flag change (removing `emit_hlsl_debug_symbols`) also makes each compile faster. Do 03 first, then record pipelines with the final flags (recipes don't depend on the flags, but timing does).
- The seed must be re-recorded if shaders or worker pipeline logic change.
- Keep the jsonl and seed files in `node-webgpu\`, not the mirror.
