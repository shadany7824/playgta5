# Httpfs / file-system bridge for a native WAMR host (research notes)

Scope: how the working Emscripten JS harness serves GTA V data files to the wasm, and the minimum native equivalent. All statements are tagged **verified** (read directly from the cited file/decompile) or **inferred** (logical consequence, not observed). Line numbers refer to the files as they exist in this workspace on 2026-11-26.

## Key question 1 — Exact import signatures/semantics (`wasm_httpfs_manifest_js`, `wasm_httpfs_io_start_js`, `wasm_has_page_js`, `wasm_httpfs_io_get_result_js`)

### Takeaway
The wasm imports are `wasm_httpfs_io_start_js(i64 table_addr) -> void`, `wasm_httpfs_manifest_js(i64 buf, i32 cap) -> i32` (two-call size/copy protocol), and `wasm_has_page_js() -> i32`; **`wasm_httpfs_io_get_result_js` does not exist anywhere** — read results come back in shared linear memory, not through an import return value.

### Cited Findings
- Decompiled import table: `import function wasm_httpfs_io_start_js(a:long); // func3`, `import function wasm_httpfs_manifest_js(a:long, b:int):int; // func4`, `import function wasm_has_page_js():int; // func9` — [game.dcmp:205496-205508](E:/Malik/game/game.dcmp). `wasm_httpfs_io_get_result_js` is not among the imports (full list at [game.dcmp:205490-205514](E:/Malik/game/game.dcmp)), not in the 85 registered native symbols ([gta_aot_host.cpp:987-1075](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp)), and not in `game.js`/`game-node.js` (searched both).
- Working `game-node.js` implementation, verbatim (diagnostic version; clean `game.js` is the same minus `__diag`):
  ```js
  function wasm_httpfs_manifest_js(buf,cap){
    if(typeof XMLHttpRequest==="undefined")return-1;
    let bytes=globalThis.__httpfsManifest;
    if(bytes===undefined){bytes=null;try{const x=new XMLHttpRequest;
      x.open("GET",self.location.origin+"/data/manifest.json",false);x.send();
      if(x.status===200)bytes=(new TextEncoder).encode(x.responseText)}catch(e){...}
      globalThis.__httpfsManifest=bytes}
    if(bytes===null)return-1;
    if(cap>bytes.length){(growMemViews(),HEAPU8).set(bytes,Number(buf));
      (growMemViews(),HEAPU8)[Number(buf)+bytes.length]=0;
      globalThis.__httpfsManifest=undefined}
    return bytes.length}
  function wasm_httpfs_io_start_js(table){if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;
    Module["__ioStarted"]=true;
    Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)})}
  function wasm_has_page_js(){return 1}   // game-node.js diagnostic build
  ```
  — [game-node.js:2066-2080, 2109-2110](E:/gta/playgta5/node-webgpu/game-node.js); clean browser build: `wasm_has_page_js(){return typeof process!=="undefined"&&process.versions&&process.versions.node?0:1}` and identical manifest/io_start bodies — [game.js:110741-111500](E:/gta/playgta5/game.js).
