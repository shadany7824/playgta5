# Local "playgta5" browser port — port-level performance techniques (research notes)

Snapshot under research: `E:\Malik\game\playgta5` (build id `8b0b5899ed`), served locally by `serve_local.py` at `http://localhost:8000`.
All `file:line` refs are relative to that folder. `game-log.txt` = the user's own aggregated log (12.4 MB, multiple sessions). Target machine: i3-7100U, HD Graphics 620, ~3.9 GB RAM, game files on HDD (E:), pagefile+Chrome on SSD (C:), Chrome 155. All claims below are sourced from local files/lines or public URLs; unverifiable claims are marked as inference or gap.

---

## Q1: Every supported URL parameter and engine flag of this build

### Takeaway
The page (`homepage.html`, identical to the served `mirror\playgta5.com\index.html`) exposes ~22 query parameters plus `?args=` passthrough for arbitrary engine command-line flags. The port itself classifies most extra params (`nohints`, `nopack`, `limits`, `keep`, `slots`, `syncpipelines`, `record`, `trace`, `mem`, `dbg`, `console`, `shot`) as diagnostics; the player-facing performance set is `low`, `shadows`, `cores`, `res`, `scale`, `fixed`, `fps`, `args`, `newgame`, `mode`, `log`.

### Cited Findings
- Param parsing: `q = new URLSearchParams(location.search)` — `homepage.html:53`.
- `?args=-flag1,-flag2=value` — comma-split, appended to engine cmdline (`homepage.html:52`, `:407`).
- `?log=1` — stream log via POST `/log`; comment says it is off by default because it costs "the player's upload bandwidth and this thread's time" (`homepage.html:57-60`).
- `?low=1` forces low-memory profile; `?low=0` forbids it; default when `navigator.deviceMemory <= 4` (`homepage.html:360-371`).
- LOW_ARGS exact list: `-textureQuality=0 -pedVariety=0 -vehicleVariety=0 -shadowQuality=(shadows==1?0:-1) -reflectionQuality=0 -particleQuality=0 -grassQuality=0 -cityDensity=0 -lodScale=0 -pedLodBias=0 -vehicleLodBias=0` (`homepage.html:368-369`).
- `?shadows=1` keeps shadows at lowest level; default off in low profile (`homepage.html:368`, `README.md:76`).
- `?cores=N` overrides reported core count (default 2 in low) (`homepage.html:370`, `loader.js:9-10`).
- `?res=WxH` (even numbers, cap 2560x1440 in low / 3840x2160 otherwise), `?scale=0.25..2` (`homepage.html:373-383`).
- `?fixed=1` ignores window resizes → no swapchain reallocation on resize (`homepage.html:512-523`).
- `?fps=30|60|0` → `-frameLimit=2|1|0` (engine's own limiter; 2 = 30 FPS VSync2) (`homepage.html:406`).
- `?nogpu=1` drops `-wgpu` (no rendering) (`homepage.html:406`).
- `?newgame=1` → `-noautoload`; `?mode=story|sandbox`, `?map=env_test` (`homepage.html:191-192`, `:406`).
- `?verbose=1` restores the ~87% of log lines that are suppressed by default (script/replay spam) (`homepage.html:385-387`).
- Diagnostics: `?nohints=1` (no route hints), `?nopack=1`, `?limits=name:value,...`, `?keep=replay,net,bink,idle`, `?nocache`/`?nosw` (noStore), `?console`, `?trace=1`, `?slots=N` (frame slots, default 3), `?syncpipelines=1`, `?record=1`, `?mem=1`, `?shot=N`, `?shotrt=1`, `?dbg=1` (`homepage.html:409-422`, `:478-499`).
- Presets published by the port — Compat 720p/30: `?low=1&fps=30&res=1280x720&shadows=0`; Perf 540p/60: `?low=1&fps=60&res=960x540`; Quality/Ultra variants at `support/index.html:17-21`, `README.md:68-76`.
- Always-set engine args (not exposed): `-rootdir`, `-wgpu`, `-nodisplaycalibration`, `-noSocialClub`, `-pc:nosocialclub`, `-nonetwork`, `-output`, `-width/-height`, `-forceResolution`, `-fastscriptcore`, `-script_all=warning`, `-replay_all=warning` (`homepage.html:390-407`).
- Engine reads `-level` for map choice at ~62% of the loading bar (`homepage.html` load comments; `?map=` feeds it).
- Hosted-only extra params (`?touch=1/0`, F8 hide) exist on the third-party mirror `https://gta5-87g.pages.dev/__support/`, NOT in the local snapshot.

### Inferences
- `?log=1&mem=1` (currently used by the user's launchers) is explicitly a cost, not a feature: drop both for normal play (see ranked list).
- `?verbose` default already suppresses script spam; no gain from leaving it off.

### Gaps
- Neither `homepage.html` nor README annotate intended perf semantics of `?nopack`, `?trace`, `?mem` beyond "diagnostic"; no measured effect sizes published.

---

## Q2: Boot set, "host static copies", `?record=1`, `record_bootset.py`

### Takeaway
"Host static copies" = pre-built gzip files under `/data/batchc/<sha1>.bin` that the original PHP host generated on first request (`host/index.php save_batch`) so later visitors can GET a static file instead of POSTing raw ranges. The local mirror has no `data/batchc/` directory (hence the log's "0 of 32 batches from the host's static copies"), and `serve_local.py` only implements the POST `/data/batch?gz=1` fallback — the prefetch still works, just without the static-file shortcut. `?record=1` records a fresh boot set and posts it to the log, but the referenced `record_bootset.py` tool is absent locally and 404s on GitHub.

### Cited Findings
- Recording flow: with `?record=1` the prefetch is skipped (`if (sh && m.bootset && !m.record) prefetch(...)`) — `io_worker.js:596`; touched ranges accumulate and are posted as `[bootset] JSON` via `POST /log` after 75 s (`io_worker.js:164-185`).
- Batch fetching: GET `/data/batchc/<sha1(dataVersion+':'+body)>.bin` first; on failure POST `/data/batch?gz=1` — `io_worker.js:202-253` (esp. 232-239).
- Boot set filename chosen in loader: `bootset.json` vs `bootset_low.json` (`loader.js:24`). Both exist: `mirror\playgta5.com\data\bootset.json` (192,733 B) and `bootset_low.json` (190,351 B).
- Local server: POST `/data/batch` with `?gz=1` (gzip level 1), `X-Run-Lengths` header, ≤64 MiB/1000 runs per batch — `serve_local.py:106-166`. No `batchc` handling; unknown paths 404 → worker falls back to POST.
- Prefetch evidence: "boot set prefetched in 14 s, 244 MB ... 0 of 32 batches from the host's static copies" with 28 retried requests on the first (cold) run — `game-log.txt:625`; warm-store run: 0 s / 0 MB — `game-log.txt:631`.
- Prefetch parallelism: `RUN_LANES=32`, `BATCH_LANES=4`, runs ≤256 blocks (1 MiB) (`io_worker.js:27, 255-258, 290`); batch grouping rules `COMPRESSIBLE` regex, `WHOLE_MAX=8MB`, ≤4 MiB/300 files per batch (`io_worker.js:266-283, 358`).
- `dataVersion` comes from `manifest.json` and is part of the static-copy name (`io_worker.js:200`); `mirror\...\data\manifest.json` present (393,014 B).
- PR/host behavior: hosted defaults low=1, fps=30, res=1280x720; batching/cache patched in `build_web.py` (`https://github.com/alihammoud21/playgta5` — build script section).
- `record_bootset.py` referenced in `io_worker.js` comments; NOT present anywhere in the local tree; 404 at `https://github.com/alihammoud21/playgta5/blob/main/record_bootset.py`; not in the archival repo `shadany7824/playgta5` file list either.
- Background article: boot set recorded as 582 MB; converted ~6,000 individual shader requests into ~20 batched requests — `https://ai.thesatyajit.com` (technical breakdown article, 2025).

### Inferences
- Pre-generating the ~32 (low: fewer) static gzip batches locally is a self-contained, file-level optimization: a small script can replicate the batching rules, hash `dataVersion+':'+body`, write `data/batchc/<sha1>.bin`; benefit over the current POST+`gz=1` path on localhost is modest (saves per-boot gzip-1 CPU on the i3 and the POST round trip) but it is the port's only documented host-side fast path.
- `?record=1` is a regeneration tool: if a new build reads different ranges, run one recorded session, extract the `[bootset] JSON` line from `game-log.txt`, and drop it into `data/` as `bootset.json`.
- The 28 retried requests on first prefetch are retry-path retries; with a warm store they no longer occur.

### Gaps
- Exact `record_bootset.py` format/hash behavior unverifiable (unpublished).
- No official statement on what happens if `batchc` files are stale vs manifest `dataVersion`.

---

## Q3: The persistent store (`store.bin`) — warmth, growth, cold-cache stutter

### Takeaway
`store.bin` is an append-only 4 KB-block cache in the Origin Private File System (plus `journal.bin`) that every engine read and prefetch appends to. In the user's sessions it grew 740 MB → 1,085 MB and eliminated boot-set refetching entirely (14 s/244 MB → 0 s). It is per-origin (`localhost:8000` only), single-instance (exclusive SyncAccessHandle), and silently degrades to memory-only when the lock can't be taken — producing the log's repeated `prefetch failed: Cannot read properties of null (reading 'write')`.

### Cited Findings
- Store init/lock: open `store.bin`+`journal.bin`, exclusive handle, retry 40×250 ms (≈10 s) — `io_worker.js:120-161`; fallback `memCache` in 256 KB blocks — `io_worker.js:28, 95`.
- Block size `BS=4096`, `MAX_RUN=256` blocks per run (1 MiB); "blocks already stored or on their way cost nothing" — `io_worker.js:27, 290`.
- Growth evidence across sessions: 740 MB → 984 MB → 998 MB → 1,085 MB — `game-log.txt:47, 629, 25126, 44147, 63687`.
- Warm-store boots: prefetch 0 s / 0 MB — `game-log.txt:631, 25128, 44149, 63689`.
- Store-failure sessions: `[io] prefetch failed: Cannot read properties of null (reading 'write')` (≈90 lines) — `game-log.txt:265-357`; corresponds to `sh.write` on a null handle in the batch consumer — `io_worker.js:224`.
- pagehide closes the store for fast reloads; a new session may then wait up to ~10 s on the old handle (`homepage.html:345-346`; `io_worker.js:120-127`).
- Store facts from article: append-only store in OPFS; "582 MB boot set … 743 MB before I could walk" — `https://ai.thesatyajit.com`.
- Low profile reduces streaming set (VRAM ~1.16→0.5 GB, streamed assets ~1.38→0.95 GB per homepage comment) — `homepage.html:363`.

### Inferences
- Fastest way to "complete" the store is coverage: play/drive through areas (every engine read is cached), then future visits are local-SSD reads instead of HDD range reads + HTTP.
- Keep the origin and workflow stable: same port/host, one tab/session at a time, wait ~10 s after closing before relaunching; never use `?nocache`/`?nosw` for normal play; check for the `[io] persistent store:` open line in the log to confirm it's active.
- Moving the mirror (game files) to the SSD is the single biggest I/O change available: reads currently hit the HDD while pagefile/Chrome hit the SSD; the store itself already lives in the Chrome profile on C:.

### Gaps
- OPFS quota/eviction numbers not measured; no bulk pre-seed or "download-all" mechanism exposed by the snapshot.
- No data on whether store fragmentation affects read speed over time.

---

## Q4: Community and upstream knowledge (Oct 2026)

### Takeaway
The port/engine source is unpublished (only a compiled client snapshot + helpers/launchers). The surrounding ecosystem: main repo `alihammoud21/playgta5` (install/verify + presets), community launcher `alihammoud21/playgta5-enhanced`, a hosted Cloudflare Pages mirror `gta5-87g.pages.dev` with extra touch params, and an independent successor project `SebasKitten/Grand-V` (V2, re-release planned Friday 16 Oct 2026 per its README). No verified forum/Reddit threads with additional port-level perf knobs were found beyond the maintainer's own guidance and one deep technical article.

### Cited Findings
- Main repo README: "compiled client snapshot, not the original game-engine source code"; presets, troubleshooting, FPS guidance (`https://github.com/alihammoud21/playgta5`).
- Enhanced launcher: drop-in launcher with presets, controller support, `--engine-ram 4` (3→4 GiB initial allocation, experimental); no FPS uplift claimed (`https://github.com/alihammoud21/playgta5-enhanced`).
- Hosted mirror support page: 720p/30 laptop preset, `?touch=1/0`, F8 hide (`https://gta5-87g.pages.dev/__support/`).
- Grand-V: "GTA V reverse engineered to run natively in chromium based web browser, Using WebAssembly and WebGPU"; built on `rea`; launcher with 24/30/60 FPS cap options; re-release announced for Friday 16 Oct 2026 (`https://github.com/SebasKitten/Grand-V`).
- Archival source repo `shadany7824/playgta5` (file set matches local snapshot); points to Grand-V for V2 (github.com/shadany7824/playgta5).
- Article timings (Chromebook-class hardware): 24.6 s engine compile, 39.5 s archives, 54.6 s graphics, 69.7 s first frame, 176.2 s shaders, 188.1 s world; 4,808 WGSL shaders in 18 packs/72 MB; ~250 pipelines first view; 28,000 draws skipped in one second on a 4-core Chromebook; Chrome 15.6 ms timer fix; heap starts at 3 GB, ~20 MB per engine thread; slots round-trip caps FPS — `https://ai.thesatyajit.com`.
- Press notes: site taken down within hours; 4.5 GB RAM Linux floor; Chrome/Edge better than Firefox; crashes/artifacts reported (`todoandroid`, `vgtimes`, `gizdev` coverage, 2025).

### Inferences
- For this snapshot, the only drop-in performance-relevant options are the launcher-level ones in Q1–Q3; neither the enhanced launcher nor Grand-V claims renderer-side gains, and Grand-V is a different codebase (don't mix configs).
- The local snapshot matches the V1 file layout; treat tips for V2 as inapplicable until it ships.

### Gaps
- No community-posted per-flag benchmarks (e.g. shadows on/off) beyond the port's own numbers; no Reddit/YouTube deep dives verified.
- Enhanced launcher's served-JS patching not inspected first-hand in this research.

---

## Q5: Likely causes of multi-hundred-ms hitches and mitigations

### Takeaway
The port names three hitch classes: pipeline compilation (tens of ms per pipeline; hundreds on new content; mitigated in-build by async compile + compile-ahead seed + draw skipping), streaming I/O (32-lane prefetch at low priority; engine reads at high priority), and WebGPU fence latency (fixed in-build via `yieldTask`). The user's log shows the worst remaining frames are dominated by "worker idle" (7,642 ms of an 8,086 ms spike) and GPU-wait spikes (200–330 ms) — CPU-side stalls/descheduling and iGPU backpressure, not shader compilation at play time (which now happens almost entirely during the 37.3 s "Preparing shaders" wait at load: 867 compiled ahead, only 101 compiled on first draw).

### Cited Findings
- Worst-frame evidence: 8086 ms frame = 7642 idle/17 modules/207 uploads (3.9 MB) — `game-log.txt:1443`; 1666 ms frame w/ 1146 gpu wait — `:9988`; 898 ms w/ 755 modules + 24.7 MB uploads — `:11352`; 527 ms w/ 477 idle — `:17906`; 331 ms gpu wait — `:19444`.
- Load-time pipeline cost: "world shown: title screen held 37.3 s for compiling pipelines (248 draws skipped meanwhile…); compiled ahead 867, used 86, compiled when first drawn 101" — `game-log.txt:23518`.
- Recipe counts: "165 from this browser, 720 in the seed, 868 to compile ahead (3 at a time)" growing to 294-from-browser/997-ahead on later boots — `game-log.txt:46, 25161` (browser recipe cache grows → cheaper later boots).
- Mechanics: async compile skips draws (white holes) vs blocking sync compile — `wgpu_worker.js:1177-1203, 1287-1345`; compile-ahead budget `AHEAD_MAX = max(2, min(8, cores-1))` → 3 at a time at 4 cores — `wgpu_worker.js:1304`; `FRAME_SLOTS` default 3 — `wgpu_worker.js:728`.
- I/O priority: engine reads at high priority, prefetch at low; a 6.6 s blocking read was measured before the priority fix — `io_worker.js:323-324, 332`; throughput with runs: 6→128 in flight = 3.4→14.1 MB/s — `io_worker.js:255-256`.
- Focus behavior: blur releases keys, engine `FOCUS` atom — `homepage.html:560-562`; visibility wait comment notes it "added 15 ms to a frame" — `homepage.html:391-395`; the user's launchers already pass occlusion/background-throttling-defeating Chrome flags.
- Loading-screen watchdog reports 30 s stalls (diagnostic, not a fix) — `homepage.html:280-291`; HDD detection/promotions (`is on HDD, promoting to CACHE_INSTALLER_FILE`) — `game-log.txt:43ff`.

### Inferences
- Worker-idle megaspikes = GPU worker had no commands because the wasm main thread stalled: likely GC/JIT pauses plus pagefile thrash (3.9 GB RAM) plus HDD range-read contention. Mitigations: cut logging (`log=1&mem=1`), reduce memory pressure (close apps), SSD for mirror + pagefile (pagefile already on SSD), keep store warm.
- GPU-wait spikes = iGPU finishing large uploads/draw bursts; cut pixels/texture mips/shadows; `?slots=2` (already used) limits frames in flight.
- `?syncpipelines=1` converts non-blocking compile into blocking frames — do not use for play.
- Alt-tab: no direct evidence of a focus pause > normal frame; the launcher's occlusion flags are the mitigation; keep the game window visible/focused (precaution).

### Gaps
- No instrumentation to attribute "worker idle" to GC vs pagefile vs I/O; no official statement on focus/visibility behavior beyond the 15 ms note.

---

## Q6: Ranked port-level techniques (the actionable answer)

Ordered by expected impact for this machine (i3-7100U/HD620/3.9 GB RAM/HDD). "Applied how" = launcher `.cmd` / URL / local file edit. Items marked SOURCE mean a script/edit beyond existing settings.

### Loading time
1. **Keep the store warm and stable** — same origin (`localhost:8000`), one tab at a time, wait ~10 s after closing the game before relaunching, never use `?nocache`/`?nosw`. (Applied how: launcher discipline; evidenced by 14 s→0 s prefetch, `game-log.txt:625,631`.)
2. **Move the game mirror to the SSD** — `serve_local.py --root` against a copy on C: (file-level; biggest I/O change; store/journal already on SSD in the Chrome profile).
3. **Drop `?log=1&mem=1` for normal play** — the page itself calls logging a thread-time/bandwidth cost (`homepage.html:57-60`); use them only when diagnosing.
4. **Let the boot-set prefetch finish and don't touch the tab** during "Preparing shaders" (~37 s compile-ahead on this machine, `game-log.txt:23518`).
5. **Pre-generate `data/batchc/<sha1>.bin` static gzip batches** (SOURCE/file-level script; removes per-boot gzip-1 + POST; rules in `io_worker.js:202-283`, currently "0 of 32", `game-log.txt:625`).
6. **Optional regeneration only if a future build reads differently**: one `?record=1` session → extract `[bootset] JSON` from `game-log.txt` → `data/bootset[_low].json` (tool `record_bootset.py` unpublished; manual path works, `io_worker.js:164-185`).
7. **Pick mode/map up front** (`?mode=story|sandbox`, `?map=env_test`) so the engine doesn't wait on the 62 % menu choice (`homepage.html:191-192`).

### Average FPS
1. **`?low=1&fps=30&res=960x540&fixed=1`** with shadows off — the port's own 540p preset (`support/index.html:17-21`); low profile zeroes texture/ped/vehicle variety, densities, LODs (`homepage.html:368-369`).
2. **Keep `?res=` even and within 2560x1440 low cap** (`homepage.html:373-383`); 720p only if heading to 60 caps out the framerate anyway on HD620 — prefer 540p/30.
3. **Shadows off** (default in low). Compare `?shadows=1` only if wanted; port measured the shadow cascade pass as a large draw share.
4. **Stay `fps=30` (VSync2)**; `fps=0` for benchmarks only (`homepage.html:406`).
5. **Keep the existing launcher Chrome flags** (occlusion/timer throttling defeaters, `--force-device-scale-factor=1` — the log shows a 1536x864@1.125 screen, so DPI scaling otherwise wastes pixels).
6. **Power plan already high-performance** (`Play-Optimized.cmd`); keep plugged in; close other apps (RAM pressure).
7. **Keep `?slots=2`** (fewer frames in flight, less memory; default is 3, `wgpu_worker.js:728`).
8. **`?cores=2`** (default under low) — fewer threads, less RAM (`homepage.html:370`).

### Stutter / freezes
1. **Warm store + coverage** — first visit to a new area streams via HDD range reads; revisit areas to cache them (`io_worker.js:290`).
2. **Remove `log=1&mem=1`** (fewer main-thread stalls; see Loading #3).
3. **Avoid store-lock sessions** — if you see `prefetch failed: Cannot read properties of null` or a memory-only store line, relaunch after waiting; those sessions re-hit the HDD every boot (`game-log.txt:265-357`).
4. **Reduce RAM pressure** to stop pagefile thrash (3.9 GB RAM; the 7,642 ms idle spike pattern, `game-log.txt:1443`): close Chrome extras, use the launchers' taskkill list.
5. **Do not use diagnostics for play** — `?nohints`, `?nopack`, `?trace`, `?keep`, `?syncpipelines` (blocking compiles), `?nocache` all worsen or do nothing.
6. **If using low=0/Quality**, `-textureQuality=1` caused 500–2000 ms freezes per its own launcher comment — prefer `low=1` or `textureQuality=0`.
7. **Keep the window visible/focused**, maximized, not occluded (launcher flags already pass; `homepage.html:391-395,560-562`).

### Do-not-use / dead ends (sourced)
- `?syncpipelines=1` — blocks frames instead of skipping draws (`wgpu_worker.js:1177-1203`).
- `?record=1` — disables prefetch by design (`io_worker.js:596`).
- `?nogpu`, `?shot`, `?shotrt`, `?dbg`, `?console`, `?trace`, `?limits` — diagnostics/other purposes.
- Hosted extras (`?touch`, enhanced launcher `--engine-ram 4`) are not in this snapshot (`https://gta5-87g.pages.dev/__support/`, `https://github.com/alihammoud21/playgta5-enhanced`).

---

## Source index
- Local: `homepage.html` (= `mirror\playgta5.com\index.html`), `loader.js`, `io_worker.js`, `wgpu_worker.js`, `serve_local.py`, `support\index.html`, `README.md`, `game-log.txt`, `mirror\playgta5.com\data\bootset.json`, `…\bootset_low.json`, `…\manifest.json`, launcher `Play-*.cmd`/`Launch-Local.cmd`.
- Web: https://github.com/alihammoud21/playgta5 · https://github.com/alihammoud21/playgta5-enhanced · https://github.com/shadany7824/playgta5 · https://github.com/SebasKitten/Grand-V · https://gta5-87g.pages.dev/__support/ · https://ai.thesatyajit.com (technical breakdown, 2025) · brief press: todoandroid, vgtimes, gizdev (2025).
