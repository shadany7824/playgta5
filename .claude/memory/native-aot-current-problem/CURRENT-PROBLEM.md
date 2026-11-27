# 25 — Native AOT host: current blocker (2026-11-27)

> **SOLUTION FOLDER (Claude, 2026-11-27): [../native-aot-solution/README.md](../native-aot-solution/README.md).** Correction: `GOT.data.internal.*` are wasm globals (TLS pointers set by `wasm_init_tls` = tls_base+720 via `_emscripten_tls_init`), NOT a WAMR AOT relocation. Next step 1 below (study WAMR GOT relocation) is RETRACTED. The host runs thread/TLS init before ctors with a no-op `_emscripten_init_main_thread_js`; JS runs it inside that import. Measure first (solution file 03), then fix (file 04).

## 2026-11-27 third session — tiny-AOT test + failed 5GB cap
- **Tiny wasm64 test (decisive):** built a 63-byte wasm by hand (`E:\gta\_tmp_claude\tiny-g.wasm`) with memory64, `gta_lod_cutoff`-like f32 global at index 0, i64 global at index 1, and a function doing `i64.const 1234; global.set 1`. Compiled with the same `wamrc` (`tiny-g.aot`), ran via a 40-line host (`tiny_host.cpp`) using the dumped `aot_debug_dump_globals`. Result: after call, g1 = `0x4d2`, global_data bytes show correct offset 0x4 — **WAMR AOT handles f32-first + i64 globals correctly**. So this is not a generic WAMR memory64 global-offset bug; the game's AOT is likely stale/mismatched vs its wasm. Rebuild from a clean wasm is justified.
- **5 GB cap attempt failed:** PowerShell Job Object (`JOB_OBJECT_LIMIT_PROCESS_MEMORY|JOB_OBJECT_LIMIT_JOB_MEMORY`, 5 GB) launched `wamrc --enable-multi-thread --opt-level=1 --size-level=1 -o E:\gta\gta-orig-test.aot E:\Malik\game\game.wasm`. Job creation/assign succeeded, but `wamrc` working set climbed to **10.9 GB** with free RAM down to 0.7 GB. Killed both processes; no AOT produced; RAM recovered to 11.6 GB. **Do not rerun while the owner's office work is active.** Job Object memory limits did not hold — need either a free PC (uncapped run, monitor) or a stronger cap mechanism.
- Tiny test artifacts: `E:\gta\_tmp_claude\make_tiny_g.py`, `tiny-g.wasm/aot`, `tiny_host.cpp/exe`, `wamrc-5gb.log`, `compile-aot-5gb.ps1`.

## 2026-11-27 second session — measured, Fix A applied, still blocked
- **Solution files 01–07 read and followed.** Global dump helper `aot_debug_dump_globals()` added to `aot_runtime.c` (dumps g0–g20 at checkpoints CP1/CP2/CP3/CPIN/CP4/CP5/CP6-fault). Host generator calls them (`E:\gta\_tmp_claude\gen_host.py`), canary bumped to `aot-host-v2-tls-in-import`.
- **Measurement (file 03) result:** g15 (`g_DisableInitNan`) = `0x79ca00` = tls_base `0x79c730` + 720 — **correct at every checkpoint including the fault**. So the "wrong TLS value" hypothesis is dead.
- **Fix A (file 04) applied:** `_emscripten_init_main_thread_js` now calls `_emscripten_thread_init(tb,1,1,1,1048576,0)` + `_emscripten_tls_init()` inside the import (re-entrant `wasm_runtime_call_wasm` works, `tls_base=0x79c730`), early init gated behind `GTA_AOT_EARLY_TLS=1`. Crash unchanged at seq 206. Hypothesis H1 dead.
- **Backtrace was misleading:** `bt2=0x1998BA83` is the return address of a SHARED exception stub (`0x1998ba77`). Scanned main's AOT code: 13 branches target it. NOP-sweep (env `GTA_AOT_NOP_AT=addr,len`) showed NOPing `0x1998bb77` (5 bytes) clears the exception — the failing check is in that cluster (`0x1998baed`/`0x1998bb04`/`0x1998bb16`/`0x1998bb43`/`0x1998bb6a`).
- **The actual bad value:** failing check computes `rax = 0x330 + [r14+0x1dc]` where `r14 = module_inst+0x68`; that address is `inst+0x244` and holds **`0x79c73000000000`** (`tls_base << 32`, a 4-byte displacement mismatch), giving `0x79c73000000330` >> bound `0xc3fffffc` → false OOB. Memory-instance bounds at `+0x60/+0x68` are correct (`0xc3fffffc`/`0xc3fffff8`); `module_inst->memories[0]` pointer is correct.
- **Failed experiments (do not repeat):** poking the AOT disp32 from `0x1dc` to `0x1e0` (one site only, other sites still fail); shifting all global_data by -4 (`GTA_AOT_SHIFT_GLOBALS`, crash moves earlier to seq 203); writing `tls_base` into `inst+0x244` (`GTA_AOT_FIX_R14`, no change). environ zero-count and dev_flag pre-set also no change.
- **Next:** find which runtime/AOT struct field `inst+0x244` really is (`WASMModuleInstance` layout: `cur_exception` at +0x68, so r14+0x1dc may be a mis-offset AOT-global cache). Figure out why it holds `tls_base<<32`; likely a 32/64-bit global store offset bug in WAMR AOT for this wasm64 module (or an AOT compiled from a wasm with a different global layout — `gta_lod_cutoff` f32 was inserted at global index 0). Consider rebuilding the AOT with the extra global appended at the end (index 58) so all original global offsets stay identical — needs a wat→wasm tool (none found yet) or a binary global-section rewrite.

