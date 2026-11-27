# Emscripten pthreads in the working JS harness — exact mechanism and native-host requirements

Scope: Windows x64, WAMR 2.4-era AOT host, GTA wasm (memory64 + shared memory, 85/86 imports incl. memory, 89368-entry table). All line/byte offsets below are from the files named in each citation. `[VERIFIED]` = read directly from the local harness / wasm binary / upstream Emscripten source; `[INFERENCE]` = reasoning from those facts.

---

## Key question 1 — Exact signatures and semantics of `__pthread_create_js`, `__emscripten_thread_init`, `__emscripten_thread_mailbox_await`, `_emscripten_tls_init`, `__emscripten_thread_free_data`, `__emscripten_thread_exit`

### Takeaway
In this build only `__pthread_create_js` is a JS **import**; the other five are wasm **exports** called by the JS pthread glue. All pointers are wasm64 `i64` values (JS converts them with `bigintToI53Checked`), and the C-side pthread struct is allocated inside wasm linear memory by `__pthread_create`.

### Cited Findings

**Binary-level signatures (from `wasm-objdump -x`, UTF-16 `objdump.txt`):**
- Import `func[62] __pthread_create_js <- env.__pthread_create_js`, `sig=28 = (i64,i64,i64,i64)->i32`. [Source](file:///E:/gta/playgta5/node-webgpu/objdump.txt)
- Import `func[52] _emscripten_init_main_thread_js <- env._emscripten_init_main_thread_js`, `sig=1 = (i64)->nil`; import `func[53] _emscripten_thread_mailbox_await <- env._emscripten_thread_mailbox_await`, `sig=1 = (i64)->nil`; import `func[73] _emscripten_notify_mailbox_postmessage`, `sig=3 = (i64,i64)->nil`. [Source](file:///E:/gta/playgta5/node-webgpu/objdump.txt)
- Export `func[91110] _emscripten_thread_init`, `sig=131 = (i64,i32,i32,i32,i32,i32)->nil`; export `func[90693] _emscripten_tls_init`, `sig=12 = ()->i64`; export `func[90881] _emscripten_thread_free_data`, `sig=1 = (i64)->nil`; export `func[90882] _emscripten_thread_exit`, `sig=1 = (i64)->nil`; export `func[91024] emscripten_stack_set_limits`, `sig=3 = (i64,i64)->nil`. [Source](file:///E:/gta/playgta5/node-webgpu/objdump.txt)
- JS binding proof (`assignWasmExports`): `__emscripten_tls_init=wasmExports["_emscripten_tls_init"]; __emscripten_thread_init=wasmExports["_emscripten_thread_init"]; __emscripten_thread_free_data=wasmExports["_emscripten_thread_free_data"]; __emscripten_thread_exit=wasmExports["_emscripten_thread_exit"]; _emscripten_stack_set_limits=wasmExports["emscripten_stack_set_limits"]; __emscripten_stack_restore=wasmExports["_emscripten_stack_restore"]; __indirect_function_table=wasmTable=wasmExports["__indirect_function_table"]; globalThis.__wasmTable=wasmTable;` [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js) (offset 117512)

**`__pthread_create_js(pthread_ptr, attr, startRoutine, arg) -> i32`** (JS glue, `___pthread_create_js`, offset 18154):
- Converts all 4 BigInt params to numbers; `if(!_emscripten_has_threading_support()) return 6` (`EAGAIN`; support = `!!globalThis.SharedArrayBuffer`). `transferList=[]`, `error=0`.
- `if (ENVIRONMENT_IS_PTHREAD && (!transferList.length||error)) return pthreadCreateProxied(...)` → synchronous proxy `proxyToMainThread(2,0,1,...)`. Otherwise on a pthread: sets `threadParams.cmd=5`, `postMessage(threadParams,transferList)`, returns 0. On main: `return spawnThread(threadParams)`.
- `threadParams = { startRoutine, pthread_ptr, arg, transferList }`.
- Upstream identical logic: `__pthread_create_js` returns `EAGAIN` with no SharedArrayBuffer; builds `threadParams`; from a pthread sets `cmd = CMD_SPAWN_THREAD (5)` and returns 0; from main calls `spawnThread`. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- The wasm-side caller `__pthread_create` first allocates one contiguous block holding `struct pthread` + TLS data + TSD slots + guard + stack, sets `new->self=new`, `new->stack` = top-of-stack, calls `_emscripten_thread_mailbox_init(new)`, then `__atomic_store_n(res,new,SEQ_CST)` **before** calling `__pthread_create_js(new,&attr,entry,arg)`; on failure it unlinks the thread and zeroes `*res`. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/system/lib/pthread/pthread_create.c)

**`_emscripten_thread_init(ptr,is_main,is_runtime,can_block,default_stacksize,start_profiling)`**:
- C implementation: `__set_thread_state(ptr,is_main,is_runtime,can_block)`; if `is_runtime && default_stacksize` sets the wasm global `__default_stacksize`; optional profiler enable + status RUNNING. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/system/lib/pthread/emscripten_thread_init.c)
- JS main-thread call passes `(tb, !ENVIRONMENT_IS_WORKER, 1, can_block, 1048576, false)`; worker cmd=2 call passes `(pthread_ptr, 0, 0, 1, 0, 0)` (offset 6271). [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)

**`_emscripten_thread_mailbox_await(pthread_ptr)`** (JS import handler at offset 93521):
- `if(!waitAsyncPolyfilled){ var wait=Atomics.waitAsync(HEAP32, pthread_ptr/4, pthread_ptr); wait.value.then(checkMailbox); var waitingAsync=pthread_ptr+204; Atomics.store(HEAP32, waitingAsync/4, 1) }`. `waitAsyncPolyfilled = !Atomics.waitAsync || Chrome<91`; under Node 24 it is false, so this runs.
- Upstream: `Atomics.waitAsync` on the pthread struct address arms a promise that re-arms `checkMailbox`; stores 1 at `C_STRUCTS.pthread.waiting_async` (upstream offset build-dependent; **this build uses 204**). When `waiting_async` is 0, wasm's `emscripten_thread_mailbox_send` instead calls `_emscripten_notify_mailbox_postmessage` (atomic-notify path is only used when the flag is 1). [Source](https://github.com/emscripten-core/emscripten/commit/db28eec196def521a373238283e8ecdbd09bc74c)
- `checkMailbox = () => { var p=_pthread_self(); if(!p)return; callUserCallback(()=>{ __emscripten_thread_mailbox_await(p); __emscripten_check_mailbox() }) }`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `_emscripten_notify_mailbox_postmessage(targetThread,currThreadId)`: if same thread `setTimeout(checkMailbox)`; if on a pthread `postMessage({targetThread,cmd:4})`; on main `PThread.pthreads[targetThread].postMessage({cmd:4})`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)

