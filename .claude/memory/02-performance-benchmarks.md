# 02 — Performance benchmarks (all measured 2026-11-20 from `game-log.txt`)

FPS values are steady-state **world** numbers (not loading-screen/title numbers). Draws/frame and GPU-worker busy come from the `[wgpu] fps:` line.

| Preset (URL) | World FPS | Draws/frame | Worker busy | Verdict |
|---|---|---|---|---|
| True MAX: `low=0&res=1280x720&fps=60&shadows=1&args=-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2` | **6.9–7.4** | 1008–2407 | 72–96% | Pretty but unplayable |
| MAX w/ density+LOD cut: `low=0&args=…density=0,variety=0,lod=0…` (textures/shadows/reflections still 2) | **3.8–8.6** (climbed with warm shaders) | 1721–2382 | 73–86% | Barely helped |
| MAX `res=960x540`, shadow=1, particle=1, grass=1, density/LOD 0 | **6.4–11.5** | 2286–2869 | 69–100% | Still not enough |
| MAX `res=960x540`, shadow=0, particle/grass 0, density/LOD 0 | **7.2–11.2** | 2225–2513 | 76–96% | Still not enough |
| LOW + visual overrides (`low=1` + texture/reflection/particle/grass=2) — **NOT max mode** | 9–22 (dense scenes 9–14) | 380–2197 | 49–98% | Wrong target; owner rejected |
| LOW plain `low=1&res=1024x576&fps=30&slots=5` | **30.0** | 14 (idle) / few hundred in world | 8% | Owner says good |
| MAX + `cores=2` (`-numCores=2`), all quality 2, 1280x720 | **7.8–8.9** | 724–1274 | 87–94% | Fewer draws, same low FPS |
| Exact `Play-720p.cmd` profile (shadow=-1, reflection=0, aniso=2, FXAA, cores=2, 1280x720) | **2.0–4.3** | 1832–4282 | 87–100% | Aniso/FXAA disastrous on HD 620 |
| Edge (not Chrome), MAX 960x540, shadow=1, texture/reflection=2, particle/grass=0 | **11.6–13.7** | 1188–1324 | 95–100% | **Best true-max so far** |
| Edge, same MAX at 800x450 | **10.8–12.9** | 1339–2163 | 94–100% | Lower res gives no gain → CPU/draw-bound |

## Root cause (proved, not guessed)
- **GPU worker command execution is the wall**: 2200–2800 draws/frame at max, worker 76–100% busy. The engine emits the draws; JS replays every one. Lowering resolution does NOT fix it.
- The 5 readbacks/frame (`readback 4.1–5.1`) are engine `READBACK` opcodes (`wgpu_worker.js:2861-2866 → 2344-2387`), not the diagnostic readbacks. Engine waits 0 ms on them in the logs → **not the bottleneck**; no-oping them breaks exposure rendering.
- RAM is NOT the bottleneck: 11+ GB free even at 68% used; WASM memory stays 3072 MB (initial) with max 16 GB (`game.js` `INITIAL_MEMORY=3221225472`, `maximum:262144n`). Forcing 10–15 GB upfront would not add FPS.
- Chrome flags and `slots=5` helped pipelining (menu/title 20–43 FPS) but do not cut engine draw calls.
- `cores=2` cuts draws ~2× but FPS stays ~8 — per-draw cost rises, no win.
- Lowering resolution 960x540 → 800x450 gives no gain: the limit is CPU/WebGPU command dispatch, not pixels.
- Edge is marginally better than Chrome (~13.7 vs ~11 FPS) but still below target.

## Status of owner's request: "improve FPS to 15–25 in MAX graphics"
**NOT ACHIEVED in true max mode after 10+ tested configurations.** Best true-max result: **~13.7 FPS in Edge at 960x540** with max textures/reflections + shadows at 1 (still below 15). Chrome best ~11 FPS. The engine emits 1200–2800 draws/frame in max and the WebGPU worker is 94–100% busy. Do not claim success; do not swap in low mode and call it max.

## Where to look next (unverified ideas)
- `?dbg=1` draw isolation exists (`index.html:478-499`) but breaks the image — diagnostic only, not a fix.
- No quality-preserving code-level draw switch exists in the JS worker (`doDraw` at `wgpu_worker.js:1780-1829` executes every command).
- Engine args are the only lever; ranges above 1/2 are inferred from GTA V conventions, not documented locally.
- A faster discrete GPU / stronger CPU is the real fix for max graphics.

## 2026-11-23 STEP-3: Node/Dawn vs Chrome, matched 1920x1080 (VALID A/B)
- Node: `node-webgpu\diag-step3-1080.txt`, WGPU_SHOT off, console off, `-width=1920 -height=1080 -textureQuality=2 -shadowQuality=0 -reflectionQuality=1 -particleQuality=0 -grassQuality=0 -cityDensity=0 -lodScale=0 -frameLimit=0`, sandbox, 300 s. Steady (last 12 samples): **12.36 FPS avg (10.1-14.6), 1344 draws/frame (1228-1462), gpu wait 0**.
- Chrome: `game-log.txt` appended from mark 321868490, URL `?log=1&low=0&mode=sandbox&res=1920x1080&fps=0&slots=5&args=<same quality args>`, 200 s. Steady (last 12): **6.06 FPS avg (5.1-7.8), 1382 draws/frame (1038-1681), gpu wait 0**.
- Scene validity: draws within 2.8% (1344 vs 1382) -> PASS the +-15% rule. Both uncapped, same quality args, sandbox.
- **Gain: +104% (~2.0x) for native Dawn under Node over Chrome's WebGPU wire at true 1080p.** Both GPU-wait 0; the win is the removed wire/IPC.
- Caveat: Chrome window was 1536x864@1.375, but render size came from URL res=1920x1080; Node render size from args. Both 1080p render.
