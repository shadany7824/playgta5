# Chrome / Web Audio crackle fixes on weak Windows laptops (i3-7100U class)

Research date: 2026-10-16. Target: the local playgta5 mirror (`C:\Malik\game\playgta5`, served on `http://localhost:8000`) played on this laptop — Intel i3-7100U (2 cores / 4 threads, no Turbo, 2.4 GHz), 4 GB RAM, Intel HD 620, Windows 10 22H2 (19045), Chrome 155 (`155.0.8059.80`).

Companion doc: `port-audio-issues.md` (this folder) covers the port's own audio pipeline, the engine-side "falling behind" diagnosis, and the port's built-in diagnostics. Read that first — this doc picks up where it ends: browser, Windows and power settings that reduce crackle.

Method: every Chromium behavior below was read out of the Chromium source (main branch, 2026-10-16) with file + symbol named so it can be re-checked; Windows/audio guidance cites the linked pages. Read-only research; no game files were changed, and nothing here was measured in a live play session (see §8).

---

## 0. The short version (ranked for this exact laptop)

| # | Fix | Layer | Why it helps here | Cost / risk |
|---|---|---|---|---|
| 1 | Keep playing at `?fps=30&low=1` (already in `Play-Optimized.cmd`) | engine (wasm) | Port doc: crackle = wasm mixer starved, worklet plays literal silence on underrun. On a 2-core CPU this is the dominant cause. | none |
| 2 | Add `--audio-buffer-size=960` to the Chrome line in `Play-Optimized.cmd` (L46–54) | Chrome output | 960 frames @48 kHz = 20 ms device buffer instead of ~10 ms; absorbs scheduler jitter in the audio service. `480` / `1920` are the smaller/larger alternatives. | none; +10 ms latency; full Chrome restart |
| 3 | Plugged in + High performance plan + min CPU 100% + core parking off + power throttling off for `chrome.exe` | Windows power | Stops clock drops (800 MHz steps) and core park/unpark delays that directly cause underruns (gigperformer: "drop-outs in intensive real-time audio processing"). | small admin commands |
| 4 | Disable BD PROCHOT if the CPU throttles to ~800 MHz under load (ThrottleStop) | Windows/CPU | PROCHOT bursts are a classic crackle source on 7100U-class laptops; watch temps. | tool install; hides a protection mechanism |
| 5 | Windows audio device hygiene: enhancements off, 48 kHz default format, exclusive mode unchecked, spatial sound off, ducking "Do nothing" | Windows audio | Removes the shared-mode DSP chain as a glitch/resample source; 48 kHz matches the port's AudioContext so no extra resampling. | none |
| 6 | Driver check with LatencyMon; update Intel GPU + Realtek drivers | drivers | DPC/ISR above ~1 ms glitches audio (WPT doc). Typical culprits: `netwtw` (Wi-Fi), `iaStor`, `igdkmd64`. | free tools |
| 7 | A/B experiments, one at a time: `--raise-timer-frequency`; `--disable-features=AudioServiceOutOfProcess` | Chrome | Marginal; only if 1–6 are not enough. Measure with §5 counters. | experimental |
| 8 | MMCSS `SystemResponsiveness = 10` | Windows | Slightly less CPU reserved for low-priority background work (default 20). | minor |

Do **not** bother with: `--audio-process-high-priority` (enterprise-policy-gated, code path being removed), `--force-wave-audio` (legacy, worse), the JS `AudioContext.renderCapacity` API (removed from the spec), `--disable-gpu` (only if LatencyMon blames the GPU driver). Details in §2.7.

---

## 1. Why this port crackles — two independent layers

