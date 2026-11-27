def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 02 part 2B — engine ceiling (Stage 38, 2026-11-24): ~14 FPS
- Diagnostic: WGPU_NODRAW=1 skips every draw in the node worker (backup wgpu_worker_node.js.bak-nodraw); all other kept flags on, true 1920x1080.
- Result: 0 draws/frame, validation +0, steady FPS last12 = 14.15 (vs 7.60 with 1594 draws). Even a perfect zero-cost GPU worker caps at ~14 FPS -> the wasm engine itself cannot make 20 FPS today.
- Consequence: 20 FPS at true 1080p requires engine-side speed (file 14 V8 tiering / wasm-opt, engine thread work), not just worker optimizations. File 14 promoted to critical.
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 38: 02 2B engine ceiling ~14.15 FPS (no-draw) (2026-11-24)
- WGPU_NODRAW=1: 0 draws, 14.15 FPS last12, validation +0. Normal 7.60 FPS @1594 draws. Worker can at most add ~6.5 FPS; engine is now the binding constraint for the 20 FPS goal. Restored worker from .bak-nodraw.
''')
print('logged')
