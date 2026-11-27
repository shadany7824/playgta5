# PlayGTA5 (browser GTA V) — audio issues, audio settings, and fixes

Research date: 2026-10-16. Scope: the community "GTA V in a browser" port (playgta5.com, taken offline within hours of going live on 2026-10-06), specifically the copy mirrored locally at `C:\Malik\game\playgta5` (build `b/8b0b5899ed`, served by the bundled local server on `http://localhost:8000`).

Everything quoted from the port's own code below was read directly out of this local mirror on 2026-10-16. Other facts carry source URLs. Read-only research: no files in the mirror were changed.

---

## 0. Bottom line first (honesty note)

Direct, port-specific audio **bug reports are thin**. There is no official FAQ (the site is dead; direct fetches return 401 / loading failure), the Telegram/Discord groups are login-walled, and the port exposes **no audio settings of its own** (no volume, no mute, no audio URL parameters — verified). What actually exists:

1. **Open, unresolved issue #13 — no vehicle engine sounds** (other audio works). No confirmed fix; the maintainer's guidance is "click the game to unlock browser audio and check tab mute … a confirmed fix is still pending".
2. **Launch-day press reports: voices sounded "compressed and weird"** — cause is the aggressively compressed/streamed asset delivery; no client-side fix known.
3. **Crackling / dropping output = the engine falling behind** (CPU), per a mirror guide's troubleshooting table and the port's own design (an underrun plays pure silence, it is not smoothed over).
4. **Stuck at 66% "Loading audio metadata"** — a known, unresolved class of boot failure; it is *labeled* audio-metadata, not proven to be an audio-device problem.
5. **"No sound at all" cases are usually fixable**: the port starts audio only after the first click/keypress (browser autoplay policy), and it logs whether audio actually started (see §4 diagnostics).

Since direct coverage is thin, §6 lists the closest analog evidence (native GTA V no-sound fixes for the same engine, browser-ported WebAudio behavior, Emscripten/AudioWorklet docs).

---

## 1. How the port's audio pipeline works (verified in the local build)

The audio path is: **engine mixer thread (inside the wasm engine) → ring buffer in shared wasm memory → `AudioWorklet` processor → speakers.** No sample ever passes through the page's main thread.

### 1.1 The worklet — `mirror\playgta5.com\b\8b0b5899ed\audio-worklet.js` (29 lines)

- Processor name: `game-audio`. Header comment: "*plays the engine mixer's stereo output from the ring buffer in the shared wasm memory (platform/audio/browser_audio_wasm.cpp). Header (uint32 words): write, read, capacity, heartbeat; float data (interleaved L R) at byte 64.*"
- Reads `write`/`read` counters with `Atomics`, copies up to one render quantum of interleaved stereo floats, and on underrun fills the remainder with **zeros — literal silence** (line 23: `// underrun: silence`). There is **no resampling, no fade, no rate control** in the worklet.
- Diagnostics built in: word 4 of the header is the peak sample since the page last looked (×1e6, line 22), and word 3 is a heartbeat incremented per callback (line 25).

### 1.2 The page bootstrap — `homepage.html` (same file as the mirror's `index.html`)

- Audio is **gesture-gated**: "*Browsers only allow audio after a user gesture: the context is created on the first click/key press.*" Handlers: `addEventListener('pointerdown'|'keydown', …)`.
- Context creation (exact code):
  `new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' })` → `ctx.audioWorklet.addModule(BASE + '/audio-worklet.js')` → `new AudioWorkletNode(ctx, 'game-audio', { numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [2], processorOptions: audioPending })` → `node.connect(ctx.destination)` → `await ctx.resume()` plus extra `pointerdown`/`keydown` → `ctx.resume()` listeners.
