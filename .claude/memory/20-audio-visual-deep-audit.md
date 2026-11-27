# 20 — Deep audit: NPC voices + road/wall textures (2026-11-25)

## 1. NPC voices "breaking" — engine-side, NOT the worklet

**Verified live (fresh Chrome session, last 60k log lines):**
- `[page] audio started: 48000 Hz, base latency 0.01` — audio starts, `audio failed` count = **0**
- Served `audio-worklet.js` contains the new carry-over code (`lastL/lastR` present, hard-silence comment gone) → the worklet fix IS live.
- Yet speech is dropped by the ENGINE:
  - `Can't Speak - No voice hash <hash>` × **4** → voice asset hash has no bank/wave mapping in the port's data
  - `Can't Speak - 1.Speech already playing <hash>` × **12** → speech slot still busy, new dialogue rejected
  - Older 250k-line window: 431 such events (same two kinds).
- String table in `game.dcmp:1909-1918` lists all the "Can't Speak" reasons (No speech slot / No voice hash / 1. or 2. Speech already playing / Conversation on going / Deafening / Ambient speech disabled / Speaking Disabled / Context blocked / Dead).
- Relevant engine functions in `engine-function-index.tsv`: `audSpeechAudioEntity_Say` (dcmp line 1636262), `audSpeechManager_GetAmbientSpeechSlot` (1654270), `audSpeechManager_PopulateAmbientSpeechSlotWithPlayingSpeechInfo` (1654362), `rage_audSpeechSound_LoadSpeechMetadata` (629869), `FindBankIdForVoiceAndContext` (630002).
- Research (`research_notes/GTA5 audio fixes/port-audio-issues.md`): "voices sound compressed and weird" is a **known port-wide issue** from aggressively compressed/streamed asset delivery, **no client-side fix known**. Issue #13 = no vehicle engine sounds, also unresolved.

**Verdict:** The worklet carry-over fixes general crackle/underruns, but cannot fix missing voice hashes or a stuck speech slot. Fixing NPC voices requires engine/asset data (voice bank mapping) or an engine patch — NOT a JS audio change. Do not keep "fixing" the worklet for this symptom.

## 2. Road/wall still flat — launch args, not broken texture files

**Verified:** The Chrome process launched by `Launch-Chrome-Mode.cmd` with `MODE` unset was running the **FAST** preset:
`-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=0`
Stage 39 already proved that `shadowQuality=0` + `grassQuality=0` + no anisotropic is the cause of flat road/wall/grass, and that the visual preset fixes it (screenshot-verified).

**Fix applied:** relaunched with visual args (confirmed in Chrome command line):
`-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-anisotropicQualityLevel=2`
(`Play-Chrome-Visual.cmd` sets `MODE=visual`; alternatively set the env before calling `Launch-Chrome-Mode.cmd`).
Fresh run reached the world: `1390 draws/frame @ 7.7 fps`, then `~220 draws @ ~30 fps` in a lighter scene, `draws waiting +0`, `validation +0`.

**User's "texture shader file broken / not connected" suspicion — audited:**
- Mirror `b/8b0b5899ed` has **4,808 `.wgsl`** files + `index.json` (685,955 bytes); shader loading works (pipelines build, 0 failures). Textures are NOT loose files — they come from served game archives via HTTPFS (mirror has only `title/*.png`).
- 207× `grcProgram::ConnectCBuffer()...local TextureSamplerDiffPal clashes with a global` (+78 DepthMapTexSampler, +18 NoiseSampler) — engine translator warnings, present in BOTH fast and visual runs; shaders still compile and render.
- 113× `[wgpu] ... writes colour output(s) N with no render target bound` — `wgpu_worker.js:1277` is only a `logOnce` diagnostic; the pipeline/draw still proceeds (depth/shadow passes). Benign.
- `Warning: Ped 'A_M_M_Tennis_01' parent texture dictionary not found! Disabling this type for HD.` ×6 — one ped's HD texture missing, unrelated to road/wall.

**Verdict:** No broken shader/texture-file connection found. The visible road/wall problem was the FAST quality args; visual preset is now active.

## 3. Environment issues found during audit
- Two python servers were listening on port 8000 (old hung PID 9920 from 11:14 + new PID 3408). Requests could hit the hung one → Node game runs stalled at engine thread 7 with identical 5,098-byte logs for BOTH original and patched wasm. Killed PID 9920; one server (3408) now owns port 8000, HTTP 200. The stall was environment, not the patched LOD wasm.
- Chrome remote-debugging port 9222 was unreachable after the visual relaunch (CDP ECONNREFUSED / timeout) — CDP-based checks (screenshot, reload) unavailable until Chrome is relaunched cleanly with the debug port free.

## 4. What NOT to do next
- Don't keep tweaking `audio-worklet.js` for NPC voices — wrong layer.
- Don't rewrite shader/texture files for road/wall — the fix is launching with visual args; the sampler/render-target warnings are noise.
- Always confirm `MODE=visual` (or the full visual QUALITY_ARGS) before judging visuals.
