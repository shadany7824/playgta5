# Windows and Hardware-Level Tuning for Smoother Browser Gaming on a Weak Laptop (HP / i3-7100U / HD 620 / 4GB / GTA V wasm64 WebGPU port)

Context for the report writer: the target machine is an HP consumer laptop with Intel Core i3-7100U (2C/4T Kaby Lake, 2.4 GHz, 15W, **no Turbo Boost** per Intel ARK), Intel HD Graphics 620 (Gen9, 24 EUs, 192 shaders, max 1.0 GHz on this SKU, uses shared system RAM — no eDRAM), 4GB DDR4 (3.9GB usable), Windows 10/11, game files on internal HDD, page file fixed at 10GB on SATA SSD. The game is the unofficial GTA V browser port (playgta5-class project) running in Chrome at localhost:8000: RAGE engine compiled to wasm64 + pthreads shared memory (~75 threads), WebGPU rendering via a worker that maps D3D11 to WebGPU, ~21GB of assets streamed from a local Python HTTP server via Range requests, mostly 4KB blocks. The port's own docs list 8GB RAM minimum (low-memory mode) / 16GB recommended and note it was tested on an RTX 3070 / 32GB machine — this laptop is far below that baseline, so the report should keep expectations honest.

Read-only verification on the target machine (Oct 2026, no modifications made): Windows 10 Pro 22H2, build 19045.6466; GPU = Intel(R) HD Graphics 620, driver 31.0.101.2140 dated 2025-11-05; registry HwSchMode = 2 present under HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers; VBS = not enabled (Win32_DeviceGuard VirtualizationBasedSecurityStatus = 0, no security services running); RAM = 3.9GB visible / 0.15GB free at inspection; pagefile C:\pagefile.sys 10240MB allocated, 2827MB in use, peak 3790MB; commit limit ≈ 13.9GB.

---

## HAGS (Hardware-Accelerated GPU Scheduling) on Intel gen9 iGPUs (HD 620)

### Takeaway
HAGS does not apply to this hardware. Intel officially supports HAGS only on Intel Arc B-Series discrete cards on Windows 11 22H2+ (and not even on Arc A-Series); Intel integrated GPUs are not supported. The registry value HwSchMode=2 found on the machine is inert for HD 620. Nothing to gain, nothing to fix — leave it alone.

