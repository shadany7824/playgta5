# 21 — C++ worker DRAWS: 3 root causes + the log-diff method that found them (2026-11-25)

> **Why this file exists:** Stages 2/3 had been reported as "C++ doDraw working" but the C++ worker's own
> stats said `draw=0, skipDraw=100k+` — the game was still rendering through the **JS** path. This doc records
> the real bugs, the exact evidence, and the reusable debugging method (lessons 05/04/10/27). Read it before
> touching `native_worker.cpp` again.

## 1. The win (verified)
`diag-pword-FIXED.txt`:
- `JSDRAW p=379092604 ringW=379061248 pWord=379092604 kind=0 count=156 inst=1` (what JS sees)
- `CPPDRAW pWord=379092604 cmd=[0,156,1,0,0,0]` (what C++ sees — **now identical**)
- `CPPWORKER {"set":251810,"skip":717117,"draw":104828,"clamp":0,"skipDraw":0}` — draws REALLY go through C++
- `validation errors +0`

## 2. The three root causes (all were invisible until we logged both sides of the boundary)

### Bug A — BigInt handles crossed N-API as the wrong type
- JS `objectHandle(pl)` = valid BigInt (e.g. `1610820492704n`); C++ `as_ptr` read **0**.
- Evidence: `REGPIPE id=1 handle=0 raw=0 status=17 lossless=0 type=6`. Type 6 = `napi_object`, status 17 = bigint expected — the value arrived **boxed/not as a bigint primitive**.
- Fix: convert in JS with `Number(...)` before passing (handles are < 2^53, safe as double), and make C++ `as_ptr` accept both `napi_bigint` and `napi_number`. Applied at 7 call sites (regBuffer/regBG/regPipe/regTexture/setQueue/setPass/setZero).

### Bug B — wrong arg count / layout in `Draw`
- C++ `Draw` read 6 args with `plid=a[3]`; JS passed 7 args. C++ read zeros / wrong pipeline.
- Fix: `size_t argc=7; napi_value a[7]` with `a[0]=pWord, a[1]=lid, a[2]=plid, a[3]=foldV, a[4]=foldI, a[5..6]=unused`.

### Bug C — **double divide-by-4** (the one that produced all the zeros)
- `ringW = w32(ringBase) = floor(ringBase/4)` is **already a word index**; `p = base + 2` is **a word index**.
- JS called `cppWorker.draw(p >> 2, ...)` — dividing by 4 **twice**. C++ read `U[94773178]` (near memory start = zeros) instead of `U[379092712]` (real draw).
- Evidence: `JSDRAW p=379092712 ringW=379061248 pWord=94773178 count=168` vs `CPPDRAW pWord=94773178 cmd=[0,0,0,0,0,0]`.
- Fix: pass `p` directly. `processNext` was correct (it takes word offsets and converts byte tail with `>> 2`).

### Bonus — wasm `memory.grow` detaches the buffer
- C++ `U` was attached once at startup to a stale buffer after grow. `refreshViews()` in JS knows this and refreshes `u32`; we added `cppWorker.attach(memBuffer, cppStateU32.buffer)` there, and made `Attach` not reset state on re-attach.

## 3. The debugging method that found it (reusable — this is the real win)
1. **Don't trust your own "it works" claim** — check the component's OWN counters (lesson 27). `CPPWORKER stats` showed `draw=0` even though the game rendered → my earlier Stages 2/3 were wrong and got retracted in Stage 50.
2. **Log both sides of the boundary with the same inputs** (lesson 05): `JSDRAW` in JS and `CPPDRAW` in C++ at the identical `pWord`. Diff them (lesson 04). The mismatch (`count=168` vs `cmd=[0,...]`) pointed straight at the offset.
3. **Prove the instrument** (lesson 10): the C++ `REGPIPE ... status=17 type=6` dump proved the handle conversion was broken, not the pipeline.
4. **One change per run** (lesson 19): each fix got its own rebuild + unit test + one harness run with output to a file.
5. **Unit test the N-API layer in isolation** (`E:\gta\_tmp_claude\test-native-worker.js`, 8/8 pass) before the full game run.

## 4. Re-run / verify recipe
```
# unit (fast, no game)
E:\gta\playgta5\node24\node_modules\node\bin\node.exe E:\gta\_tmp_claude\test-native-worker.js
# full game (output to file, read stats after)
node24 harness.js > E:\gta\_tmp_claude\diag-XXX.txt 2>&1
# checks
Select-String diag-XXX.txt -Pattern 'CPPWORKER'   # want draw>0, skipDraw=0
Select-String diag-XXX.txt -Pattern 'validation errors' # want +0
```
Flags (all default **ON** now): `WGPU_CPP_STATE/DRAW/UPLOAD` — disable with `=0`.

## 5. Current state / caveats
- **A/B benchmark (Stage 51, first fair one after the fix): C++ ON 6.7 fps @ 1189 draws vs JS 7.5 fps @ 1310 draws. No FPS win** — ~2ms draw / ~2ms upload savings are drowned out by N-API crossings and scene variance. The C++ port is CORRECT (draw=75k verified) but does not improve FPS. The real bottleneck is the ~10,000 Dawn wire/IPC calls/frame, which neither path avoids. Do NOT chase more JS→C++ porting for FPS; see wire-profile.md.
- Upload path wired (CPP_UPLOAD); the earlier 'upload -55%' claim was measured while C++ draws were NOT running — void.
- Remaining bottleneck is still Dawn wire IPC (~10k calls/frame), now C++→Dawn, not JS. See `wire-profile.md`.
- Clean-up pending: remove `JSDRAW/CPPDRAW/DRAWARGS/REGPIPE/ZERO/NODRAW` diagnostic logs from `wgpu_worker_node.js` and `native_worker.cpp` once no longer debugging.

## 6. Related memory
- `engine-code-map/ERROR-TRACE.md` Stages 45-50 (driver freeze fix, stages 1-4, retractions, root cause).
- `think-like-claude/04,05,10,18,19,26,27` — the lessons that drove this.
