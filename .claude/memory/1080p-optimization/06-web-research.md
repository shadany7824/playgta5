# 06 — Web research: remaining solutions for draw-bound WebGPU (2026-11-21)

## Sources
- webgpufundamentals.org "WebGPU Speed and Optimization"
- webcodingcenter.com "When Bundles Help" + "Performance Best Practices"
- toji.dev "Render Bundle best practices" / "Indirect Draw best practices"
- MDN GPURenderBundle
- Original port article (ai.satyajit.si) — describes this exact engine's optimizations

## What the web says can still cut per-draw CPU cost
1. **Render bundles**: save JavaScript/validation work, NOT GPU work. Measured 10,000 draws: direct 0.4 ms → bundle 0.1 ms encode; completion unchanged (4.9–5.8 ms). Best when the draw list is static/repeated. GTA V culls/sorts and changes state per frame, so only parts may qualify. Three.js `BundleGroup` shows dynamic transforms are possible via uniform/storage buffers.
2. **Indirect draw / GPU-driven**: collapse many CPU draw calls into one `drawIndexedIndirect`, GPU fills args. Big win in engines that can restructure; here the engine emits a D3D11-like stream, so this would require translating each DRAW into an indirect args buffer write — a rewrite of `doDraw()`, high risk.
3. **Instancing / merging**: not applicable cleanly — engine already decides geometry; merging changes image.
4. **storeOp:'discard'** for attachments never read, clear folding, depth-proxy elimination: save memory bandwidth and passes. Our GPU is only 44–79% busy and `gpu wait = 0`, so bandwidth is not the measured wall; low expected gain.
5. **Port's own already-done optimizations** (from the original article): cached `GPUBuffer.size` (~5% of worker), numeric pipeline keys, async pipeline compiles, dynamic offsets, pooled readback buffers, hinted prefetch — we confirmed these exist in our copy. So the "easy" JS wins are exhausted.
6. Official port docs: no universal FPS fix; presets trade quality for FPS. No verified 90–200 FPS claim.

## Honest conclusion
No web source shows a safe, verified way to take THIS draw-bound port from ~9 to 25 FPS at true 1080p on an i3-7100U/HD 620. Render bundles/indirect draws are the only structurally larger levers, both high risk and unproven with a changing draw list. Practical options remain: (a) near-1080p internal + GPU upscale (~16 FPS), (b) plain low profile (30 FPS, low quality), (c) faster hardware.