**`_emscripten_tls_init() -> i64`**:
- Registered once per instance via `registerTLSInit(wasmExports["_emscripten_tls_init"])` inside `createWasm()/receiveInstance` (offset 9608); called by `PThread.threadInitTLS()` on **every** thread start. In non-relocatable builds it just pushes the export into `PThread.tlsInitFunctions`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js); [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- It rebases TLS to the new thread's `tls_base` (returned `__tls_base`); in relocatable builds `registerTLSInit` wraps it to relocate GOT TLS exports. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)

**`_emscripten_thread_free_data(pthread_t t)`:
- Called from `returnWorkerToPool` **on the main thread**, never by the exiting thread itself: `delete PThread.pthreads[ptr]; unusedWorkers.push(worker); worker.pthread_ptr=0; PThread.clearMailboxAwait(ptr); __emscripten_thread_free_data(ptr)`. `clearMailboxAwait` = `Atomics.notify(HEAP32, pthread_ptr/4)` (cancels the `waitAsync`). [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- C: asserts `t != pthread_self()`, clears `t->self=NULL`, `emscripten_builtin_free(t->map_base)` (the whole malloc block containing pthread struct + TLS + TSD + guard + stack). [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/system/lib/pthread/pthread_create.c)

**`_emscripten_thread_exit(void* result)`:
- C: stores `result` in `self->result`, shuts down mailbox, runs cleanup handlers + TSD destructors; for main runtime thread calls `exit(0)`; otherwise processes robust mutex list, unlinks from thread list, `__set_thread_state(NULL,0,0,1)`, CAS `detach_state` to `DT_EXITING`/`DT_DETACHED` (detached ⇒ `_emscripten_thread_cleanup(self)`), stores `DT_EXITED` and `__wake`s joiners. `__pthread_exit` = `_emscripten_thread_exit(retval)` + `emscripten_unwind_to_js_event_loop()`. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/system/lib/pthread/pthread_create.c)
- JS `invokeEntryPoint` calls the wasm export `__emscripten_thread_exit(result)` directly after the entry point returns; only sets `EXITSTATUS` and returns when `keepRuntimeAlive()`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)