1. **Engine layer (wasm).** The wasm mixer writes into a ring buffer; the worklet (`audio-worklet.js`, line 23: `// underrun: silence`) fills any missing frames with **literal silence** — no fade, no resampling, no drift control (port doc §1.1, §5.2). If the mixer thread is CPU-starved, every late frame is an audible gap. **No browser buffer setting fixes this layer**; only more CPU headroom does (fixes 1, 3, 4).
2. **Output layer (Chrome).** The AudioWorklet thread renders 128-frame quanta (Web Audio render quantum; `kWebAudioRenderQuantumSize = 128`, media/base/audio_latency.cc) and Chrome's audio service feeds the WASAPI device in buffer-size chunks. If a deadline is missed here (scheduler jitter, EcoQoS, MMCSS starvation, driver DPC), you get glitch bursts even when the engine is healthy. Fixes 2, 5–8 target this layer.

§5 shows how to tell the two apart with counters before/after each change.

---

## 2. Chrome-side flags (source-verified on main, 2026-10-16)

### 2.1 `--audio-buffer-size=N` — the main browser-side knob

Frames per buffer for the audio streams, at the device sample rate (48 kHz here). Verified chain:

- Declared in `media/base/media_switches.cc` L54: `kAudioBufferSize[] = "audio-buffer-size"`.
- Parsed in `media/audio/audio_manager_base.cc`, `AudioManagerBase::GetUserBufferSize()` (~L870): the string is parsed as int; only `> 0` is accepted, otherwise 0 (= no override).
- Applied on Windows in `media/audio/win/audio_manager_win.cc`, `AudioManagerWin::GetPreferredOutputStreamParameters()` (~L430): `int user_buffer_size = GetUserBufferSize(); if (user_buffer_size) buffer_size = user_buffer_size;` — this **overrides** the hardware-derived buffer size for the WASAPI output stream (it intentionally runs after the min/max clamp). The same file's exclusive-mode branch carries the comment "tune these values for best possible WebAudio performance", i.e. this is the function that sizes WebAudio's device stream.
- Forwarded to the out-of-process audio service in current main: `content/browser/service_host/utility_process_host.cc` L445–451 — "These flags are used by the audio service:" `kAudioBufferSize`, … (Windows-only audio flags follow at L460–466). So the flag does reach the process that actually opens the device.

Value grid (48 kHz):

| Value | Buffer | Latency added vs ~10 ms default | Note |
|---|---|---|---|
| 480 | 10 ms | 0 | default-class; safest minimum to try |
| 960 | 20 ms | +10 ms | **start here** on this laptop |
| 1920 | 40 ms | +30 ms | max sensible for a game |

- Frames are at 48 kHz because the port requests `sampleRate: 48000` (`homepage.html` L447). Keep the Windows device format at 48 kHz too (§3) so nothing resamples; note that `kWebAudioRemoveAudioDestinationResampler` is enabled by default off-Android (`media/audio/audio_features.cc` L62–72), meaning any rate mismatch is resampled in the AudioService — extra CPU this laptop cannot spare.
- Windows shared-mode WASAPI may realign very small requests; don't go below 480. The renderer side targets the hardware buffer size on Windows (`AudioLatency::GetInteractiveBufferSize` returns `hardware_buffer_size` unchanged; audio_latency.cc), and that size flows from the audio service's device parameters — confirm the effective value in `chrome://media-internals` (§5).
- Applies to all audio in that Chrome instance (a second Chrome instance/window started with different flags = different value). Kill all Chrome processes before relaunching with the new flag; verify on `chrome://version` that the command line contains it.

**Suggested edit (not applied — research only):** add `--audio-buffer-size=960` to the flags block in `Play-Optimized.cmd` (L47–53). If the engine-side starvation dominates (port doc §2.3), expect only partial improvement — this knob fixes output-layer jitter, not wasm mixer starvation.

### 2.2 Keep the existing launcher flags — especially the EcoQoS ones

