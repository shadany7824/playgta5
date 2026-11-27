# 03 — Test plan (one stage at a time, stop at the first failure)

## T1. Unit test the function (seconds): DONE by Claude 2026-11-25, 10/10 both modes (`E:\gta\_tmp_claude\swz-test.js`)
Copy `flattenSwizzles` into `E:\gta\_tmp_claude\swz-test.js` and assert:
| Input | single mode | all mode |
|---|---|---|
| `clamp(r1.yyyy.w, 0.0f, 1.0f)` | `clamp(r1.y, 0.0f, 1.0f)` | same |
| `v.zyx.x` | `v.z` | same |
| `v.xyzw.xy.x` | `v.x` | `v.x` |
| `v.xy.yx` | unchanged | `v.yx` |
| `v.xy.xyxx` | unchanged | `v.xyxx` |
| `f(a).xyz.y` | `f(a).y` | same |
| `m[0].xy.y` | `m[0].y` | same |
| `v.xy.z` (out of range, invalid anyway) | unchanged | unchanged |
| `s.xyz_name.x` | unchanged | unchanged |
| `r0.xyzw` (single swizzle) | unchanged | unchanged |
All must pass before going on.

## T2. Offline: transform all 4,808 shaders and count (minutes, HDD): DONE by Claude 2026-11-25
Result (`E:\gta\_tmp_claude\swz-all.js` → `swz-all.out`): 4,808 files, **578 changed, 987 rewrites, 0 triggers left**; `6eb493968c2b2b89.wgsl` → `o0.w = clamp(r1.y, 0.0f, 1.0f);`. The agent continues at **T3**.

Original T2 instructions:
Script on E: (`E:\gta\_tmp_claude\swz-all.js`): read every `.wgsl` in `mirror\playgta5.com\b\8b0b5899ed\shaders`, run `flattenSwizzles` (single mode), and report: files changed (expect 578), rewrites (expect ≥ 987, because nested ones count more than once), and that **no `.A.B` with single outer remains**. Re-scan the output with the same regex. **Don't write back** into the mirror folder. If you want to keep output, use `E:\gta\_tmp_claude\shaders-flat\`.

## T3. Offline compile with native Dawn (strongest proof, recommended)
Small Node 24 script that creates a device with the **native-dawn** module (same as the harness: `WGPU_NODE_MODULE = E:/gta/playgta5/native-dawn-test/node_modules/native-dawn`, see how `wgpu_worker_node.js` creates it), then for every transformed shader:
`device.createShaderModule({code})` → `await mod.getCompilationInfo()` → collect errors.
- The bug appeared in **pipeline** creation ("While initializing RenderPipeline", Tint IR generation). A shader module alone may not trigger IR lowering on every backend. If it doesn't, pair shaders the way the game does (the failing names are VS+PS pairs, e.g. `scaleform_shaders::VS_GFill_ColorPremult + PS_GFill_ColorPremult`), or just rely on T4.
- Also run the **original** failing shader (`6eb493968c2b2b89.wgsl`) untransformed: it must reproduce the error (proves the test can see the bug), and transformed it must pass.

## T4. Game run (native-dawn module, JS draw path)
From file 19 §6: Node 24, `WGPU_NATIVE_DRIVER=0` (pipelines built through native-dawn's bindings, draws still JS), ~170 s → `diag-native-flat.txt`.
Pass: 0 `swizzle view` errors, `draws waiting for a compiling pipeline` back to ~0, draws/frame > 500 in the world, validation +0. Also make sure the old bad `enable swizzle_assignment` prepend is **gone** (`grep -n "swizzle_assignment" wgpu_worker_node.js` → only the comment).

## T5. Native driver ON
Unset `WGPU_NATIVE_DRIVER` (driver active), same run. Pass: draws > 500, validation +0, no crash in 300 s. Take **one screenshot** (`WGPU_SHOT_EVERY` + `WGPU_SHOT_PREFIX=E:/gta/playgta5/node-webgpu/shots/`) and compare it with a JS-driver screenshot at the same spot. Swizzle composition must not change any color or shape.

## T6. Benchmark
Screenshots off, 300 s, same args as the **8.32 FPS** JS baseline (file 19) → fps, draws, worker ms/frame, µs/draw. Write the result to `02-performance-benchmarks.md` and `1080p-30fps-engine-plan\RESULTS.md`.

## If something fails
- T1/T2 fail → fix the function, don't run the game.
- T4 still shows `swizzle view` errors → print the failing shader's transformed source around the error line. Look for a chain the regex missed (e.g. a space before a dot, or a different nesting) and extend the regex. If it's a different Tint bug, go to file 04.
- T5 crashes → that's a driver bug, separate from swizzles. Log the stack and keep `WGPU_NATIVE_DRIVER=0` working.
