def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 13 feasibility + JS batching attempt (Stage 34, 2026-11-24)
- Feasibility: NO C++/Rust toolchain installed (cl/msbuild/cmake/rustc absent); webgpu npm package has only prebuilt dawn.node (no headers/libs/source); dawn.node exposes no native device handle. Building Dawn from source would take hours on 2 cores -> native addon BLOCKED without major setup.
- JS batching middle step: removed 6 per-draw diagnostic timing closures/performance.now() wrappers from doDraw in the node worker copy (backup .bak-batch). A/B at true 1080p: baseline 7.60 FPS / 94.1 ms draw; batch run1 7.97 / 87.1 (looked good), batch run2 7.02 / 105.3 (noise/scene variance) -> NO proven >=5% gain. Reverted to .bak-batch (keeps diagnostics).
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 34: file 13 native addon blocked; JS batching no proven gain (2026-11-24)
- Native C++/Rust: no compiler toolchain, no Dawn headers/libs, no device handle -> hours of setup, deferred (owner aware).
- Removed per-draw timing closures: 7.97 FPS first run, 7.02 second vs 7.60 baseline -> no reproducible gain, reverted (wgpu_worker_node.js.bak-batch).
- Status: true 1080p still ~7.6 FPS with kept levers (03/04/05/07); remaining untested: 14 V8 tiering, 15 submits/passes, 16 hardware, plus engine ceiling 2B.
''')
print('logged')