`Play-Optimized.cmd` L51 already disables `UseEcoQoSForBackgroundProcess`, `BatterySaverModeAvailable`, `HighEfficiencyModeAvailable`, `CalculateNativeWinOcclusion`. Keep them: Windows "efficiency mode" (EcoQoS) applied to Chrome processes is the documented cause of robotic/stuttering audio (Jitsi issues #14125 / #15183; standard workaround = `--disable-features=UseEcoQoSForBackgroundProcess`). Note that Chromium's own realtime-audio threads are excluded from EcoQoS by code (`base/threading/platform_thread_win.cc` L437–438 — `kRealtimeAudio` → `desire_ecoqos = false`), so this flag mainly protects everything else Chrome does on 2 cores.

### 2.3 `--raise-timer-frequency` (experimental)

`content/public/common/content_switches.cc` L963–967: "Raise the timer interrupt frequency in all Chrome processes, for experimental purposes… as of Windows 10 2004 the scheduling effects of changing the timer interrupt frequency are not global… See https://crbug.com/1128917". Forwarded to the audio service on Windows (utility_process_host.cc L464). Mechanism sits in `base/time/time_win.cc` (high-resolution timer manager / `timeBeginPeriod`). Try only as a one-variable A/B test (§5); it costs power (the opposite of what Microsoft recommends for battery).

### 2.4 `--enable-exclusive-audio` (advanced, risky)

`media/base/media_switches.cc` L306–312: exclusive-mode WASAPI streaming, "Leads to lower latencies for audio streams which use the AUDIO_PCM_LOW_LATENCY path" (MSDN link in source). In `audio_manager_win.cc` the exclusive branch sets `48000 Hz` + **256-frame buffer** (~5.33 ms) with the comment "tune these values for best possible WebAudio performance… Note that exclusive mode is experimental". Trade-offs on this laptop:

- Bypasses the Windows shared-mode mixer + per-device effects — removes one class of glitches, but those effects are also disabled in §3 anyway.
- 256 frames is an aggressive buffer; on a weak CPU it can make underruns *worse*. The user override from §2.1 runs after the branch, so `--enable-exclusive-audio --audio-buffer-size=960` gives exclusive mode with a sane 20 ms buffer.
- While it holds the device, other apps' audio goes silent; some Realtek/laptop setups won't open exclusive mode at all (Chrome then falls back / no sound).

Keep this as a last resort, test with the §5 counters.

### 2.5 Audio service out-of-process / sandbox — leave at defaults

`content/public/common/content_features.cc`: `kAudioServiceOutOfProcess` and `kAudioServiceSandbox` are **enabled by default** on Windows (L156+). There is no `--disable-audio-service-sandbox` switch in current sources. `--disable-features=AudioServiceOutOfProcess` runs audio inside the browser process — a measuring experiment at most (fewer processes on a 4 GB machine, but the audio thread then shares with heavier browser work); it does not disable the sandbox concept and weakens isolation. Don't ship it as a "fix" without measurements.

### 2.6 Already optimal: thread priorities (don't chase these)

- The AudioWorklet render thread runs with `ThreadType::kRealtimeAudio` by default — `kAudioWorkletThreadRealtimePriority` is **enabled by default** (`third_party/blink/common/features.cc` L144–148), and on Windows `kRealtimeAudio` maps to `THREAD_PRIORITY_TIME_CRITICAL` (`platform_thread_win.cc` L392–394), never EcoQoS.
- The audio service's device thread opts into MMCSS ("Pro Audio" task) + `AVRT_PRIORITY_CRITICAL` via `avrt.dll` (`media/audio/win/avrt_wrapper_win.cc`; used by the low-latency WASAPI output).

Conclusion: Chrome's audio threads are already at maximum priority. Crackle on this machine comes from CPU starvation below them or from the wasm engine side — not from missing priority. No flag "improves" this further.

### 2.7 Dead ends (with evidence, so they don't get re-tried)

- `--audio-process-high-priority` (`content_switches.cc` L973–974) — only forwarded to the audio service when `ShouldEnableAudioProcessHighPriority()` returns true (`content/browser/audio/audio_service.cc` L127–129); the default is `false` (`content/public/browser/content_browser_client.cc` L1050–1054, with `TODO(crbug.com/40242320): Delete…`), and Chrome's override consults only the enterprise policy `AudioProcessHighPriorityEnabled` (`chrome/browser/media/audio_service_util.cc`; policy page: "temporary measure… will be removed"). Enterprise-only, expiring — skip.
- `--force-wave-audio` / `--waveout-buffers` (`media_switches.cc`) — legacy waveOut API; higher latency; only for broken drivers. Skip.
- `--disable-gpu` — makes the port render on the CPU, which this laptop cannot afford; use only as a short isolation test if LatencyMon points at `igdkmd64` (Intel GPU driver).
- JS `AudioContext.renderCapacity` / `AudioRenderCapacity` — **removed from the Web Audio spec** (WebAudio/web-audio-api issue #2614, PR #2624, TPAC 2024 consensus; WebIDLpedia lists it deprecated since 2025-03-05; Chrome never shipped the JS API). Use the DevTools WebAudio panel instead (§5) — it is CDP-based and unaffected.
- Windows "multimedia" registry hacks not listed here (HPET toggles, `bcdedit` timer overrides, disabled drivers) — unverified and risky; intentionally excluded.

---

## 3. Windows 10 audio device settings (fix 5)

Device used: whatever is the real output (internal speakers / 3.5 mm / USB). Do these once:

1. **Disable audio enhancements.** Right-click the volume icon → Sounds → Playback → select device → Properties → **Enhancements → "Disable all enhancements"** → OK. (Microsoft Support, "Fix distorted or crackling audio in Windows", Solution 1.)
2. **Default format 24-bit, 48000 Hz.** Same Properties → **Advanced → Default Format → 24-bit, 48000 Hz** → OK. Matches the port's 48 kHz AudioContext (`homepage.html` L447) and avoids AudioService resampling (§2.1).
3. **Uncheck exclusive mode.** Advanced tab → uncheck **"Allow applications to take exclusive control of this device"**. Prevents another app silently locking the device away from Chrome (winbuzzer guide).
4. **Spatial sound off** (Spatial sound tab / device properties): Windows Sonic etc. adds DSP that can glitch under CPU load.
5. **Communications tab → "Do nothing".** Stops Windows from ducking/attenuating game audio when any app claims "communications" activity. Equivalent registry value if needed: `HKCU\SOFTWARE\Microsoft\Multimedia\Audio` → `UserDuckingPreference` (DWORD) = `3` ("Do nothing").
6. **Disable unused playback devices and stray recording devices** (keengamer no-sound checklist; a known GTA V family cause of audio weirdness). Keep just the device actually in use.
7. **Check services** (services.msc): "Windows Audio" and "Windows Audio Endpoint Builder" must be Running/Automatic (Microsoft Support, Solution 4).
8. **Update the Realtek (or Intel SST) audio driver** from the laptop OEM / Windows Update. Old Realtek drivers are a common crackle source on this class of machine.
9. **Avoid Bluetooth audio while playing** (HFP/A2DP adds latency and dropouts). Wired output preferred; the classic GTA V fix for BT headsets is disabling the "hands-free telephony" service (port doc §6.3).

---

## 4. Power / CPU settings (fixes 3–4, 6, 8) — where the engine-side crackle lives

The wasm mixer must keep a real-time ring fed on a 2-core CPU with no Turbo. Anything that drops clocks or adds scheduling delays causes audible dropouts. Apply (Admin):

```
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c        REM High performance (already in Play-Optimized.cmd L9)
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 100
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 100
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100
powercfg /setactive SCHEME_CURRENT
powercfg /powerthrottling disable /path "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

- **Min processor state 100%** (`PROCTHROTTLEMIN`, GUID 893dee8e-2bef-41e0-89c6-b55d0929964c): stops deep clock drops that show up as mixer underruns.
- **Core parking off** (`CPMINCORES=100`; Microsoft Learn "CPMinCores": "The Core Parking algorithm is disabled if the value of this setting is 100%"). If the setting is hidden in the power-plan GUI, unhide it the gigperformer way: in `regedit`, search for `dec35c318583` (the power setting GUID `0cc5b647-c1df-4637-891a-dec35c318583`) under PowerSettings keys and set `Attributes` = 0, then set "Processor performance core parking min cores" = 100%. Gigperformer's guide explicitly ties this to preventing "drop-outs in intensive real-time audio processing".
- **Power throttling / Efficiency mode off for Chrome** (`powercfg /powerthrottling disable /path …`; Super User Q&A 1763751 — the same mechanism that halves CPU on non-foreground work; alternative: Process Lasso, Super User 1930867).
- **Play plugged in.** Power plans have separate AC/battery values; on battery Windows may override or throttle regardless.
- **BD PROCHOT (fix 4):** if the laptop throttles to ~800 MHz under load (watch with ThrottleStop or HWiNFO during play), that burst *will* crackle. ThrottleStop can disable BD PROCHOT (ThrottleStop guide "BD PROCHOT"; open-source variant: github.com/yyearth/turnoff-BD-PROCHOT). **Caution:** BD PROCHOT is a protection mechanism (bad battery/VRM/thermal signals); only disable it on a ventilated, healthy laptop and keep an eye on temperatures.
- **MMCSS (fix 8, optional/minor):** `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile` → `SystemResponsiveness` (DWORD) = `10`. Microsoft Learn (MMCSS): the value is the % of CPU reserved for low-priority tasks; default 20; "Values below 10 and above 100 are clamped to 20. A value of 100 disables MMCSS." So 10 is the lowest useful value; leave the `Tasks` subkeys alone.
- **LatencyMon (fix 6):** run `LatencyMon` (resplendence.com/latencymon) for ~10 min idle and ~5 min at load; sort by "DPC count / highest execution". WPT's multimedia-optimization exercise explains the mechanism: DPC/ISR execution above ~1 ms directly causes audio glitches. Typical findings on this laptop class: Wi-Fi driver (`netwtw*`) — update or use Ethernet/disable Wi-Fi while playing; storage (`iaStorAC`/`storahci`) — update chipset/storage driver; GPU (`igdkmd64`) — update the Intel HD 620 driver from Intel/OEM. Audio cannot be smooth if a DPC routine hogs the CPU.
- Background load: the `taskkill` list in `Play-Optimized.cmd` (L12–17) plus paused Windows Update / Defender scans (active hours) matter more on 4 GB than on any normal machine.

---

## 5. Diagnostics playbook — measure, don't guess (and tell the layers apart)

1. **`chrome://media-internals`** (Audio tab). Before/after every change, inspect the output stream entry. The audio service writes device stats into the stream log (keys literally include `Delay`, `GlitchCount`, `GlitchDuration` — `media/audio/audio_device_stats_reporter.cc`; histogram family `Media.AudioOutputDevice.AudioService`). Also note the stream's **buffer size** — it should reflect `--audio-buffer-size` (§2.1).
2. **`chrome://histograms`** — search `Media.AudioRendererMissedDeadline3` and `Media.AudioRendererAudioGlitches2` (`services/audio/output_glitch_counter.cc`; the deadline histogram also has a `.LatencyInteractive` variant). These are **per-browser-session** counters: for an A/B test, do a fresh Chrome start per configuration and compare counts after the same 2-minute scenario. Missed deadlines phoning home to the *output layer*; healthy counters while the game still crackles ⇒ engine-side starvation.
3. **DevTools → WebAudio panel** (More tools → WebAudio, in current Chrome; powered by the CDP WebAudio domain, not the removed JS API — see §2.7). Watch the realtime render-capacity graph while playing: sustained near 100% or glitch events = the renderer/graph (wasm engine) is out of CPU, not the device path. Background: web.dev "Profiling Web Audio apps in Chrome".
4. **The port's own log** (`?mem=1`, port doc §4): every 5 s it prints `[page audio] state …, frames written N, read M, peak P`. `written` frozen ⇒ engine not producing; `read` catching up to `written` ⇒ underruns (crackle); `peak 0.000` while running ⇒ mixer silent. This is the cheapest engine-vs-output discriminator.
5. **LatencyMon** (§4) for system jitter during play.
6. **Method:** same save/scenario, one variable per run, note the metrics from 1–4 before/after. Keep a small table; assumptions are how audio fixes turn into superstition.

---

## 6. What can only be fixed in the port's code (not by any setting)

The worklet design has no jitter buffer, no drift compensation and hard silence on underrun (`audio-worklet.js`; port doc §5.2). Real robustness would need: a larger ring target/hysteresis in the worklet, crossfade or zero-order-hold instead of silence, and drift-compensated rate control between the wasm mixer and the AudioContext clock. The mirror ships the JS/WASM, so these are (in principle) patchable locally, but that is a code change, not a setting — out of scope for this research doc. Until then, `?fps` (cap), `?low=1`, `?res` and closing everything else are the levers that protect the wasm mixer.

---

## 7. Sources

Chromium source (read 2026-10-16, `main`; all file paths relative to chromium/src):
- `media/base/media_switches.cc` L54 (`kAudioBufferSize`), L306–312 (`kEnableExclusiveAudio`), `kForceWaveAudio`, `kWaveOutBuffers`, `kTrySupportedChannelLayouts`
- `media/audio/audio_manager_base.cc` ~L870 — `AudioManagerBase::GetUserBufferSize()`
- `media/audio/win/audio_manager_win.cc` — `GetPreferredOutputStreamParameters()` (exclusive branch; user buffer override ~L430); input side L222
- `content/browser/service_host/utility_process_host.cc` L445–451 and L460–466 — switches propagated to the audio service ("These flags are used by the audio service")
- `content/public/common/content_switches.cc` L963–967 (`kRaiseTimerFrequency`), L973–974 (`kAudioProcessHighPriority`)
- `content/browser/audio/audio_service.cc` L121–147 (switch added only when `ShouldEnableAudioProcessHighPriority()`)
- `content/public/browser/content_browser_client.cc` L1050–1054 (default `false`, crbug.com/40242320) and `.h` L1745
- `chrome/browser/media/audio_service_util.cc` — `IsAudioProcessHighPriorityEnabled()` (policy only)
- `content/public/common/content_features.cc` — `kAudioServiceOutOfProcess`, `kAudioServiceSandbox` (defaults on Windows)
- `third_party/blink/common/features.cc` L144–148 (`kAudioWorkletThreadRealtimePriority`, default on), L158–160 (`kAudioWorkletThreadPool`)
- `base/threading/platform_thread_win.cc` L354–455 (`kRealtimeAudio` → `THREAD_PRIORITY_TIME_CRITICAL`; EcoQoS mapping)
- `media/audio/win/avrt_wrapper_win.cc` (+ low-latency WASAPI output) — MMCSS "Pro Audio" + AVRT critical via `avrt.dll`
- `media/audio/audio_features.cc` L62–72 (`kWebAudioRemoveAudioDestinationResampler`, default on off-Android)
- `media/base/audio_latency.cc` — `kWebAudioRenderQuantumSize = 128`; `GetInteractiveBufferSize` (returns hardware size on Windows); `GetHighLatencyBufferSize` (20 ms rounding on Windows)
- `media/audio/audio_output_resampler.cc` — `kMinLowLatencyFrameSize = 2048`
- `services/audio/output_glitch_counter.cc` — histograms `Media.AudioRendererMissedDeadline3`, `Media.AudioRendererAudioGlitches2`
- `media/audio/audio_device_stats_reporter.cc` — `Delay`, `GlitchCount`, `GlitchDuration`, `Media.AudioOutputDevice.AudioService`
- `services/audio/system_info.cc` — device parameters surfaced to renderers (`GetOutputStreamParameters`)

Port/mirror files (read-only):
- `C:\Malik\game\playgta5\homepage.html` L439–458 — `new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' })`, audio start log
- `C:\Malik\game\playgta5\Play-Optimized.cmd` L9, L46–54 — current flags, plan, taskkills
- `audio-worklet.js` ("underrun: silence") — via `port-audio-issues.md` §1.1

Web:
- Web Audio API spec (render quantum 128; `renderSizeHint`): https://www.w3.org/TR/webaudio-1.1/
- RenderCapacity removal: https://github.com/WebAudio/web-audio-api/issues/2614, PR https://github.com/WebAudio/web-audio-api/pull/2624, chromestatus entry https://chromestatus.com/feature/5180333360676864, TAG review https://github.com/w3ctag/design-reviews/issues/843
- Profiling Web Audio (DevTools panel): https://web.dev/articles/profiling-web-audio-apps-in-chrome
- Jitsi EcoQoS: https://github.com/jitsi/jitsi-meet/issues/14125, https://github.com/jitsi/jitsi-meet/issues/15183 (workaround: `--disable-features=UseEcoQoSForBackgroundProcess`)
- Microsoft Support "Fix distorted or crackling audio in Windows": https://support.microsoft.com/en-us/windows/hardware/audio/fix-distorted-or-crackling-audio-in-windows
- MMCSS (SystemResponsiveness semantics): https://learn.microsoft.com/en-us/windows/win32/procthread/multimedia-class-scheduler-service
- CPMinCores: https://learn.microsoft.com/en-us/windows-hardware/customize/power-settings/options-for-core-parking-cpmincores
- Gig Performer core-parking guide: https://gigperformer.com/docs/ultimate-guide-to-optimize-windows-for-stage/coreparking.html
- Power throttling per-app: https://superuser.com/questions/1763751/... , https://superuser.com/questions/1930867/... , https://winaero.com/disable-power-throttling/
- winbuzzer crackle guide (exclusive mode, DPC latency): https://winbuzzer.com/2024/03/22/how-to-fix-audio-popping-or-crackling-in-windows-10-xcxwbt/
- BD PROCHOT: https://www.throttlestopsoftware.com/guides/bd-prochot , https://github.com/yyearth/turnoff-BD-PROCHOT
- DPC >1 ms ⇒ glitch mechanism (WPT exercise 4): https://learn.microsoft.com/en-us/windows-hardware/test/wpt/optimizing-windows-devices-for-multimedia-experiences-exercise-4
- LatencyMon: https://www.resplendence.com/latencymon
- Chrome Enterprise policy (audio process priority, "temporary"): https://chromeenterprise.google/intl/en_uk/policies/audio-process-high-priority-enabled/
- Chromium switch list (third-party reference): https://peter.sh/experiments/chromium-command-line-switches/

---

## 8. What was NOT verified (limitations)

- No live play session in this research: all Chrome claims are source-read, not A/B-measured on this machine. Numbers for "how much" (e.g. `--audio-buffer-size=960` improvement) do not exist yet — §5 is the measuring recipe.
- `--raise-timer-frequency`, `--enable-exclusive-audio`, `--disable-features=AudioServiceOutOfProcess` are deliberately experimental code paths (comments in source say so); Chrome updates can change or remove them.
- BD PROCHOT behavior depends on firmware/EC of this specific laptop; check actual throttle frequency (800 MHz) before disabling anything.
- MMCSS/thread-priority details are per Microsoft docs and Chromium source; the basic/rapid distinctions are documented, but the practical gain on Windows 10 22H2 is small and was not measured here.
- The port offers no audio settings of its own (verified in `port-audio-issues.md` §3) — everything in this doc is host-side.
