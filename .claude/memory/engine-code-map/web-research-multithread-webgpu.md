# Web research: multi-worker / WebGPU CPU reduction (2026-11-23)

User asked: "increase the JS worker" (more workers) to raise FPS. Researched. Verdict:

## Multi-worker: DEAD on Chrome
- Posting a `GPUDevice` to a worker throws `DataCloneError` in Chrome 154; each worker needs its own device. Two threads cannot record into one device in parallel (webcodingcenter, WebGPU architecture article).
- GPUWeb issue #4244 (Kangz, WebGPU contributor): "No WebGPU object can be transferred at the moment... Adding multi-worker support to WebGPU is an extremely complicated addition... it will be a long time before it is present."
- GPUWeb issue #354: `GPUCommandEncoder` / `GPURenderPassEncoder` are neither transferable nor serializable; device is serializable but not transferable.
- GPUWeb issue #4622: no spec path for parallel command encoding; `MTLParallelRenderCommandEncoder` would map to `GPURenderBundle` but even that isn't real multithreaded encoding.
- Vulkan sample: ~15% gain from 8-thread command recording — but that's Vulkan, not WebGPU.
- **Our single worker owns all WebGPU objects; it cannot be split. More JS workers ≠ more GPU throughput.**

## What CAN reduce draw-call CPU cost on WebGPU
1. **Render Bundles (`GPURenderBundle` + `executeBundles()`)** — pre-record commands once, replay per frame. Data (webcodingcenter/toji.dev):
   - 10,000 draws direct encode 0.4 ms → bundle 0.1 ms; with bind group per draw 1.2 ms → 0.1 ms.
   - "Bundles save JavaScript and validation work, not GPU work" — validation/native encoding done once at record time.
   - **Limits:** only helps if draws repeat unchanged across frames; "rebuilding bundles every frame removes the benefit"; static scenery/UI/instanced crowds are ideal; scenes whose draw list changes (culling/sorting) don't benefit; no help when GPU-bound.
   - RAGE's draw list changes per frame → bundles MAY not fit; unproven.
2. **Fewer draws** (instancing / indirect / GPU-driven culling) — the real fix, but RAGE doesn't use indirect for bulk draws (see indirect-draw-lead.md) and we can't patch the engine.
3. WebGPU per-draw CPU cost is real: Babylon 7.34 µs/draw on i7-10700F vs PlayCanvas 1.22 µs — engine bookkeeping matters, but our driver's ~10k wire calls/frame is the cost.

## Bottom line
"Increase JS workers" is impossible on Chrome's WebGPU. The only untried WebGPU-level idea is render bundles for repeated draw sequences, but it needs per-frame draw-list stability that RAGE likely doesn't provide. No safe path to 30 FPS at true 1080p remains; config `-lodScale=1` (+25%) is the only win.

Sources: WebGPU Explainer (gpuweb.github.io/gpuweb/explainer), GPUWeb issues #354/#4244/#4622, webcodingcenter WebGPU architecture/off-thread recording, toji.dev render bundles, ICS media BundleGroup, Babylon forum CPU-per-draw benchmarks, Vulkan command buffer sample.
