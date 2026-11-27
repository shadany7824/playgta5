# 02: Code hot spots (mirror `wgpu_worker.js`, line numbers as of 2026-11-21, file 3031 lines)

File: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js`.
Line numbers drift after every patch. Re-grep the function name before editing.

## Per command (runs ~25,000 times/frame)
- `runCommands()` **:2846-2960**: one `switch` per command from the shared ring. Yields to the event loop every 1024 commands if 2 ms passed (`:2943-2955`).
- `uploadBuffer()` **:601-615**: constant buffers copy into a JS `shadow` (`:604`). Vertex/index buffers do a `queue.writeBuffer` per upload (`:609`), plus a second write for non-4-byte tails (`:610-613`). If a recorded draw already used the buffer, it calls `flush('buffer upload')` (`:607`).
- State ops `SET_*` **:2898-2918**: cheap, but `SET_CBUFFERS/SET_SRVS/SET_SAMPLERS` bump `bindEpoch` (`:2904-2906`), which knocks every program off the bind-group fast path.

## Per draw (~2000/frame at 1080p)
`doDraw()` **:1719-1844**, in order:
1. `objs.get()` for VS/PS/layout + `shaderProgram()` (`:1728-1735`).
2. `prepareDepthProxies()` x2 (`:1736-1737` → `:1448-1463`): scans texture bindings unless cached as "none".
3. `ensurePass()` (`:1738` → `:1401-1444`): string key only rebuilt after `SET_RENDER_TARGETS`.
4. Pipeline lookup when `pdirty` (`:1740-1745` → `getPipeline :1145-1208`): an integer-tuple hash. Runs for most draws, because nearly every draw changes some state.
5. `stageBG()` x2 (`:1753-1754` → `:1507-1546`): fast path, else `stageBindGroup()` (`:1569-1665`), which calls `packCopy()` (`:779-827`) to copy every constant buffer the shader reads into the uniform ring (`dst.set` per member, `:812`).
6. Vertex/index buffer binding loop (`:1767-1790`), viewport/scissor/blend/stencil compares (`:1792-1806`).
7. The draw-count clamp loop (`:1820-1831`), then `pass.drawIndexed` / `pass.draw`.

**Cost driver:** each WebGPU call from a worker is serialised over Chrome's wire to the GPU process. JS work plus wire encoding is the ~60 µs/draw.

## Per frame
- `present()` **:2703-2831**: blit to canvas at `DISPLAY` size (GPU upscale, note 13), `flush('present')`, then waits on the ring slot (`:2829`). That wait is 0 ms at 1080p today.
- `flushUniforms()` **:770-777**: one `writeBuffer` per dirty 8 MB ring chunk.

## Things that scale with PIXELS (these get worse at 1080p)
- **Depth proxies**: `depthProxy()` **:953-987** and `floatToDepthProxy()` **:913-950**. Every time a depth texture is written and then sampled as float, the worker ends the current render pass (`endPass()`) and runs a **full-screen copy pass per mip x layer** into an `r32float` / `r8uint` / `depth32float` copy. At 1920x1080 each copy is 2 M pixels, and it also splits the engine's render pass.
- **Clears**: `clearRT()` **:2430-2437** / `clearDS()` **:2439+** each open and close an empty render pass with `loadOp:'clear'`. The next draw then opens a second pass with `loadOp:'load'` (`ensurePass :1412`, `:1427`), so the same 1080p target is written then read back again.
- **All passes use `loadOp:'load'` + `storeOp:'store'`** (`:1412`, `:1427-1428`), even for targets the engine fully overwrites or never reads again (bandwidth on shared-RAM HD 620).
- **Upscale blit** (`makeBlit :2451`, `present :2716-2723`): one full-screen pass at display size. Cheap.

## Already done (note 14). Don't redo these.
srvEpoch narrowing, proxy fast path with generation guard, stable GPU-object bind-group keys, yield threshold 1024, readback batching into one submit.

## Page side
- `mirror\playgta5.com\index.html:373-384`: `wantSize()`; `?res=WxH` forces the back buffer, `?scale=` render scale.
- `:407`: engine args; `-numCores=` added only when `cores <= 2`.
