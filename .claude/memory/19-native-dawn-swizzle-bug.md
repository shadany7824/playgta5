# 19 — Native-Dawn Blocker: Tint "swizzle view" Bug (2026-11-25)

> **SOLUTION FOLDER: [19-swizzle-bug-solution/README.md](19-swizzle-bug-solution/README.md).** Risk #1 (scalar bases) CLEARED 2026-11-25: 20,984 chains, all vector bases, 0 scalar/unknown/rgba/assignment; trigger = 987 outer-single chains in 578 files. No newer native-dawn on npm (0.1.6 latest).

> **Status:** BLOCKER. Native Dawn driver fails to build 26 render pipelines → **0 draws** on Node.
> JS/WebGPU fallback still works (8.32 FPS baseline). This is the single gate in front of the
> C++ hot-path port.

---

## 1. One-line summary

The bundled **native-dawn** module pins a **Dawn revision from 2026-08-22**, which is
**10 days before** the upstream fix for a known Tint compiler bug. Our GTA V shaders trip that
bug → pipeline creation fails → nothing draws.

---

## 2. The error

When `wgpu_worker_node.js` compiles the game's pre-generated WGSL with the native Dawn driver,
26 pipelines fail like this:

```
[wgpu] pipeline failed (scaleform_shaders::VS_GFill_ColorPremult + scaleform_shaders::PS_GFill_ColorPremult):
  An error occurred while generating Tint IR
error: swizzle view instruction still has usages after lowering
 - While initializing [RenderPipeline "..."]
```

- Evidence file: `E:\gta\playgta5\node-webgpu\diag-native-driver.txt.err` (26 such errors, 12:46 AM).
- Result: `0 draws/frame`, `26.9 fps` (idle — no work), `draws waiting for a compiling pipeline +23`.
- Failing shaders are real game ones, e.g. `6eb493968c2b2b89.wgsl`:
  ```wgsl
  o0.w = clamp(r1.yyyy.w, 0.0f, 1.0f);   // <-- triggers the bug
  ```
  where `r1 : vec4<f32>` (line 5 of that file).

---

## 3. Root cause (researched on the web)

**Chromium issue:** `crbug.com/553777974` — *"swizzle view instruction still has usages after lowering"*.
Tint P0. Culprit: Dawn CL **329876** (chained-swizzle refactor).

**The bug (per the fix commit message, CL 338555):**
> Single-element swizzles on a SwizzleView (e.g. `v.zyx.x`) were only typed as a SwizzleView
> when the `swizzle_assignment` language feature was enabled. Without the feature, it resolved
> to a bare scalar value, emitting an `Access` without a `Load` and causing IR lowering to fail.

So the **trigger pattern** is: **an inner multi-component swizzle + an outer single-component swizzle**
(`v.AAAA.b` where `A` = 2-4 xyzw components, `b` = 1 component).
Our `r1.yyyy.w` is exactly that: inner `.yyyy` (SwizzleView) + outer `.w` (single).

**Timeline (all UTC):**

| Date | Event | CL |
|---|---|---|
| pre-153 | Culprit chained-swizzle refactor lands | 329876 |
| **2026-08-22 12:02** | **Dawn rev `1e975e28` (what native-dawn 0.1.6 pins)** | — |
| 2026-08-27 | `swizzle_assignment` feature **ships** (default-on M154) | 337155 |
| **2026-09-01** | **Fix lands** (M153 + M154) | **338555** / cherry-pick 338975 |
| 2026-09-02 | Verified fixed in Chrome 155 | — |

**Decisive fact (verified this session by decoding the git object of rev `1e975e28`):**
```
commit unix=1787400155
UTC: 2026-08-22 12:02:35 Z
=> Dawn rev 1e975e28 is BEFORE the swizzle fix
```
Source: `native-dawn-test/node_modules/native-dawn/upstream.json` → revision
`1e975e28f98a0285e44150a7f64b3bb89f27c719`, fetched from
`https://dawn.googlesource.com/dawn/+/1e975e28...` (gitiles returns base64 git object).

---

## 4. Why the "just enable the feature" fix does NOT work here

WGSL fix would be `requires swizzle_assignment;` (or `enable swizzle_assignment;`).

**Tried and failed.** Prepending `enable swizzle_assignment;` in `shaderProgram` produced:
```
:1:8 error: expected extension
```
Reverted immediately (`wgpu_worker_node.js` back to clean).

**Why it fails:** the feature only *exists* from 2026-08-27 (CL 337155). Our Dawn is
**2026-08-22** — 5 days too old. Its WGSL parser doesn't even know the name
`swizzle_assignment`, hence "expected extension". No Dawn runtime flag
(`enable-dawn-features=...`) can conjure a language feature that isn't compiled in.

**Conclusion: the feature/flag route is dead. The source-level rewrite is the only path.**

---

## 5. The chosen fix: flatten chained swizzles at load time

Rewrite `base.a.b` → `base.compose(a,b)` **in the shader source string** inside
`shaderProgram()` in `wgpu_worker_node.js`, before `packUniforms(source)`.

**Composition rule:** `compose(t) = a[ idx(b[t]) ]` where `idx('x')=0,'y'=1,'z'=2,'w'=3`.

