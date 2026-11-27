# 1080p optimization: raise FPS at true 1920x1080 internal render (started 2026-11-21)

Goal from the owner: more FPS at **true 1920x1080** (`res=1920x1080`), not the 960x540 + upscale trick.

| File | What it holds |
|---|---|
| [01-proven-bottleneck.md](01-proven-bottleneck.md) | What the logs prove limits 1080p today (numbers + where they came from) |
| [02-code-hotspots.md](02-code-hotspots.md) | Every code path that runs per draw / per frame, with file:line, and what each costs |
| [03-optimization-plan.md](03-optimization-plan.md) | Ranked list of optimizations: what to change, where, how to test, how to revert |
| [04-test-protocol.md](04-test-protocol.md) | The exact A/B procedure every change must pass before it is called a win |
| [05-measurements.md](05-measurements.md) | Applied steps, measured FPS, verdicts, and what remains |
| [06-web-research.md](06-web-research.md) | Render bundles / indirect draw / storeOp research — why no safe 25 FPS fix exists |
| [07-engine-codebase.md](07-engine-codebase.md) | No engine source exists — only compiled wasm + symbols; draw count cannot be capped from outside |
| [08-re-skill-and-gamesall.md](08-re-skill-and-gamesall.md) | Android RE skill + Gamesall checked — no GTA/RAGE/WASM source; car_game is Unity/IL2CPP Android only |
| [09-wasm-decompile-research.md](09-wasm-decompile-research.md) | How to decompile the wasm: WABT/JEB/Ghidra/diswasm, commands, Memory64 flags, why no C++ source returns |
| [10-rage-engine-formats-repo.md](10-rage-engine-formats-repo.md) | Kalmarv/rage-engine-formats = read-only Rust RAGE file parser; no writers/keys/render, cannot cut draw calls |
| [11-grand-v-repo.md](11-grand-v-repo.md) | SebasKitten/Grand-V = launcher/server only, no game assets or engine; issue #20 confirms renderer is external |
| [12-fps-booster-repo-warning.md](12-fps-booster-repo-warning.md) | "GTA-5-FPS-Booster-2026" = empty marketing repo linking to forum .exe; scam/malware risk, avoid |
| [13-gtav-config-repo.md](13-gtav-config-repo.md) | gamingbyWPG/GTAV_config = native v27 settings.xml; tried GPU string + SamplingMode=3, no FPS gain (-forceResolution overrides) |
| [14-wasm-decompile-results.md](14-wasm-decompile-results.md) | WABT 1.0.41 local decompile done: 591 MB WAT + 191 MB pseudo-C, Memory64 confirmed, no readable C++ |
| [15-wasm-patching-research.md](15-wasm-patching-research.md) | Web research: WAT round-trip, exported `__indirect_function_table` hook, BREWasm/SCRIBE — why none fix draw count safely |
| [16-source-recovery-research.md](16-source-recovery-research.md) | Web research: no tool recovers original C++ from wasm; wasm2c/Ghidra/NotDec/WaDec produce equivalent C only |
| [17-wasm-patch-proof.md](17-wasm-patch-proof.md) | PoC: patched GetGameFrame to return 0 in WAT, recompiled to valid wasm (backup copy only; do not load) |
| [18-nodraw-diagnostic-and-restore.md](18-nodraw-diagnostic-and-restore.md) | Diagnostic no-op DrawIndexed proved draw wall (26-56 FPS, 142 draws); original wasm restored, game relaunched |
| [19-touch-controls.md](19-touch-controls.md) | On-screen W/A/S/D + action buttons + swipe-look overlay added (`?touch=1`), visually verified on PC |
| [20-lan-https-mobile.md](20-lan-https-mobile.md) | LAN HTTPS server on 0.0.0.0:8000 + self-signed cert; phone URL; firewall rule needs admin |
| [21-cloud-gaming-clarification.md](21-cloud-gaming-clarification.md) | Owner wants laptop-rendered streaming; Sunshine+Moonlight / Steam Link needed, not browser hosting |
| [22-web-research-low-preset.md](22-web-research-low-preset.md) | Official low=1/30fps path; ENTER button fixed to Enter; fullscreen launcher now 1024x576 ~30 FPS |
| [23-fullscreen-high-preset.md](23-fullscreen-high-preset.md) | Play-Fullscreen-High.cmd + settings card 6: max shadows/reflections ~7-9 FPS |
| [24-reverse-engineering-solution.md](24-reverse-engineering-solution.md) | **SOLUTION:** full RE method: decompile, extract one function's engine code (tested awk recipe), read/patch, LOD-scale next patch. Original C++ is unrecoverable |

## Status (2026-11-21)
- Best true-1080p so far: **7.4-9.8 FPS** (texture 1, shadow 0, reflection 0, particles/grass/city/LOD 0, slots 5, all worker patches in 14).
- Applied so far: step 4b (skip redundant `SET_SRVS`, backup `wgpu_worker.js.bak-srvskip-20261121`) — no clear gain, kept. Prior note-14 worker patches (proxy fast path, srvEpoch, gpuUid, yield 1024, readback batching) are already active. Results in `05-measurements.md`.
- Still unapplied: 0b counters, step 2 (proxy elimination), step 3 (clear folding), 4c/4d, 5 (`-numCores=3`), 6 (near-1080p + upscale).
- Honest ceiling: 25 FPS needs the worker's ~120 ms/frame cut to ~40 ms (3x). JS tweaks alone are unlikely to reach it; a realistic target for the code-only plan is **11-13 FPS**. Do not promise more until 04 measures it.

## Rules for this work
- One change at a time, backup first (`wgpu_worker.js.bak-<name>-<date>`), `node --check`, then 04's A/B. (U22)
- Patch the **mirror** copy the browser loads: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js`. The root `E:\gta\playgta5\wgpu_worker.js` is NOT loaded.
- Never compare a city scene with a countryside scene. Same spot, same camera, or it isn't an A/B.