### Inferences
- A native host must expose `__pthread_create_js` as an **import** (i64,i64,i64,i64)->i32 and get the other five as **exports** by name (`_emscripten_thread_init`, `_emscripten_tls_init`, `_emscripten_thread_free_data`, `_emscripten_thread_exit`, `emscripten_stack_set_limits`/`_emscripten_stack_restore`, `_emscripten_check_mailbox`).
- The host must **not** allocate the `pthread_t` struct itself: it is allocated inside wasm memory by `__pthread_create`; the host only receives its address and the table index of the entry function.
- Because `_emscripten_thread_exit` does not itself unwind in this build (JS calls it as a plain export), the native host can simply call it on the same exec-env after `call_indirect` returns; no "unwind" exception path is required.

### Gaps
- Exact `struct pthread` field layout beyond `stack @+80`, `stack_size @+88`, `waiting_async @+204` was not dumped; upstream source shows offsets vary by build flags.
- No decompile file (`game.dcmp`) exists under `E:\gta` or `E:\gta\playgta5`, so time-bar registration code could not be read directly here (only the ERROR-TRACE summary).

---

## Key question 2 — `__emscripten_init_main_thread_js(tb)`: what it does and what `tb` is

### Takeaway
It is a JS import (func[52], `(i64)->nil`) that installs the **main thread's** pthread identity and TLS into the wasm globals; `tb` is the address of the static `struct pthread __main_pthread` inside wasm linear memory (observed `0x1c399c8` = 29596104).

