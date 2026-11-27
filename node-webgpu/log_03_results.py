import os

def add(path, text):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(text)

results = r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md'
add(results, '''
## 03 — Dawn flags (Stage 21, 2026-11-23)
Setup: harness 1920x1080, sandbox, uncapped, screenshots off, 300 s each, last 12 steady samples.
| Run | WGPU_DAWN_FLAGS | FPS | draws/f | TIME draw | us/draw | pipeline wall (12 samples) | verdict |
|---|---|---|---|---|---|---|---|
| D0 | (default, HLSL debug symbols ON) | 10.77 | 1331 | 55.17 ms | 40.6 | 7175 ms | baseline |
| D1 | `enable-dawn-features=disable_symbol_renaming` | 11.15 | 1137 | 37.68 ms | 33.1 | 1558 ms | KEEP (-18% us/draw, debug symbols gone) |
| D2 | `enable-dawn-features=skip_validation` | 11.10 | 1372 | 44.51 ms | 32.3 | 2105 ms | REVERT: no >=5% gain, draws differed 21%, validation risk |
- D1's gain is mostly from removing `emit_hlsl_debug_symbols` (matches Stage 20 profile: sync pipeline creation 24.8% of worker self time).
- Permanent flag for Node launcher: `set WGPU_DAWN_FLAGS=enable-dawn-features=disable_symbol_renaming`.
''')
trace = r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md'
add(trace, '''
## Stage 21: file 03 Dawn flags — HLSL debug symbols removed (-18% us/draw) (2026-11-23)
- Method: env-var only, one lever per 300 s run, last-12 steady samples, parser `node-webgpu\parse_03_levers.py`. Logs `diag-03-d0/d1/d2.txt`.
- D0 baseline (debug symbols on): 10.77 FPS, 1331 draws, 55.17 ms draw, 40.6 us/draw, pipeline wall 7175 ms.
- D1 `enable-dawn-features=disable_symbol_renaming`: 11.15 FPS, 1137 draws, 37.68 ms draw, 33.1 us/draw, pipeline wall 1558 ms. KEEP.
- D2 `enable-dawn-features=skip_validation`: 11.10 FPS, 1372 draws, 32.3 us/draw, validation +0. No >=5% gain and scene draws differed 21% -> REVERT to D1 (risk without reward).
- Conclusion: the default `emit_hlsl_debug_symbols` flag was costing real pipeline time; set D1 permanently in the Node launcher. No crash in any run; screenshots not needed (flag removed only debug info, image unchanged by design).
''')
print('logged')