## Goal / method (owner directive)
- Port the **working JS harness into a native C++ WAMR AOT host**. No hybrid (JS worker + native game) — owner rejected that.
- Method: **test/verify in JS first, then apply the same logic in C++** (memory 16 rule). JS harness runs the *same wasm source* as `gta-sl1-opt1.aot` (`E:/Malik/game/game-lodlive-fixed2.wasm`), so it is a valid reference. JS cannot load `.aot` directly.
- Motivation: FPS. Native host removes JS harness overhead + real threads. Caveat: if the wgpu renderer is the bottleneck, gains may be modest.

## Honest progress
- Code/harness port: ~90%. Game actually booting natively: ~35%.
- 3 days spent at time of writing. ETA 2–5 days more, possibly 1–2 weeks (chain of boot crashes is unpredictable).

## Current blocker (ROOT CAUSE FOUND, fix pending)
- Host reaches `main`, calls imports through seq=206: `wgpu_start_worker` (204), `wasm_input_publish_js` (205), `wasm_audio_publish_js` (206), then throws `Exception: out of bounds memory access` (WAMR id=2 = EXCE_OUT_OF_BOUNDS_MEMORY_ACCESS).
- `[EXC] bt2 pc=0x1998BA83 func=103 (main) off=0x51f` — **0x51f is the return address of a SHARED exception stub** (`0x1998ba77`), so it does NOT identify the faulting check by itself.
- Disassembled AOT code directly from `E:\gta\gta-sl1-opt1.aot` at file offset `0xa0e02b` (app addr `0x1998ba63`), using system `py -3` + capstone (full listing in `E:\gta\_tmp_claude\aotdis_wide.txt`).
- **Actual fault site:** `main+0x4fc` (app addr `0x1998b74c`):
  ```
  1998b735: mov byte [rdx+0x7f94a0],1        ; global 8361120 = 1 (matches decompile)
  1998b73c: mov rax, [rdi+0x230]              ; GOT data relocation: rage_g_DisableInitNan address
  1998b748: cmp rax, [rcx+0x60]               ; bounds check (4-byte)
  1998b74c: ja 0x1998b7d7                     ; FAIL -> OOB exception
  1998b752: dec dword ptr [rdx+rax]           ; c[0] = c[0]-1  (never reached)
  ```
  Decompile (`game.dcmp` ~293118, main's `return {...}` block):
  ```
  8361120L[0]:byte = 1;
  c = GOT_data_internal_rage_g_DisableInitNan;
  c[0]:int = c[0]:int - 1;
  ```
- **Root cause: the GOT data relocation value `*(rdi+0x230)` holds an address > memory bound 0xC3FFFFFF.** AOT GOT/data-reloc initialization is wrong or missing for this symbol. This is a WAMR AOT memory64 data-relocation issue, not an argv/env problem.
- Exception log fields: `mem bytes=3288334336 (0xC4000000) bound1=3288334335`; globals at fault `dev=1 argc=19 argvptr=0xc0000128 argv1=0xc0000017` (all valid).

## DEAD ENDS (do not retry)
- `getenv("WGPU")` result check at `0x1998ba63` — NOT the crash. Its exception shares the stub at `0x1998ba77`, which misled the backtrace. Proven by: setting dev_flag=1 before main (skips all 4 getenv blocks) and reporting zero env entries (getenv returns NULL) — crash unchanged at seq 206. Do not keep editing environ stubs.
- The `rootdir_global` at wasm addr `25030024` is a red herring (points into argv blob; `0xc0000020` garbage string). The real rootdir solution was `-rootdir=/game/` (memory 16), now delivered correctly.
- `patch_ud2` on func 29099 found 0 `0F 0B` bytes — dead route.
- AOT rebuild from a mirror wasm — unnecessary; no wasm mismatch.

## FIXED earlier (keep)
- WAMR memory64 argv bug in `E:\gta\wamr\core\iwasm\common\wasm_application.c` `execute_main()`: wrote `PUT_I64_TO_ADDR(&argv[1], app_addr)` into the host argv array; now `argv1[1]=(uint32)app_addr; argv1[2]=(uint32)(app_addr>>32)`. Added `argv[argc]=NULL` terminator. Rebuilt `libiwasm.lib`. Verified `[WAMR-DBG] argc=19 buf_off=0xc0000008 offs_app=0xc0000128`, argv[0]="./this.program" … argv[18]="-frameLimit=0", argv[19]=NULL; game globals argv_ptr=0xc0000128 argc=19.
- Because `-wgpu` is in argv, dev_flag=1 → `wasm_gpu_Init()` runs → 32MB ring at `0x5a601000`, `wgpu_start_worker(ring, 0x2000000, 0x64748c)` — matches JS import semantics.
- Dev flag global = wasm addr `8348848` (`0x7f64b0`); string `-wgpu` = `135449` (`0x21119`); env var `WGPU` = `2413881` (`0x24d539`); argc `8349728` (`0x7f6820`); argv ptr `8349736` (`0x7f6828`).
- `aot_runtime.c` `aot_log_fault()` extended: stack backtrace, AOT bytes dump, globals dump (`[EXC] globals dev=… argc=… argvptr=…`).
- Manifest parser fixed: `files=5814`. File bridge, fd=-44 for missing files, httpfs `Load()` via table slot 64, harness startup writes — all verified.

## JS reference facts (for the "JS first" method)
- `pthread-msg-log.txt`: after `AUDIO ring=8153472 cap=16384`, next is `wasm_module_js("keepThreads")` inside `rage_sysIpcCreateThread` (func128, `game.dcmp` ~295443), then `openat ./this.cmp`.
- Import name is `wasm_module_js` (func11), logged as `MODULE_INT` on JS side.
- JS `getEnvStrings()` returns exactly 7 entries (USER/LOGNAME/PATH/PWD/HOME/LANG/_), no WGPU. Our host now reports 0 entries (equivalent for getenv).
- wgpu worker: `wgpu_worker_node.js` (3303 lines) owns the WebGPU device and processes ring commands; it already delegates to native `native_dawn_driver_full.node` and partially to `native_worker.node` (`WGPU_CPP_STATE=1`). C++ sources exist: `native_dawn_driver_full.cpp` (9.9 KB), `native_worker.cpp` (36 KB, N-API addon), `webgpu_dawn.dll` (10.8 MB). Porting the worker to standalone C++ is a separate, larger task — do it only after boot works.

## Build / run
- Runtime: `cmake --build "E:\gta\wamr-build-aot" --config Release --target iwasm`
- Host: `cmd /c "\"D:\VSBuildTools\VC\Auxiliary\Build\vcvars64.bat\" >nul && cl /nologo /EHsc /MD /D_CRT_SECURE_NO_WARNINGS /DWASM_RUNTIME_API_EXTERN= /I\"E:\gta\wamr\core\iwasm\include\" /I\"E:\gta\wamr\product-mini\platforms\windows\" \"E:\gta\playgta5\node-webgpu\native\gta_aot_host.cpp\" \"E:\gta\wamr-build-aot\Release\libiwasm.lib\" advapi32.lib ws2_32.lib ntdll.lib /Fe\"E:\gta\playgta5\node-webgpu\native\gta_aot_host.exe\""`
- Generate host: `E:\gta\playgta5\runtime\python.exe E:\gta\_tmp_claude\gen_host.py`
- Run: `set GTA_AOT_CALL_MAIN=1 && set GTA_AOT_SKIP_FUNC=90974 && gta_aot_host.exe E:\gta\gta-sl1-opt1.aot`; audit `E:\gta\_tmp_claude\native-host-audit.log`.
- `GTA_AOT_NO_FORCELOAD=1` skips forced `Load()` + io reader (untested behavior).

## NEXT STEPS (in order)
1. Find WAMR AOT GOT / data-relocation init for memory64. Inspect `AOTModuleInstance` fields and `aot_runtime.c` data-section relocation code; determine what `rdi+0x230` points to and why `rage_g_DisableInitNan` resolves out of bounds. Compare with how JS/Emscripten initializes that global (0 expected → `dec` to -1).
2. Options: fix WAMR relocation handling, or patch the AOT module's GOT value at load time in the host (write the correct app address for that symbol), or patch the game wasm to drop the `dec` on a null GOT pointer. Prefer the first two.
3. After boot: verify next import is `wasm_module_js("keepThreads")`, then thread creation and `openat ./this.cmp`.
4. Only after native boot works: plan the standalone C++ wgpu worker port (JS-first reference → C++), for FPS.
