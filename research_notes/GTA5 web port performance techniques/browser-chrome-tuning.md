# Browser-level (Chrome) tuning for a WebGPU + WASM game (GTA V port) on Intel HD 620 / i3-7100U / 4 GB, Chrome 155 stable, Oct 2026

Scope: browser-level techniques only (flags/settings available from a .cmd or chrome://settings, valid in Chrome 140+ / 2025-2026). Machine: HP laptop, Intel Core i3-7100U (2C/4T Kaby Lake), Intel HD Graphics 620 (Gen9.5, shared RAM), ~3.9 GB usable RAM, Windows, Chrome 155 stable assumed. Already applied by the user: `--start-maximized --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --disable-features=CalculateNativeWinOcclusion --force-device-scale-factor=1 --enable-gpu-rasterization`, Windows GPU preference = High performance. The port's `--force-webgpu-compat` fallback was already measured 2.2x slower — excluded below.
Two symptoms to separate: (a) low average FPS = GPU-bound rendering, (b) multi-hundred-ms freezes = almost always shader/pipeline compilation, tab discard, GPU-process restart, process QoS throttling, or memory pressure/swap — the techniques below are grouped accordingly.

## KQ1 — Ranked list of current browser-level techniques (exact flag/setting, what it changes, expected impact, risk, verification)

### Takeaway
Only a handful of the classic "Chrome gaming flags" are still real and relevant in Chrome 140+: verify the WebGPU backend/driver via chrome://gpu, fix process-level interference (EcoQoS/efficiency mode), control Memory/Energy Saver settings, and isolate the game in a clean profile/window. Backend-switching flags for WebGPU (`--use-webgpu-adapter=swiftshader|compat`) and power-preference flags are no-ops or slower on this single-GPU machine. `--disable-frame-rate-limit`/`--disable-gpu-vsync` are diagnostics, not daily-use settings; `--disable-gpu-driver-bug-workarounds` exists but is a risky test-only experiment.

### Cited Findings

**Tier 1 — Safe, do first (highest expected value for this scenario)**

1. **Verify backend/device with chrome://gpu and keep the Intel driver current** (prerequisite for everything else).
   - chrome://gpu shows `WebGPU: Hardware accelerated` under "Graphics Feature Status", a "Dawn Info" section (e.g. `D3D12 backend - <adapter name>`, `[WebGPU Status] Available`, `[Adapter Supported Features]`), and driver capability lines (`Driver D3D12 feature level: D3D 12.1`, `Driver Vulkan API version`, `2D graphics backend: Skia/<major>`), plus the effective flag list under "Command Line" — [Chromium issue 438515329 (chrome://gpu contents)](https://issues.chromium.org/issues/438515329).
   - Broken WebGPU on an Intel iGPU (HD 630) was traced to an old Intel driver (22.20.16.4836) failing `d3d_image_utils.cc: Failed to create shared texture memory`; Intel engineers said to update to driver 31.0.101.2128+ — [Chromium issue 355006335](https://issues.chromium.org/issues/355006335).
   - Dawn (Chrome's WebGPU implementation) requires D3D12 feature level 11.1+ on Windows; D3D12 is its "preferred target API when available" (Vulkan on Windows is only "best effort") — [Dawn platform support doc](https://github.com/google/dawn/blob/main/docs/support.md).
   - Chrome's Dawn info collection is deliberately delayed 120 s after startup; `--collect-dawn-info-eagerly` starts it immediately, and `--no-delay-for-dx12-vulkan-info-collection` does the same for the separate DX12/Vulkan info-collection GPU process — [gpu_switches.cc (current main)](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
2. **Settings: keep Energy Saver out of the session; Memory Saver cannot discard the active game tab but can be neutralized per-site.**
   - Energy Saver "reduces the display refresh rate, affecting scrolling and animation fidelity and video frame rates"; it is meant for unplugged/low-battery states — [Chrome for Developers blog: Memory and Energy Saver](https://developer.chrome.com/blog/memory-and-energy-saver-mode). If it engages while gaming, rAF/animation rate drops.
   - Memory Saver only proactively discards tabs "unused in the background for some time"; users can exempt specific sites (per-site setting), and can test discard behavior via chrome://discards ("Urgent Discard") — [same blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode). Discard ordering puts the selected tab last, but the game tab being visible is not a hard guarantee under urgent memory pressure — [Chromium docs: Tab Discarding and Reloading](https://www.chromium.org/chromium-os/chromiumos-design-docs/tab-discarding-and-reloading). Memory Saver's aggressiveness is also policy-controllable (`MemorySaverModeSavings` 0/1/2 with `HighEfficiencyModeEnabled`) — [Chromium policy template](https://chromium.googlesource.com/chromium/src/+/HEAD/components/policy/resources/templates/policy_definitions/Miscellaneous/MemorySaverModeSavings.yaml).
3. **`--disable-features=UseEcoQoSForBackgroundProcess` (Windows efficiency mode / EcoQoS workaround).**
   - To free the foreground tab from Windows "Efficiency Mode" (EcoQoS, which caps a process at low priority/clock), Chromium added this flag; it was removed in M132, **restored in M139** ("workaround should be working again in stable as of August 5th [2025]") — [Chromium issue 406667206, comment](https://issues.chromium.org/issues/406667206) and [Chromium issue 40914659](https://issues.chromium.org/issues/40914659). Chrome itself applies EcoQoS to background processes; the flag matters when Chrome (or Windows 11's own policy) puts *game-adjacent* processes (renderer/GPU) into efficiency mode — [Chromium issue 40914659](https://issues.chromium.org/issues/40914659).
   - Verify before using: Task Manager → the chrome.exe processes tied to the game window — if they show the efficiency-mode leaf icon, this flag is worth testing; effect is situational, not universal.
4. **Isolate the game: dedicated profile + no extensions + app window.** `--user-data-dir=<fresh dir>`, `--disable-extensions`, `--app=http://localhost:8000` (app mode = chromeless window, one tab, no tab UI). No benchmark evidence was found for FPS gain (see Gaps), but on 4 GB/2C4T, fewer renderer/extension processes reduce RAM and CPU contention — this is an infrastructure reduction, expect small-to-moderate FPS/RAM relief, low risk, trivially verifiable with Task Manager + FPS counter. Rationale source: extensions/tabs each cost a process and memory; Chrome's own tab-discard rollout and task-manager docs treat per-tab/extension memory as the main lever — [Chrome for Developers: tab discarding](https://developer.chrome.com/blog/tab-discarding).
5. **Stutter triage via shader/pipeline caching (do not clear caches; A/B to attribute the freezes).**
   - Chrome's GPU shader disk cache is on by default since M28 (`--disable-gpu-shader-disk-cache` exists to turn it off, default cache size 6 MB, overridable with `--gpu-disk-cache-size-kb`) — [Chromium issue 41017839](https://issues.chromium.org/issues/41017839), [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
   - WebGPU/Dawn pipeline caching (BlobCache) is on disk and keyed to Chrome+driver version; multi-hundred-ms first-time hits are typically shader compilation, and WebGPU apps "might create many pipelines… ballooning" their caches — [Chromium issue 370343334 (Dawn/Vulkan pipeline caching)](https://issues.chromium.org/issues/370343334).
   - Practical use: after a stutter zone has been played once, re-visiting it should be much smoother if the cause is pipeline compilation (cache hit). `--disable-gpu-shader-disk-cache` run is the control condition for this experiment. `--gpu-disk-cache-size-kb=` increase is plausible but not verified for WebGPU specifically (mark uncertain).
6. **`--disable-gpu-process-crash-limit` (test-purpose flag; use only if chrome://gpu/Event logs show repeated GPU-process crashes).** "Disable the limit on the number of times the GPU process may be restarted. This switch is intended only for tests." Default behavior blocks/degrades GPU after repeated crashes (a plausible cause of sudden sustained slowdowns or freezes during long play sessions on an old driver) — [content_switches.cc (current main)](https://github.com/chromium/chromium/blob/main/content/public/common/content_switches.cc). Risk: turns a crash-loop into an endless crash-loop instead of graceful degradation.
7. **Skia Graphite: check what you're on, A/B if the UI/compositing is janky.**
   - On Windows, Chrome is rolling out Graphite (rendering through Dawn's D3D11 backend by default: `Skia Backend: GraphiteDawnD3D11` visible in chrome://gpu); a Chrome 151-stable user saw tab-close UI hitches fixed reproducibly by `chrome://flags/#skia-graphite` → Disabled — [Chromium issue 550420344](https://issues.chromium.org/issues/550420344).
   - Switches (current main): `--enable-skia-graphite` / `--disable-skia-graphite`, `--skia-graphite-dawn-backend=d3d11|d3d12|vulkan|opengles|metal|swiftshader`, `--enable/--disable-skia-graphite-precompilation` — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
   - Rollout status context (secondary source, treat as indicator): Graphite default on Mac by Dec 2025, "progressing" on Windows through Dawn D3D11; a Graphite use-after-free (CVE-2026-6304) was fixed in Chrome 147.0.7727.101/102 on 15 Apr 2026 — [Chromium patterns: Skia Graphite transition](https://chromium.bartleyeditions.com/skia-graphite); primary launch announcement with ~15% MotionMark 1.3 gain (on Apple Silicon) and Dawn as the abstraction layer — [blog.google/Chromium 8 Jul 2025](https://blog.google/chromium/introducing-skia-graphite-chromes). Tracker "Ship Skia Graphite everywhere" incl. D3D11 Intel UHD770 optimization work — [Chromium issue 40280551](https://issues.chromium.org/issues/40280551).
   - For a fullscreen WebGPU game the affected surfaces are browser UI/canvas compositing; impact on the game viewport is unverified (A/B it).

**Tier 2 — Diagnostics only (temporarily, from a separate test .cmd; revert before daily play)**

8. **`--disable-frame-rate-limit`** — "Disables begin frame limiting in both cc scheduler and display scheduler. Also implies --disable-gpu-vsync" — [components/viz/common/switches.cc](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/viz/common/switches.cc). Use to measure the true GPU ceiling (is 60 fps actually reachable?) and to separate vsync-pacing artifacts from GPU-bound slowness. Side effects: tearing, no frame pacing, heat/power — [Chromium issue 41356819 (the two vsync flags explained)](https://issues.chromium.org/issues/41356819).
9. **`--disable-gpu-vsync`** — "Stop the GPU from synchronizing presentation with vblank" — [ui/gl/gl_switches.cc (current main)](https://chromium.googlesource.com/chromium/src/+/main/ui/gl/gl_switches.cc). Same diagnostic class as above; on Windows, presentation without vsync was specifically patched to not wait for vsync intervals when these switches are used — [Chromium issue 343248823](https://issues.chromium.org/issues/343248823).
10. **`--enable-webgpu-developer-features`** (chrome://flags/#enable-webgpu-developer-features) — no perf change by itself; it exposes non-standard runtime verification info: `GPUAdapterInfo.backend` (`D3D12`, `vulkan`, …) and `type` (`integrated GPU`/`discrete GPU`), `powerPreference` string, and disables timestamp-query quantization (helpful for profiling frame times) — [Chrome for Developers: WebGPU developer features](https://developer.chrome.com/docs/web-platform/webgpu/developer-features), [What's New in WebGPU Chrome 120](https://developer.chrome.com/blog/new-in-webgpu-120), [Chrome 137](https://developer.chrome.com/blog/new-in-webgpu-137). `--enable-unsafe-webgpu` is only needed for experimental features (e.g. timestamp-query), not for standard WebGPU on stable — [same docs](https://developer.chrome.com/docs/web-platform/webgpu/developer-features).

**Tier 3 — Risky / experimental (only as A/B experiments with rollback)**

11. **`--disable-gpu-driver-bug-workarounds`** — "Disable workarounds for various GPU driver bugs" — [ui/gl/gl_switches.cc](https://chromium.googlesource.com/chromium/src/+/main/ui/gl/gl_switches.cc). These workarounds exist precisely because Intel Gen9-class drivers misbehave (Chromium has Gen9.5/Gen11-specific D3D12 workarounds — [Chromium issue 438515329](https://issues.chromium.org/issues/438515329)); disabling them can crash, hang, or corrupt output. Risk: high; keep only if an A/B shows a repeatable win and the machine stays stable.
12. **`--no-delay-for-dx12-vulkan-info-collection` / `--disable-gpu-process-for-dx12-info-collection`** — Chrome spawns a non-sandboxed GPU process 120 s after startup for DX12/Vulkan info collection — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc). On a 4 GB/2-core machine this background process can itself cause a hiccup ~2 min in; disabling/delaying it is low-value but harmless (test-oriented switches). Unverified impact — treat as minor.
13. **`--gpu-no-context-lost`** — "Inform Chrome that a GPU context will not be lost in power saving mode, screen saving mode, etc." — [ui/gl/gl_switches.cc](https://chromium.googlesource.com/chromium/src/+/main/ui/gl/gl_switches.cc). Only relevant if freezes correlate with display sleep/screensaver; otherwise no-op. Unverified.
14. **`--gpu-watchdog-timeout-seconds`** — overrides the GPU watchdog timeout — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc). Possible use: under extreme stall on this iGPU, the watchdog can kill the GPU process (manifesting as a freeze + recovery). Test-oriented; only touch if chrome://gpu/Event log shows watchdog terminations. Unverified impact.

**Not worth using (for this machine), with reasons**

15. `--use-webgpu-adapter=swiftshader|compat` — the only documented values besides `default`; `swiftshader` is CPU software rendering and `compat` is the D3D11-class compat mode the user already measured 2.2x slower — [Chromium issue 40057808](https://issues.chromium.org/issues/40057808), [Blink FlagSpecificConfig](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/web_tests/FlagSpecificConfig).
16. `--force-high-performance-gpu` and `--use-webgpu-power-preference=default-high-performance` — exist (defined in [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc); power-preference values per [FlagSpecificConfig](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/web_tests/FlagSpecificConfig)) but on Windows Chrome uses the same GPU adapter as other Chrome workloads and powerPreference/dual-GPU selection is not honored (defaults to integrated GPU on laptops) — [Chromium issue 393263507](https://issues.chromium.org/issues/393263507), [Blink gpu.cc comment](https://chromium.googlesource.com/chromium/src/+/master/third_party/blink/renderer/modules/webgpu/gpu.cc). This machine has a single GPU (HD 620), so both are no-ops.
17. `--ignore-gpu-blocklist` — exists ("Ignores GPU blocklist", [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc)). WebGPU is already hardware-accelerated on HD 620 (it meets Dawn's D3D12 FL 11.1 requirement); this flag would unblock *other* features Chrome deliberately disabled for stability. Not recommended; unverified benefit.
18. `--enable-features=Vulkan` — for WebGPU on Windows this is **not** a supported backend selector: Dawn's Vulkan-on-Windows support is "best effort", D3D12 is the preferred/default target, and no current official flag was found that forces Dawn's Vulkan backend on Windows official builds (the one WebGPU adapter-selection flag only accepts default/compat/swiftshader — see #15). See Gaps.

Baseline flags the user already runs are still current practice (`--disable-features=CalculateNativeWinOcclusion`, `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`, `--disable-background-timer-throttling` — semantics documented in chrome-launcher's flag list: [Chrome flags for tooling](https://github.com/GoogleChrome/chrome-launcher/blob/main/docs/chrome-flags-for-tools.md)); `--enable-gpu-rasterization` maps to the existing switch ("Allow heuristics to determine when a layer tile should be drawn with the Skia GPU backend", [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc)).

### Inferences
- On a GPU-bound WebGPU game, most FPS is algorithmic/resolution bound (port side), so browser techniques are expected to buy small percentage gains at best; the bigger browser-level wins here are stutter-reduction (pipeline cache warmup, no discards, no efficiency-mode throttling, crash resistance) and RAM headroom (fewer processes) on a 3.9 GB machine where Windows+Chrome overhead otherwise forces paging.
- The ranked order above optimizes for "low risk × plausible impact": verification (#1), settings (#2), QoS (#3), isolation (#4), stutter attribution (#5). Graphite (#7) is the only rendering-path change with plausible compositing impact, but its documented regressions are UI-side, so A/B it rather than adopt blindly.
- Multi-hundred-ms freezes that survive a warm cache and don't coincide with discards/crashes should be treated as port-side (asset streaming, WASM GC/JIT, worker stalls) — browser-level levers will not fix them.

### Gaps
- No benchmark found measuring FPS gain from dedicated profile/no-extensions/app-mode on 4 GB machines (Tier 1 #4 rests on memory/process-count reasoning, not a measured FPS delta).
- No data found on whether Graphite improves or degrades a fullscreen WebGPU-canvas game on Intel Gen9 specifically; only UI-side regressions/optimizations were found (D3D11 Intel UHD770 work is the closest analog — [Chromium issue 40280551](https://issues.chromium.org/issues/40280551)).
- No current documented flag exists to force Dawn's Vulkan backend (or D3D11 backend) for WebGPU on Windows official builds; `--enable-features=Vulkan`'s interaction with WebGPU-on-Windows in Chrome 140+ is unverified in official sources. Treat any claim otherwise as speculative.
- CanvasOopRasterization (`--enable-features=CanvasOopRasterization`) could not be verified as still-relevant in Chrome 140+ source or docs from the sources reviewed (it predates this search window); no current evidence it is a usable lever — consider it a no-op/uncertain until checked against chrome://flags on the actual install.

## KQ2 — WebGPU backend/adapter selection on Windows (Dawn D3D12 vs D3D11 vs Vulkan; unsafe-webgpu; driver-bug workarounds)

### Takeaway
On Windows, Chrome's WebGPU runs on Dawn's D3D12 backend by default and this is the only practical hardware path; there is no supported flag to switch an official Windows build to Dawn-Vulkan, and the adapter-selection flag only offers default/compat/swiftshader. `--enable-unsafe-webgpu` is no longer needed for standard WebGPU (shipped in Chrome 113). `--disable-gpu-driver-bug-workarounds` still exists but is a high-risk, test-only experiment.

### Cited Findings
- WebGPU shipped by default in Chrome 113 on Windows "devices with Direct3D 12 support"; the standard backend on Windows is D3D12 — [Chrome for Developers: WebGPU overview](https://developer.chrome.com/docs/web-platform/webgpu/overview), [Chrome ships WebGPU](https://developer.chrome.com/blog/webgpu-release).
- Dawn: D3D12 is "the preferred target API when available"; it needs feature level 11.1; Vulkan on Windows is supported "as best effort"; a D3D11 backend "is available but not considered ready for production uses yet" — [Dawn platform support doc](https://github.com/google/dawn/blob/main/docs/support.md).
- `--use-webgpu-adapter` may be "compat" or "swiftshader" to force compat/software adapters; "default" uses normal behavior — [Chromium issue 40057808](https://issues.chromium.org/issues/40057808); `--use-webgpu-power-preference` accepts default-low-power / default-high-performance per [Blink FlagSpecificConfig](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/web_tests/FlagSpecificConfig).
- Chrome on Windows does not honor powerPreference for adapter choice and defaults to the integrated GPU (single shared adapter for all Chrome workloads) — [Chromium issue 393263507](https://issues.chromium.org/issues/393263507), [Chromium issue 40268366 (powerPreference ignored)](https://issues.chromium.org/issues/40268366), [Blink gpu.cc TODO comment](https://chromium.googlesource.com/chromium/src/+/master/third_party/blink/renderer/modules/webgpu/gpu.cc).
- Current switch inventory (`gpu_switches.cc`, main branch, Oct 2026): `enable-unsafe-webgpu`, `enable-webgpu-developer-features`, `force-high-performance-gpu`, `use-webgpu-adapter`, `use-webgpu-power-preference`, `force-webgpu-compat`, `enable/disable-dawn-features`, `enable-dawn-backend-validation`, `collect-dawn-info-eagerly`, graphite switches — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
- `--disable-gpu-driver-bug-workarounds` ("Disable workarounds for various GPU driver bugs") is still defined in current main — [ui/gl/gl_switches.cc](https://chromium.googlesource.com/chromium/src/+/main/ui/gl/gl_switches.cc). Chromium maintains a per-GPU workaround list (`gpu_driver_bug_list.json` / `gpu/config/`) — [gpu_driver_bug_workarounds.h](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_driver_bug_workarounds.h). A Gen9.5/Gen11-specific Dawn toggle is enabled by default on D3D12 "due to driver issues" — [Chromium issue 438515329](https://issues.chromium.org/issues/438515329).
- `--enable-unsafe-webgpu` still exists but its documented purpose is enabling WebGPU where not yet launched plus experimental features; stable Windows already has WebGPU — [WebGPU developer features](https://developer.chrome.com/docs/web-platform/webgpu/developer-features), [Blink FlagSpecificConfig comment](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/web_tests/FlagSpecificConfig).
- Dawn shader toggles usable via `--enable-dawn-features=` / `--disable-dawn-features=` (e.g. Chromium's own WebGPU tests use `--disable-dawn-features=use_dxc` to switch the D3D shader compiler path) — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc), [FlagSpecificConfig](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/web_tests/FlagSpecificConfig). No evidence found that any Dawn toggle improves performance on Intel Gen9 — treat `use_dxc` switching as untested (see Gaps).

### Inferences
- On this machine (HD 620 only, D3D12-capable at FL 12.1 per the driver, D3D12 is Dawn's preferred path), there is nothing to "select" — the default is already the best-supported backend; the compat mode (D3D11-class) was measured slower by the user, consistent with it being a compatibility path, not a performance path.
- `--disable-gpu-driver-bug-workarounds` could in principle re-enable faster codepaths that Chromium disabled for Gen9-era drivers, but given the same driver generation ships the known D3D12 quirks referenced in Chromium's own workarounds, the probability of instability is high; if tested, do it only in an A/B cmd with a quick rollback and watch for corruption/crashes.

### Gaps
- No official statement found on whether `--enable-features=Vulkan` affects Dawn/WebGPU on Windows in Chrome 140+; Dawn's own docs describe Vulkan-on-Windows as best effort, and no WebGPU backend-forcing flag surfaced.
- No data on performance of `--disable-dawn-features=use_dxc` (FXC vs DXC shader compilation) on Intel Gen9 for either FPS or shader-compile stutter.

## KQ3 — Skia Graphite, canvas/compositing, and rAF/frame-limit techniques

### Takeaway
Skia Graphite is now the relevant compositing/rasterization variable on Windows (rolled out via Dawn's D3D11 backend; `Skia Backend: GraphiteDawnD3D11` in chrome://gpu) and is toggleable via chrome://flags/#skia-graphite — worth an A/B, with known UI-jank regressions to watch. rAF is display-driven; the only browser levers are the frame-limit/vsync diagnostic switches and keeping Energy Saver off.

### Cited Findings
- Graphite launch/architecture: uses Dawn as the abstraction layer, multithreaded, precompiles pipelines; ~15% MotionMark 1.3 improvement on Apple Silicon M3 at launch — [blog.google/chromium, 8 Jul 2025](https://blog.google/chromium/introducing-skia-graphite-chromes).
- Windows status: Chrome 151 stable user had `Skia Backend: GraphiteDawnD3D11` active by default; disabling via chrome://flags/#skia-graphite removed a reproducible tab-close hitch; flag state persists in Local State (`skia-graphite@5`) — [Chromium issue 550420344](https://issues.chromium.org/issues/550420344). Related scrolling/window-drag lag toggled by the same flag — [Chromium issue 325633289](https://issues.chromium.org/issues/325633289).
- Current switches: `--enable-skia-graphite`, `--disable-skia-graphite`, `--skia-graphite-dawn-backend=d3d11|d3d12|metal|opengles|swiftshader|vulkan`, `--skia-graphite-vulkan-backend`, `--enable/--disable-skia-graphite-precompilation` — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
- `--disable-frame-rate-limit` disables begin-frame limiting in both the compositor scheduler and display scheduler and implies `--disable-gpu-vsync` — [components/viz/common/switches.cc](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/viz/common/switches.cc); the two flags' distinct semantics are described in [Chromium issue 41356819](https://issues.chromium.org/issues/41356819); Windows presentation was explicitly fixed to present immediately when these are set — [Chromium issue 343248823](https://issues.chromium.org/issues/343248823).
- Energy Saver reduces display refresh rate, influencing rAF animation rate — [Memory and Energy Saver blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode).
- Chrome 140-156 "What's New in WebGPU" entries are Dawn/tooling updates (e.g. Tint IR completed in 141, buffer upload optimizations, shader compilation improvements) with no Gen9-iGPU-specific performance items listed — [What's New in WebGPU index/Chrome 136 page](https://developer.chrome.com/blog/new-in-webgpu-136).

### Inferences
- For a fullscreen WebGPU canvas, the per-frame cost the browser adds is compositing/present; if the user's stutter is UI-only (tab strip, window drag), Graphite toggling matters; if stutters are in the game viewport, Graphite is unlikely to be the lever.
- `--disable-frame-rate-limit` is the cleanest way to answer "is this GPU-bound or pacing-bound": if uncapped FPS is barely above 60, the GPU (HD 620) is the wall and browser tweaks cannot raise average FPS materially.

### Gaps
- No benchmark found for Graphite vs Ganesh specifically on WebGPU canvas content or on Intel Gen9/dGPU-less laptops.
- No verified status for `CanvasOopRasterization` flag in Chrome 140+ (see KQ1 gaps).

## KQ4 — Dedicated Chrome window/profile, extensions, app/kiosk mode: does scheduling/CPU contention measurably change?

### Takeaway
No direct experimental evidence (benchmarks) was found showing FPS changes from `--user-data-dir`/`--disable-extensions`/`--app=` alone; the defensible benefits are memory/process-count reduction on a 3.9 GB machine and elimination of extension background activity — treat as contention reduction, not measured FPS improvement.

### Cited Findings
- Chrome keeps per-tab/pages and extensions in separate processes and Memory Saver was introduced because background content consumes real memory; the per-site exemption exists because discarding reloads pages — [Memory and Energy Saver blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode), [Chrome for Developers: tab discarding](https://developer.chrome.com/blog/tab-discarding).
- `--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows` (already used by the user) exist precisely because Chrome otherwise treats occluded/hidden windows as background and throttles them; documented in [chrome-launcher flags for tools](https://github.com/GoogleChrome/chrome-launcher/blob/main/docs/chrome-flags-for-tools.md).
- Chrome's own guidance for memory pressure: close tabs/uninstall heavy extensions; Task Manager (Shift+Esc) shows per-process usage — [Chromium: Tab discarding and reloading](https://www.chromium.org/chromium-os/chromiumos-design-docs/tab-discarding-and-reloading). (Even though written for ChromeOS, the ranking logic is the shipped behavior.)
- App mode (`--app=`) behavior is a chromeless window for a single URL — general Chromium practice; no perf claim found. (Not separately citable from reviewed sources; see Gaps.)

### Inferences
- On 2 cores/4 threads with 3.9 GB RAM, removing extension processes and browser-UI/tab overhead reduces both paging risk and CPU scheduling contention with the game's renderer/GPU processes; the expected FPS effect is small but the freeze-risk effect (memory pressure → discard/paging) is plausibly real.
- Fresh `--user-data-dir` also guarantees a clean profile (no coupons, no third-party extension timers, no history sync churn), which is the main controllable variable — low cost, zero risk.

### Gaps
- No benchmark (e.g. FPS before/after app-mode + clean profile) found for this or similar hardware; evidence is indirect (process/memory model, not measured deltas).

## KQ5 — Chrome memory management on 4 GB machines (Memory Saver / efficiency features; can the game tab be throttled or discarded?)

### Takeaway
Memory Saver discards only background-unused tabs by design, so it should not touch the active game tab in normal play; the settings-level defenses are: per-site "keep active" (or Memory Saver off), and `chrome://discards` to confirm the tab isn't marked discardable. Energy Saver is the more dangerous one for a game (refresh-rate reduction) and should be off or "only on battery".

### Cited Findings
- "When Memory Saver mode is enabled, Chrome will proactively discard tabs that have been unused in the background for some time… Users can instruct Chrome not to discard tabs for specific sites"; discard testing via `chrome://discards` → Urgent Discard; detection after the fact via `document.wasDiscarded` — [Memory and Energy Saver blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode).
- Energy Saver "reduces the display refresh rate, affecting scrolling and animation fidelity and video frame rates" — [same blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode).
- Discard order (worst-to-keep first): internal pages → long-ago-selected → recent → audio-playing → apps-in-window → pinned → **selected tab last**; memory pressure is the trigger for non-Memory-Saver discards — [Tab Discarding and Reloading (Chromium)](https://www.chromium.org/chromium-os/chromiumos-design-docs/tab-discarding-and-reloading).
- Memory Saver aggressiveness levels (moderate/balanced/maximum) and `HighEfficiencyModeEnabled` policy semantics — [MemorySaverModeSavings policy template](https://chromium.googlesource.com/chromium/src/+/HEAD/components/policy/resources/templates/policy_definitions/Miscellaneous/MemorySaverModeSavings.yaml).
- Independent confirmation that discards can occur even with Memory Saver off under memory pressure (ChromeOS case; platform policy differs on Windows but the "urgent discard" path exists) — [Chromium issue 463748015](https://issues.chromium.org/issues/463748015).

### Inferences
- With the game visible/fullscreen and a fresh profile, Memory Saver discard of the game tab is very unlikely; the realistic 4 GB risks are (a) general paging (Windows-managed) and (b) urgent discard under critical memory pressure — mitigated by keeping no other tabs and nothing else running.
- The per-site "always keep active" exemption is cheap insurance for the localhost origin; keep Energy Saver disabled entirely if the laptop is normally used plugged in for gaming.
- How to verify: `chrome://discards` — the game tab's row shows discardability/"Is discardable: false"; if it's ever discarded, the page reloads mid-game (visible as a full restart of the port, `document.wasDiscarded === true` after reload).

### Gaps
- No data found on how often the "urgent discard" path triggers on Windows for a *visible* fullscreen tab in Chrome 140+; the rating in chrome://discards is the closest observable proxy.

## KQ6 — GPU/renderer process priorities and iGPU contention with the compositor/DWM

### Takeaway
The only real browser-level process-priority lever on Windows is the EcoQoS/efficiency-mode workaround (`--disable-features=UseEcoQoSForBackgroundProcess`, restored in M139, valid in 140+); there is no Chrome flag to raise the GPU process's or renderer's OS priority, and GPU-process robustness flags (crash limit, watchdog timeout) exist but are test-oriented.

### Cited Findings
- Windows 11 pushes chrome.exe processes into "Efficiency Mode" (EcoQoS / BasePriority 4); the Chromium workaround flag was removed in M132 and restored in M139 (stable from 5 Aug 2025); Chrome's own guidance in the thread: launch via cmd line with the flag; verify with Task Manager and via chrome://version that the flag is in the command line; some reports say Edge/Windows-forced efficiency mode can override it anyway — [Chromium issue 406667206](https://issues.chromium.org/issues/406667206), [Chromium issue 40914659](https://issues.chromium.org/issues/40914659), [MS Q&A thread](https://learn.microsoft.com/en-us/answers/questions/3894586/disabling-efficiency-mode-for-chrome-does-not-work).
- `--disable-gpu-process-crash-limit` ("Disable the limit on the number of times the GPU process may be restarted. This switch is intended only for tests.") — [content_switches.cc](https://github.com/chromium/chromium/blob/main/content/public/common/content_switches.cc).
- `--gpu-watchdog-timeout-seconds` (override GPU watchdog timeout) — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
- The GPU process handles WebGPU command buffers in Chrome (WebGPUDecoderImpl is "an extension of the Chrome GPU Command Buffer abstraction… used for transferring Dawn Wire data between the renderer and GPU processes") — [Chromium WebGPU technical report](https://chromium.googlesource.com/chromium/src/+/main/docs/security/research/graphics/webgpu_technical_report.md), i.e. heavy WebGPU games share one GPU process with all Chrome compositing — a single contention point on a 2-core machine.

### Inferences
- Because WebGPU work and the compositor both live in the GPU process ([technical report](https://chromium.googlesource.com/chromium/src/+/main/docs/security/research/graphics/webgpu_technical_report.md)) and DWM composits the window (Windows-level), the practical browser-side mitigations are the ones in this document: keep other Chrome activity to zero, keep the game tab foreground (occlusion/backgrounding flags already set), and prevent OS-level throttling of the game's processes (EcoQoS flag).
- There is no Chromium switch to set process priority classes (none exists in current switch inventories reviewed); any "priority" tweak would be external process tools (out of scope for this browser-level research).

### Gaps
- No measurements found for the actual CPU-time impact of Chrome's background EcoQoS on a 2C/4T Intel machine while a WebGPU game runs in the foreground.
- No official mechanism found to give the GPU process higher scheduling priority; treat as non-existent at browser level.

## KQ7 — chrome://gpu (and related) verification: what to check, and expected log entries

### Takeaway
chrome://gpu is the authoritative check: "Graphics Feature Status" must say `WebGPU: Hardware accelerated`; the "Dawn Info" section must show the `D3D12 backend` on the Intel adapter with `[WebGPU Status] Available`; "Command Line" must list your flags; driver lines (`Driver D3D12 feature level`) confirm the HD 620 meets Dawn's requirements. Dawn info populates after ~120 s by default (or immediately with `--collect-dawn-info-eagerly`).

### Cited Findings
- Documented chrome://gpu content from a real report: "Graphics Feature Status" lines including `WebGPU: Hardware accelerated`; "2D graphics backend: Skia/<major>"; "Dawn Info" section showing e.g. `D3D12 backend - <GPU>` and per-backend `[WebGPU Status]`, `[Adapter Supported Features]`; "Command Line" echo of active switches; driver lines `Driver D3D12 feature level: D3D 12.1`, `Driver Vulkan API version`, and Skia/GPU identifiers — [Chromium issue 438515329](https://issues.chromium.org/issues/438515329); a second report confirms `Skia Backend: GraphiteDawnD3D11` appears in chrome://gpu on Windows Graphite — [Chromium issue 550420344](https://issues.chromium.org/issues/550420344).
- Dawn info collection is delayed 120 s by default; `--collect-dawn-info-eagerly` (and `--no-delay-for-dx12-vulkan-info-collection` for the DX12/Vulkan collector) remove the delay — [gpu_switches.cc](https://github.com/chromium/chromium/blob/main/gpu/config/gpu_switches.cc).
- Runtime verification inside the page: with `--enable-webgpu-developer-features`, `adapterInfo.backend` reports `D3D12`/`vulkan`/etc. and `type` reports `integrated GPU`/`discrete GPU`/`CPU`/`unknown`; https://webgpureport.org surfaces the same — [What's New in WebGPU Chrome 120](https://developer.chrome.com/blog/new-in-webgpu-120), [WebGPU developer features](https://developer.chrome.com/docs/web-platform/webgpu/developer-features).
- If the wrong thing is happening: a real-world iGPU failure mode on old Intel drivers was `Failed to create shared texture memory` (d3d_image_utils.cc) fixed by updating the Intel driver — [Chromium issue 355006335](https://issues.chromium.org/issues/355006335).
- Tab-state verification: chrome://discards shows "Is discardable" status per tab and offers Urgent Discard to test behavior — [Memory and Energy Saver blog](https://developer.chrome.com/blog/memory-and-energy-saver-mode).

### Inferences
- Recommended standing checks for this machine: (1) chrome://gpu right after a game session — WebGPU still "Hardware accelerated" (detects post-crash downgrades), (2) "Dawn Info" backend = D3D12 on Intel HD 620, (3) "Skia Backend" = GraphiteDawnD3D11 (note it, then A/B if jank), (4) chrome://discards during play — game tab not discardable, (5) Task Manager — game window's processes not in efficiency mode.
- Because chrome://gpu's Dawn section can be empty for the first ~2 minutes after launch, use `--collect-dawn-info-eagerly` in the diagnostic .cmd to avoid false "WebGPU not working" conclusions.

### Gaps
- No dedicated chrome://webgpu-internals page was confirmed to exist in reviewed sources; verification is via chrome://gpu (Dawn Info) plus in-page adapterInfo — treat "chrome://webgpu" as unverified/unavailable.

## KQ8 — Browser choice in 2026: Chrome vs Edge vs Firefox for WebGPU on this hardware

### Takeaway
Chrome remains the safest host: WebGPU has the longest stable history there, and Edge runs the same Chromium engine/Dawn with no documented Windows-WebGPU divergence found. Firefox 141 (July 2025) shipped WebGPU on Windows, but Mozilla's own release notes list known performance bottlenecks (unbuffered IPC, interval timers, missing importExternalTexture) — evidence points to lower performance, not higher, on weak hardware; no Firefox-on-Intel-iGPU benchmark was found.

### Cited Findings
- Chrome has had WebGPU on Windows D3D12 since Chrome 113 (2023); Firefox 141 shipped WebGPU on Windows in July 2025 (macOS later, per Firefox 145/147); all major browsers support WebGPU by Dec 2025/Jan 2026 — [Chrome for Developers overview](https://developer.chrome.com/docs/web-platform/webgpu/overview), [PCWorld (Firefox 141)](https://www.pcworld.com/article/2851602/firefox-is-finally-getting-webgpu-but-only-on-windows.html), [TechSpot (all browsers)](https://www.techspot.com/news/110456-webgpu-now-brings-desktop-quality-graphics-all-major.html).
- Mozilla's shipping post (as summarized) lists current Firefox WebGPU caveats: "performance bottlenecks due to unbuffered inter-process communication", "latency issues from relying on interval timers", "missing importExternalTexture" — [Linuxiac summary of the Mozilla Gfx blog](https://linuxiac.com/webgpu-lands-in-firefox-141-on-windows-eyes-linux-and-macos-next/), [GIGAZINE (Firefox 141 release)](https://gigazine.net/gsc_news/en/20250723-firefox-141); original: [Mozilla Gfx blog](https://mozillagfx.wordpress.com/2025/07/15/shipping-webgpu-on-windows-in-firefox-141/). Firefox uses wgpu (Rust), not Dawn — [Linuxiac](https://linuxiac.com/webgpu-lands-in-firefox-141-on-windows-eyes-linux-and-macos-next/).
- Edge is Chromium-based and shares engine defaults; the only engine-relevant difference surfaced in research was an Android-era trace difference (Edge lacked Vulkan work that Chrome had on Pixel 7 Pro, where disabling Vulkan eliminated stutter) — [Chromium issue 40274851](https://issues.chromium.org/issues/40274851). No Windows/Intel-specific Edge-WebGPU difference was found.
- Anecdotal community claim of "all around awful" Firefox WebGL/WebGPU performance (HN thread) — [Hacker News](https://news.ycombinator.com/item?id=37667257); weak source, listed only as weak corroboration.

### Inferences
- Switching to Edge is not expected to change anything structurally (same Dawn, same GPU process model); it is not a recommended experiment for this machine unless a specific Edge-only setting (e.g. Edge's own GPU/enhancement settings) is suspected.
- Firefox could be tested as a fallback (different engine, wgpu), but the shipping caveats plus the absence of any iGPU benchmark make "likely slower" the base assumption; it is not evidence-based to recommend it for more FPS.

### Gaps
- No head-to-head WebGPU benchmark (Chrome vs Edge vs Firefox) found for Intel HD 620-class hardware or any 4 GB iGPU laptop.
- No Edge-specific WebGPU flag/behavior documentation found (e.g. whether Edge honors the same Dawn backend defaults on Windows); assumed identical to Chromium.

## KQ9 — Chrome version/channel considerations; should the user pin a version?

### Takeaway
No published WebGPU-on-Intel-Gen9 regression/improvement specifically for Chrome 140+ was found in the sources reviewed; WebGPU's 140-156 changes are mostly Dawn/Tint improvements. Pinning an old version would forfeit security fixes (e.g. a Graphite use-after-free fixed 15 Apr 2026 in 147.x) without any identified version-specific win — staying on current stable is the defensible default.

### Cited Findings
- Chrome 140-156 "What's New in WebGPU" entries list: buffer upload optimization for Vulkan backend (140), Tint IR completed (141), SPIR-V 1.4 update for Vulkan (141), texture format capabilities (142-144), subgroup extensions (145-152), "WGSL linear_indexing" (147-148), "Dawn updates" throughout — no Intel-iGPU-specific performance items — [What's New in WebGPU (index on Chrome 136 page)](https://developer.chrome.com/blog/new-in-webgpu-136), [Chrome 120 page (includes 140+ index)](https://developer.chrome.com/blog/new-in-webgpu-120).
- Graphite (now active on Windows) had a high-severity use-after-free (CVE-2026-6304) fixed in Chrome 147.0.7727.101/102 on 15 Apr 2026 — [Chromium patterns: Skia Graphite transition](https://chromium.bartleyeditions.com/skia-graphite) (secondary source; fixed-version details attribute to the Chrome stable release note).
- The UseEcoQoSForBackgroundProcess flag was absent in M132-M139 and restored in M139 — relevant if ever downgrading: pick 139+ for that workaround — [Chromium issue 406667206](https://issues.chromium.org/issues/406667206).
- Feature-level requirements on this hardware (D3D12 FL 11.1+, driver-new-enough for shared textures) are stable across these versions; the failure mode observed historically was driver age, not Chrome version — [Dawn support doc](https://github.com/google/dawn/blob/main/docs/support.md), [Chromium issue 355006335](https://issues.chromium.org/issues/355006335).

### Inferences
- Recommend: stay on the current stable channel, keep the Intel GPU driver as new as Intel offers for Kaby Lake (that is the single highest-leverage "version" variable for WebGPU on HD 620 — old drivers caused hard WebGPU breakage and shared-texture failures), and revisit only if a specific regression is observed (in which case test the immediately previous stable via a portable/secondary install rather than pinning long-term).
- If the user wants maximum stability for a fixed workload, the only version-related settings worth using are the flags already validated above (EcoQoS workaround requires ≥ M139; Graphite toggle exists in the current stable).

### Gaps
- No Chromium bug-tracker search results surfaced for "WebGPU regression Intel Gen9/UHD 620 in Chrome 140-156"; absence of evidence here does not prove absence of regressions (the issue tracker was only searched incidentally).
- No official "known issues" page found for WebGPU on Gen9 iGPUs in late 2025/2026.
