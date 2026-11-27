# Next steps (REWRITTEN 2026-11-23 after STEP-1 and STEP-2 PASSED)

> Authority: this file. Older step files are kept for detail but this is the current truth.

## VERIFIED NOW (do not re-investigate)
- **MountAudioPacks solved** (Stage 16): `-rootdir=/game/` in harness.js args.
- **STEP-1 solved**: startMode written into the input block (`game-node.js` `wasm_input_publish_js` Node branch); `[wasm] start mode: story` currently (startMode=1; switch to 2 = sandbox only if a step needs it).
- **STEP-2 solved**: worker crash root cause found and fixed. Root cause: `worker-boot.js` `Object.defineProperty(globalThis,'onmessage',{set(){parentPort.on('message',...)}})` attached a NEW parentPort message listener every time Emscripten reassigned `self.onmessage` (stub → real handler, plus pool worker reuse). Duplicate cmd=2 delivery → `invokeEntryPoint`/`sysIpcThreadWrapper` ran twice on the same pthread → `RuntimeError: table index is out of bounds` → `[RAGE] EnumerationThread` died → main thread waited forever on `CSavegameAutoload::CheckEnumeration`. Fix: ONE bridge listener installed on first set; setter only replaces the `_onmessage` handler slot (backup `worker-boot.js.bak-onmsgfix`).
- **World loads**: `diag-bridgfix.txt` = 0 UNCAUGHT, `CheckEnumeration has finished`, `game skel`, `Init Session`, 177 `Script Name` lines, `Using controller`, 1313 packfile promotions, draws 14 → 502.
- **Real pixels proven**: `node-webgpu\shots\shot_001500.png` (and 000900/001200/001800/002100) — opened and verified: Franklin in a red jacket inside a building with glass walls, another character, HUD minimap. Real world, not black.
- Run command that works: `node-webgpu\run-step2.cmd` (sets WGPU_SHOT_EVERY=300 + WGPU_SHOT_PREFIX, runs node24 harness.js → diag-step2.txt). Server on :8000 must be up (verified 200).
- FPS with screenshots on (readbacks skew it): ~21 FPS, 659–664 draws/frame, 1.7 submits, present 1.0, readback 0.7–0.8. First-world FPS 1–2 before stabilization. Chrome reference at similar draws: ~6–8 FPS.

## STEP 3 — Fair A/B vs Chrome (do this next)
1. Turn screenshots OFF (`WGPU_SHOT_EVERY` unset / 0) — they cost ~0.8 submits/frame.
2. Run Node 300 s at identical settings to the Chrome baseline (640x360 / 960x540 low preset), collect 60+ s of steady `[wgpu] fps:` at >500 draws/frame.
3. Record FPS, draws/frame, worker busy %, gpu wait. Compare only similar draws.
4. Write the table to `engine-code-map\ERROR-TRACE.md` + `02-performance-benchmarks.md`. Answer plainly: is Node/Dawn faster than Chrome and by how much? If not faster, stop before STEP 5.

## STEP 4 — Push to max (one lever per run)
1. Resolution: 640x360 → 960x540 → 1280x720 → 1920x1080 (harness.js `-width/-height`).
2. Quality args, ONE per run: `-textureQuality=2`, `-shadowQuality=2`, `-reflectionQuality=2`, etc.
3. `-frameLimit=0` only for ceiling; 1/2 for real play.
4. Record FPS for every run. Never call a low-setting number "max" (U23). Hardware: i3-7100U 2C/4T + HD 620. If gpu wait > 0, GPU is the limit.

## STEP 5 — Make it playable (ONLY if STEP 3 shows a real gain)
- Node has no window/input/audio. Pick ONE route and prove it: native window from `webgpu` npm package / readback stream to browser / keys into the input block (256 key bytes, then mouse/buttons/focus; see index.html ~189).
- Audio: ring drain + real-time heartbeat already implemented in `game-node.js` `wasm_audio_publish_js`; "[RAGE Audio] Headless mixer" runs.
- Ask the owner before building anything big here.

## STEP 6 — Cleanup + docs
- Switch startMode back to 2 (sandbox), decide which mode is the baseline.
- Gate/remove diagnostics: PATH openat/stat64, MEMSTATE, PROXY/ALIVE, full console (`?console=1` in harness SEARCH — remove unless needed), table/tid logging in worker-boot.js. Backups exist for each patch.
- Remove diagnostic scripts (`add_*.py`, `dump_*.py`, etc.) or move them to a `diag/` folder.
- Create `E:\gta\playgta5\Play-Node-Dawn.cmd` with the final working command, test it.
- Update `CURRENT-PROBLEM.md` top box, `ERROR-TRACE.md` Stage 18, `~/.claude/architectures/playgta5.md`, `memory\README.md`.

## Report format
Step N → what changed (file:line) → exact log/screenshot evidence → verified / not verified → next step.
