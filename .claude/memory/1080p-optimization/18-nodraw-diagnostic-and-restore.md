# 18 — Diagnostic no-draw wasm patch + restore (2026-11-21)

## What happened
- Built `game-nodraw.wasm` by replacing the body of `wasm_null_d3d::NullContext::DrawIndexed` with a no-op in `game.wat`, recompiled (`wat2wasm --enable-all`, 0 errors), `wasm-validate` exit 0.
- Backed up the real mirror wasm to `game.wasm.bak-nodraw`, copied the patched binary into the mirror, and loaded the game for a diagnostic A/B.
- Result proved the CPU/draw wall: **26–56 FPS, only ~142 draws/frame, worker 13–28% busy** (vs ~8–9 FPS, ~2400 draws, worker ~99% with real draws). No WebGPU validation errors.
- But visuals break (objects missing) — owner reported "code error in game". This was expected from a no-op draw function, not a real bug.

## Fix applied
- Restored original mirror `game.wasm` from `game.wasm.bak-nodraw` (63,201,802 bytes).
- Restarted local server (PID 7376) and relaunched the normal 720p high preset; Chrome title `game - Google Chrome` confirmed.

## Conclusion
Draw-call count is definitively the FPS wall. Skipping draws is not a usable optimization because it destroys the image; the JS worker/upscale changes remain the safe gains.