### Cited Findings
- Intel official compatibility article (reviewed 2025-07-24): "This feature is supported on Intel® Arc™ B-Series Graphics cards on Windows 11 22H2 and newer builds. Currently, this is not supported on Intel® Arc™ A-Series Graphics cards." HAGS was introduced with WDDM 2.7 in Windows 10 2004. — [Intel](https://www.intel.com/content/www/us/en/support/articles/000056788/graphics.html)
- Intel moderator (Mar 2025): "currently HAGS is only supported on Intel Arc B-Series GPUs", no ETA for other Intel GPUs. — [Intel Community](https://community.intel.com/t5/Intel-Arc-Discrete-Graphics/We-know-Alchemist-and-Battlemage-have-a-unified-driver-so-where/m-p/1670785)
- Microsoft Q&A (Dec 2025, independent advisor on a UHD 730 iGPU system): "your processor doesn't natively support HAGS … if it's Intel, only the Iris and Arc series have HAGS" (advisor opinion, not an official Microsoft statement — treat as secondary). — [Microsoft Q&A](https://learn.microsoft.com/en-au/answers/questions/5684022/hardware-accelerated-gpu-scheduling-option-not-sho)
- IQON tuning guide (Feb 2026): "Integrated graphics like Intel UHD generally don't support HAGS." Also: HAGS benefits are "typically modest", main upside is reduced stutter/input lag in CPU-heavy titles. — [IQON](https://iqondigital.com/learn/pc-optimization/hardware-gpu-scheduling)
- Registry mechanics (Microsoft Q&A + an enterprise remediation script): the toggle maps to HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\HwSchMode; value 1 = disabled, 2 = enabled; requires Windows 10 2004+ (build 19041+) and a WDDM 2.7+ driver; reboot required; toggle may be grayed out when unsupported. — [Microsoft Q&A](https://learn.microsoft.com/en-ca/answers/questions/5911034/hardware-accelerated-gpu-scheduling-(hags)-toggle), [omnissa script](https://github.com/omnissa-chase/DEXSolutionScripts/blob/main/WindowsAutoRemediation/Performance/Enable-HardwareAcceleratedGPUScheduling.ps1)
- Historcal context: Intel said in June 2020 it planned HAGS support in future WDDM 2.7 drivers for its GPUs, yet the feature never shipped for gen9; even some users who could enable it reported negative impact. — [Windows Latest](https://www.windowslatest.com/2020/06/30/windows-10-hardware-gpu-scheduling-amd-intel/)
- Practitioner forum (Mar 2025): HAGS mainly matters for modern dGPU feature sets (frame generation, some display scheduling); no independent evidence of gains on low-end/integrated hardware. — [Guru3D](https://forums.guru3d.com/threads/hardware-accelerated-gpu-scheduling-turn-off-for-powerful-cpus.455675)

### Inferences
- On this machine HAGS is not a lever at all: the GPU is gen9 (HD 620) and Intel's own documentation limits HAGS to Arc B-Series. The observed HwSchMode = 2 has no effect on this GPU/driver; there is no evidence the toggle even appears in Settings for HD 620.
- Recommended action: **do nothing** (risk: safe; expected impact: 0%). If the user wants tidiness, verify in Settings > System > Display > Graphics > Change default graphics settings whether the HAGS toggle is present; if present and ON, either leave it (harmless) or turn it OFF (registry HwSchMode=1, reboot). Do not attempt to force HwSchMode=2 via registry edits to "unlock" it — unsupported paths can only cause driver instability. Verify: GPU-Z or dxdiag won't help; the authoritative check is whether the toggle exists in Settings. Undo: set HwSchMode back to 2 (or use the Settings toggle).
- The report should explicitly close this question as "not applicable" rather than list it as a tuning option.

### Gaps
- No public evidence found of any HD/UHD 620 (gen9) system where HAGS produced a measurable effect — consistent with it being unsupported. No need for further research; treat as resolved negative.

---

## VBS / HVCI (Memory Integrity) and Windows 11 security features on 2C/4T Kaby Lake

### Takeaway
Memory Integrity (HVCI) costs 3–8% average FPS and up to 15% on 1% lows on modern hardware, and typically costs more on older/weaker CPUs; Microsoft itself recommends temporarily disabling it for gamers. On this machine it is already OFF (VBS not running — verified) and mostly cannot be turned on accidentally: the Oct 2026 auto-enable only targets eligible machines (8th-gen Intel+, 8GB RAM+), which excludes this 7th-gen, 4GB laptop. Keep it off; do not disable VT-x in BIOS.

### Cited Findings
- October 13, 2026 change: Microsoft began enabling Memory Integrity by default on all supported Windows 11 systems still receiving updates; eligibility requires 8th-gen Intel or newer, AMD Zen 2+, 8GB RAM on x64, 64GB SSD, and compatible drivers. Tested penalty: up to 15% slower games (Tom's Hardware data); Microsoft (confirmed 2022) advised gamers prioritizing performance could "temporarily disable" Memory Integrity and Virtual Machine Platform. — [PCWorld](https://www.pcworld.com/article/3227631/windows-11-will-be-more-secure-from-october-but-gamers-could-suffer-as-a-result.html)
- Tom's Hardware, 15-game suite on RTX 4090/i9-13900K (2023): VBS on = ~5% average FPS loss, up to 10% (e.g., MSFS), 1% lows down as much as 15%. — [Tom's Hardware](https://www.tomshardware.com/news/windows-vbs-harms-performance-rtx-4090), [Digital Trends](https://www.digitaltrends.com/computing/windows-vbs-gaming-performance)
- Aggregated 2026 numbers: mid-single-digit geometric-mean impact (3–6%) with title-dependence; 2021 four-platform study: 3.3–5.7%; ComputerBase/Neowin (Win11 24H2, Ryzen 7 5800X3D): ~8% penalty even with hardware-assisted VBS, biggest in CPU-bound scenes; penalty persists from 21H2 through 24H2. — [Tech-Insider summary](https://tech-insider.org/windows-11-memory-integrity-gaming-performance-2026), [IQON](https://iqondigital.com/learn/pc-optimization/clipboard-memory-integrity)
- Old-CPU nuance: processors older than Intel 7th-gen and AMD Zen 2 lack hardware MBEC and emulate it, losing more; HVCI is the main cost driver vs VBS alone. Kaby Lake (7th gen) *is* the cut-off line: it has hardware MBEC. TechSpot measured a 7% DRAM latency penalty on a 10th-gen Core i3 with VBS on. — [Digital Trends](https://www.digitaltrends.com/computing/are-windows-11-security-features-killing-gaming-performance), [TechSpot](https://www.techspot.com/article/2349-windows-11-performance)
- Practical controls: disable via Windows Security > Device security > Core isolation > Memory integrity OFF (VMP off also disables VBS); verify via System Information (msinfo32) "Virtualization-based security" or Win32_DeviceGuard query. — [GamingPCBuilder](https://www.gamingpcbuilder.com/core-isolation-benchmarks-2023-intel)
- Target machine state (verified read-only): Windows 10 Pro 22H2, VBS status = 0 (not enabled), no VBS services running. Windows 10 has no Memory-Integrity-by-default push; the Oct 2026 auto-enable is a Windows 11 event and wouldn't apply to this hardware even on Win11 (7th-gen CPU, 4GB RAM are below its eligibility list).

### Inferences
- No action needed on this machine: Memory Integrity is off and protected from surprise enablement by ineligibility. Recommended: [SAFE] leave as is. To verify (documented steps): Settings > Privacy & security > Windows Security > Device security > Core isolation, or `msinfo32`; on this machine `Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard` returns status 0. If it were ever on [SAFE to switch off, reversible]: toggle off, reboot; re-enable by the same toggle. Do NOT disable virtualization (VT-x/SVM) in BIOS as a workaround — unnecessary here and risks other features (e.g., sandboxing, WSL, some OEM tools).
- For the report: frame this as "already optimal; verify occasionally after feature updates" rather than a tweak to apply.

### Gaps
- No specific VBS/HVCI benchmark on a 2C/4T Kaby Lake U-series laptop was found. Given the measured 3–8% band on stronger CPUs with hardware MBEC, the effect here would plausibly be at least in that band if enabled — but this is an estimate, not a sourced measurement. Effectively moot since it is off.

---

## Intel HD 620 driver: latest version, OEM vs Intel generic, API notes

### Takeaway
Kaby Lake sits on Intel's legacy branch: newest build found is 31.0.101.2141 (2026-04-06); the current machine already has 31.0.101.2140 (2025-11-05), so it is at most one increment behind — updating is optional and low-impact. Generic Intel drivers are the only current option (HP/OEM drivers are years stale); Intel itself says generic drivers are for temporary testing and to return to OEM drivers "until they validate and release their own version", but for a 2017 consumer laptop that OEM validation is never coming, so generic is the practical and community-endorsed path.

### Cited Findings
- Latest Kaby Lake driver tracked (as of Apr 2026): version 31.0.101.2141, released 2026-04-06, supporting 7th-gen Kaby Lake and newer (7th–10th gen + related) — [ElevenForum driver thread](https://www.elevenforum.com/t/latest-intel-graphics-driver-for-windows-11.563)
- Windows Update Catalog contains Intel display driver 31.0.101.2137 (posted 2025-08-27, Win11 servicing) and 31.0.101.2135 (2025-03-05, Win10 1903+) — Microsoft-signed legacy-branch builds. — [Microsoft Update Catalog](https://www.catalog.update.microsoft.com/Search.aspx?q=Intel%2B620)
- Intel Community solution (May 2025) for an HD 620 laptop: "The latest Graphics Driver for your CPU Integrated Graphics is version 31.0.101.2135. You may download and install the latest driver using Clean Installation method. Be aware, since the latest Intel driver is a generic driver, you may lose some OEM customization." Also notes the official way to roll back to the OEM build if problems occur. — [Intel Community](https://community.intel.com/t5/Graphics/Intel-R-HD-Graphics-620-need-updated-driver/td-p/1690190)
- Intel's own release notes for the current 32.x line (e.g., 32.0.101.8735, Apr 2026) list only Arc / Core Ultra / Xe-class products for Windows 10 22H2 and Win11 — Kaby Lake is NOT in the supported list, confirming it remains on the 31.0.101.21xx legacy branch. Same notes state the generic driver's "intention is to temporarily test new features… Once testing is complete Intel advises reinstalling the OEM driver" — boilerplate aimed at OEM-covered machines, effectively impossible to satisfy for a 2017 HP consumer machine. — [Intel release notes PDF](https://downloadmirror.intel.com/917974/ReleaseNotes_101.8735.pdf)
- API support (Intel official page): Intel HD Graphics 610/615/620/630 family supports DirectX 12, OpenGL 4.6, OpenCL 2.1 (UHD 610/620/630 row shows Vulkan 1.3; the HD 610/615/620/630 row shows same DX/GL/CL with Vulkan listed in the family table). NotebookCheck-era data for HD/UHD 620 lists Vulkan 1.1.103 support — minor version conflict between sources; the practical point is Vulkan is supported. — [Intel](https://www.intel.com/content/www/us/en/support/articles/000005524/graphics.html), [NotebookCheck](https://www.notebookcheck.net/Intel-UHD-Graphics-620-GPU-Review-Benchmarks-and-Specs.239936.0.html)
- Machine state (verified): installed driver 31.0.101.2140, dated 2025-11-05 — one build older than the latest known (31.0.101.2141). Windows 10 Pro 22H2 build 19045.6466.
- Historical note: Intel DSA (Driver & Support Assistant) has falsely reported "up to date" for HD 620 systems in the past (reported 27.20.100.9416 as latest when 31.0.101.2135 existed) — verify by version number, not by DSA alone. — [Intel Community thread above]

### Inferences
- Expected impact for THIS machine: small. A one-build update (2140 → 2141) is unlikely to change WebGPU/D3D12 performance materially; but staying on the legacy branch's newest build is still the best-supported code for Chrome's WebGPU/D3D12 path and can carry crash/perf fixes. [SAFE] risk — standard driver install, reversible.
- Recommended steps (either path): (1) Download the Kaby-Lake-family driver (31.0.101.21xx) from the Intel Download Center link in the ElevenForum thread / Intel DSA; or (2) rely on Windows Update, which already ships 31.0.101.2137+ for this family. Install with the installer's "Clean installation" option (Intel's own recommendation in the community thread above); reboot. Verify: Device Manager > Display adapters > Intel HD Graphics 620 > Driver tab (expect 31.0.101.2141 / 31.0.101.2137), or `Get-CimInstance Win32_VideoController | Select DriverVersion`. If anything breaks: Device Manager > Roll Back Driver, or reinstall the previous 31.0.101.2140 package (save the current installer first), or install the HP OEM package from the HP support page for this model [ADVANCED only because of reinstall effort; low actual risk].
- OEM vs generic: use Intel generic. OEM HP packages for this generation stopped at ~27.20.100.xxxx or earlier (pre-DCH era, older D3D12/Vulkan code); the only caveat Intel raises (losing OEM customizations e.g. display color profiles) is minor and reversible by reinstall.
- D3D12/OpenGL/Vulkan performance differences on HD 620: see Gaps — no credible recent apples-to-apples benchmark found; and for this game it's mostly moot because Chrome's WebGPU path on Windows runs over D3D12-class presentation, not OpenGL/Vulkan, which the port's own D3D11→WebGPU translation layer confirms it targets. — port architecture per [ai.thesatyajit.com](https://ai.thesatyajit.com/articles/gta5-in-the-browser)

### Gaps
- No reliable recent source comparing D3D12 vs OpenGL vs Vulkan FPS on Intel HD 620 specifically (2024–2026). Not actionable for this game anyway (browser exposes WebGPU, not API choice).
- Exact release date/notes for 31.0.101.2140 (the installed build) and whether 2141 contains any relevant fixes were not found; assume incremental.

---

## Intel Graphics Command Center (GCC) / Control Panel 3D settings for chrome.exe

### Takeaway
GCC is the right control panel for this DCH driver (the legacy panel is gone on 31.x). Commonly recommended per-app settings (texture quality = Performance, VSync off, power = Maximum Performance, Application Optimal Mode) are reasonable, low-risk experiments but no rigorous measurement of their FPS impact on HD 620 + Chrome was found in this research pass. The one well-documented caveat: some GCC per-app settings (VSync) are known to reset to defaults after reboot/sleep — rely on per-app profiles or verify after each boot.

### Cited Findings
- Intel official: GCC is the supported app on Windows 10 for video/display adjustments; GCC install is via Microsoft Store; it requires Win10 1709+ and 6th-gen Intel Core or newer — satisfied on this machine. — [Intel GCC video settings](https://www.intel.com/content/www/us/en/support/articles/000057322/graphics/processor-graphics.html), [Microsoft Store](https://apps.microsoft.com/detail/9nmr79ztjftc)
- Intel official troubleshooting: VSync settings in GCC are known to return to default after restart/sleep/after a game; suggested fixes are driver update and GCC reinstall — i.e., persistence of this specific setting is a documented weak spot. — [Intel](https://www.intel.com/content/www/us/en/support/articles/000093381/graphics.html)
- Community/press consensus that GCC exposes per-app "Games" profiles with 3D options (AA, texture quality, VSync) and system power options; YouTube tutorial "Best Intel GCC Settings to BOOST FPS" (2025) markets texture/VSync/power settings as FPS boosters — but this is an unverified content-farm style claim; no measured methodology visible from the snippet. — [YouTube](https://www.youtube.com/watch?v=98gNVWNEwXo)
- No Intel documentation found that quantifies FPS impact of any individual GCC 3D setting on gen9 + browser workloads.

### Inferences
- For THIS machine, treat GCC 3D profiles as [SAFE, unverified-gain] experiments, one change at a time, measured in-game: (a) Add chrome.exe as an app in GCC (Games section); (b) set Texture Quality to Performance (reduces texture bandwidth pressure — the iGPU shares the DDR4-2133 bus with the CPU, so bandwidth is the scarcest resource); (c) set VSync OFF cautiously — the game targets 30 FPS caps anyway; tearing risk exists and Chrome/DWM may re-impose vsync, so measure; (d) GCC power settings to Maximum Performance on AC power (keeps iGPU clocks from napping and can reduce clock-ramp stutter); this is redundant with the Windows High Performance plan but harmless.
- "Application Optimal Mode": on modern DCH drivers this per-game toggle is generally harmless; no source found showing it matters for Chrome/WebGPU — include as optional off/on A/B, not a recommendation.
- Verification method that matches the port's design: use the game's own comparison flow (same spot after shader preparation, compare ?low=1&fps=60&res=1280x720 vs a changed GCC setting) and chrome://gpu to confirm WebGPU is hardware-accelerated on "Intel HD Graphics 620". — [playgta5 README](https://github.com/alihammoud21/playgta5)
- Undo: GCC has restore-to-defaults per setting; worst case, remove the chrome.exe profile.

### Gaps
- No measured, citable FPS deltas for GCC 3D settings on HD 620 (any workload). Claims are community lore; the report should present these as low-risk, unproven tweaks, not "boosters".

---

## iGPU shared memory / BIOS DVMT on this laptop class

### Takeaway
Do not touch BIOS/DVMT here. Intel iGPUs already allocate video memory dynamically; on a 4GB machine, carving out a bigger fixed pre-allocation would *reduce* usable system RAM and hurt more than it helps. HP consumer BIOSes typically lock these advanced options anyway, and the real bandwidth lever (dual-channel RAM) is hardware, not BIOS.

### Cited Findings
- HP Support Community solution (2025, HD 620 thread): the 128MB "dedicated" figure is just a baseline reservation; Windows/Intel dynamically allocate from system RAM as needed; increasing DVMT only possible if BIOS exposes it (Advanced > Graphics Configuration > DVMT Pre-Allocated / UMA Frame Buffer) and "probably" won't help much because bottleneck is GPU processing power; recommends instead: more RAM, dual-channel RAM, lower settings, latest drivers. — [HP Community](https://h30434.www3.hp.com/t5/Gaming-Notebooks/Dedicated-video-Memory/td-p/9358130)
- HP Community (2020, HP notebook): "Integrated video (iGPU) does not have room to keep VRAM, it relies on System… System will work this out and allocate/assign spare/available system RAM to VRAM automatically when required up to max limit" — BIOS manual control is largely obsolete on these platforms. — [HP Community](https://h30434.www3.hp.com/t5/Gaming-Notebooks/Reduce-shared-GPU-memory-and-increase-dedicated-GPU-memory/td-p/7616683)
- HP Community (2024, HP Envy): "advanced options seem to be locked by HP" on consumer models — DVMT is commonly not exposed. — [HP Community](https://h30434.www3.hp.com/t5/Notebook-Software-and-How-To-Questions/Make-the-shared-GPU-memory-work/td-p/8960036)
- Machine context: dxdiag "Approx. Total Memory" already shows ~1GB AdapterRAM reported (WMI) on this machine while actual usage is dynamic; with 3.9GB RAM and 10GB pagefile, the constraint is total RAM availability, not a carve-out size.

### Inferences
- Recommended action: [SAFE] do nothing in BIOS. Expected impact of DVMT increase: zero-to-negative on a 4GB machine (loses system RAM; the game's wasm64 heap + Chrome need system RAM far more than the GPU needs a pre-allocated buffer). [RISKY] any BIOS flashing/undocumented menu unlocking on an HP consumer laptop — not recommended, high brick/no-support risk, negligible upside.
- If the user asks "why is dedicated video memory only 128MB": explain dynamic allocation (HP solution above). Verify: dxdiag Display tab; Task Manager > Performance > GPU shows shared usage. Undo: n/a (no change made).
- The genuinely valid hardware path — if the machine has a free SO-DIMM slot and the budget exists — is 2×4GB dual-channel (see dual-channel finding below); that is out of scope (not a Windows tweak) but is the single biggest iGPU uplift available to this class.

### Gaps
- Whether this specific HP model (unknown exact SKU) exposes DVMT in BIOS or has a free RAM slot was not determined (needs the exact model number). Report should note the check: HP support page for the model > specifications > memory slots.

---

## Windows gaming features: Game Mode, Game Bar/DVR, fullscreen optimizations, windowed-game optimizations, refresh rate, scaling

### Takeaway
For THIS game the Windows frame-level features are mostly irrelevant: "Optimizations for windowed games" only affects DX10/11 games (Chrome is not one; it's Win11-only anyway and the machine runs Win10), fullscreen-optimization overrides don't apply to Chrome's flip-model rendering. What matters here: keep Game Mode ON (free, harmless), disable Game Bar background capture if enabled, run the game fullscreen, and use the game's own resolution/FPS presets (540p/720p @ 30–60 cap) rather than OS-level tricks.

### Cited Findings
- Microsoft official (Optimizations for windowed games): improves windowed/borderless DirectX 10 and DirectX 11 games by moving them from blt-model to flip-model presentation (lower latency); toggled in Settings > System > Display > Graphics > Change default graphics settings; per-app opt-out exists; DX12 games already use flip model. — [Microsoft Support](https://support.microsoft.com/en-gb/windows/optimizations-for-windowed-games-in-windows-11-3f006843-2c7e-4ed0-9a5e-f9389e535952)
- Microsoft says Game Mode "should be on by default" and points to the Graphics default-settings page for HAGS/Auto HDR/windowed-games toggles (Win11). — [Microsoft Windows 11 gaming page](https://www.microsoft.com/en-us/windows/windows-11-pc-gaming)
- Background: Windows has converted exclusive-fullscreen games to borderless since 2019, and the flip-model change was described as significantly improving latency for windowed modes. — [BleepingComputer](https://www.bleepingcomputer.com/news/microsoft/windows-11-gaming-gets-significant-latency-and-hdr-improvements), [PCWorld](https://www.pcworld.com/article/615360/new-windows-11-build-reveals-new-pc-gaming-hdr-improvements.html)
- Xbox/Wire: "Efficiency mode improves gaming performance on Windows 10/11 by automatically reducing browser resource usage when a PC game is launched" — i.e., Windows may throttle browsers when a *separate* game runs; here the browser IS the game, so this feature is a caveat: ensure Chrome is foreground/fullscreen rather than letting background-throttling mechanisms apply to it. — [Xbox Wire](https://news.xbox.com/en-us/2022/09/20/windows-11-2022-update-available-today)
- Windows 11 tuning roundup (2025): Game Mode steps, power mode slider to Best Performance, startup-app impact list — general-purpose, not browser-game-specific. — [Windows Central](https://www.windowscentral.com/microsoft/windows-11/my-top-21-ways-to-improve-windows-11-to-increase-gaming-performance-without-hardware-upgrade)
- Game-specific presets from the port's own README: compatibility page at http://localhost:8000/__support/ offers clickable presets; "lower-memory 720p / 30 FPS launch option"; compare ?low=1&fps=60&res=1280x720 or ?low=1&fps=60&res=960x540 "in the same place after shader preparation"; FPS value is a cap, not a guarantee; check the active GPU in chrome://gpu. — [playgta5 README](https://github.com/alihammoud21/playgta5)
- The M1-MacBook community build (same wasm port family) shipped optimized "reduced graphical presets, a resolution cap, and a 30 FPS frame-rate limiter" and still "regularly hits the strict memory limits… leading to occasional crashes". — [Ubergizmo](https://www.ubergizmo.com/2026/10/gta-v-ported-browser/)
- Port architecture: RAGE streamer "queues reads and performs them one at a time on one thread" (single-threaded asset streaming); ~75-thread shared-memory wasm64 engine; assets streamed over HTTP Range requests in ~4KB blocks. — [ai.thesatyajit.com](https://ai.thesatyajit.com/articles/gta5-in-the-browser), [Gaming Ideology](https://www.gamingideology.com/how-developers-ported-grand-theft-auto-v-to-web-browsers-using-webassembly/)
- Machine state: Windows 10 22H2 → the "Optimizations for windowed games" feature (Win11 22H2+) does not exist here; nothing to toggle.

### Inferences
- Recommended for THIS machine: [SAFE] Game Mode stays ON (Settings > Gaming > Game Mode) — zero cost, possible small reduction of background interference; [SAFE] if Game Bar is active, open Xbox Game Bar settings (Win+G > Settings > Capturing) and ensure "Record in the background while I'm playing a game" is OFF (background capture costs CPU/GPU — expected impact on a 2C/4T iGPU: small but positive; no citable measurement found, mark as standard practice); [SAFE] make sure chrome://settings/system "Use graphics acceleration when available" is ON (the port's README requires it; chrome://gpu must show WebGPU hardware-accelerated) — verify, expected impact: critical if off; [SAFE] uncheck per-app "Disable fullscreen optimizations" for chrome.exe if anyone set it (default state is correct; FSO manipulation has no documented effect on Chrome's flip-model canvas; leave compatibility flags alone).
- Fullscreen and FPS cap: run the game tab in fullscreen (F11/thin fullscreen), use the README's low-memory 720p/30 preset; do NOT chase 60 on this class of hardware — use the cap to stabilize (30 is smoother than 45 oscillating). Expected impact: this is the largest easing lever the game itself offers on this GPU class.
- Refresh rate: this class of laptop panel is a fixed 60Hz (no VRR); nothing to tune. If Windows shows other modes (59/60Hz), simply keep 60Hz [SAFE]. No source was found indicating dynamic refresh options matter on this hardware.
- Display scaling: if the panel runs at >100% scaling, dropping to 100% reduces DWM's per-frame scaling work and typically frees a sliver of iGPU time [SAFE, unverified magnitude]; the game canvas resolution is controlled by ?res= regardless. If the user relies on larger text, skip this — the game's own resolution presets are the meaningful dial.

### Gaps
- No measured FPS figures found for Game Mode on/off or Game Bar capture on/off for browser games, and none for FSO toggles with Chrome. Claims here are standard-practice, not benchmarked. Report should frame them as low-risk hygiene rather than performance evidence.

---

## CPU / thermal: keeping Kaby Lake 15W clocks up (and what is placebo)

### Takeaway
This i3-7100U has NO Turbo Boost — 2.4 GHz is the ceiling — so "boost mode" tweaks cannot raise clocks; the only real fight is preventing throttling below 2.4 GHz (thermals, erroneous BD PROCHOT, battery limits). Keep it plugged in, cool, dust-free; ignore core-parking/boost folklore; if the machine ever sits stuck at ~400 MHz at low temperature, that is the known BD PROCHOT failure mode and ThrottleStop is the (advanced) remedy.

### Cited Findings
- Intel ARK for i3-7100U: base 2.40 GHz, "Intel® Turbo Boost Technology: No", Hyper-Threading Yes, Speed Shift Technology Yes, TDP 15W, configurable TDP-down 7.5W, Tjmax 100°C. — [Intel ARK](https://www.intel.com/content/www/us/en/products/sku/95442/intel-core-i37100u-processor-3m-cache-2-40-ghz/specifications.html)
- Processor performance boost mode (PERFBOOSTMODE) controls how the CPU picks turbo bins: values 0=Disabled, 1=Enabled, 2=Aggressive; set via `powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 1` (and /SETDCVALUEINDEX for battery), then `powercfg /S SCHEME_CURRENT`; it is a hidden setting (GUID be337238-0d82-4146-a960-4f3749d470c7). — [Microsoft Q&A](https://learn.microsoft.com/en-nz/answers/questions/5889318/changing-the-processor-performance-boost-mode-on-a)
- Known throttle failure: an HP i3-7100U laptop stuck at 400MHz (1x multiplier) at only 30°C; disabling BD PROCHOT in ThrottleStop restored full frequency — diagnosed in an Intel Community thread where Intel staff first suggested dust/thermal checks. — [Intel Community](https://community.intel.com/t5/Mobile-and-Desktop-Processors/Benchmarks-say-i3-7100U-is-performing-very-poorly-but-Intel/td-p/1210951)
- Benchmark variance for i3-7100U systems is wide (UserBenchmark: 95th–5th percentile range 38%) — consistent with cooling/power-state differences dominating, not silicon lottery. — [UserBenchmark](https://cpu.userbenchmark.com/SpeedTest/176913/IntelR-CoreTM-i3-7100U-CPU---240GHz)
- Machine context: plugged-in High Performance plan already applied (per task brief); no Turbo bins exist to unlock.

### Inferences
- Do not bother with PERFBOOSTMODE tweaks on THIS CPU [SAFE but pointless]: with no turbo bins, values 0–2 change nothing (it still pins to 2.4 GHz max). Expected impact: 0%. The report should say this explicitly to preempt "free FPS" folklore.
- Meaningful actions ranked: [SAFE] always run plugged in (15W package on battery can be OEM-limited; also iGPU+CPU share the power budget — unverified magnitude on this exact model, standard practice); [SAFE] thermal hygiene: dust out the fan/heatsink (Intel staff advice in the thread above), raise the laptop on a stand/pad so the intake breathes — honest framing: pads show modest, inconsistent gains in reviews; the certainty is that a clogged fan or blocked intake costs clock speed. Use `Get-CimInstance`/HWiNFO to watch clocks: if sustained load holds ~2.4 GHz with acceptable temps (~<85°C), thermals are fine; if it dives to ~1.5–2.0 GHz, throttle is costing frames. Verify: HWiNFO64 "CPU Core Clock" + "Package Temperature" during 10 min of gameplay. Undo: n/a.
- [ADVANCED] If (and only if) clocks pin at 400 MHz at low temperature — the documented BD PROCHOT malfunction — ThrottleStop with BD PROCHOT unchecked is the known fix (community-proven on this exact model class), with small risk exposure (it writes MSRs; revert by re-enabling the option/rebooting). Verify: observed clock recovery while temperature stays low. Undo: uncheck again or don't run the tool.
- Core parking / minimum processor state: on a 2C/4T part under a continuously loaded browser game, cores stay unparked anyway; forcing "min processor state 100%" mostly adds heat. [SAFE, unverified, low expected gain]. If experimenting: `powercfg` hidden GUIDs (discover via `powercfg /q SCHEME_CURRENT SUB_PROCESSOR`) — set on AC only; undo by restoring the plan defaults (`powercfg -restoredefaultschemes` on a custom twin). Report framing: placebo-tier for this scenario; skip unless the user insists.
- Verify the machine isn't an outlier throttler before spending effort elsewhere: a 10-minute HWiNFO log answers "is the CPU/iGPU actually reaching its 2.4 GHz / 1.0 GHz ceilings". — consistent with the Intel Community diagnostic path.

### Gaps
- No measured cooling-pad/repaste benchmarks for this exact class were found in this pass (2024–2026); effect size claims for pads remain qualitative. The honestly supported statements: dust removal and unobstructed intake are certain good; pads are usually small-to-marginal.
- The exact HP model's thermal profile/BIOS (e.g., HP "Command Center" fan modes) could not be researched without the exact model number — noted for the report as a model-specific check.

---

## Memory: 4GB constraints, page file, memory compression, SysMain/SuperFetch, ReadyBoost

### Takeaway
RAM is the true bottleneck (3.9GB visible; 0.15GB free at idle; the port wants 8GB minimum). Three concrete, low-risk actions: keep memory compression ON, keep the page file on the SSD (10GB fixed is defensible; raising to 16GB buys commit headroom, not speed — optional), and disable SysMain to cut background RAM/disk churn on this dual-drive machine. ReadyBoost is obsolete here. The biggest structural win is ensuring asset reads don't hit the HDD (defrag it, or move the ~21GB game data to the SSD if space ever allows).

### Cited Findings
- Microsoft page-file sizing doc: page sizing depends on commit-charge peaks; commit limit = RAM + page files; system-managed minimum varies with usage history (RAM÷8 max 32GB), max = 3×RAM or 4GB whichever is larger, capped by volume size ÷ 8. — [Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/how-to-determine-the-appropriate-page-file-size-for-64-bit-versions-of-windows)
- Rule-of-thumb history: initial 1.5×RAM / max 3×RAM (TechTarget paraphrase of Microsoft guidance); compressed memory is on by default and is faster than paging to disk; disabling it is possible via PowerShell. — [TechTarget](https://www.techtarget.com/searchenterprisedesktop/tip/Learn-native-Windows-10-virtual-memory-management-methods)
- Windows keeps SysMain running even on SSD-only systems "by design" — it is not auto-disabled for SSDs anymore. — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/3297259/windows-10-prefetch-superfetch-is-used-although-an)
- Community guides conflict: one repo's matrix says disable SysMain+Prefetch on any SSD (keep only on HDD-only systems); TheWindowsClub says defaults are best and disabling often shows no improvement; a Microsoft Q&A answer shows the disable commands (`sc stop "SysMain" & sc config "SysMain" start=disabled`). — [insovs repo](https://github.com/insovs/Optimization-Windows/blob/main/Services/SysMain%20&%20Prefetch/README.md), [TheWindowsClub](https://www.thewindowsclub.com/disable-superfetch-prefetch-ssd), [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/3163566/superfetch-disable), forum-level counterpoint [LTT](https://linustechtips.com/topic/1089365-should-you-still-disable-superfetchsysmain)
- Port memory/traffic facts: wasm64 + shared-memory workers; assets (~21GB) streamed via HTTP Range in ~4KB blocks from the local server; streamer reads one-at-a-time on one thread. — [Gaming Ideology](https://www.gamingideology.com/how-developers-ported-grand-theft-auto-v-to-web-browsers-using-webassembly/), [ai.thesatyajit.com](https://ai.thesatyajit.com/articles/gta5-in-the-browser)
- Port requirements: 8GB RAM minimum ("low-memory mode"), 16GB recommended; browser must support WebAssembly Memory64 + WebGPU; tested on RTX 3070 / 32GB / 25GB free space. — [playgta5 README](https://github.com/alihammoud21/playgta5), [SebasKitten/Grand-V](https://github.com/SebasKitten/Grand-V)
- Machine state (verified): commit limit ≈13.9GB (3.9GB RAM + 10GB pagefile); pagefile peak usage during (recent) sessions 3.79GB — the system already pages during this workload.

### Inferences
- Page file [SAFE]: keep it on the SATA SSD (never on the HDD — SSD random reads are ~50–100× faster, which matters for page-in latency). 10GB fixed is acceptable (≈2.5–3× RAM, inside Microsoft's max guidance). Optional: raise fixed size to 16384MB (or set system-managed) to give commit headroom for 3GB-class wasm allocations plus Chrome spikes; expected impact: fewer low-memory hard failures during asset loading, not FPS. Leave a second pagefile config alone. Verify: `Get-CimInstance Win32_PageFileUsage` (AllocatedBaseSize, PeakUsage) and Task Manager > Performance > Memory (Commit committed/limit). Undo: set back to 10240 fixed. Keep fixed (not system-managed) to avoid on-the-fly resize I/O during gameplay — an inference from Microsoft's sizing doc, not a measured claim.
- Memory compression [SAFE]: keep ON (default). On 4GB it is active and is faster than disk paging; disabling would increase pagefile traffic. Verify with `Get-MMAgent` (e.g., MemoryCompression : True). Do not disable; if anyone did: `Enable-MMAgent -mc`.
- SysMain [SAFE, medium confidence]: disable it on this machine — with ~zero free RAM, SysMain's preloading competes with the game for both RAM and disk, and its HDD-side activity can add stutter while assets stream. Steps: `sc.exe stop SysMain`, `sc.exe config SysMain start= disabled` (as in Microsoft Q&A), reboot later. Verify: `Get-Service SysMain` = Stopped/Disabled; also watch Task Manager for disappearance of System (Memory Compression is separate — don't confuse). Undo: `sc.exe config SysMain start= auto`. Note for report: two credible community sources conflict (disable vs keep); effect here is expected small-positive, not a silver bullet.
- ReadyBoost: no source found in this pass (2024–2026) recommending it; conceptually obsolete with an SSD system disk and irrelevant to this workload; do not spend a USB stick on it (see Gaps — stated as inference/logic, no current citation).
- HDD I/O is the stutter-engine [SAFE]: because the port streams thousands of small reads, a fragmented HDD magnifies seek latency. Ensure the weekly defrag task isn't disabled and run a defrag of the game drive once; expected impact: fewer asset-pop stutter spikes, load-time improvement; verify by comparing the README's "same spot" test before/after. If the SSD has ≥25GB free, moving the game folder to the SSD is the single largest structural improvement available on this machine (port needs ~25GB) — [playgta5 README] space figure.
- Reducing base RAM load [SAFE]: the port README's own low-memory preset (720p/30) plus launching with only Chrome running (already done per brief) is the RAM-side play. Windows 10 memory compression + larger pagefile + fewer background services are the levers inside Windows.

### Gaps
- ReadyBoost status 2024–2026: I found no recent authoritative source in this research pass; guidance above is reasoned inference (SSD makes it pointless), not a citation. Report should phrase it as "no longer recommended by any modern guide; no source found defending it".
- No measured RAM-compression on/off benchmark for 4GB machines found; the keep-ON recommendation rests on Microsoft/TechTarget mechanics (compression faster than disk paging), which is well-established, not on a gaming benchmark.

---

## Windows 10 vs Windows 11 for this hardware (24H2/25H2/26H2 landscape)

### Takeaway
This machine "standard unmodified consumer install" = Windows 10 (verified: Win10 Pro 22H2) because Windows 11 requires 8th-gen Intel and 4GB RAM minimums this 7th-gen CPU fails; Win11 here would be an unsupported bypass install. Staying on Win10 22H2 with ESU (consumer coverage now to Oct 12, 2027) is the supported path; no evidence found that Win11 is faster on this class, and Win11 brings heavier background/security defaults. Don't upgrade for performance; don't bypass-install for performance either.

### Cited Findings
- Windows 10 support ended 2025-10-14; consumer ESU (free via Microsoft account sync / Rewards / $30) originally ran to 2026-10, then Microsoft quietly extended consumer coverage to **2027-10-12**. — [Microsoft Support](https://support.microsoft.com/en-us/windows/deployment/updates-lifecycle/windows-10-support-has-ended-on-october-14-2025), [BleepingComputer](https://www.bleepingcomputer.com/news/microsoft/microsoft-quietly-extends-free-windows-10-esu-support-to-october-2027/)
- Microsoft's Windows 11 hardware requirements: 8th-gen Intel+ (Kaby Lake 7th-gen unsupported), 4GB RAM minimum; machines failing CPU/TPM checks are outside the supported path. — [TechRepublic](https://www.techrepublic.com/article/news-windows-10-support-ended-5-options) (restating Microsoft requirements)
- 2026 landscape: Windows 11 24H2 Home/Pro reached end of support 2026-10-13; 26H2 ("2026 Update") rolling out to eligible devices. Windows 10 Enterprise LTSB 2016 also ended. — [BleepingComputer](https://www.bleepingcomputer.com/news/microsoft/microsoft-windows-11-24h2-home-and-pro-reached-end-of-support)
- Benchmark context (2021, TechSpot): fresh Win10 vs Win11 on a 10th-gen Core i3 were essentially equal; the only meaningful differentiator was VBS (Win11 config with VBS on lost ~7% memory latency and a few % in apps); on the i9 side VBS cost up to 7–10%. — [TechSpot](https://www.techspot.com/article/2349-windows-11-performance)
- Win11 feature set for gaming (Auto HDR, optimizations for windowed games) is documented, but windowed-games optimization targets DX10/11 games — not this WebGPU/DX12-class browser workload. — [Microsoft](https://support.microsoft.com/en-gb/windows/optimizations-for-windowed-games-in-windows-11-3f006843-2c7e-4ed0-9a5e-f9389e535952)
- Machine state (verified): Windows 10 Pro 22H2 build 19045.6466 (fully updated tier for Win10).

### Inferences
- Recommendation: stay on Windows 10 22H2; ensure ESU enrollment (free options exist) so security updates continue to Oct 2027; do NOT do an unsupported Win11 bypass install on 2C/4T/4GB — no source shows a performance benefit, and Win11's background/security budgets on such hardware are unmeasured and likely neutral-to-worse. [SAFE = do nothing / enroll ESU; RISKY = forced Win11 bypass install with no evidence of gain.]
- Verify: `winver` (Win10 22H2 build 19045.x); ESU status in Settings > Update & Security. Undo: n/a.
- IF a clean reinstall were ever considered (out of scope of this brief), a debloated Win10 22H2 remains the best-supported OS for this laptop — but do not recommend reinstalling to a non-technical user without strong cause as the current install is already Win10 with the tuned settings in place.

### Gaps
- No 2024–2026 head-to-head Win10 vs Win11 gaming benchmark on Kaby Lake 2C/4T 4GB found (would be academically interesting but the support situation makes it moot: Win11 is unsupported on this CPU). Win11 24H2/25H2 noted for landscape only.

---

## Startup/services minimal safe debloat + Defender exclusions

### Takeaway
Defender exclusions are officially documented and safe when done with narrow, fully-qualified paths — exclude the game folder (and optionally the localhost-serving folder) plus chrome.exe's full path, not bare image names; verify with MpCmdRun. For services, only SysMain has a decent case on this machine (see Memory section); telemetry (DiagTrack) disabling is common practice with no quantified gaming evidence found; use Task Manager's startup-impact list for the rest. Disabling Windows Search indexing on the HDD game drive is a reasoned I/O-contention measure.

### Cited Findings
- Microsoft Defender official guidance: exclusions exist primarily to mitigate performance impact; don't exclude broad locations (C:\Users, Program Files app folders, temp dirs); a bare file name like "Filename.exe" is NOT a reliable exclusion — use fully qualified paths; image-name process exclusions are broad (any process with that name, any path); process exclusions use `Add-MpPreference -ExclusionProcess "c:\internal\test.exe"`; verify with `MpCmdRun.exe -CheckExclusion -path <path>`. — [Microsoft Learn: process exclusions](https://learn.microsoft.com/en-us/defender-endpoint/configure-process-opened-file-exclusions-microsoft-defender-antivirus), [Microsoft Learn: common mistakes](https://github.com/MicrosoftDocs/defender-docs/blob/e3e647c6514202d72b2ed43f515c706ed1da4a2b/defender-endpoint/defender-endpoint-exclusions-common-mistakes.md), [Microsoft Learn: extension/file exclusions + MpCmdRun](https://github.com/MicrosoftDocs/defender-docs/blob/70c002199d41227d798f67372b7d07cd80631b21/defender-endpoint/configure-extension-file-exclusions-microsoft-defender-antivirus.md)
- A game publisher's support doc (WWZ) documents folder exclusions as a legitimate fix for performance/crash issues and gives the Windows Security GUI path. — [Saber Support](https://support.saber.games/hc/en/world-war-z-aftermath/articles/adding-game-folder-to-the-exception-list-of-windows-defender-and-antivirus-software-pc-9)
- Windows startup management: Task Manager > Startup apps with "Startup impact" sorting is the standard, safe approach. — [Windows Central](https://www.windowscentral.com/microsoft/windows-11/my-top-21-ways-to-improve-windows-11-to-increase-gaming-performance-without-hardware-upgrade)
- SysMain disable commands and the SSD-by-design context — see Memory section citations (Microsoft Q&A x2, insovs, TheWindowsClub).
- Machine context: the game is served from E:\Malik\game\playgta5 over localhost by a local process; assets (~21GB) live on the internal HDD; the port performs many small file reads. — [playgta5 README](https://github.com/alihammoud21/playgta5), [ai.thesatyajit.com](https://ai.thesatyajit.com/articles/gta5-in-the-browser)

### Inferences
- Defender exclusions [SAFE, officially documented; small positive on load times/IO]: add folder exclusions for the game install/serve directory (e.g., `E:\Malik\game\playgta5` or wherever the served assets live) and the HDD asset folder; add real-time-relevant chrome.exe exclusion carefully — prefer the file exclusion `C:\Program Files\Google\Chrome\Application\chrome.exe` (stable path; the versioned subfolder changes) or a folder exclusion over the architecture-wide process exclusion. Steps (elevated PowerShell): `Add-MpPreference -ExclusionPath "E:\Malik\game\playgta5"`; verify `MpCmdRun.exe -CheckExclusion -Path "E:\Malik\game\playgta5"`; remove with `Remove-MpPreference -ExclusionPath "..."`. Risk note: any exclusion reduces protection in that path — keep them narrow; do NOT exclude C:, user profile, temp, or use bare "chrome.exe". Expected impact: reduced Defender CPU spikes while the game streams thousands of small asset reads; magnitude not benchmarked in this pass.
- Windows Search indexing [SAFE, unverified magnitude]: Indexing Options > Modify > uncheck the HDD game drive (keep the SSD indexed), so the indexer's HDD reads don't compete with asset streaming; undo by re-checking. Alternatively set the drive's "Allow files on this drive to have contents indexed" checkbox off in drive properties.
- Telemetry (DiagTrack / "Connected User Experiences and Telemetry") [SAFE, unquantified]: no game-FPS benchmark found; disabling is long-standing community practice and known-safe for a home machine (`sc.exe config DiagTrack start= disabled`; undo: `start= auto`). Present as optional hygiene, evidence-weak.
- Startup apps: trim the Task Manager startup-impact list aggressively [SAFE] — on 4GB RAM, every resident helper (OneDrive syncing the HDD, HP bloatware assistants, Teams/Copilot helpers) directly steals memory and disk headroom from the game; the brief says Copilot/Edge/OneDrive are already closed manually — making those non-starting removes the 3–10 min post-boot HDD/CPU churn that also hurts "first launch" smoothness.
- Also Windows-level: "Best performance" power mode slider (Win10: Settings > System > Power) aligns with the already-applied High Performance plan [SAFE].

### Gaps
- No quantified evidence found (2024–2026) that disabling DiagTrack or Windows Search yields measurable FPS on low-end systems; recommendations above are hygiene-tier, labeled as such. No source found on Defender exclusion FPS gains measured in a browser-game context either — the justification is official docs (exclusions are the sanctioned performance lever) plus the workload's I/O profile.

---

## Community guides for GTA V / browser gaming on 4GB-class machines (2024–2026)

### Takeaway
The relevant "guides" for this specific game are the port's own READMEs (which double as the authoritative performance-tuning doc) plus the M1-port writeups describing the same optimizations this laptop needs (resolution cap, 30 FPS cap, low-memory mode). No dedicated 2024–2026 r/lowendgaming-grade guide for a *4GB* wasm64 GTA V machine was found — because the port itself lists 8GB as its floor; the honest framing is "below stated minimum, tuned to a best-effort state".

### Cited Findings
- playgta5 Windows launcher README (the closest thing to an official guide): enable Chrome hardware acceleration via chrome://settings/system; use the compatibility page at http://localhost:8000/__support/ and choose the "lower-memory 720p / 30 FPS" option; compare `?low=1&fps=60&res=1280x720` vs `?low=1&fps=60&res=960x540` in the same spot after shader preparation; fps cap ≠ guarantee; check active GPU in chrome://gpu; needs ~25GB free space; tested on RTX 3070/32GB. — [playgta5 README](https://github.com/alihammoud21/playgta5)
- Grand-V (sibling port) README: WebGPU + wasm64 memory64 + shared-memory workers; desktop minimum "8 GB (low-memory mode)", 16GB recommended, Windows most tested; frame caps 24/30/60 offered. — [Grand-V README](https://github.com/SebasKitten/Grand-V)
- Same-family, weak-hardware precedent: the community ran the port self-hosted on a MacBook Air M1 offline by applying "reduced graphical presets, a resolution cap, and a 30 FPS frame-rate limiter", and still crashed occasionally at browser memory limits — i.e., caps + low memory mode are the survival kit on modest hardware. — [Ubergizmo](https://www.ubergizmo.com/2026/10/gta-v-ported-browser/)
- Engine structure that dictates where this laptop hurts: 63MB wasm64 engine, ~75 threads, single-threaded asset streamer making small reads, D3D11 calls replayed on WebGPU by a worker, ~21GB assets over HTTP Range (4KB blocks). — [ai.thesatyajit.com](https://ai.thesatyajit.com/articles/gta5-in-the-browser), [Gaming Ideology](https://www.gamingideology.com/how-developers-ported-grand-theft-auto-v-to-web-browsers-using-webassembly/), [ENGINE_INVESTIGATION.md](https://github.com/shadany7824/playgta5/blob/main/ENGINE_INVESTIGATION.md)
- For classic GTA V on this iGPU class, published testing puts the HD 620-family around "playable at ~30 FPS" territory at low settings — context for what "low FPS with stutters" naturally means here. — [TechCenturion](https://www.techcenturion.com/intel-uhd-graphics-620)
- Dual-channel iGPU doctrine (relevant to any RAM purchase decisions): Intel's own support engineers state iGPU bandwidth on a single module is ~half of dual-channel and that dual-channel "provides a noticeable performance improvement"; community HD 620 single-vs-dual tests exist. — [Intel Community](https://community.intel.com/t5/Gaming-on-Intel-Processors-with/Core-Ultra-265K-igpu-single-channel-vs-dual-channel/m-p/1755275), [Brue Computing (HD 620 test)](https://www.youtube.com/watch?v=tQvOXa9K-UE)
- Copyright context for the report: the public playgta5 site was pulled within hours (Oct 2026); the surviving path is a local self-hosted mirror. — [Tom's Hardware](https://www.tomshardware.com/video-games/pc-gaming/gta-v-playable-in-browser-immediately-nuked-unofficial-webassembly-port-built-with-ai-gets-taken-down-within-hours-of-going-live), [VideoCardz](https://videocardz.com/newz/someone-ported-gta-v-to-a-web-browser)

### Inferences
- Ranked best-effort plan synthesized from the above for this exact machine (all previously-detailed risks/undo apply): 1) game-side presets (540p/720p, fps=30 cap, low memory flag) — biggest lever; 2) keep VBS off + SysMain off + narrow Defender exclusions + trimmed startup — system headroom; 3) pagefile to 16GB fixed + compression on — memory headroom; 4) HDD defrag (or move game to SSD if it ever fits) — stutter reduction; 5) Game Mode on, Game Bar capture off, fullscreen — hygiene; 6) optional GCC texture quality=Performance, VSync off, max power — marginal; 7) driver update 2140→2141 — marginal; 8) HAGS/DVMT/Win11/boost-mode — explicitly not applicable. 
- Expectation management for the report: this is below the port's 8GB minimum; even a fully tuned machine will run low-FPS with asset-streaming stutters. The honest promise is "fewer stutters and fewer memory-limit crashes", not "smooth 60".

### Gaps
- No dedicated 2024–2026 lowendgaming/Intel-community guide specific to this browser port on 4GB machines was found (the port is too new and below-spec for guides); the port READMEs above are the best available. If the report-writer needs community anecdote-tier sources, none met the evidence bar for citation here.