Examples:
- `r1.yyyy.w` → `r1.y`   (a=`yyyy`, b=`w` → a[3]=`y`)
- `v.xy.xyxx` → `v.xy`   (a=`xy`,  b=`xyxx` → x→x, y→y, x→x, x→x = `xyxx`… see note)
- `v0.xy.xyxx.xy` → `v0.xy` (iterated to fixed point)

**Why it's safe — scanned across all 4,808 `.wgsl` files (`scan-swizzle2.js`):**
- **24,300** chained swizzles in **4,111** files.
- **0** out-of-range compositions (would be invalid WGSL anyway).
- **0** used as **assignment targets** (so no lvalue/duplicate-component hazard).
- **0** struct/field names are pure `xyzw` (so `.xy` after an identifier is always a swizzle,
  never a field access → no ambiguity).
- Every rewrite **shortens** the text by ≥3 chars → **guaranteed termination**, even for
  multi-level chains (each rewrite re-examined at the same index).

**Files:** `E:\gta\playgta5\node-webgpu\scan-swizzle.js` (has a const-reassign bug, do not use),
`scan-swizzle2.js` (validated version), `scan-fields.js`, `scan-ctx.js`.

### Open correctness risks (must resolve BEFORE trusting the transform)

1. **Scalar-base broadcast.** If a chain's base were a *scalar* (`x.yyyy.w`), then `x.yyyy`
   broadcasts and the result is just `x`. Flattening to `x.y` would be **invalid WGSL**
   (scalar has no `.y`). The scanner did **not** check base types.
   - In the one failing shader we read, `r1 : vec4<f32>` → safe. But we have **not** proven
     this for all 24,300 chains.
   - Mitigation: either (a) restrict rewriting to bases provably typed `vecN`, or
     (b) verify no scalar bases exist by scanning declarations.
2. **Narrow trigger vs. broad rewrite.** Only **26 pipelines** actually failed, but there are
   24,300 chains. The bug needs *single-element outer*. A full rewrite is safe if risk #1 is
   cleared, but we could alternatively rewrite **only** `b.length==1` chains (the true trigger)
   to minimise surface area.
3. **A long-running verification scan timed out at 120 s** (the PowerShell loop over all files).
   Re-run with a larger timeout or port it to the Node scanner.

---

## 6. Exact next steps (in order)

1. **Clear risk #1:** write a quick scan that flags any chain whose base identifier is declared
   as a scalar (`f32/i32/u32/bool`) rather than `vecN`. If zero → full rewrite is safe.
2. **Implement `flattenSwizzles(src)`** in `wgpu_worker_node.js` near line ~101; call it in
   `shaderProgram` before `packUniforms(source)`. Gate with env `WGPU_FLATTEN_SWIZZLE`
   (default on, `0` to disable) so it's reversible without an edit.
3. `node --check` on the file.
4. **Test run:** bundled v24 node, `WGPU_NATIVE_DRIVER=0`, native-dawn module, ~170 s →
   check `diag-native-*.txt` for `swizzle view` errors and a non-zero draw count.
   (The last run `diag-native-swizzle.txt` still had the BAD `enable swizzle_assignment`
   prepend — it must be re-run after the revert + flatten.)
5. Once pipelines pass: enable the driver (unset `WGPU_NATIVE_DRIVER`), verify draws +
   validation, benchmark vs the **8.32 FPS** JS baseline.
6. Then continue the actual goal: port the hot path (`runCommands` / `doDraw` / `setBG`)
   from JS to C++.

---

## 7. Environment gotchas (repeat offenders)

- **Always use the bundled Node 24:**
  `E:\gta\playgta5\node24\node_modules\node\bin\node.exe` (v24.22.3).
  PATH `node` is v22.23.2 and dies with
  `TypeError: Cannot convert a BigInt value to a number` at `initMemory`
  (`new WebAssembly.Memory({initial:BigInt(...),address:"i64"})` needs Node 24).
- Server must be up: `http://localhost:8000/data/manifest.json` → 200
  (`E:\gta\playgta5\serve_local.py`, Cache-Control: no-cache).
- Harness driver switch: `wgpu_worker_node.js:72` → `nativeOn()` gated by
  `process.env.WGPU_NATIVE_DRIVER !== '0'`.
- Harness module pick: `harness.js:10` →
  `process.env.WGPU_NODE_MODULE = 'E:/gta/playgta5/native-dawn-test/node_modules/native-dawn'`.
- `nativeSetBG` already converts `g.dyn` → `Uint32Array` (handles plain/empty Array).
- C: drive is FULL (0 GB) — everything to E:.

---

## 8. Why this matters (bigger picture)

The whole point of native-dawn is to replace the JS WebGPU hot path with C++ calls
(`setPipeline`/`setBindGroup`/`setVertexBuffer`/`draw`…) to escape the JS per-draw overhead
that caps us at 8.32 FPS with a no-draw ceiling of 11.55 FPS. The driver code is **already
written and integrated** (`native_dawn_driver.node`, JS fallback in place) — it is inert only
because pipelines can't compile. **Clearing this swizzle bug unblocks the entire C++ port.**