- `audioPending` is a message that came **up from the engine** (`worker.onmessage: if (ev.data.audio) { audioPending = ev.data.audio; tryStartAudio(); }`) — it carries the shared memory and ring address (`postMessage({audio:{memory, ring, capacity}})`; wasm import `wasm_audio_publish_js(ring, capacity)`).
- If anything throws: `postLog('[page] audio failed: ' + e)`, and `audioStarted` resets so the **next click retries**. On success: `postLog('[page] audio started: ' + ctx.sampleRate + ' Hz, base latency ' + ctx.baseLatency)`.
- The page and `game.js` contain **no volume, mute, or gain control at all** (string scan: `mute` 0, `volume` 0). The only knob is the engine's own settings menu (§3).

Practical consequence of the fixed `sampleRate: 48000`: the engine's audio is 48 kHz (see §5.1), so 48 kHz is the correct match. If the selected Windows output device cannot accept 48 kHz (some virtual devices, "hands-free" Bluetooth profiles, exotic driver modes), **context creation can fail** — that failure prints as `[page] audio failed: …` and there will be no sound until a different output device is chosen.

### 1.3 Loading-screen stage map — `game.js`

From the port's own progress table (regex → percent → label):

| Engine log line matched | % | Label shown |
|---|---|---|
| `/^Audio rpf =/` | 24 | "Mounting archives" |
| `/Using Settings/` | 38 | "Reading settings" |
| `/created D3D11/` | 45 | "Starting graphics" |
| `/CShaderLib::Init/` | 50 | "Loading shaders" |
| `/LOAD_ADDITIONAL_TEXT - finished/` | 56 | "Loading text" |
| `/Starting audio thread/` | 62 | "Starting audio" |
| `/Loading singleplayer metadata/` | 66 | **"Loading audio metadata"** |
| `/^Loading SRL file/` | 72 | "Starting scripts" |
| (further stages follow) | … | … |

So the notorious **66% stall is the "Loading audio metadata" stage** (game metadata unpacking, not the output device). The worklet's ring is only published later, at/after "Starting audio thread" — an audio context that never starts is consistent with a stall before this point.

### 1.4 Asset streaming side — `io_worker.js`

- Comment in the file: "*radio and talk-radio streams (audio/sfx/RADIO_*.rpf) are read as ~33 KB blocks, one after another and each a network round trip, with nothing queued behind for the hints to use…*" Read-ahead is granted to sequential block reads (one track playing).
- Priority: "*…so that the reads the engine blocks on (the audio engine's included) are not queued behind them*" — audio-engine reads are explicitly treated as latency-critical (`HINT_PAR = 96`, `LOW_PAR = 48`, `HINT_QUEUE_MAX = 2000`).
- Consequence: with the **local mirror** this is disk-speed and fine; on the hosted site it was network-bound — a plausible source of radio drop-outs during bandwidth collapse, and one reason localhost is the best way to play now.

### 1.5 Engine-side evidence (read-only string scan of `game.wasm`, 63,201,802 bytes)

Tokens present (raw strings): `sampleRate` (2), `MusicVolume` (5, RAGE audio symbol names such as `audRadioAudioEntity::UpdateReplayMusicVolume`), `Audio3d`/`audio3d` (1), `noAudio` (8), `audioConfig` (3), `AudioSettings` (50), `settings.xml` (2), `RAGE Audio … "Don't initialise any audio hardware for output"` (developer flag description), `"Starting audio thread"`, `"Audio rpf"`, and a config path string `audio:/config/dlc_gtao_speech.dat config/speech.dat audioconfig.dat … audio:/config/game.dat`. Tokens **absent**: `audioQuality`, `masterVolume` — the guessed engine flags do not exist as strings in this build.

---

## 2. Reported audio problems and what is actually known

### 2.1 No vehicle engine sounds (all other audio OK) — GitHub issue #13 — unresolved

