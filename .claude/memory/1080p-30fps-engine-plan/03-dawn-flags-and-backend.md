# 03 — Dawn flags and backend (zero code, env var only)

## Why
Native Dawn does validation and robustness work on **every** API call. At ~10,000 state calls + ~1,500 draws per frame, that CPU cost is large. Today the Node worker also runs Dawn with a **debug flag**:
`mirror\...\wgpu_worker.js` line ~514:
```js
gpu = dawn.create(process.env.WGPU_DAWN_FLAGS ? process.env.WGPU_DAWN_FLAGS.split(',') : ['enable-dawn-features=emit_hlsl_debug_symbols']);
```
`emit_hlsl_debug_symbols` makes every shader compile with debug info (slower pipeline creation, maybe slower shaders). It's a developer setting.
The env var `WGPU_DAWN_FLAGS` overrides this. **No file edit needed.** Set it in the run `.cmd` before starting node.

## Flag format (dawn.node, package `webgpu` v0.6.2)
From its README: `create(["enable-dawn-features=allow_unsafe_apis,dump_shaders,disable_symbol_renaming"])`. Each array entry is `key=value`. Known keys in dawn.node: `enable-dawn-features=<toggle,...>`, `disable-dawn-features=<toggle,...>`, `backend=<d3d11|d3d12|vulkan|...>`, `adapter=<name>`, `power-preference=...`.
**Verify the exact key names** in `node24\wgpu\node_modules\webgpu\` (README, `dist/`, or strings in the `.node` binary: `grep -a "enable-dawn-features\|backend=" build/*.node`) before using them. Note: the worker splits `WGPU_DAWN_FLAGS` on commas, so put ONE toggle per `enable-dawn-features=` entry, e.g. `enable-dawn-features=skip_validation,enable-dawn-features=disable_robustness` → check how dawn.node handles repeated keys. If it doesn't merge them, patch the worker copy (file 09) to split on `;` instead.

## Runs (one per run, compare µs/draw and FPS)
| Run | WGPU_DAWN_FLAGS | What it tests |
|---|---|---|
| D0 | (unset) | baseline: debug symbols on |
| D1 | `enable-dawn-features=disable_symbol_renaming` (any harmless toggle, so the debug default is gone) | removes the debug HLSL symbols |
| D2 | D1 + `skip_validation` | Dawn skips API validation (biggest expected CPU win) |
| D3 | D2 + `disable_robustness` | no robust buffer access in shaders (GPU-side, small) |
| D4 | D2 + `backend=d3d11` | D3D11 backend: often lower CPU overhead on Intel iGPUs |
| D5 | D2 + `backend=vulkan` | compare (Intel HD 620 Vulkan driver quality varies) |
| D6 | D2 + `backend=d3d12` | explicit D3D12 (probably today's default; confirm from the adapter log) |
Toggle names are Dawn's (`skip_validation`, `disable_robustness`, `use_dxc`, `disable_lazy_clear_for_mapped_at_creation_buffer`, ...). Confirm each exists in this Dawn build; an unknown toggle may be ignored silently. Log the adapter info and the active backend at startup (`adapter.info` / `requestAdapterInfo`) so you can prove which backend ran.

## Safety
- `skip_validation`: an invalid call can then crash the GPU process or Node (earlier sessions saw `0xC0000409`). We already run with `validation errors +0` (Stage 19), so the risk is lower. Still run the full 300 s and one screenshot run.
- If a backend crashes or renders wrong: record the error, the screenshot and the exit code, and drop that backend.

## Pass / keep criteria
- Keep a flag set only if: FPS up ≥ 5% over 2 runs, validation +0, screenshot correct, no crash in 300 s.
- Report µs/draw (TIME draw ÷ draws) for each run. Dawn flags should lower it.

## Where to make it permanent
In the Node launcher `.cmd` (`run-*.cmd` / later `Play-Node-Dawn.cmd`): `set WGPU_DAWN_FLAGS=...`. Not in the mirror worker (the Chrome path ignores this env anyway).
