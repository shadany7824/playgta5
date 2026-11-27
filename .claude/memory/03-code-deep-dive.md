# 03 — Code deep dive (verified 2026-11-20, cite lines)

Files: `E:\gta\playgta5\wgpu_worker.js`, `loader.js`, `mirror\playgta5.com\index.html`, `README.md`, `game.js`.

## Readbacks (the 5 per frame)
- Opcode table `READBACK: 42` at `wgpu_worker.js:35`; dispatch `case 42` at `:2861-2866` calls `readback(p)` fire-and-forget then clears the engine flag via `done()`.
- `readback()` at `:2344-2387`: buffer path `copyBufferToBuffer` `:2359` → `flush('readback')` `:2360` → `mapAsync` `:2361` → `getMappedRange` `:2363`; texture path `:2378-2385`. One submit per readback is deliberate (`:2351-2352`: deferring to present caused 50–300 ms waits).
- `flush(reason)` counts submits at `:165-176`; the fps line is built at `:2685`.
- **No URL param disables opcode 42.** No-oping it corrupts exposure (engine consumes stale/zero data). Engine wait on readbacks logged as 0 ms → not the FPS problem.
- `?shot=N` / `?shotrt=1` add extra diagnostic readbacks (`screenshot()` `:2487`, `floatStats()` `:2531`, `nanScanAfterDraw()` `:2610`) — off by default.

## Frame slots
- `FRAME_SLOTS` default 3, URL `?slots=N` at `:728`. Comment `:726-727`: with 3 slots (2 frames in flight) the round trip capped FPS. `slots=5` used in tests. `slots=1` (Play-Ultra) = 1 frame in flight.

## Quality / engine args
- `index.html:360-369`: low profile auto when `navigator.deviceMemory <= 4`; `low=1` forces it, `low=0` forbids. LOW_ARGS listed at `:368-369` (texture/ped/vehicle/shadow/reflection/particle/grass/cityDensity/lodScale/pedLodBias/vehicleLodBias all 0; shadows `?shadows=1` → 0 else -1). `cores` = 2 in low mode else `navigator.hardwareConcurrency` (`:370`).
- `index.html:373-383`: `?res=WxH` forces back-buffer; `?scale=0.75` render scale; `fixed=1` keeps startup size.
- `index.html:406-407`: engine args order — base args, LOW_ARGS (if low), then `?args=` last (so `args=` overrides LOW_ARGS values).
- Shadows: cascade pass was 600–900 of 1300–2900 draws (`:364-365`). Low profile uses `pipelines_low.json` with **no shadow pipelines** — forcing `-shadowQuality=3` in low mode will not create shadows.
- `game.js` (single minified line): `INITIAL_MEMORY=3221225472` (3 GiB), `new WebAssembly.Memory({initial:…, maximum:262144n, shared:true, address:"i64"})` → max 16 GiB, grows on demand.

## Flags/params that HURT (avoid)
`syncpipelines=1` (blocking compiles), `nogpu=1` (no rendering), `dbg=1` (broken image), `limits=` (weaker device), `nopack=1` (slow boot), `nocache`/`nosw` (destroy warm store), `verbose=1`/`console=1` (log overhead), `fps=0` (uncapped, heat), `slots=1` (less pipelining). Browser flags `--use-webgpu-adapter=compat` (2.2× slower), `--disable-gpu-driver-bug-workarounds` (risky).

## Historic crash trap (from core architecture report)
NEVER pass `-shaderQuality=0` or `-waterQuality=0` in `args=` → `DistortionParams` abort. Port's own LOW_ARGS deliberately omits them.
