# AUDIO — how it works, what's broken, what fixes it

Written: 2026-11-23. Scope: this port (mirror `b/8b0b5899ed`) on Node AND Chrome.
Companion research: `E:\gta\playgta5\research_notes\GTA5 audio fixes\port-audio-issues.md` and
`chrome-webaudio-crackle-fixes.md` (read those for the full evidence + source URLs).

---

## 1. The audio pipeline (verified from the mirror code)

```
wasm engine mixer thread  ──writes──►  ring buffer in SHARED wasm memory
                                          │  header (uint32 x8) @ ring+0:
                                          │    [0]=write  [1]=read  [2]=capacity
                                          │    [3]=heartbeat  [4]=peak(x1e6)
                                          │  float32 interleaved L,R  @ ring+64
                                          ▼
                              AudioWorklet "game-audio"  (audio-worklet.js, 29 lines)
                                          │  copies up to 128 frames (one render quantum)
                                          │  UNDERRUN => fills the rest with LITERAL ZEROES
                                          ▼
                                   ctx.destination  →  speakers
```

Key facts:
- **Sample rate is fixed 48000 Hz.** `new AudioContext({sampleRate:48000, latencyHint:'interactive'})`.
  The engine audio data is 48 kHz too, so there is no resample — *unless the Windows device
  itself is not 48 kHz, in which case Chrome resamples* (extra CPU + possible pitch weirdness).
- **Audio is gesture-gated.** The AudioContext is only created on the first `pointerdown`/`keydown`.
  Before that: guaranteed silence. If creation throws, `audioStarted` resets and the *next* click retries.
- **No page-level volume/mute at all.** String scan: `mute` 0, `volume` 0. The only knobs are the
  engine's own Settings → Audio menu (SFX/Music volume, "Mute Audio on Focus Loss").
- **The ring is drained by whoever reads it.** In the browser that is the worklet. On **Node** the
  worklet does not exist, so the ring must be drained manually — see §3.

## 2. The two independent failure layers (this is the important part)

| Layer | Who is at fault | Symptom | Fix lives where |
|---|---|---|---|
| **A. Engine/mixer (wasm)** | mixer thread CPU-starved, ring not fed | gaps, clicks, crackle; `written` frozen in log | more CPU headroom: `?fps=30`, `?low=1`, close apps, power plan |
| **B. Output (Chrome/WASAPI)** | scheduler jitter, EcoQoS, buffer too small, Windows DSP chain | glitch bursts even when engine is fine | `--audio-buffer-size=960`, Windows device hygiene, power settings |

**How to tell them apart cheaply:** open the page with `?mem=1` — every 5 s it prints
`[page audio] state <running|suspended>, frames written N, read M, …, peak P`.
- `written` frozen ⇒ **layer A** (engine not producing).
- `read` snapping up to `written` mid-play ⇒ **underruns = crackle** (layer A, or clock drift).
- `peak 0.000` while `state running` ⇒ mixer is silent (engine bug / volumes at 0).
- `peak > 0` but you hear nothing ⇒ **layer B** (tab mute, Windows mixer, wrong output device).
- `state suspended` ⇒ click the page again.

## 3. Node-specific: the ring was NEVER drained (fixed, keep this)

On Node, `wasm_audio_publish_js(ring,capacity)` originally **early-returned** —
`if (typeof process!=="undefined" && process.versions.node) return;`
So the engine wrote into the ring forever, `write` raced past `read`, and the ring wrapped /
filled. There is no AudioWorklet in Node, so we drain it ourselves.

Patch applied by `E:\gta\playgta5\node-webgpu\apply_audio_drain.py` (backup `game-node.js.bak-step1-audio`):
on Node it stores `globalThis.__audioRing/__audioCap` and starts a `setInterval(10ms)` that
reads `write`/`read`, advances `read` to `write` (discarding the PCM — Node has no speakers
path yet) and bumps the heartbeat.

Follow-up patch `fix_audiohb.py` (backup `game-node.js.bak-audiohb`): the heartbeat was
incremented by **1 per 10 ms tick** (= 100/s), but the engine treats heartbeat as a
**sample-clock at 48 kHz / 375 frames** (= 128/s). Now it computes
`ticks = round(dt_ms * 375 / 1000)` from wall-clock `Date.now()` so the engine's audio
clock advances at the right rate. Without this the engine's audio timeline drifts vs. real time.

> So on Node today: audio **clock + ring drain are correct**, but **no sound is produced**
> (we discard the PCM). Producing real sound in Node needs a native output (WASAPI/XAudio2) —
> the toolchain already has `xaudio2.h` under `toolchain/mingw64`.

## 4. Chrome side — what to change (the actual fixes)

