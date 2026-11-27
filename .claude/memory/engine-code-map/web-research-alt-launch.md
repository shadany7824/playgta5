# Web research: alternate launch paths (Node/Dawn, other browsers) (2026-11-23)

User asked: instead of Chrome, can we launch differently to raise FPS?

## Findings

### Native WebGPU (Node + Dawn) is faster than browser WebGPU
- Three.js benchmarks (SamG-Coder, 2026-09-10): native WebGPU lower latency in all 8 scenes; browser/native ratios 1.49× (meshes) to 4.26× (triangles-medium); on-screen update/submission 1.295 ms browser vs 1.007 ms native in city scene. Browser callback ~16.67 ms vs native ~4-5 ms.
- Dispatch overhead paper (arXiv 2604.02344): true WebGPU per-dispatch 24-36 µs on Vulkan; command-buffer submission = 40% of that. Browser safety checks add up to 42% on some GPUs. Chrome/Dawn is the best browser implementation, but native bypasses the wire protocol + sandbox.

### The port already HAS a Node/Dawn path (unfinished)
- `wgpu_worker.js` line 38: `isNode = typeof process !== 'undefined' && process.versions.node`.
- If Node: uses `worker_threads`, `WGPU_NODE_MODULE` (default `D:/wasm_build/shaders/node/node_modules/webgpu`), `WGPU_SHADER_DIR` (default `D:/wasm_build/web/shaders`), reads `.wgsl` + `.consts.json` from disk, `fs.writeSync` logging, explicit `compileSync` path, screenshots via file writes.
- Setup files from the original build are NOT present on this machine: `D:/wasm_build/shaders/node/node_modules/webgpu` = missing; `D:/wasm_build/web/shaders` = missing.
- Node WebGPU (`dawn-gpu/node-webgpu`, npm `webgpu`): needs `npm install webgpu`; supports backends d3d12/vulkan/opengl. **No canvas/display** — renders to textures + readback only. Need a presentation path (e.g., stream via Sunshine/Moonlight — memory 21-cloud-gaming-clarification says not built).
- Node v22.23.2 IS installed.

### Other browsers
- Edge is installed (C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe) but uses the SAME Dawn engine as Chrome — no expected gain.
- Firefox (wgpu/Rust) and Safari (WebKit) typically slower/less stable (llamas-on-web paper: Chrome/Dawn consistently highest). Not installed here.

## Verdict
Native Node+Dawn could remove the browser wire overhead (the measured bottleneck), but requires: installing `webgpu` npm, obtaining the shader package (missing), wiring up the Emscripten main thread in Node, and building a display/streaming path. Substantial setup with no guarantee the port runs headless correctly. Not attempted. The playable 30 FPS low-mode config remains the practical answer.

Sources: github.com/SamG-Coder/three-runtime-benchmarks WEBGPU-REPORT, arXiv 2604.02344, github.com/dawn-gpu/node-webgpu, webcodingcenter WebGPU architecture, llamas-on-web arXiv 2605.20706.