- Exact return values: manifest import returns **-1** when `XMLHttpRequest` is unavailable or the GET fails; otherwise the **byte length of the manifest** (393014 bytes for the current file, [manifest.json](E:/gta/playgta5/mirror/playgta5.com/data/manifest.json)). Bytes are copied into wasm memory plus a trailing NUL **only when `cap > bytes.length`**; the cached copy is cleared so the next call re-fetches. `io_start` has no result; `wasm_has_page_js` returns 1 in a browser main thread (0 in clean Node) — [game-node.js:2066-2110](E:/gta/playgta5/node-webgpu/game-node.js), [game.js](E:/gta/playgta5/game.js).
- Wasm-side two-call protocol, verified: `u = wasm_httpfs_manifest_js(0,0); if (u < 0) goto fail; q = malloc(u+1); if (wasm_httpfs_manifest_js(q,u+1) != u) {free(q); goto fail;}` then `strstr(q,"\"files\"")` parses the JSON — [game.dcmp:297833-297843](E:/Malik/game/game.dcmp); string `3811822` decodes to `"files"` (passive data segment 0, address − 1024 = file offset relative to 48550243) — decoded from [game-lodlive-fixed2.wasm](E:/Malik/game/game-lodlive-fixed2.wasm); string-address convention recorded in [ERROR-TRACE.md:103](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- `io_start` is called from the wasm **only** on a runtime thread and only once: `if (!is_runtime_thread) goto skip; if (AtomicLoad(8284724)) goto skip; wasm_httpfs_io_start_js(8284736); AtomicStore(8284724,1)` in both `wasm_httpfs_lookup` and `wasm_httpfs_pread` — [game.dcmp:299068-299071, 299282-299285](E:/Malik/game/game.dcmp); the argument `8284736` is the address of the shared control block — [ERROR-TRACE.md:64](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- `wasm_has_page_js` is used only for start-mode selection (`if (eqz(wasm_has_page_js())) { ... }`), not for httpfs — [game.dcmp:310059-310075](E:/Malik/game/game.dcmp).
- Current C++ host stubs: `imp_003_wasm_httpfs_io_start_js` and `imp_004_wasm_httpfs_manifest_js` are pure audit stubs returning 0; `imp_009_wasm_has_page_js` returns 1 — [gta_aot_host.cpp:191-207, 243-252](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).
- WAMR `register_natives_raw` convention: native function is `void foo(wasm_exec_env_t, uint64_t *args)`; arguments are raw 64-bit slots and the return value is written back to `args[0]` — [WAMR API docs](https://bytecodealliance.github.io/wamr.dev/docs/html/wasm__export_8h.html), [WAMR export-native-API guide](https://wamr.gitbook.io/document/wamr-in-practice/features/export_native_api).

### Inferences
- On memory64, the manifest `buf` argument is a full 64-bit address; the native implementation should convert it with `wasm_runtime_addr_app_to_native(env, buf)` (the helper pattern already in the host at [gta_aot_host.cpp:75-84](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp)), not truncate to 32 bits.
- The JS "clear cache after successful copy" means an exact-size query followed by a copy is the supported sequence; a native host can simply always return the same size and copy on every call with sufficient `cap`.
- Because there is no result import, the native host must implement the shared-slot protocol (question 4) for reads to work at all.

### Gaps
- No source file for the engine's original `httpfs_wasm.cpp` exists in this workspace; all wasm-side details come from `game.dcmp` and `io_worker.js` comments.
- The apparent decompiler anomaly where `wasm_httpfs_pread` seems to read the state field rather than the result field (`AtomicLoad(c)` at [game.dcmp:299302-299316](E:/Malik/game/game.dcmp)) is almost certainly a decompiler artifact: the JS worker writes bytes to `w+7` and state 2 to `w` ([io_worker.js:522-524](E:/gta/playgta5/io_worker.js)), and the caller treats the return as a byte count ([game.dcmp:296791-296794](E:/Malik/game/game.dcmp)). The native implementation must follow the JS worker layout (result at `w+7`).

## Key question 2 — `data/manifest.json` format and path mapping (`/game/...` vs Rockstar dev paths)

### Takeaway
The manifest is `{"mount":"/game/","version":"1791169379-5814","files":[[relative_path, size, unix_mtime], ...]}` with 5814 entries; `/game/<relative_path>` is the only path form the engine routes to httpfs, and the real files live under `mirror/playgta5.com/data/` (not `E:\gta\playgta5\data\`, which does not exist).

### Cited Findings
- Top-level keys and example entries (verified by parsing the JSON): keys `mount`, `version`, `files`; `mount = "/game/"`, `version = "1791169379-5814"`, 5814 file entries, **all 3-element arrays**; e.g. `["common/RadioLog.csv",47,1790860560]`, `["x64/textures/sandbox/sandbox.ytd",60,1790539440]` — [manifest.json](E:/gta/playgta5/mirror/playgta5.com/data/manifest.json). File size is 393014 bytes — same file, as reported in [ERROR-TRACE.md:69](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- The worker consumes only the first two elements: `files = j.files.map((f) => ({path:f[0],size:f[1]}))`, `dataQuery = '?v=' + encodeURIComponent(j.version)`, and fetches `base + f.path` — [io_worker.js:588-593, 330](E:/gta/playgta5/io_worker.js).
- Wasm lookup accepts exactly two path forms: `strncmp(a, "/game/", 6) == 0` or `strcmp(a, "/game") == 0`; otherwise it returns -1 immediately. It then builds the key from `a+6` (or the empty string for bare `/game`), strips a trailing `/`, and lowercases it — [game.dcmp:299054-299073, 299144-299210](E:/Malik/game/game.dcmp); strings `3122734` = `"/game/"`, `1755962` = `"/game"`, `4086926` = `""` decoded from passive data segment 0 of [game-lodlive-fixed2.wasm](E:/Malik/game/game-lodlive-fixed2.wasm).
- `wasm_httpfs_lookup(path, out_size, out_mtime)` returns the manifest index as a non-negative int, and writes size/mtime through its two out-pointers: caller converts mtime to Windows FILETIME via `mtime*10000000 + 116444736000000000` — [game.dcmp:299118-299141, 297208-297220, 296945-296959](E:/Malik/game/game.dcmp).
- `rage_fiDeviceLocal_Open` uses httpfs **only** when the path starts `/game/` and `wasm_httpfs_active()` is nonzero; otherwise it calls libc `open()`. The prefix check decodes to `"/gam"` + `"e/"` (`1835099951`, `12133`) — [game.dcmp:296643-296695](E:/Malik/game/game.dcmp), [lesson 07](E:/gta/playgta5/.claude/memory/think-like-claude/07-decode-magic-numbers.md).
- Verified failure mode: without `-rootdir=/game/`, the logged path was `E:/P1/gta5/build/dev_ng/x64/audio/audio.rpf` (Rockstar internal dev root, string at wasm address `3122485`) and `MountAudioPacks` trapped with "Unable to find critical archive '%s'". Adding `-rootdir=/game/` made MANIFEST and IO_START fire and the game reach the loading screen — [ERROR-TRACE.md:100-107](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md), [lesson 05](E:/gta/playgta5/.claude/memory/think-like-claude/05-log-the-real-inputs.md), [lesson 06](E:/gta/playgta5/.claude/memory/think-like-claude/06-read-the-crashing-function.md).
- Browser and native host both pass `-rootdir=/game/`: [index.html](E:/gta/playgta5/mirror/playgta5.com/index.html) launch args, [harness.js](E:/gta/playgta5/node-webgpu/harness.js) `arguments: ['-rootdir=/game/', ...]`, and host `build_game_argv()` / `call_main()` — [gta_aot_host.cpp:1155-1210](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).
- Real on-disk data root: `E:\gta\playgta5\mirror\playgta5.com\data\` contains `manifest.json`, `bootset.json`, `bootset_low.json` and nested `common/`, `x64/` trees (e.g. `x64/audio/audio.rpf`, 29,728,768 bytes). `E:\gta\playgta5\data` does **not** exist (verified with `Test-Path`). `serve_local.py` sets `ROOT = mirror/playgta5.com` and serves `ROOT/data` with byte-range support and `POST /data/batch` — [serve_local.py:7, 74-128, 156-201](E:/gta/playgta5/serve_local.py).

### Inferences
- Map a guest path to a host file by: require prefix `/game/`, strip it, lowercase, strip trailing slash, look up the manifest key, take the 0-based index as the file id, and open `E:/gta/playgta5/mirror/playgta5.com/data/<relative_path>` read-only. Use the manifest's size (not the on-disk size) as the authoritative size, but clamp reads to the actual file end as `io_worker.js` does via `shrink()` — [io_worker.js:98-115](E:/gta/playgta5/io_worker.js).
- The third manifest element is a Unix-seconds mtime (the engine multiplies by 10^7 and adds the Windows epoch offset).
- Rockstar dev paths should never reach httpfs once `-rootdir=/game/` is set; if they still appear, the launch args/ArgStartMode are wrong rather than the file bridge.

### Gaps
- The manifest's meaning for a directory/root entry (`/game`) is not documented; the wasm inserts an empty-name entry when parsing. No game code path that needs it was observed.
- It was not verified whether every manifest path is unique after lowercasing; the host should defend against duplicates.

## Key question 3 — WASI `__syscall_openat`, `__syscall_stat64`, `__syscall_fstat64`, `fd_read`, `fd_pread` in the JS harness

### Takeaway
These are Emscripten's JS-musl syscalls backed by the in-memory Emscripten FS (MEMFS mounted at `/`), **not** the httpfs path: httpfs files are opened by `wasm_httpfs_lookup()` and read by `wasm_httpfs_pread()` directly, so there are no httpfs file descriptors at all.

### Cited Findings
- The JS runtime mounts MEMFS at `/` in `FS.staticInit()` and initializes stdio fds 0/1/2 in `FS.init()` — [game-node.js (readable copy) lines 54228/54280 region](E:/gta/playgta5/node-webgpu/game-node.js), [FS.createStandardStreams](E:/gta/playgta5/node-webgpu/game-node.js). In pthreads, each syscall proxies to the main thread (`if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(N, ...)`) — [game-node.js:1552, 1671, 1418](E:/gta/playgta5/node-webgpu/game-node.js).
- `___syscall_openat(dirfd, path_ptr, flags, varargs)`: converts i64 cells via `bigintToI53Checked`, decodes path with `UTF8ToString`, resolves relative paths with `SYSCALLS.calculateAt(dirfd,path)` (`dirfd == -100` → cwd), reads `mode` from varargs when `flags & 64` (O_CREAT), and returns `FS.open(path,flags,mode).fd` or `-e.errno` — [game-node.js:1552-1561](E:/gta/playgta5/node-webgpu/game-node.js).
- `___syscall_stat64(path,buf)`: `SYSCALLS.writeStat(buf, FS.stat(path))`, returns 0 / `-errno`; `___syscall_fstat64(fd,buf)`: `SYSCALLS.writeStat(buf, FS.fstat(fd))`, returns 0 / `-errno` — [game-node.js:1671, 1418](E:/gta/playgta5/node-webgpu/game-node.js). `___syscall_lstat64` and `___syscall_newfstatat` are analogous.
- Exact `writeStat` buffer layout (104 bytes, all offsets in bytes; memory64 cells are 8 bytes): `+0 dev u32`, `+4 mode u32`, `+8 nlink u64`, `+16 uid u32`, `+20 gid u32`, `+24 rdev u32`, `+32 size u64`, `+40 blksize i32 = 4096`, `+44 blocks i32`, `+48 atime_sec i64`, `+56 atime_nsec u64`, `+64 mtime_sec i64`, `+72 mtime_nsec u64`, `+80 ctime_sec i64`, `+88 ctime_nsec u64`, `+96 ino i64` — [game-node.js (readable copy) 1383-1386](E:/gta/playgta5/node-webgpu/game-node.js); field order cross-checked against upstream Emscripten `struct_info.json` — [Emscripten struct_info.json](https://raw.githubusercontent.com/emscripten-core/emscripten/main/src/struct_info.json).
- `fd_read(fd,iov,iovcnt,pnum)` and `fd_pread(fd,iov,iovcnt,offset,pnum)`: iovec is `{u64 ptr, u64 len}` (16 bytes); helper `doReadv` loops iovecs and calls `FS.read(stream, HEAP8, ptr, len, offset)`; total is written to `*pnum` as an 8-byte value; import returns 0 on success (or an errno from the catch), with `fd_pread` rejecting `NaN` offset with 22 (EINVAL) — [game-node.js:106752-109000 region](E:/gta/playgta5/node-webgpu/game-node.js); host mirrors this with `iovs + i*16`, `app_read(...,8)` and `app_write(nread_ptr,total,8)` — [gta_aot_host.cpp:91-126](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).
- The engine distinguishes httpfs handles from native fds by address: `rage_fiDeviceLocal_Read` uses `wasm_httpfs_pread` only when the handle `b >= 65536`; otherwise it calls libc `read(fd,...)`. `rage_fiDeviceLocal_ReadBulk` likewise calls `wasi_fd_pread` for fd handles and queues httpfs reads for large handles — [game.dcmp:296788-296856](E:/Malik/game/game.dcmp). HTTPFS "file id" is an int stored in a 24-byte malloc'd handle, not an fd — [game.dcmp:296684-296688](E:/Malik/game/game.dcmp).
- Current native host: `fd_read`/`fd_pread` share `wasi_fd_read_impl`, which writes `nread=0` and returns 0 for every fd; `openat`, `stat64`, `fstat64` are no-ops returning 0 (i.e. "success", fd 0) — [gta_aot_host.cpp:119-126, 538-598, 733-740](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).

### Inferences
- A native host does not need to emulate an httpfs mount inside the WASI FS for `/game/` paths; it needs real behavior for the four httpfs-related imports plus a small FS for non-httpfs paths (`/userdata/...` saves/settings, `/dev/stdin|stdout|stderr`, occasional config files).
- For a file that does not exist, return `-2` (ENOENT) from `openat`/`stat`/`fstat` (negative errno), not 0; 0 would alias stdin or claim success while leaving the stat buffer uninitialized.
- `writeStat` is an Emscripten-specific struct (wasm64 LP64 layout), not the host's Win64 `struct stat`; the host must write the 104-byte layout field by field.

### Gaps
- No log was found enumerating all non-`/game/` paths opened during a full successful run; a native host should log unknown paths during the first run and add them as needed.
- Whether `fd_pread`'s catch path returns positive or negative errno in this exact Emscripten build is unclear from the generated snippet; successful calls return 0 in all cases.

## Key question 4 — `io_worker.js` protocol (`init`, `open`, `read`, `stat` messages)

### Takeaway
There are no `open`/`read`/`stat` postMessage messages: after one `init` message and one `{memory,table}` message, the worker communicates exclusively through 64-byte slots and a hint ring in the shared wasm heap; `stat` data comes from the manifest, not from a message.

### Cited Findings
- `init` message, exactly as posted by the loader: `{init:true, base: self.location.origin+'/data/', noStore, record, trace, log, noHints, bootset:'bootset_low.json'|'bootset.json'}` — [loader.js:23-24](E:/gta/playgta5/loader.js). Node harness uses `base:'http://localhost:8000/data/'` — [harness.js](E:/gta/playgta5/node-webgpu/harness.js). Worker handler: `if(m.init){ready=init(m);return;}`; `init` fetches `base+'manifest.json'`, builds `files[]` from `j.files`, sets `dataQuery='?v='+version`, optionally opens the OPFS store and starts bootset prefetch — [io_worker.js:587-597, 633-643](E:/gta/playgta5/io_worker.js).
- The only other engine->worker messages are `{memory:wasmMemory, table:Number(table)}` (from `wasm_httpfs_io_start_js`), `{userdata:{path,data,mtime}}`, `{userdataDelete:path}`, and a BroadcastChannel `'close'` — [game-node.js:2076-2083](E:/gta/playgta5/node-webgpu/game-node.js), [io_worker.js:600-606, 633-643](E:/gta/playgta5/io_worker.js). No `open`/`read`/`stat` message types exist.
- Shared-memory layout (verbatim comment): control block at `table` (word index `bell = table/4`): `[0]` doorbell, `[1]` slot counter, `[2]` hint-ring word offset, `[3]` ring capacity, `[4]` hints claimed, `[5]` hints consumed. Slot `i` starts at word `16+16*i` (byte `table+64+64*i`): `[0]` state (0 idle / 1 requested / 3 taken / 2 done), `[1]` file id, `[2..3]` offset (low/high u32), `[4..5]` destination address (low/high u32), `[6]` length, `[7]` result (bytes or -1). Hint ring entries are 4 words: file id, offset low, offset high, length written last (bit 30 = low-priority hint, mask `0x3fffffff`, 0 = free) — [io_worker.js:15-20, 474-525, 550-569](E:/gta/playgta5/io_worker.js).
- Worker loop: read doorbell, scan `n = header[1]` slots, `compareExchange(state,1,3)` to claim, call `serve(slot)`, then `Atomics.waitAsync(HEAP32, bell, seen)` — [io_worker.js:571-584](E:/gta/playgta5/io_worker.js).
- `serve(slot)` reads `id = slot[1]`, `off = slot[2] | slot[3]<<32`, `dst = slot[4] | slot[5]<<32`, `len = slot[6]`; clamps `len` to `f.size`, returns 0 for `off >= f.size`, writes bytes directly to `HEAPU8[dst..]`, then `Atomics.store(slot+7,result)`, `Atomics.store(slot,2)`, `Atomics.notify(slot,1)` — [io_worker.js:474-525](E:/gta/playgta5/io_worker.js). File size/mtime come from the manifest entry `f.size`; no `stat` message is involved — [io_worker.js:588-593](E:/gta/playgta5/io_worker.js).
- Wasm side of the slot protocol, verified: `wasm_httpfs_pread(id, dst, off, len)`: takes slot index from `tls_base+80` (assigning one via atomic increment of the slot counter if `<0`, fails if `>511`), writes `slot+4 = id`, `slot+8 = off` (i64), `slot+16 = dst` (i64), `slot+24 = len`, sets state 1, increments the doorbell, `emscripten_futex_wake(8284736,1)`, waits on the slot until state 2, writes state 0, returns the byte count — [game.dcmp:299272-299317](E:/Malik/game/game.dcmp). Slot stride is 64 bytes (`(h<<4)<<2`) and the control block is at 8284736 — [game.dcmp:299287-299299](E:/Malik/game/game.dcmp), [ERROR-TRACE.md:64](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- Hint producer: `rage_fiDeviceLocal_ReadBulk` writes 256-entry hint rings directly (`(counter&255)*16` stride), increments header[4], doorbell, and futex-wakes 8284736 — [game.dcmp:296818-296829](E:/Malik/game/game.dcmp); hints are purely prefetch; `drainHints` returns early when `noHints` or no store — [io_worker.js:550-569](E:/gta/playgta5/io_worker.js).
- Storage is an optimization only: 4096-byte blocks in OPFS `store.bin` + `journal.bin` (header magic `0x4a415449`/`ITAJ` + version), with a 48 MB memory fallback — [io_worker.js:24-29, 117-162, 434-467](E:/gta/playgta5/io_worker.js).

### Inferences
- The minimal native reader should poll the doorbell, CAS state 1→3, do a direct `pread()` from the mapped host file, `memcpy` into the wasm address, then store result and state=2 with release semantics and wake the waiting wasm thread.
- The hint ring can be ignored initially (equivalent to `?nohints=1`) — it only affects throughput, not correctness. The slot counter and doorbell words must still be preserved because the wasm increments them.
- File ids are indices into the `files` array parsed from the manifest, so the native worker should build the same ordered vector.

### Gaps
- It is not verified how WAMR implements wasm `memory.atomic.wait/notify` for the futex in `wasm_httpfs_pread`: writing state=2 through a raw native pointer may not wake a parked WAMR thread. The host must confirm WAMR's atomic-notify behavior (or provide an equivalent wake) before relying on blocking reads.
- The exact initial values the wasm writes into header words `[2]`/`[3]` (hint ring offset/capacity) at startup were not located; they matter only if hints are consumed.

## Key question 5 — Minimal correct native implementation

### Takeaway
Four real imports plus a slot-serving reader thread are sufficient: copy the manifest into wasm memory on the two-call protocol, record the table address in `io_start`, serve request slots with direct `pread()`, and keep `-rootdir=/game/` in argv; no OPFS/batch/cache machinery is needed.

### Cited Findings
- Existing host registers 85 native symbols in `"env"` and `"wasi_snapshot_preview1"` but almost all are audit-only stubs — [gta_aot_host.cpp:987-1086](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp); `wasm_httpfs_manifest_js` and `io_start` return 0 and copy nothing — [gta_aot_host.cpp:191-207](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).
- The host already has the needed primitive for i64-address access: `wasm_runtime_addr_app_to_native(inst, addr)` via `app_read`/`app_write` — [gta_aot_host.cpp:71-84](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp), and WAMR raw-natives argument/return convention — [WAMR API docs](https://bytecodealliance.github.io/wamr.dev/docs/html/wasm__export_8h.html).
- The data root with all 5814 files is `E:/gta/playgta5/mirror/playgta5.com/data/` — [manifest.json](E:/gta/playgta5/mirror/playgta5.com/data/manifest.json), directory listing verified locally; `serve_local.py` reads exactly this directory for `/data/...` and `/data/batch` — [serve_local.py:7, 172-188](E:/gta/playgta5/serve_local.py).
- Native host already passes `-rootdir=/game/` to `__main_argc_argv` — [gta_aot_host.cpp:1155-1210](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp); browser equivalent — [index.html](E:/gta/playgta5/mirror/playgta5.com/index.html), [ERROR-TRACE.md:104-106](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- Manifest protocol: two calls, exact byte count returned — [game.dcmp:297833-297841](E:/Malik/game/game.dcmp), [game-node.js:2066-2075](E:/gta/playgta5/node-webgpu/game-node.js). Slot protocol details — [io_worker.js:474-525](E:/gta/playgta5/io_worker.js), [game.dcmp:299272-299317](E:/Malik/game/game.dcmp).

### Inferences — proposed minimal implementation (ordered)
1. **Manifest import**: once at host startup, read `E:/gta/playgta5/mirror/playgta5.com/data/manifest.json` into a `std::string` (393014 bytes). `imp_004`: `size = manifest.size()`; if `args[0]==0 || (int)args[1] < (int)size`, write `size` to `args[0]` and return; else `memcpy(native_ptr(args[0]), manifest.data(), size)` and write NUL at `+size`; always return `size`. Never return 0/-1 for a present manifest.
2. **Parse manifest natively** with any JSON parser (or a small hand parser for the known shape): ordered vector of `{path, size, mtime}` plus a lowercase-path → index map; mount prefix `/game/`. Reuse this vector in the reader.
3. **io_start import**: `void`, one argument `args[0] = table address`; store it in an atomic global; start exactly one native reader thread (ignore repeats, as the wasm already guards with `8284724`). No return value needs to be written for a void import (verify with WAMR raw-native convention).
4. **Reader thread**: poll `int32` words at `table/4`; maintain `seen_doorbell`; for each slot with state 1, CAS 1→3; read id, off (u32 pair), dst (u32 pair), len; look up id → host path; open (cache `FILE*` / `HANDLE` per id); `pread` at `off` with `min(len, manifest_size-off)` and clamp to actual file size; `memcpy` result to `native_ptr(dst)`; write result to `slot+7`, then state=2 (atomic release); increment doorbell and wake any wasm waiter. Set state back to 0 only on the wasm side, as today.
5. **Keep argv** including `-rootdir=/game/`; do not force-call `Load()` from the host.
6. **`wasm_has_page_js`**: keep returning 1 (already implemented).
7. **Non-httpfs files**: implement a small virtual/native FS behind `openat`/`stat64`/`fstat64`/`fd_read`/`fd_pread`/`fd_seek` for `/userdata/...` (maps to a persistent host directory), `/dev/stdout|stderr`, and any other path that appears in logs; return negative errno for missing files; fill the 104-byte stat layout.
8. **Skip** OPFS store, journal, compressed batches, bootset prefetch, and hint consumption in the first native version. Direct disk `pread` is faster than the JS worker's HTTP fetches; skipping hints only reduces parallelism, not correctness.

### Gaps
- No end-to-end native run was performed as part of this research; this is a design proposal, not a verified working host.
- The host does not currently implement pthread creation with real execution environments; the io worker thread described above is a native std::thread, distinct from wasm pthreads. Interaction with the wasm futex still needs validation (see question 4 gap).

## Key question 6 — Risks of returning 0/-1 from these imports during ctors and main

### Takeaway
`wasm_httpfs_manifest_js` returning -1 or 0 keeps httpfs inactive (or empty) and ends in the intentional `MountAudioPacks` trap; a no-op `io_start` with an active flag turns reads into an infinite futex wait; zero-returning syscall stubs can silently alias stdin or leave stat buffers garbage.

### Cited Findings
- `Load()` bails out on a negative or mismatched manifest result and only sets the active byte `8321672[0]=1` after a successful parse — [game.dcmp:297833-297841, 298063-298066](E:/Malik/game/game.dcmp). `rage_fiDeviceLocal_Open` checks `wasm_httpfs_active()` and otherwise calls `open()`; `CFileMgr::MountAudioPacks` deliberately traps after `rage_fiPackfile_Init` fails — [game.dcmp:296676-296695](E:/Malik/game/game.dcmp), [lesson 06](E:/gta/playgta5/.claude/memory/think-like-claude/06-read-the-crashing-function.md).
- Historical evidence: with httpfs never activated, the game hit `RuntimeError: unreachable` at `CFileMgr::MountAudioPacks`; the exact fix was `-rootdir=/game/`, after which MANIFEST + IO_START fired and 4217 io fetches completed — [ERROR-TRACE.md:36-38, 100-107](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- `wasm_httpfs_lookup` and `wasm_httpfs_pread` return -1 immediately when the active byte is zero — [game.dcmp:299064-299067, 299280-299281](E:/Malik/game/game.dcmp). `wasm_httpfs_pread` also returns -1 when its per-thread slot index exceeds 511 — [game.dcmp:299287-299290](E:/Malik/game/game.dcmp).
- If `io_start` is a no-op but the active byte is set, `wasm_httpfs_pread` waits on the slot forever (`do_futex_wait(c,g,inf)`) — [game.dcmp:299300-299311](E:/Malik/game/game.dcmp); historically "io worker fetches all files but `wasm_httpfs_io_start_js` never called → no read serving" — [ERROR-TRACE.md:45-46](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- Forcing `Load()` manually from JS during runtime init caused a `null function or function signature mismatch` trap inside `operator new`; this evidence was later retracted as an invalid way to call Load (allocator/vtable not ready) — [ERROR-TRACE.md:67-83](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).
- Failed reads are retried forever by the engine (e.g. `CFileMgr::ReadLine` on `loadingtime.dat`); the worker therefore shrinks a file's recorded size instead of repeatedly failing — [io_worker.js:98-104](E:/gta/playgta5/io_worker.js).
- `fd_write` in the native host must copy bytes and set `*nwritten`; otherwise a zero-length write loop was observed — [gta_aot_host.cpp:91-117](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp). `fd_read` currently always writes `nread=0` (EOF) — [gta_aot_host.cpp:119-126](E:/gta/playgta5/node-webgpu/native/gta_aot_host.cpp).
- `wasm_has_page_js()==0` changes start-mode behavior (skips waiting for the loading-screen choice) but did not fix httpfs in Node — [game.dcmp:310059-310075](E:/Malik/game/game.dcmp), [ERROR-TRACE.md:45-48](E:/gta/playgta5/.claude/memory/engine-code-map/ERROR-TRACE.md).

### Inferences
- Return **-1** from `wasm_httpfs_manifest_js` only for a genuinely missing/unreadable manifest (mirrors JS); for a present manifest always return the exact byte length. A **0** return would look like an empty manifest and set the active byte with no files — equivalent failure to -1, but harder to diagnose.
- A zero return from `openat` means "opened fd 0"; subsequent `fd_read` returns 0 bytes (EOF), which the engine may treat as an empty-but-valid file or retry forever. Return negative errno (`-2` ENOENT, `-13` EACCES) on failure and a fresh positive fd on success.
- `stat64`/`fstat64` returning 0 without writing the buffer leaves arbitrary size/mode/timestamps in the guest; either fill all 104 bytes or return `-errno`.
- Do not call httpfs-related engine functions from the host during `__wasm_call_ctors`; let `call_once` fire naturally at the first lookup after runtime init.
- The 512-slot limit means a native reader must never invent extra slots; it must only consume slots the wasm has claimed.

### Gaps
- No native host log showing the exact behavior of a zero-length manifest or a zero-returning `openat` was available; those consequences are inferred from the decompiled control flow and the JS harness, not observed in a native run.
- The behavior of `wasm_has_page_js()==0` on the full game flow (beyond skipping the start-mode wait) was not tested.