- Issue: https://github.com/alihammoud21/playgta5/issues/13 — "No engine sounds broken minimap?" (opened 2026-10-12; still open, no confirmed fix).
- Maintainer/hub guidance (README, quoted via https://www.repoburst.com/repo/alihammoud21/playgta5): "*No vehicle engine sound / broken minimap: click the game to unlock browser audio and check tab mute. If other sounds work, identify an affected vehicle/location and any failed audio/texture request. Verify files and compare Story/Sandbox. Include a minimap screenshot and first error in issue #13; a confirmed fix is still pending.*"
- The same README lists as **known unresolved engine limitations**: "*Minimap roads, vehicle audio/entry animations and the reported minimap initialization crash remain unresolved.*"
- Assessment: since the ring/worklet path demonstrably plays *all other* audio, this failure mode is engine-side (which sound banks/events are loaded and triggered), not a browser audio bug. No workaround beyond the click-to-unlock and file-verification steps. Reproduce in both Story and Sandbox and report to #13 with an F12 console capture.

### 2.2 Voices "compressed and weird" — launch-day reports, no fix

- TweakTown (2026-10-06): "*…it ran smoothly enough and didn't seem overly compressed (save for the voices, which did sound compressed and weird).*" — https://www.tweaktown.com/news/113929/gta-v-was-briefly-playable-in-a-web-browser-and-it-reportedly-ran-smoothly-but-its-now-been-taken-down/index.html
- handheld.guru (2026-10-07): "*…the audio experience suffered from noticeable compression.*" — https://handheld.guru/browser-based-gta-v-runs-smoothly-but-vanishes-hours-after-launch/
- Cause (as reported): the build boots from ~700 MB of compressed assets and "*the assets are aggressively compressed, so the game pauses and streams in higher quality chunks as you travel*" — https://www.gizdev.com/play-ported-gta-5-in-your-browser/ . If voices sound lossy/robotic in the local mirror too, it is encoded that way in the asset set; there is no client-side setting that changes it. Note the caveat: no A/B measurement against the native game was published.

### 2.3 Crackling, stuttering, drop-outs while playing — "the engine is falling behind"

- Mirror guide table (2026-10-14): "*Sound crackles or drops — The engine is falling behind — Lower other load, close tabs, and use a more powerful GPU.*" — https://onlinegta5.com/gta-v-online-browser/
- Launch guide: "*Laggy Audio / Low FPS: Close heavy background apps, Discord hardware acceleration, and video streaming tabs to free up system memory and VRAM.*" — https://www.ogmodz.com/blog/how-to-play-gta-5-browser-playgta5-guide
- Mechanism (from the verified code in §1): the wasm mixer thread must keep the ring fed; the worklet plays **strict silence** for any undelivered frames — so CPU starvation produces audible gaps/crackle, never smoothing. Anything that pushes CPU/GPU over budget (uncapped fps, other tabs/apps, shader compiles) can cause it.
- Concrete mitigations, easiest first:
  1. Use the low-profile preset: `?low=1&fps=30&res=1280x720` (optionally `&shadows=0`). On machines reporting ≤4 GB `deviceMemory` the page already auto-enables `low` (verified in `homepage.html`).
  2. Keep the fps cap on (the default `-frameLimit` caps at 60; `30` halves engine CPU). Avoid `?fps=0` (uncapped, diagnostics only) — it increases the risk.
  3. Close other apps and tabs; turn off Discord hardware acceleration and video playback in other tabs (OGmodz).
  4. Keep the game tab focused/visible while playing (background throttling starves the engine further).
  5. Do **not** use `?nohints=1` — it disables the read-ahead built specifically to keep the audio engine's reads flowing; it is a diagnostics switch.
  6. On the local mirror, prefer serving from a fast disk and leave the server window alone (radio tracks stream as ~33 KB sequential reads).

### 2.4 Stuck at 66% — "Loading audio metadata"

- Issue: https://github.com/alihammoud21/playgta5/issues/6 (stuck at 66%; a sibling report sits at 24%). Mirror support page: "*Do not treat missing assets, a 66% audio-metadata stall, or a black world as an FPS problem.*" — https://gta5-87g.pages.dev/__support/
- Known attempts (none confirmed): relaunch from scratch, update the browser + GPU driver, verify hardware acceleration (`chrome://gpu`), try the lower-memory link, verify the mirrored files. Support page advice for a related freeze: "*Close every game tab, stop the local server with Ctrl+C if you use one, and launch again. Update the browser and graphics driver…*" (https://gta5-87g.pages.dev/__support/).
- Honest assessment: the stall is *labeled* "Loading audio metadata" because the engine's last printed step is that one, but no source establishes the root cause. Treat it as unresolved.

### 2.5 No sound at all — the fixable case

Ordered checklist (steps 1–3 are port-specific, verified in code; the rest are device-side and drawn from the analog sources in §6):

1. **Click once inside the game area (or press a key).** Audio cannot start before that by browser policy; the code creates the AudioContext on the first `pointerdown`/`keydown` only. Same guidance in the hub README ("*click the game to unlock browser audio*") and OGmodz ("*click anywhere inside the game frame. Modern browsers require explicit user interaction before allowing audio output*").
2. **Check the browser tab's mute state** (speaker icon on the tab) and the Windows volume mixer entry for the browser — the hub FAQ explicitly lists "check tab mute" (README via https://www.repoburst.com/repo/alihammoud21/playgta5).
3. **Check the log** (§4): with `?log=1` the page reports `[page] audio started: 48000 Hz, base latency …` or `[page] audio failed: …`. If "failed", the output device likely refused a 48 kHz context — switch the Windows default output to a standard device (not a Bluetooth hands-free/virtual device) and click again.
4. Check in-game **Settings → Audio**: keep the engine's own volumes up and "Mute Audio on Focus Loss" **off** (native GTA V menu options; see §3).
5. Make the default Windows playback device the one actually in use; disable unused playback/recording devices (one documented case of GTA V silence was a recording device conflict — keengamer, §6).
6. If using Bluetooth: disable the hands-free/telephony service on the device (the classic "no game audio on BT headset" fix; steps in the YouTube guide, §6). If voices are pitched/tinny, also try toggling Windows Sonic/spatial audio both ways (same guide).
7. Play in the visible, focused tab with sound not routed through an exotic chain; audio in a browser needs the page to stay active.
8. For vehicle engine sounds specifically missing while everything else plays: that is the open bug in §2.1, not a device problem.

---

## 3. The port's own audio settings (what exists, honestly)

**In-game (engine) settings.** The port runs the game's real frontend, so the engine's own **Settings → Audio** menu is the only place volumes/mute live (the page itself has no audio UI, verified §1.2). Engine strings in `game.wasm` include `AudioSettings`, `Audio3d`, `MusicVolume`, `audioConfig` (`audio:/config/…`), and `settings.xml`, consistent with native GTA V's Audio tab — whose options are SFX Volume, Music Volume, Output device, and "Mute Audio on Focus Loss" (options list from the native-GTA V guides in §6). I could not click through the menu in a running session during this research; treat presence as expected-but-unverified, and note the port's virtual userdata persists these settings like saves ("Story Mode continues from the newest savegame" — `homepage.html`).

**URL parameters — complete list parsed by the port** (from `homepage.html`, `wgpu_worker.js`, `io_worker.js`), none of which is audio-specific:

`args`, `console`, `cores`, `dbg`, `fixed`, `fps`, `keep`, `limits`, `log`, `low`, `map`, `mem`, `mode`, `newgame`, `nocache`, `nogpu`, `nohints`, `nopack`, `nosw`, `record`, `res`, `scale`, `shadows`, `shot`, `shotrt`, `slots`, `syncpipelines`, `trace`, `verbose`.

- There is **no** `mute`, `volume`, `audio`, `sampleRate`, or audio-device parameter in any of the three files.
- `?args=-flag1,-flag2=value` is the only escape hatch: it appends raw **engine command-line flags** (`homepage.html` comment: "*?args=-flag1,-flag2=value (added to the engine command line)*"). No audio flag is documented, and the guessed flags `-audioQuality` / `-masterVolume` do **not** exist in this build (string scan, §1.5). Do not pass unknown flags blindly.

**Engine command line the page builds by default** (verified): `-rootdir=/game/`, `-wgpu` (unless `?nogpu`), `-nodisplaycalibration`, `-noSocialClub`, `-pc:nosocialclub`, `-nonetwork`, `-output`, `-width=…`, `-height=…`, `-forceResolution`, `-Script_all=warning`, `-replay_all=warning` (unless `?verbose`), `-fastscriptcore`, `-frameLimit=…` (2=30 fps, 1=60 fps, 0=uncapped), `-numCores=N` (≤2 cores only), plus `LOW_ARGS` quality flags (`-textureQuality=0`, `-pedVariety=0`, `-vehicleVariety=0`, `-shadowQuality=…`, `-reflectionQuality=0`, `-particleQuality=0`, `-grassQuality=0`, `-cityDensity=0`, `-lodScale=0`) and any `?args=`. **No audio flags are used, and none are documented.**

**Dev-only audio switches found in the wasm** (evidence only, not usable): RAGE developer flag descriptions such as "Don't initialise any audio hardware for output" exist as strings in `game.wasm`; no page parameter maps to them.

---

## 4. Built-in diagnostics (concrete, verified)

The port logs enough to tell apart "engine is not producing audio" from "browser is not playing it":

| What to look for | Meaning |
|---|---|
| `[page] audio started: 48000 Hz, base latency …` | Output path is live (context + worklet created). |
| `[page] audio failed: <reason>` | Context/worklet creation failed — usually the output device refusing 48 kHz; switch device, click again. |
| With `?mem=1`, every 5 s: `[page audio] state <running/suspended>, frames written N, read M, …, peak P` | `state: suspended` → click again (resume). `written` not advancing → **engine side** (mixer thread not producing; loading not finished / engine bug class). `written` advancing and `peak 0.000` → engine mixer is silent (e.g., vehicle-sound bug #13, or in-game volumes at 0). `peak > 0` but inaudible → device/mute path (tab mute, Windows mixer, wrong output device). `read` catching up to `written` mid-play → transient underruns = the crackle class (§2.3). |

Where the logs go: `postLog` posts to the local server's `/log` endpoint when `?log=1` is on (`const remoteLog = q.get('log') === '1'`), and the loading-screen log line plus the browser console do not depend on it. So the recipe on the local mirror is: open `http://localhost:8000/?log=1&mem=1` (add `&verbose=1` if needed), reproduce, then read the server window's log. The worklet additionally maintains a heartbeat (header word 3) and a peak meter (word 4, ×1e6) that any instrumentation can read from the shared buffer.

---

## 5. Context and technical background (why it behaves this way)

### 5.1 Sample rate and asset format

- The page requests a 48 kHz AudioContext (§1.2), matching the game's audio data: the deep-dive article (via search index only — the live page returned **HTTP 402** on 2026-10-16, matching the note in `reports\GTA5 web port performance techniques.md` line 86) describes `x64/audio/tracks/admin_gun.awc` as a multichannel `ADAT` stream, two channels at **48,000 Hz**, 16 blocks of 32,768 bytes, codec id 12 at ~43 kb/s — "*very likely Opus*" (the engine carries `rage::audDecoderOpus`). Source: https://ai.thesatyajit.com/articles/gta5-in-the-browser (unverified copy).
- The same article lists `x64/.../sfx` at 1.88 GB across 54 files including 19 radio-station banks — consistent with the local mirror's `snapshot\asset-evidence.json` (`x64/audio/audio.rpf`, `sfx/RADIO_*.rpf`).
- Native-family analog: GTA V users have reported pitched-down/tinny voices when the Windows output device runs 44.1 vs 48 kHz — matching the device to 48 kHz is the standard fix (see §6). The port already requests 48 kHz, so it is the *device side* that should be normalized if voice pitch sounds wrong.

### 5.2 What the design does not have

- **No drift control**: the worklet copies a fixed read/write ring with no rate adjustment. The standard robust design (used in emulator projects) adds dynamic rate control for clock drift; here, long sessions *could* in theory drift toward periodic underruns if clocks diverge. No user reports of this for the port were found — listed as a theoretical risk, not a known issue.
- **No smoothing/jitter buffer**: any shortfall is hard silence. A tiny extra buffer is the classic cure for crackle in WebAudio game ports but cannot be added without changing the port's code.

---

## 6. Closest analog evidence (direct coverage is thin)

Labeled clearly: these are not about this port unless stated.

1. **Emscripten audio porting** — the canonical constraints: the main loop must yield for audio to keep up; browsers auto-resume Web Audio after a gesture; sample rate is dictated by the browser/device. https://emscripten.org/docs/porting/Audio.html
2. **Chrome AudioWorklet design patterns** — ring buffer + underrun handling best practice; this port follows the pattern (and the printed report in `research_notes\GTA5 web port performance techniques\web-platform-techniques.md` §4.3 already cites it). https://developer.chrome.com/blog/audio-worklet-design-pattern
3. **Native GTA V / GTA V Enhanced "no sound" fixes (same RAGE engine family)** — in-game Settings → Audio (raise SFX/Music; set Output to the real device; turn **off** "Mute Audio on Focus Loss"), Windows volume mixer per-app unmute, disable unused playback **and recording** devices, update DirectX/audio drivers, verify game files: https://www.keengamer.com/articles/guides/7-ways-to-fix-grand-theft-auto-vs-sound-not-working-on-a-windows-pc/ and https://www.youtube.com/watch?v=vmFlOftgFt4 (also covers: Windows Sonic toggle both ways, Bluetooth "hands-free telephony" off, mono-audio toggle).
4. **Rockstar official support — "Failed to initialize audio hardware"** (GTA V Enhanced): device driver and configuration issues; "*If you only have stereo speakers do not set your Windows speaker settings to 5.1.*" https://support.rockstargames.com/articles/7h8CvZTcLgyRIaPxUFCkm0/grand-theft-auto-v-enhanced-on-pc-failed-to-initialize-audio-hardware-error
5. **Steam Deck: GTA V crackle then total audio loss, fixed via output-volume quirk** (Echo Sink at 100 %) — an example of hard-to-guess device-side audio failures: https://steamcommunity.com/app/1675200/discussions/1/3395175706747277749/
6. **Browser-streamed GTA V (cloud gaming) "no audio"** — answer: "*you need to turn it on in the browser window*"; i.e., browser-level mute/unmute, the same class as the port's click-to-unlock: https://www.reddit.com/r/BoosteroidCommunity/comments/ukfxke/gta_5_has_no_audio/
7. **RAGE audio design (GDC 2014 slides, "The Sound of Grand Theft Auto V")** — official PDF of the engine's audio architecture: https://gta.com.ua/img/news/sound-of-gta5-gdc2014.pdf

---

## 7. Sources (all, with role)

Port code (local mirror, read 2026-10-16; build `b/8b0b5899ed`):
- `C:\Malik\game\playgta5\mirror\playgta5.com\b\8b0b5899ed\audio-worklet.js` — the worklet (all §1.1 quotes)
- `C:\Malik\game\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js` — stage table, `wasm_audio_publish_js`, no mute/volume strings
- `C:\Malik\game\playgta5\mirror\playgta5.com\b\8b0b5899ed\io_worker.js` — radio streaming comments (§1.4)
- `C:\Malik\game\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.wasm` — string scan (§1.5)
- `C:\Malik\game\playgta5\homepage.html` (= mirror `index.html`) — AudioContext bootstrap, URL params, diagnostics routing (§1.2, §3, §4)
- `C:\Malik\game\playgta5\snapshot\asset-evidence.json` — `x64/audio/*.rpf` inventory
- `C:\Malik\game\playgta5\reports\GTA5 web port performance techniques.md` — prior report; its line 86 flags ai.thesatyajit.com as HTTP 402
- `C:\Malik\game\playgta5\research_notes\GTA5 web port performance techniques\web-platform-techniques.md` — prior notes; AudioWorklet pattern pointer (§4.3)

Community/official pages:
- https://github.com/alihammoud21/playgta5/issues/13 — no engine sounds (open)
- https://github.com/alihammoud21/playgta5/issues/6 — 66 % stall
- https://www.repoburst.com/repo/alihammoud21/playgta5 — README quotes (engine limitations; click/tab-mute guidance)
- https://gta5-87g.pages.dev/__support/ — mirror support page (66 %/"not an FPS problem"; relaunch advice)
- https://onlinegta5.com/gta-v-online-browser/ — "Sound crackles or drops … engine is falling behind"
- https://www.ogmodz.com/blog/how-to-play-gta-5-browser-playgta5-guide — click-to-activate audio; close background apps for laggy audio
- https://www.tweaktown.com/news/113929/gta-v-was-briefly-playable-in-a-web-browser-and-it-reportedly-ran-smoothly-but-its-now-been-taken-down/index.html — voices "compressed and weird"
- https://handheld.guru/browser-based-gta-v-runs-smoothly-but-vanishes-hours-after-launch/ — noticeable audio compression
- https://www.gizdev.com/play-ported-gta-5-in-your-browser/ — 700 MB compressed boot; chunk streaming; archive/mirror links (https://web.archive.org/web/20261006055917/https://playgta5.com/, https://gta.deloskiyt.pl/, https://fiveplay.lol/)
- https://deonmenezes.com/resources/gta5 — "Sound went through shared memory" summary
- https://ai.thesatyajit.com/articles/gta5-in-the-browser — deep technical article (audio track/codec details §5.1); live page returned HTTP 402 on 2026-10-16 — content seen was via a search-index copy, treat as unverified

Analog:
- https://emscripten.org/docs/porting/Audio.html — Emscripten audio constraints
- https://developer.chrome.com/blog/audio-worklet-design-pattern — worklet/ring-buffer design
- https://support.rockstargames.com/articles/7h8CvZTcLgyRIaPxUFCkm0/grand-theft-auto-v-enhanced-on-pc-failed-to-initialize-audio-hardware-error — audio device config (stereo vs 5.1, drivers)
- https://www.keengamer.com/articles/guides/7-ways-to-fix-grand-theft-auto-vs-sound-not-working-on-a-windows-pc/ — native no-sound checklist
- https://www.youtube.com/watch?v=vmFlOftgFt4 — Windows Sonic/mono/BT hands-free fixes
- https://steamcommunity.com/app/1675200/discussions/1/3395175706747277749/ — device quirk causing crackle→silence
- https://www.reddit.com/r/BoosteroidCommunity/comments/ukfxke/gta_5_has_no_audio/ — browser-window mute analog
- https://gta.com.ua/img/news/sound-of-gta5-gdc2014.pdf — GDC 2014 RAGE audio slides

---

## 8. What could not be verified (limitations)

- playgta5.com is dead (401 / never finishes loading), so no first-party FAQ or official settings documentation exists to cite; the Telegram/Discord communities are login-walled and could not be read (t.me/s/playgta5regen, t.me/fivestarport render a JS stub; discord.gg/ACgUGFwm4 not fetchable).
- The in-game Settings → Audio menu was not opened in a live session (research-only, no playthrough); its presence is inferred from engine strings + the fact the port runs the real frontend.
- Issue #13 has no confirmed fix; nothing in the research suggests one exists as of 2026-10-16.
- The "66 % = audio metadata" label is the port author's own stage name; no source establishes the root cause.
- No port-specific report of delayed/desynced audio was found; the only concrete claim in that space is the launch-day voice-compression report. Clock-drift behavior is a theoretical risk of the design (§5.2), not an observed issue.
