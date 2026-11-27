# Project memory â€” PlayGTA5 (GTA V browser port)

> **CURRENT STATUS (2026-11-23 late):** MountAudioPacks crash SOLVED — harness was missing the `-rootdir=/game/` launch arg. Engine now reaches the loading screen under Node+Dawn. Next: send the Story/Sandbox start choice. See [CURRENT-PROBLEM.md](CURRENT-PROBLEM.md) and [engine-code-map/ERROR-TRACE.md](engine-code-map/ERROR-TRACE.md) Stage 16. **How solved + plan to max: [16-how-solved-mountaudiopacks-and-next-max-plan.md](16-how-solved-mountaudiopacks-and-next-max-plan.md)**

**Real game folder:** `E:\gta\playgta5` (NOT `E:\Malik\game\playgta5` â€” that old shell is empty; `GAME-MOVED-README.txt` pointed to `C:\Malik\game\playgta5`, also gone).
**Old workspace:** `E:\Malik\game` (stale `playgta5` shell, installer ZIPs, `Remove-old-game-folder.cmd`).

Read these before touching this project:

> **MANDATORY FIRST READ (all sessions):** [think-like-claude/](think-like-claude/README.md) —
> **30 lessons** on how to think like Claude (debugging, numbers, code changes, hand-offs), each
> from a real mistake in this project. Start with [30-the-one-page-checklist.md](think-like-claude/30-the-one-page-checklist.md)
> when stuck. Global copy: `C:\Users\HP\.claude\think-like-claude\` (rule 6 in `always-rules.txt`).
> **Current problem solution:** [19-swizzle-bug-solution/](19-swizzle-bug-solution/README.md) —
> native-Dawn Tint swizzle bug is solved on paper (flattenSwizzles tested 10/10, all 4,808 shaders
> transformed offline, 0 triggers left); the agent continues at file 02 → test plan T3.

| File | What it holds |
|---|---|
| [00-machine-facts.md](00-machine-facts.md) | Verified CPU/GPU/RAM/drives â€” checked live 2026-11-20 |
| [01-server-and-launch.md](01-server-and-launch.md) | Exact server start (must be detached), Chrome flags, URL recipes |
| [02-performance-benchmarks.md](02-performance-benchmarks.md) | Measured FPS/draws/RAM for every preset tested â€” with verdict |
| [03-code-deep-dive.md](03-code-deep-dive.md) | Why readbacks happen, which params exist, what NOT to use |
| [04-mistakes-and-rules.md](04-mistakes-and-rules.md) | Mistakes made in this project â†’ universal rules |
| [05-session-log-2026-11-20.md](05-session-log-2026-11-20.md) | Full timeline of the RAM/FPS investigation |
| [06-two-hour-audit-findings.md](06-two-hour-audit-findings.md) | Detached 2-hour live audit (PID 12200) â€” GPU/CPU/RAM per process, priorities, what to check |
| [07-hd-filter.md](07-hd-filter.md) | `?fx=hd` CSS sharpen filter + cinema/vivid/cool/noir looks in serve_local.py |
| [08-settings-enter-fix.md](08-settings-enter-fix.md) | Settings "Save/Yes" issue â€” latch was reverted; real cause is port bug issue #32, use settings page |
| [09-optimization-16fps.md](09-optimization-16fps.md) | Verified 13-15 -> 16.5-16.8 FPS via shadow=0/reflection=1; new High-optimized preset |
| [10-1080p-tests.md](10-1080p-tests.md) | True 1920x1080 = 5.6 FPS (max) / ~8 FPS (optimized); 960x540 + fx=hd is the viable 1080p-looking route |
| [11-postfx-experiment-failed.md](11-postfx-experiment-failed.md) | postFX/fxaa/tessellation/SSAO args made FPS worse (12-13); reverted. 16.5 FPS remains the ceiling |
| [12-custom-wgsl-shader.md](12-custom-wgsl-shader.md) | Custom WGSL post shader in mirror wgpu_worker.js (5-tap unsharp + grade), backup + Play-Shader.cmd |
| [13-true-gpu-upscale.md](13-true-gpu-upscale.md) | True GPU upscale: canvas configured at display size, WGSL sampler blit (FSR-like). Patched index.html + loader.js + wgpu_worker.js, backups |
| [14-worker-optimizations-and-1080p.md](14-worker-optimizations-and-1080p.md) | srvEpoch + proxy fast-path + readback cleanup; final true 1080p = 4.4-6.1 FPS, 25 FPS still impossible |
| [15-reverse-engineering-wasm.md](15-reverse-engineering-wasm.md) | Wasm/RAGE engine RE: 91,008 named functions in `game.dcmp`, proven patch method, honest FPS ceiling |
| [16-how-solved-mountaudiopacks-and-next-max-plan.md](16-how-solved-mountaudiopacks-and-next-max-plan.md) | **How MountAudioPacks was solved** (missing `-rootdir=/game/`, method step by step) + **ordered plan to MAX**: start choice → pixels → A/B vs Chrome → max settings → playable |
| [17-agent-brief-next-6-steps.md](17-agent-brief-next-6-steps.md) | **Hand-off brief for a code agent**: the 6 next steps (start choice → pixels → A/B vs Chrome → max → playable → clean-up) with exact code, run commands, pass checks, rules |
| [next-steps/](next-steps/README.md) | **One detailed file per next step (1-6)** for the code agent: exact code, commands, pass checks, failure paths |
| [1080p-30fps-engine-plan/](1080p-30fps-engine-plan/README.md) | **ACTIVE (2026-11-23): 1080p 20-30 FPS plan for the code agent.** 11 files: measure, Dawn flags, pipeline seed, engine LOD override (+flag bit 23319072), near/far streaming, ped/car density globals, shadows/reflections/lights, worker dedup, threads/GC, labelled upscale fallback |
| [19-swizzle-bug-solution/](19-swizzle-bug-solution/README.md) | **Solution for the native-Dawn swizzle bug (file 19)**: verified facts, exact `flattenSwizzles()` code, test plan T1-T6, fallback Dawn rebuild |
| [think-like-claude/](think-like-claude/README.md) | **30 lessons for code agents**: how to debug, measure, change code safely and report, each from a real event in this project + a one-page checklist (file 30) |
| [native-aot-solution/](native-aot-solution/README.md) | **Solution for the native AOT host crash at main+0x4fc** (2026-11-27): TLS-global diagnosis, host-vs-JS init-order fix, measure-first dumps, test plan |
| [1080p-optimization/](1080p-optimization/README.md) | **Active work (2026-11-21):** raise FPS at true 1920x1080. Proven bottleneck (JS worker ~120 ms/frame, GPU wait 0), code hot spots with lines, ranked plan, A/B protocol. Plan only, nothing implemented yet |
| [engine-code-map/](engine-code-map/README.md) | **Full engine function map (2026-11-23):** 91,008 RAGE functions indexed, 163 driver functions, LOD/draw/settings call chains, wire-call profile — navigate the engine code without re-parsing 191 MB |
| [18-audio-explained.md](18-audio-explained.md) | **Audio pipeline explained (2026-11-25):** two failure layers (Node has no speakers → ring-drain + 375 Hz heartbeat patched; Chrome worklet hard-silence on underrun), ranked Chrome fixes, diagnostics cheat-sheet |
| [24-aot-native-host-audit.md](24-aot-native-host-audit.md) | **AOT native-host audit rule (2026-11-26):** every host function logs entry/exit + real args/return to `native-host-audit.log`; canary proves the logger; imports generated from the real wasm table |
| [23-three-stages-bugfix-method.md](23-three-stages-bugfix-method.md) | **How the 3-stage bugs were found+fixed (2026-11-25):** Stage 8 test crash was a test setup bug (empty color attachments + occlusion query set crashes native-dawn *before* C++) → step logs found it; full-game DXGI device hang isolated by one-flag-at-a-time to DISPATCH (compute bind group needs dynamic offsets, hard-disabled); counters reset each stats call → read multiple samples. Re-run recipes included |
| [21-cpp-worker-draw-win.md](21-cpp-worker-draw-win.md) | **C++ worker draw path fixed + reusable debug method (2026-11-25):** 3 root causes (BigInt crossed N-API as object → `Number()`; Draw had 6 vs 7 args; **double `/4`** — `p` was already a word index, `p>>2` read zeros), plus wasm memory.grow re-attach. Lessons 05/04/10/27: log both sides of boundary, check component's own counters (`draw=0` retracted earlier false "working" claims). Verified `draw=104828, skipDraw=0, validation +0`. Flags now default ON |
| [20-audio-visual-deep-audit.md](20-audio-visual-deep-audit.md) | **Deep audit (2026-11-25):** NPC voice breaks = ENGINE-side (`Can't Speak - No voice hash` / `Speech already playing`), NOT the worklet — worklet carry-over fix is live and audio starts; road/wall flat = FAST launch args (shadow/grass=0), visual preset fixes it; sampler/render-target warnings are benign; double-server on port 8000 caused Node run stalls |
| [19-native-dawn-swizzle-bug.md](19-native-dawn-swizzle-bug.md) | **BLOCKER (2026-11-25):** native-dawn pins Dawn rev `1e975e28` (2026-08-22) = 10 days before the Tint swizzle fix (CL 338555). 26 pipelines fail "swizzle view instruction still has usages after lowering" → 0 draws. `enable swizzle_assignment` dead (feature didn't exist yet). Fix = flatten chained swizzles at load; scan results, safety risks, exact next steps |
| `Play-Final.cmd` | FINAL launcher: 1920x1080 window, 960x540 render + soft fx=hd, shadow 0 / reflection 1, ~16-17 FPS |
| `Play-Shader.cmd` | Launcher for the WGSL shader preset (no CSS fx) |
| `audit-2h.ps1`, `audit-2026-11-20.csv`, `audit-2026-11-20-summary.md` | Sampler + raw data + 10-min rollups |

Core architecture report (older, path now stale in line 2): `C:\Users\HP\.claude\architectures\playgta5.md`.