Already in `Launch-Chrome-Mode.cmd` line 18: **`--audio-buffer-size=960`**
(960 frames @48 kHz = 20 ms device buffer; absorbs scheduler jitter; +10 ms latency).
Alternatives: 480 (10 ms, min safe) / 1920 (40 ms, max sensible for a game).
Verify it took effect on `chrome://version` (command line) — Chrome must be fully restarted.

Also already in the launcher (keep them — they matter more than people think):
- `--disable-features=UseEcoQoSForBackgroundProcess` — Windows "efficiency mode" is the
  documented cause of robotic/stuttering audio.
- High-performance power plan + `powercfg /powerthrottling disable` for `chrome.exe`.

**Ranked remaining Chrome-side fixes** (from `chrome-webaudio-crackle-fixes.md` §0):
1. `?fps=30&low=1` — protects the wasm mixer (layer A, dominant cause).
2. `--audio-buffer-size=960` — done.
3. Plugged in + High performance + min CPU 100% + core parking off + power throttling off.
4. Windows device: enhancements OFF, default format **24-bit / 48000 Hz**, exclusive mode UNCHECKED,
   spatial sound OFF, Communications = "Do nothing".
5. Disable unused playback *and* recording devices.
6. LatencyMon: DPC > 1 ms (typical: `netwtw` Wi-Fi, `iaStor`, `igdkmd64`) glitches audio directly.

**Do NOT bother with:** `--audio-process-high-priority` (enterprise-gated, being removed),
`--force-wave-audio` (legacy/worse), `AudioContext.renderCapacity` (removed from the spec),
`--disable-gpu`.

## 5. What ONLY a code change can fix (the real remaining bug)

The worklet (`audio-worklet.js`) has:
- **no jitter buffer** — it copies whatever is in the ring right now;
- **no drift compensation** — ring producer clock (engine) vs `AudioContext` clock are never
  reconciled, so long sessions drift toward periodic underruns;
- **hard silence on underrun** (line 23 `// underrun: silence`) — no fade, no zero-order-hold
  carry-over, so every late frame is an audible click.

Fixes that belong in `audio-worklet.js` (all local, all patchable):
1. **Target-depth hysteresis** — hold a target of e.g. 2–3 quanta; if `avail` dips below
   half the target, repeat the last frame (or crossfade) instead of writing zeroes.
2. **Carry-over instead of silence** — on underrun, re-emit the last stereo frame
   (zero-order hold). Removes the hard click at near-zero cost.
3. **Drift compensation** — nudge the read pointer by ±1 frame when `avail` sits above/below
   target for many consecutive callbacks (classic emulator dynamic rate control).

> These are the difference between "crackly" and "clean" on a 2-core CPU. They are the
> next code lever for audio, independent of anything GPU-related.

## 6. Known engine-side audio bugs (NOT fixable client-side)

- **Issue #13 — no vehicle engine sounds** (other audio works). Open, no confirmed fix.
  Engine-side (which sound banks/events load), not a browser bug.
- **Voices sound "compressed and weird"** — launch-day press reports; caused by the
  aggressively compressed asset set. No client-side setting changes it.
- **66% "Loading audio metadata" stall** — boot failure class; labeled audio-metadata but
  the root cause is not established. Not an output-device problem.
- Log noise like `Failed to find audio:/config/test_sounds.dat54` / animal-params warnings
  are benign — they appear even in healthy runs.

## 7. Diagnostics cheat-sheet

| Goal | How |
|---|---|
| See engine audio activity | `game-log.txt` → lines with `[RAGE Audio]`, `LoadBank`, `Triggering deferred sound` |
| Live counters (Chrome) | open `http://localhost:8000/?log=1&mem=1`, read server log for `[page audio] state …` |
| Confirm worklet started | `[page] audio started: 48000 Hz, base latency …` (vs `audio failed: …`) |
| Output-layer glitches | `chrome://media-internals` → `GlitchCount`, `GlitchDuration`; `chrome://histograms` → `Media.AudioRendererMissedDeadline3` |
| Ring header peek (Node) | `new Int32Array(wasmMemory.buffer, __audioRing, 8)` → `[write, read, cap, heartbeat, peak]` |

## 8. State as of writing

- Node: ring drain + heartbeat clock **patched and in place** (`game-node.js`), no speakers yet.
- Chrome: `--audio-buffer-size=960` + EcoQoS-off **already in the launcher**; worklet still the
  original hard-silence version (§5 fixes NOT yet applied).
- `cdp-audio.js` written to read AudioContext state over CDP port 9222 — first run got
  `ECONNREFUSED` because Chrome was not launched with `--remote-debugging-port=9222`.
  Relaunch via `Launch-Chrome-Mode.cmd` (it sets the port + a non-default `--user-data-dir`)
  before using CDP.
