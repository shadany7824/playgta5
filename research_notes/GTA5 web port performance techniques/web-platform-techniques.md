# GTA V browser port — web-platform performance techniques (research notes)

- Date of research: 2026-10-16
- Target browser: Chrome 155 (Windows)
- Test machine: Intel i3-7100U (2C/4T), Intel HD 620 iGPU (shared memory, no dedicated VRAM), 4 GB RAM (~3.9 GB usable), game files on HDD, 10 GB pagefile on SSD.
- Purpose: for each relevant web-platform technique (2024-2026), give: what it is / measured or expected impact / feasibility for this port. Notes are self-contained for a downstream report writer.

## Feasibility legend (used on every item)

- **(a) Already used by the port** — evidence from the local files listed below (`file` + quoted code comment where helpful).
- **(b) User-adjustable today** — via the port's URL parameters / launcher options, no code changes.
- **(c) Requires port (or browser) developer changes** — not exposed to the user today.
- **⚠ UNVERIFIED/UNCERTAIN** — claim not fully confirmed; do not present as fact without re-checking.

## Local port files examined (mirror of playgta5.com, build `8b0b5899ed`)

- `E:\Malik\game\playgta5\homepage.html` — launcher. LOW_ARGS (`-textureQuality=0`, `-pedVariety=0`, `-vehicleVariety=0`, `-shadowQuality=-1/0`, `-reflectionQuality=0`, `-particleQuality=0`); adds `-numCores=<n>` when cores ≤ 2; checks `crossOriginIsolated` (COOP/COEP); comment about using a 1 ms idle `setInterval` to defeat Chrome/Windows ~15.6 ms timer rounding; comment that each engine thread is a Web Worker (~20 MB) and that a full profile spawns 80–116 workers.
- `E:\Malik\game\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js` — engine bootstraps inside a Worker; forwards `?cores=N` (fakes `navigator.hardwareConcurrency` before engine start), `?slots=`, `?syncpipelines`, `?low`, `?nopack`, `?shotrt`, `?limits` etc.
- `...\wgpu_worker.js` (2969 lines) — WebGPU driver worker: `FRAME_SLOTS` default 3 (`?slots=N`); comment: "3 slots = 2 frames in flight; the GPU-process wire round trip — not work — was capping frame rate". Uniform ring (RING_CHUNK 8 MB, 64 KB UBO window per slot region, one shared buffer, one bind group + dynamic offsets); bind-group cache; texture-view cache; pipeline "recipes" persisted to IndexedDB (`gta-pipelines` / `recipes`, saved every 20 s) plus server seed `pipelines.json`/`pipelines_low.json`; compile-ahead `AHEAD_MAX=max(2,min(8,hc-1))`; async pipeline compilation by default with skipped draws; `?syncpipelines=1` forces sync; title screen held until 1.5 s of frames with no skipped pipelines; canvas `configure()` only on first present/resize; present via blit pipeline, no `presentMode` set (default fifo). Comments about FXC quirks in the npm wgpu D3D12 build (terse-arg X3694/X3695).
- `...\io_worker.js` (644 lines) — OPFS store: `store.bin` append-only, 256 KB block reservations + `journal.bin` (16-byte entries); 48 MB in-memory fallback (no OPFS, or second tab → `createSyncAccessHandle` is exclusive); replaced earlier sync-XHR + Service Worker path that held ~1.5 GB in the renderer + ~0.9 GB in the SW; Atomics hint ring in shared wasm heap (HINT_PAR=96, LOW_PAR=48, `?nohints=1`); `/data/batch` POST + gzip + DecompressionStream; pre-baked `batchc/<hash>.bin` (CDN-cached, fetched with low priority); RUN_LANES=32 concurrent range requests (Apache per-stream cap workaround), BATCH_LANES=4; read-ahead MAX_AHEAD 512 KB / FIRST_AHEAD 64 KB / AHEAD_MIN_READ 64 KB; `bootset.json` prefetches ~600 MB of archive headers/startup data; IndexedDB `gta5-userdata`; diagnostics `?record=1`, netStat.
- `...\audio-worklet.js` (29 lines) — AudioWorklet `game-audio` processor consuming a ring in shared wasm memory via Atomics; silence on underrun; heartbeat word.
- `...\game.js` (124 KB) / `...\game.wasm` (~63 MB) — engine artifacts.

Third-party confirmation of architecture:

