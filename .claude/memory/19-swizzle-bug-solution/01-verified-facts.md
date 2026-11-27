# 01 — Verified facts (2026-11-25)

## 1. Scalar-base risk: CLEARED
Scan script: `E:\gta\_tmp_claude\scan3.js` (run with Node 24 over `mirror\playgta5.com\b\8b0b5899ed\shaders`, ~5 min on the HDD). For each chain `base.A.B[.C...]` it resolved the base identifier's declared type (`var/let/const name : T`, function params `name : T`, `let name = vecN<T>(...)`).

Result:
```
files 4808 | chains 20984 | outerSingle 987 (in 578 files)
rgbaChains 0 | mixedSets 0 | assignTargets 0
vecBase 20984 | scalarBase 0 | unknownBase 0
```
- **Every chain has a vector base.** 0 scalar, 0 unknown.
- Also by the WGSL spec: **swizzles exist only on vectors. A scalar has no `.x` at all** (unlike HLSL). So `scalar.yyyy.w` can't appear in any shader that compiles in Chrome. Since the game's shaders compile in Chrome and in the `webgpu` npm Dawn (Stage 19 world render), every chain base is a vector.
- Bases like `arr[i].xy.x` or `(a*b).xyz.x` weren't separately counted by this regex (it anchors on an identifier or `)`). By the same spec rule they are vectors too, and composing the swizzle doesn't depend on the base, so the fix is safe for them.
- No `rgba` swizzles are used → the fix only needs the `xyzw` set.
- 0 chains as assignment targets → no lvalue / duplicate-component problems.
- The agent's earlier count (24,300) used a different regex. Both agree on the zero-risk findings.

## 2. The bug trigger is narrow
Per the Dawn fix commit (CL 338555): only an **outer single-component** swizzle on a SwizzleView breaks (`v.zyx.x`). That's **987 chains in 578 files**. The 26 failing pipelines are the ones the game actually used in that run. More will show up in other scenes, so the fix must cover all 987, not just the 26.

## 3. No newer native-dawn package
npm registry (`registry.npmjs.org/native-dawn`, checked 2026-11-25): versions 0.1.0-0.1.6, latest **0.1.6 (2026-10-16)**, which is the one installed. Its `upstream.json` pins Dawn `1e975e28...` (2026-08-22). **No upgrade path via npm.**

## 4. Why the working `webgpu` npm Dawn can't be swapped in
`node24\wgpu\node_modules\webgpu\dist\win32-x64\dawn.node` (v0.6.2, 12 MB) is **one statically linked Node addon**. It doesn't ship a separate `webgpu_dawn.dll` + headers. The C++ driver (`native_dawn_driver.node`) links against native-dawn's `webgpu_dawn.dll` (`native-dawn-test\webgpu_dawn.dll`, 10.8 MB), so it can't use the other package's Dawn.

## 5. The "enable extension" route is dead (from file 19, confirmed reasoning)
`enable swizzle_assignment;` → `expected extension`: the feature was added 2026-08-27, after our Dawn revision. No runtime toggle can add a language feature.

## 6. Conclusion
Rewrite the WGSL text (file 02). Use the minimal mode (outer single only, 987 chains) first; full mode is safe too by facts 1 and 5 above.
