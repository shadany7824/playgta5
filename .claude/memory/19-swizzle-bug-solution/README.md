# SOLUTION — Native-Dawn Tint "swizzle view" bug (for the code agent)

Problem file: [../19-native-dawn-swizzle-bug.md](../19-native-dawn-swizzle-bug.md). Written 2026-11-25.

## Verdict
**Solvable now, in JS, no Dawn rebuild:** flatten chained swizzles in the WGSL text before the shader module is created. The open safety risk from file 19 (scalar bases) was **checked and cleared** (file 01). A fallback (rebuild native-dawn on a fixed Dawn revision) is in file 04.

## Already done by Claude (2026-11-25)
- Scalar-base risk cleared (file 01).
- `flattenSwizzles()` unit-tested 10/10 (a first version failed on `v.xyzw.xy.x` and was fixed; file 02 has the fixed code).
- Applied offline to all 4,808 shaders: 578 files / 987 rewrites / **0 triggers left** (file 03 T2).
- **Agent starts at:** file 02 (put the code into `wgpu_worker_node.js`), then file 03 **T3**.

## Files (do in order)
| # | File | What |
|---|---|---|
| 01 | [01-verified-facts.md](01-verified-facts.md) | What was proven: the scan results, why scalar bases can't exist, no newer native-dawn, why the webgpu-npm Dawn can't be reused |
| 02 | [02-the-fix-code.md](02-the-fix-code.md) | Exact `flattenSwizzles()` code, where to put it, env gates, minimal mode first |
| 03 | [03-test-plan.md](03-test-plan.md) | Unit tests → offline compile of all 4,808 shaders → game run → benchmark |
| 04 | [04-fallback-rebuild-dawn.md](04-fallback-rebuild-dawn.md) | Only if 02/03 fail: build native-dawn against a Dawn revision after the 2026-09-01 fix |

## Rules (same as always)
One change per run · back up `wgpu_worker_node.js` first · `node --check` · prove by log/screenshot · log a new `## Stage N` in `engine-code-map\ERROR-TRACE.md` · Node 24 only (`E:\gta\playgta5\node24\node_modules\node\bin\node.exe`) · C: is full, so temp files go to `E:\gta\_tmp_claude\` · no git.

## Pass = done
1. 0 `swizzle view instruction still has usages after lowering` errors.
2. Draws/frame > 500 in the world with the native driver ON, `validation errors +0`.
3. A screenshot looks the same as the JS-driver screenshot at the same spot.
4. FPS compared with the 8.32 FPS JS baseline (and the 11.55 no-draw ceiling noted in file 19).