- GitHub `SebasKitten/Grand-V`: GTA V browser port using WebAssembly **memory64** + WebGPU; README cites RAM demands (min 8 GB recommended 16 GB). ⚠ Details summarized from search result; re-verify quotes on the repo page if quoted in the report.
- `ai.thesatyajit.com` article (2026-10-06) analyzing this port: matches local mirror (game.js ~124 KB, game.wasm ~63 MB, wgpu_worker.js ~194 KB); describes wgpu_worker as replaying D3D11-era commands on WebGPU. ⚠ Exact post URL not saved; re-search title if needed.

## 0. Key facts to lead with

1. The port already uses nearly every "modern web game" platform feature: wasm64 + shared memory + pthreads, WebGPU in a dedicated worker, OPFS sync-access streaming, AudioWorklet, SharedArrayBuffer/Atomics, IndexedDB caches. Remaining wins are mostly tuning **(b)** and a few dev changes **(c)**.
2. On 4 GB RAM the two dominant risks are **wasm/GPU memory exhaustion** (crash: `WebAssembly.Memory(): could not allocate memory`) and **pipeline-compile stutter** (hundreds of ms).
3. Browser-side improvements already live in Chrome ≤155 that help automatically: Tint IR for D3D12 (Chrome 136, up to 10x faster WGSL→HLSL translation in initial tests), DXC instead of FXC (Chrome 121), up to 2x faster `writeBuffer`/`writeTexture` incl. Dawn Wire (Chrome 144), Dawn pipeline disk cache.

## 1. WebGPU renderer techniques

### 1.1 Frames in flight / present pacing — **(b)**
- What: `FRAME_SLOTS` count (`?slots=N`, default 3). Each slot gets its own region of a shared uniform ring and its own present path.
- Impact on this port: the port's own comment says the cap was the GPU-process **wire round trip**, not GPU work — i.e., more slots can lift fps on fast GPUs, fewer slots reduce latency/memory. Try `?slots=2` (currently used), 3, 4; measure.
- Evidence: local `wgpu_worker.js` (~line 727). ⚠ No external authoritative source found for this exact wire-latency behavior; it is the port's own documented rationale.