### Cited Findings
- Exact body (game-node.js offset 92888): `function __emscripten_init_main_thread_js(tb){tb=bigintToI53Checked(tb);var can_block=!ENVIRONMENT_IS_WEB;__emscripten_thread_init(tb,!ENVIRONMENT_IS_WORKER,1,can_block,1048576,false);PThread.threadInitTLS()}`. In this Node harness `ENVIRONMENT_IS_WEB=false`, `ENVIRONMENT_IS_WORKER=false`, so the call is `__emscripten_thread_init(tb,1,1,1,1048576,false)` followed by `_emscripten_tls_init()`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- Upstream comment: the pointer is passed "to the native code where they are stored in wasm globals which act as a form of TLS"; global constructors accessing it earlier is UB. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- C caller: constructor priority 48 `_emscripten_init_main_thread()` sets `__main_pthread.self`, `detach_state`, `robust_list.head`, `tid=getpid()`, `next=prev=self`, `tsd=__pthread_tsd_main`, then calls `_emscripten_init_main_thread_js(&__main_pthread)`, then fills `__main_pthread.stack = emscripten_stack_get_base()` and `stack_size`, then `_emscripten_thread_mailbox_init`, `_emscripten_thread_mailbox_await`. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/system/lib/pthread/library_pthread.c)
- Runtime trace from the working harness: `IMPORT env._emscripten_init_main_thread_js n=1 a0=29596104 ...` and the next import `env._emscripten_thread_mailbox_await a0=29596104`. [Source](file:///E:/gta/playgta5/node-webgpu/pthread-msg-log.txt)
- `29596104` decodes to `0x1c399c8` — matches the owner-supplied `tb` address. [Source](file:///E:/gta/playgta5/node-webgpu/pthread-msg-log.txt)

### Inferences
- `tb+0` holds `self` (self-pointer magic), `tb+80/+88` hold `stack`/`stack_size` as u64 (used by `establishStackSpace`), `tb+204` holds `waiting_async`.
- The native host must perform these two export calls **before `__wasm_call_ctors` completes** (i.e., when the wasm ctor invokes the import), not merely at module load; ERROR-TRACE Stage 75 records that a no-op stub caused the "uninitialized element" table trap, and implementing them removed that trap. [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)

### Gaps
- Whether `can_block` should be 1 in a native host is not separately verified; the working Node harness uses 1.

---

## Key question 3 — `worker-boot.js` cmd protocol: exact fields and branch calls (cmd 1/2/4)

### Takeaway
`worker-boot.js` is only the Node/worker_threads bridge; the cmd state machine itself lives in the minified `game-node.js`. Cmd 1 = load wasm into worker, cmd 2 = start a pthread, cmd 3 = loaded ack, cmd 4 = check mailbox. Full cmd set is 1..9.

### Cited Findings
- cmd constants in Emscripten: `$CMD_LOAD:1, $CMD_RUN:2, $CMD_LOADED:3, $CMD_CHECK_MAILBOX:4, $CMD_SPAWN_THREAD:5, $CMD_CLEANUP_THREAD:6, $CMD_MARK_AS_FINISHED:7, $CMD_UNCAUGHT_EXN:8, $CMD_CALL_HANDLER:9`. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- **cmd 1 (worker side, game-node.js offset 5616):** `if(cmd==1){ let messageQueue=[]; self.onmessage=e=>messageQueue.push(e); startWorker=()=>{postMessage({cmd:3}); for(let msg of messageQueue){handleMessage(msg)} self.onmessage=handleMessage}; for(const handler of msgData.handlers){ if(!Module[handler]||Module[handler].proxy){ Module[handler]=(...args)=>{postMessage({cmd:9,handler,args})}; if(handler=="print")out=Module[handler]; if(handler=="printErr")err=Module[handler]}} wasmMemory=msgData.wasmMemory; updateMemoryViews(); wasmModule=msgData.wasmModule; createWasm(); run(); startWorker() }`.
- **cmd 1 (main side):** `worker.postMessage({cmd:1, handlers, wasmMemory, wasmModule})`; `handlers` = subset of `["onExit","onAbort","print","printErr"]` that are enumerable own properties of `Module`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- **cmd 2 (worker side, verbatim):** `else if(cmd==2){ establishStackSpace(msgData.pthread_ptr); __emscripten_thread_init(msgData.pthread_ptr,0,0,1,0,0); PThread.threadInitTLS(); __emscripten_thread_mailbox_await(msgData.pthread_ptr); if(!initializedJS){initializedJS=true} try{ invokeEntryPoint(msgData.start_routine,msgData.arg) } catch(ex){ if(ex!="unwind"){throw ex} } }`.
- **cmd 2 (main side, `spawnThread`):** `var msg={cmd:2, start_routine:threadParams.startRoutine, arg:threadParams.arg, pthread_ptr:threadParams.pthread_ptr}; worker.postMessage(msg, threadParams.transferList); return 0`; `PThread.pthreads[ptr]=worker; worker.pthread_ptr=ptr`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- **cmd 4 (worker side):** `else if(cmd==4){ if(initializedJS){ checkMailbox() } }`; `checkMailbox` re-arms `Atomics.waitAsync` and calls wasm export `_emscripten_check_mailbox`. On main, cmd 4 comes from `_emscripten_notify_mailbox_postmessage` as `{cmd:4}` (optionally `{targetThread,cmd:4}` for forwarding). [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `worker-boot.js` bridging: `globalThis.postMessage = m => parentPort.postMessage(m)` (logs `SEND cmd=<n>` for pthread workers); `Object.defineProperty(globalThis,'onmessage',{get...,set(fn){ if(!__bridgeInstalled){...parentPort.on('message', data=>{ if(_onmessage) _onmessage({data}) })}}})`; cmd=2 messages are logged with `sr=<start_routine> arg=<arg> tlen=<table length>`. `WorkerGlobalScope` + `name='em-pthread'` are synthesized when `workerData.pthread` is true; `instantiateWasm` is installed **only on the main thread** (pthreads use `new WebAssembly.Instance(wasmModule)` from cmd 1). [Source](file:///E:/gta/playgta5/node-webgpu/worker-boot.js)
- Observed runtime: `PTH MSG cmd=1 tid=3`, `cmd=1 tid=4`, `SEND cmd=3` x2, then `PTH MSG cmd=2 tid=4 sr=14 arg=0 tlen=89368` and `cmd=2 tid=3 sr=15 arg=34322552 tlen=89368`. [Source](file:///E:/gta/playgta5/node-webgpu/pthread-msg-log.txt)
- ERROR-TRACE Stage 2 (worker allocated its own 3 GiB memory → OOM because `ENVIRONMENT_IS_PTHREAD` was false) fixed by setting `WorkerGlobalScope`/name; Stage 4 (async `instantiateWasm` in pthread broke cmd-3 handshake) fixed by main-only `instantiateWasm`; Stage 6 (browser `worker.onmessage` vs Node `worker.on`) fixed by an `Object.defineProperty` bridge; Stage 17 (duplicate delivery: a new `parentPort.on('message')` listener was attached on every `onmessage` reassignment) fixed by one-time bridge install. [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)

### Inferences
- The native host does not need to reproduce the *message passing* literally, but must reproduce its **startup sequence per thread**: memory/module association → stack setup → thread init → TLS init → mailbox await → indirect call of `start_routine` → `_emscripten_thread_exit`.
- The JS `cmd:3` ack exists only because Emscripten's prerun dependency counter waits for all pool workers; a native host spawning OS threads can skip it.

### Gaps
- cmd 5/6/7/8/9 handling exists in game-node.js but was not exhaustively quoted; cmd 9 (`{cmd:9,handler,args}`) proxies `print`/`printErr`/`onAbort`/`onExit` back to main.

---

## Key question 4 — `establishStackSpace`, `_emscripten_stack_set_limits`, `stackRestore`, `invokeEntryPoint`, `PThread.threadInitTLS`

### Takeaway
These are the per-thread wasm-state setup steps executed in cmd 2, in a strict order; omitting any one leaves wasm globals pointing at the main thread's stack/TLS and produces table/OOB traps.

### Cited Findings
- `establishStackSpace` (game-node.js offset 17069): `var stackHigh=Number(HEAPU64[(pthread_ptr+80)/8]); var stackSize=Number(HEAPU64[(pthread_ptr+88)/8]); var stackLow=stackHigh-stackSize; _emscripten_stack_set_limits(stackHigh,stackLow); stackRestore(stackHigh)`. A native footprint: `tb+80` = `pthread.stack` (top of stack), `tb+88` = `pthread.stack_size`, both **u64**. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `stackRestore=val=>__emscripten_stack_restore(val)`; `stackSave=()=>_emscripten_stack_get_current()`; `stackAlloc=sz=>__emscripten_stack_alloc(sz)`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `invokeEntryPoint` (verbatim): `var invokeEntryPoint=(ptr,arg)=>{runtimeKeepaliveCounter=0;noExitRuntime=0;var result=(a1=>Number(getWasmTableEntry(ptr).call(null,BigInt(a1))))(arg); function finish(result){if(keepRuntimeAlive()){EXITSTATUS=result;return}__emscripten_thread_exit(result)} finish(result)};` — entry point is a **table index**, called with one `i64` arg (BigInt under MEMORY64), result passed to `_emscripten_thread_exit`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `getWasmTableEntry=funcPtr=>{funcPtr=Number(funcPtr);var func=wasmTableMirror[funcPtr];if(!func){wasmTableMirror[funcPtr]=func=wasmTable.get(BigInt(funcPtr))}return func}` — i64 table indices. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `PThread.threadInitTLS(){PThread.tlsInitFunctions.forEach(f=>f())}`; `registerTLSInit=tlsInitFunc=>PThread.tlsInitFunctions.push(tlsInitFunc)`; the single registered function is the wasm export `_emscripten_tls_init`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- Upstream `establishStackSpace` does exactly: read `pthread.stack` and `pthread.stack_size` → `stackLow=stackHigh-stackSize` → `_emscripten_stack_set_limits(stackHigh,stackLow)` (caches limits in wasm globals) → `stackRestore(stackHigh)` (sets up stack frame in wasm module scope) → optional stack cookie. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- Upstream `invokeEntryPoint`: resets `runtimeKeepaliveCounter=0` and `noExitRuntime=0` so pthreads actually finish, calls `makeDynCall('pp','ptr')` (table dispatch of `void* (*)(void*)`), then `__emscripten_thread_exit(result)` unless runtime kept alive. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)
- ERROR-TRACE Stage 75: JS-vs-C++ import diff showed the empty-slot crash was caused by a no-op `_emscripten_init_main_thread_js`; implementing `__emscripten_thread_init` + `_emscripten_tls_init` removed it. Remaining OOB at seq=70 and later `unreachable` in `CApp_UpdateState` were separate. [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)

### Inferences
- Exact native cmd-2 equivalent order: (1) read `stack`/`stack_size` from wasm memory at `tb+80/+88`; (2) call export `emscripten_stack_set_limits(stackHigh, stackLow)`; (3) call export `_emscripten_stack_restore(stackHigh)`; (4) call export `_emscripten_thread_init(tb,0,0,1,0,0)`; (5) call export `_emscripten_tls_init()`; (6) arm mailbox await; (7) `call_indirect` with `start_routine` as table index and `arg` as i64; (8) call export `_emscripten_thread_exit(ret)`.
- Steps (1)-(3) must be executed **on the new thread's exec env** so wasm's stack globals are per-thread; in WAMR each pthread needs its own `wasm_exec_env_t` over one shared `wasm_module_inst_t`.

### Gaps
- Whether `_emscripten_stack_set_limits` globals are WAMR per-instance or per-exec-env was not verified in WAMR source here.

---

## Key question 5 — How workers share memory and the WebAssembly.Table with main

### Takeaway
They share the **same `WebAssembly.Memory` object** (a 3 GiB shared, memory64 SAB) and the **same compiled `WebAssembly.Module`**; each worker creates its own instance (and thus its own table copy) synchronously from that module.

### Cited Findings
- `initMemory()` on main: `var INITIAL_MEMORY=3221225472; wasmMemory=new WebAssembly.Memory({initial:BigInt(INITIAL_MEMORY/65536),maximum:262144n,shared:true,address:"i64"})`. `initRuntime()` returns early for pthreads (`if(ENVIRONMENT_IS_PTHREAD)return`), so workers never allocate their own memory. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- cmd 1 passes `wasmMemory` and `wasmModule` by structured clone (both are shareable); worker sets `wasmMemory=msgData.wasmMemory; updateMemoryViews(); wasmModule=msgData.wasmModule; createWasm(); run()`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- `createWasm()` on a pthread is synchronous: `if(ENVIRONMENT_IS_PTHREAD){ var instance=new WebAssembly.Instance(wasmModule,getWasmImports()); return receiveInstance(instance,wasmModule) }`. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- From `assignWasmExports`: the table comes from each instance's export `__indirect_function_table` and is cached into `wasmTable`/`globalThis.__wasmTable`; `wasmTableMirror` caches `get` results. [Source](file:///E:/gta/playgta5/node-webgpu/game-node.js)
- Wasm binary: `memory[0] pages: initial=49152 max=262144 shared i64 <- env.memory`; `table[0] -> "__indirect_function_table"`; export table length observed `89368` entries in traces; AOT instrumentation found exactly one null slot, index 0 (`NULL_REF=FFFFFFFFFFFFFFFF`), element offset i64.const 1, length 89367. [Source](file:///E:/gta/playgta5/node-webgpu/objdump.txt); [Source](file:///E:/gta/playgta5/node-webgpu/pthread-msg-log.txt); [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)
- Upstream asserts `wasmMemory instanceof WebAssembly.Memory` and `wasmModule instanceof WebAssembly.Module` before cmd 1; instantiating the same module is the documented pthread model. [Source](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/lib/libpthread.js)

### Inferences
- "Sharing the table" means sharing the *compiled module and its element segments*, not one mutable table object: each instance's table is initialized identically. A native host should use one WAMR module instance / one `__indirect_function_table` shared by all pthread exec-envs (which is stronger than the JS model but functionally equivalent), with slot 0 invalid and valid indices 1..89367.
- The 3 GiB shared memory is why a native host must set memory64 + shared-memory + bounds checks compatible with WAMR 2.4; a per-thread allocation is fatal (Stage 2).

### Gaps
- Whether WAMR 2.4 AOT can share a single table across multiple exec-envs without explicit API calls was not verified in WAMR headers during this research.

---

## Key question 6 — Mandatory steps before engine threads can register time bars (global 12370200) and avoid `unreachable` in `CApp_UpdateState`

### Takeaway
The host must actually **run** the pthreads (`__pthread_create_js` must spawn real threads that execute `start_routine`), not just return 0; plus main-thread `init` + TLS + per-thread stack/thread/TLS setup. A stubbed `__pthread_create_js` is the recorded cause of time-bar count 0.

### Cited Findings
- ERROR-TRACE Stage 78: "with `GTA_AOT_SKIP_FUNC=90974`, `call_main ctors ok=1` at seq 201. `main` then reaches seq 252 and raises `unreachable` in func 29099 = `CApp_UpdateState(int,int,rage::fwFsm::Event)`. Decompile game.dcmp:2271761: the `unreachable` is hit when global 12370200 (time-bar count) == 0. **Likely because the game's emscripten pthreads never run (our `__pthread_create_js` stub returns 0).**" [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)
- Same Stage 78: "NEXT (big remaining work): run the game's emscripten pthreads (implement `__pthread_create_js` with real WAMR exec_envs / call_indirect), then httpfs/file imports. Until then the game aborts in `CApp::UpdateState`." [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)
- Stage 75 proved main-thread init is mandatory: no-op `_emscripten_init_main_thread_js` → "uninitialized element" table trap; implementing `_emscripten_thread_init` + `_emscripten_tls_init` removed it. [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)
- Working reference run: 27 cmd=2 thread starts, `tlen=89368`, `CheckEnumeration has finished`, world loads (Stage 17). [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)
- Engine function index confirms time-bar subsystem functions exist (`rage_pfTimeBars_Init`, `rage_pfTimeBars_StartTimeBar`, `rage_pfTimeBarMgr_Init`, etc.). [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/engine-function-index.tsv)
- WAMR caveats recorded: memory64 AOT software bounds checks enabled by default (#4350); AOT+SIMD+LLVM opt can create false OOB; `--opt-level=0` more consistent (issues #4525/#4527). [Source](file:///E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md)

### Inferences — actionable native-host checklist (ordered)
1. **Keep** the already-working main-thread behavior: call `_emscripten_thread_init(0x1c399c8,1,1,1,1048576,0)` and `_emscripten_tls_init()` when the wasm calls `env._emscripten_init_main_thread_js`; do this before/around ctors. (Verified necessary, Stage 75.)
2. **Implement `env.__pthread_create_js(i64 tb,i64 attr,i64 start_routine,i64 arg)->i32`** so it returns 0 **and** creates a real OS thread with its own WAMR `wasm_exec_env_t` on the shared 3 GiB memory64 module instance. Returning 0 without running the entry point is the documented cause of the time-bar = 0 crash.
3. **On each new thread exec env, in this order:** read u64 `stack=tb+80`, `stack_size=tb+88`; call `emscripten_stack_set_limits(stack, stack-stack_size)`; call `_emscripten_stack_restore(stack)`; call `_emscripten_thread_init(tb,0,0,1,0,0)`; call `_emscripten_tls_init()`; then `wasm_runtime_call_indirect(start_routine, arg)` (table index, one i64 arg), then call `_emscripten_thread_exit(ret)`.
4. **Support nested creates**: if `__pthread_create_js` is invoked from a worker exec env, proxy to the "main" dispatcher (JS cmd 5) or spawn directly; do not lose the `pthread_ptr`/`start_routine`/`arg` triple.
5. **Implement mailbox/proxying**: `env._emscripten_thread_mailbox_await` (either set `waiting_async @ tb+204` and use atomic-notify, or leave 0 and make `env._emscripten_notify_mailbox_postmessage(target,curr)` wake the target thread to call export `_emscripten_check_mailbox`); `env._emscripten_run_js_on_main_thread` + `env._emscripten_receive_on_main_thread_js` for proxied JS calls. Without this, futex/condvar/proxy waits between engine threads deadlock.
6. **Thread reclamation**: on entry-point return, `_emscripten_thread_exit` handles most teardown; the host should emulate `returnWorkerToPool` by calling `_emscripten_thread_free_data(tb)` from a *different* exec env and waking any mailbox waiter (`Atomics.notify`-equivalent on `tb`), reusing the exec env for a later thread.
7. **Keep the `arg` argument as an i64 pointer**: observed `arg=34322552` for one thread; passing a truncated i32 would corrupt thread startup. Table indices observed are small (14, 15) but must be used as table indices, not function addresses.
8. Only after real threads run should the `CApp_UpdateState` time-bar guard be re-tested; do not patch the game's `unreachable` to hide a missing-thread bug.

### Gaps
- No runtime evidence yet that a correct native `__pthread_create_js` actually makes global 12370200 nonzero; this is an inference from Stage 78, not a verified fix.
- No decompile source available to confirm exactly which engine thread writes 12370200 (candidates: `rage_pfTimeBars_Init` / `rage_pfTimeBarMgr_Init`, both present in the function index).
