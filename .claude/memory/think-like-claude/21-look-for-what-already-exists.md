# 21 — Look for what already exists before you build it

## The lesson
Large codebases already contain tools, flags and caches for most needs. **Search first** (grep for keywords, env vars, options). Building a second version wastes time and adds bugs.

## What happened here
- **Screenshots:** the plan said "add a screenshot readback if none exists". A 10-second grep found the worker already has it: `WGPU_SHOT_EVERY=<n>` + `WGPU_SHOT_PREFIX=<path>`, with its own PNG encoder and a frame-stats dump. The only problem was the default path `D:/wasm_tmp/` (doesn't exist here).
- **Pipeline cache:** the worker already has `WGPU_RECORD_PIPELINES` and `WGPU_PIPELINE_SEED` to pre-compile pipelines. No new system needed.
- **Dawn options:** `WGPU_DAWN_FLAGS` already overrides the Dawn startup flags, and it revealed that the default was a **debug** flag (`emit_hlsl_debug_symbols`).
- **Engine features:** the engine already has script commands for the owner's "load near fully, far less" idea (`OverrideLodScaleThisFrame`, `SetRemappingFromScript`, density multipliers, stream volumes). The plan uses them instead of inventing new culling.
- Owner rule U21 came from re-implementing a working export instead of reusing it.

## How to apply
1. Grep the code for the obvious names: `grep -n "SHOT\|screenshot\|readback"`, `grep -o "WGPU_[A-Z_]*" | sort -u` (lists every env option).
2. Check the engine index for existing commands (`engine-function-index.tsv`: `*_commands_Command*`, `Set*Multiplier`).
3. Read the found code's defaults and limits before using it.
4. Only build new when nothing fits, and write in the hand-off why the existing thing didn't fit.

## One-line rule
**Grep before you build.**