### 1.2 Pipeline-compile stutter and pipeline caches
Platform-side (automatic in Chrome ≤155; upgrade is the only lever):
- Tint IR on D3D12: "up to 10 times faster" WGSL→HLSL translation in initial tests (Unity shaders); rollout "progressively expanded to Windows devices with D3D12" (Chrome 136, Apr 2025; issue 42251045): https://developer.chrome.com/blog/new-in-webgpu-136 ⚠ "progressively" means Intel Gen9/HD 620 coverage is not guaranteed — verify.
- DXC instead of FXC for Tint-generated HLSL on Windows (Chrome 121): https://developer.chrome.com/blog/new-in-webgpu-121
- Earlier generic shader-compile improvements: Chrome 126 https://developer.chrome.com/blog/new-in-webgpu-126 ; Chrome 130 (Metal) https://developer.chrome.com/blog/new-in-webgpu-130
- Dawn/Chrome pipeline **disk** cache: `GpuPersistentCache` stores per-API caches including `kDawnWebGPU`: https://chromium.googlesource.com/chromium/src/gpu/+/refs/heads/main/command_buffer/service/gpu_persistent_cache.cc ; default GPU disk cache size is small (gpu_switches.cc, `kGpuDiskCacheSizeKB` 6 MB in trunk — ⚠ check current Chrome 155 default) and may be far too small for a GTA-V-scale pipeline set (thrash/eviction). D3D12 backend persists via `ID3D12PipelineState::GetCachedBlob`/`CachedPSO` (`LoadCachedBlob`/`StoreCachedBlob`): https://dawn.googlesource.com/dawn/+/HEAD/src/dawn/native/d3d12/ComputePipelineD3D12.cpp
- Chrome 117 "Caching pipelines with automatically generated layout" (helps engines that don't supply layout): https://developer.chrome.com/blog/new-in-webgpu-117
- ⚠ Enlarging the browser-side GPU disk cache would need a Chrome/Chromium command-line switch (verify whether a stable override for `kGpuDiskCacheSizeKB` exists before recommending it) — **(c)** browser-level.

Port-side (**(a)**):
- Pipeline recipes cached in IndexedDB `gta-pipelines`/`recipes` (flushed every 20 s) + server-seeded `pipelines.json`/`pipelines_low.json`; compile-ahead up to `max(2,min(8,hc-1))` pipelines; async compile by default (draws skipped while compiling); `?syncpipelines=1` forces sync; title screen waits until 1.5 s of frames with no skipped pipelines. (local evidence)
- Anecdote: godotwebgpu (May 2026) reported WebGPU pipeline compile spikes of 200–1200 ms with caches not helping in that case — ⚠ low authority, one report.

### 1.3 Buffer/uniform uploads — **(a)** + platform wins
- Port: one shared uniform ring buffer (8 MB chunks), 64 KB UBO windows per slot region, single bind group + dynamic offsets — avoids per-frame allocs/uploads. (a)
- Chrome 144 (Jan 2026): `writeBuffer`/`writeTexture` up to **2x faster**, "affects all users of the Dawn Wire implementation as well" (issue 441900745): https://developer.chrome.com/blog/new-in-webgpu-144
- Chrome 145: experimental synchronous buffer mapping in workers: https://developer.chrome.com/blog/new-in-webgpu-145 (⚠ experimental; possible future **(c)** win for worker-owned uploads).
- Chrome 126: buffer upload optimization for Vulkan backend: https://developer.chrome.com/blog/new-in-webgpu-126

### 1.4 Render bundles — **(c)**, not evidently used
- What: pre-recorded GPU command streams to cut JS draw-call overhead; biggest gains when JS overhead is the bottleneck (MDN). toji.dev guidance. gpuweb#4104 measured 45 ms → 5.5 ms JS per frame (M1, ~40k objects).
- Relevance: the port replays draw commands in JS from `wgpu_worker.js`, and the CPU is a 2C/4T — CPU-side savings could matter. ⚠ No `renderBundle` usage found in scanned sections; adopting = dev change.
- URLs: https://developer.mozilla.org/en-US/docs/Web/API/GPURenderBundle ; https://toji.dev/webgpu-best-practices/render-bundles ; https://github.com/gpuweb/gpuweb/issues/4104

### 1.5 Bind-group / pipeline re-use — **(a)**
- Port caches bind groups and texture views; toji best practices recommend exactly this (also dynamic offsets, single big buffers): https://toji.dev/webgpu-best-practices/
- Khronos WebGPU best practices (compressed textures, etc.): https://www.khronos.org/developers/linkto/webgpu-best-practices

### 1.6 MSAA / render-target bandwidth — ⚠ gap
- No dedicated port parameter for MSAA found. Quality levers are the engine args (`-shadowQuality`, `-reflectionQuality`, `-particleQuality`, `-textureQuality`). Costs on a shared-memory iGPU are plausible inference, not sourced. Flag as open question.

### 1.7 Present mode / VSync — platform limitation
- WebGPU canvas `presentMode` is effectively fifo-only in browsers (no mailbox/immediate to bypass VSync). So the port's only pacing lever is `?slots` (1.1). Port uses the default — consistent. ⚠ Confirm spec wording: https://www.w3.org/TR/webgpu/#enumdef-gpupresentmode

### 1.8 WebGPU compatibility mode (fallback for old GPUs) — **(b/c)** via browser
- Origin trial Chrome 139: https://developer.chrome.com/blog/new-in-webgpu-139 ; GLES 3.1 backend Chrome 146: https://developer.chrome.com/blog/new-in-webgpu-146 ; featureLevel selection Chrome 133: https://developer.chrome.com/blog/new-in-webgpu-133
- Relevance: a fallback D3D11/GLES path can matter on Gen9-era iGPUs (HD 620) if the D3D12 path misbehaves. ⚠ Post-OT availability/shipping state in Chrome 155 unverified.

### 1.9 Texture memory — **(b)**
- `-textureQuality=0` skips the largest mip level → roughly quarter texture memory once resident (port's own homepage.html comment). Big win on a 4 GB/shared-memory machine.
- Compressed formats (BC) reduce GPU memory/bandwidth; Chrome keeps extending support (e.g., 3D BC/ASTC textures, Chrome 139): https://developer.chrome.com/blog/new-in-webgpu-139 ⚠ Whether the engine already uses BC-compressed textures is unverified.

## 2. WebAssembly memory / threads / OOM

### 2.1 memory64 and the 3 GB reservation — root cause of the crash — **(c)**
- memory64 lets a module use 64-bit pointers/large linear memory; shipped with Chrome 133 (⚠ re-verify exact version, e.g., caniuse "wasm memory64"); max 262144 pages = 16 GiB; port reportedly uses **shared** memory64 (SebasKitten/Grand-V README).
- The failure `WebAssembly.Memory(): could not allocate memory` on this 4 GB machine is about committing/reserving a ~3 GB arena plus GPU allocations on a 4 GB budget. Fixing it is a **dev-side** change (lower initial/committed memory, allocator tuning, or 8 GB+ RAM). Context on wasm memory limits and the wasm32 2–4 GB opt-in: https://v8.dev/blog/4gb-wasm-memory ; proposal: https://github.com/WebAssembly/memory64/blob/main/proposals/memory64/Overview.md
- Emscripten knobs (`INITIAL_MEMORY`, `MAXIMUM_MEMORY`, `ALLOW_MEMORY_GROWTH`, pthreads): https://emscripten.org/docs/tools_reference/settings_reference.html ⚠ V8 virtual-reservation vs committed-page behavior on Windows not sourced; mechanism statements are tentative.

### 2.2 Thread count vs memory — **(b)** (already used)
- What: `?cores=N` makes the engine believe there are N cores (loader overrides `navigator.hardwareConcurrency` before engine start); launcher adds `-numCores=<N>` when N ≤ 2.
- Impact: each engine thread is a Web Worker (~20 MB per homepage comment; full profile 80–116 workers). Fewer workers = less memory + fewer context switches on a 2C/4T; tradeoff = less parallelism for streaming/audio. `?cores=2` already used; try `?cores=1` only to debug OOM.

### 2.3 Growable shared memory + pthreads — ⚠
- Historically memory growth + pthreads interacted poorly (may be outdated): https://github.com/emscripten-core/emscripten/issues/1271 . Relevant only if devs consider growth instead of a large reservation **(c)**.

### 2.4 GPU memory is system memory here — analysis flag
- HD 620 has no dedicated VRAM; WebGPU buffers/textures compete with the wasm heap for the same 4 GB. Hence `-textureQuality=0` (1.9), lower resolution, and fewer `?slots` all reduce OOM pressure. ⚠ Present as inference unless a source is added.

## 3. IO / storage / streaming (io_worker)

### 3.1 OPFS sync access handles — **(a)**
- Port: `store.bin` append-only with 256 KB block reservations + 16-byte journal entries; `createSyncAccessHandle` inside io_worker (exclusive per tab; second tab falls back to a 48 MB RAM cache). It replaced an earlier sync-XHR + Service Worker design that held ~1.5 GB (renderer) + ~0.9 GB (SW). (local evidence)
- Why sync handles: the File System Access "AccessHandle" proposal is explicitly motivated by Wasm, noting that "consuming asynchronous APIs from Wasm has severe performance implications": https://github.com/WICG/file-system-access/blob/main/AccessHandle.md
- MDN: OPFS is "much more performant than [the] user-visible file system", not subject to security checks; sync access handles are worker-only: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- Benchmarks (workload-specific; treat with care): https://benchmark-db-browsers.riken.me/ (IndexedDB vs SQLite/OPFS SAH vs PGlite); https://github.com/kevinlinv/cold-idb-cache-opfs-compare (cold/warm open times). ⚠ Some synthetic Chromium benchmarks show IndexedDB beating OPFS for raw typed-array read/write; the port's choice is motivated by avoiding JS-heap copies/GC for a wasm engine, not raw throughput.

### 3.2 Why not Cache API / Service Worker (report context)
- Cache API can't do random-access reads of a multi-GB logical file and the old SW design blew up memory (numbers above). SW has no synchronous APIs.

### 3.3 Batch endpoint + compression + CDN — **(a)**
- `/data/batch` POST with gzip + `DecompressionStream` (native, off-heap), pre-baked `batchc/<hash>.bin` served CDN-cached with low fetch priority. (local)

### 3.4 Parallel range requests — **(a)**
- RUN_LANES=32 concurrent range fetches (port comment: Apache caps per-stream), BATCH_LANES=4 for batches. ⚠ No external source fetched for Chrome's per-host connection limits / HTTP/2 multiplexing; port's rationale only.

### 3.5 Read-ahead / prefetch / bootset — **(a)** + **(b)** diagnostics
- MAX_AHEAD 512 KB, FIRST_AHEAD 64 KB, AHEAD_MIN_READ 64 KB; `bootset.json` prefetches ~600 MB of archive headers/startup data; `?record=1` logs block ranges for tuning; `?nohints=1` disables the hint ring. (local)
- IO-spike smoothing comes from this stack (read-ahead + bootset + CDN batches + hint ring). Note: game files on HDD make seek-heavy access intrinsically slow **(system-level, not web-platform)**.

### 3.6 Hint ring — **(a)**
- Atomics-based doorbell ring in the shared wasm heap: 96 concurrent hint fetches (48 in low profile). (local)

### 3.7 Storage persistence vs eviction — mostly **(c)**
- `navigator.storage.persist()`: Chrome auto-grants based on engagement heuristics; persisted data is "rarely evicted"; best-effort data is LRU-evicted under storage pressure: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria ; https://web.dev/articles/persistent-storage
- ⚠ Whether the port calls `persist()` was not verified; if it doesn't, that's a cheap dev change to protect the OPFS store (eviction would delete it).

## 4. CPU / scheduling / audio / timers

### 4.1 Scheduler API (`scheduler.yield`, `postTask`) — **(c)**
- `scheduler.yield()` shipped Chrome 129 (Sept 2024): https://developer.chrome.com/blog/new-in-chrome-129 ; priorities via `taskPriority` in `scheduler.postTask()`: https://developer.mozilla.org/en-US/docs/Web/API/Scheduler/postTask — both available in Workers.
- ⚠ `scheduler.wait()` status unverified; no API found to give a whole Worker higher priority.
- Relevance: yield points in io_worker/wgpu_worker JS loops could reduce jank on 2 cores.

### 4.2 Timer granularity (~15.6 ms) — workaround already used **(a)**
- Chrome/Windows clamp timers to ~15.6 ms; Chromium `base/time/time.h` has `kMinLowResolutionThresholdMs = 16`; high-res timers are activated via `ActivateHighResolutionTimer`; raised-frequency modes (1/4/8 ms) were explored power-aware (issue 40611880). Intel Vtune documents Windows' 15.625 ms default: https://www.intel.com/content/www/us/en/docs/vtune-profiler/user-guide/2024-2/timer-resolution.html
- Port works around it with a 1 ms idle `setInterval` to keep timer resolution high (homepage.html comment). ⚠ No page-level API to request high-resolution timers; the workaround remains the practical fix.

### 4.3 AudioWorklet — **(a)**
- Port: `game-audio` processor consuming a ring in shared wasm memory via Atomics; emits silence on underrun; heartbeat word. (local)
- Design guidance: https://developer.chrome.com/blog/audio-worklet-design-pattern (⚠ page not fetched/verified during research).

### 4.4 SharedArrayBuffer + Atomics — **(a)**
- Used for the IO hint ring and audio ring; requires cross-origin isolation (COOP/COEP), which the launcher checks via `crossOriginIsolated` (homepage.html).

## 5. Quick action list (user-adjustable, **(b)**)

| Lever | Where | Expected effect |
|---|---|---|
| `?cores=2` (already) → try `?cores=1` only for OOM debugging | URL | Fewer workers: less RAM, fewer context switches |
| `?slots=2` (already) vs 3 / 4 | URL | Frame pacing vs memory/latency |
| `?syncpipelines=1` | URL | Removes skipped draws but may stutter more (try/measure) |
| LOW_ARGS (`-textureQuality=0`, shadow/reflection/particle 0, ped/vehicle variety 0) | launcher | Texture memory ÷4; less GPU work |
| `?low` profile | URL | Memory-lean mode (48 MB IO cache, fewer hint fetches) |
| Keep Chrome updated | browser | Chrome 136 Tint IR, Chrome 144 writeBuffer 2x |
| Close other tabs/apps; never open a second game tab | system | 4 GB budget; second tab forces OPFS RAM fallback |
| `?record=1`, `?nohints=1`, `?nopack` | URL | Diagnostics / trade-offs for tuning |

Developer-only **(c)**: memory64 initial-size tuning, render bundles, `navigator.storage.persist()`, `scheduler.yield` in JS loops, MSAA toggle (if engine-side exists), compatibility-mode opt-in, GPU disk-cache-size switch (⚠ unverified).

## 6. Gaps / uncertainties (do not state as fact without re-checking)

- Exact GPU disk cache default size in Chrome 155 (6 MB found in Chromium trunk); whether a user-visible switch exists.
- Tint IR "+10x D3D12" rollout coverage: HD 620 (Gen9.5) inclusion unknown ("progressively expanded to Windows devices").
- memory64 exact shipping version (claimed Chrome 133) and V8 Windows reservation/commit semantics.
- Frames-in-flight wire-cap behavior: sourced only from the port's own code comment.
- `scheduler.wait()` status; no worker-level priority API found.
- MSAA/bandwidth cost on shared-memory iGPU: no source; inference only.
- AudioWorklet design-pattern page and `ai.thesatyajit.com` post URL: not fetched/saved; re-find before citing.
- Dawn Intel Gen9 quirk (subgroups disabled on Gen9 via `PhysicalDeviceD3D12.cpp`, crbug.com/391680973): relevance to HD 620 (Gen9.5) uncertain.

## Appendix — source URLs

Chrome for Developers (What's New in WebGPU):
- 136 (Tint IR D3D12 up to 10x; issue 42251045): https://developer.chrome.com/blog/new-in-webgpu-136
- 144 (writeBuffer/writeTexture up to 2x incl. Wire; issue 441900745): https://developer.chrome.com/blog/new-in-webgpu-144
- 145 (experimental sync buffer mapping in workers): https://developer.chrome.com/blog/new-in-webgpu-145
- 146 (compat mode on OpenGL ES 3.1): https://developer.chrome.com/blog/new-in-webgpu-146
- 139 (compat-mode origin trial; 3D BC/ASTC textures): https://developer.chrome.com/blog/new-in-webgpu-139
- 133 (featureLevel compat mode; WGSL discard gains): https://developer.chrome.com/blog/new-in-webgpu-133
- 126 (shader compile improvements; Vulkan buffer uploads): https://developer.chrome.com/blog/new-in-webgpu-126
- 130 (Metal shader compile): https://developer.chrome.com/blog/new-in-webgpu-130
- 121 (DXC instead of FXC on Windows): https://developer.chrome.com/blog/new-in-webgpu-121
- 117 (pipeline caching with auto layout): https://developer.chrome.com/blog/new-in-webgpu-117
- 155-156 (current release notes): https://developer.chrome.com/blog/new-in-webgpu-155-156
- News index: https://developer.chrome.com/docs/web-platform/webgpu/news

Chromium/Dawn source:
- GpuPersistentCache (kDawnWebGPU): https://chromium.googlesource.com/chromium/src/gpu/+/refs/heads/main/command_buffer/service/gpu_persistent_cache.cc
- Shader/GPU disk cache (trunk): https://chromium.googlesource.com/chromium/chromium/+/trunk/content/browser/gpu/shader_disk_cache.cc
- Dawn D3D12 cached PSO blobs: https://dawn.googlesource.com/dawn/+/HEAD/src/dawn/native/d3d12/ComputePipelineD3D12.cpp
- Timer thresholds: https://github.com/chromium/chromium/blob/main/base/time/time.h ; timer frequency exploration issue: https://issues.chromium.org/issues/40611880
- Intel Gen9 subgroups quirk: https://issues.chromium.org/issues/391680973

Web platform docs/specs:
- Wasm memory64 proposal: https://github.com/WebAssembly/memory64/blob/main/proposals/memory64/Overview.md
- V8 4 GB wasm memory (wasm32 opt-in): https://v8.dev/blog/4gb-wasm-memory
- Emscripten settings: https://emscripten.org/docs/tools_reference/settings_reference.html
- OPFS docs: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- AccessHandle proposal (Wasm motivation): https://github.com/WICG/file-system-access/blob/main/AccessHandle.md
- Storage quotas & eviction: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
- Persistent storage (web.dev): https://web.dev/articles/persistent-storage
- scheduler.yield (Chrome 129): https://developer.chrome.com/blog/new-in-chrome-129
- scheduler.postTask: https://developer.mozilla.org/en-US/docs/Web/API/Scheduler/postTask
- GPURenderBundle: https://developer.mozilla.org/en-US/docs/Web/API/GPURenderBundle
- Render bundles guide: https://toji.dev/webgpu-best-practices/render-bundles
- WebGPU best practices (toji): https://toji.dev/webgpu-best-practices/
- Khronos best practices: https://www.khronos.org/developers/linkto/webgpu-best-practices
- Render-bundle measurements (gpuweb#4104): https://github.com/gpuweb/gpuweb/issues/4104
- WebGPU presentMode enum: https://www.w3.org/TR/webgpu/#enumdef-gpupresentmode

Benchmarks:
- Browser DB benchmark (IDB vs SQLite/OPFS SAH vs PGlite): https://benchmark-db-browsers.riken.me/
- Cold/warm cache open compare: https://github.com/kevinlinv/cold-idb-cache-opfs-compare

Port / third-party:
- SebasKitten/Grand-V (memory64 + WebGPU port): https://github.com/SebasKitten/Grand-V
- ai.thesatyajit.com analysis (2026-10-06): ⚠ exact URL not saved
