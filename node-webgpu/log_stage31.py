def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)

add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 07 — Population density (Stage 31, 2026-11-24)
- Node-only population hook in wgpu_worker_node.js (backup .bak-pop): WGPU_PED_DENSITY writes 7155636 (ambient ped multiplier) every frame in present(). Chrome untouched.
- Ped 0.5: patch confirmed in log, validation +0, no resize, draws 1594 -> 1368 (-14%) vs true-1080p baseline. FPS/timing noisy (owner windows open): 7.19 vs 7.60, us/draw 75.7 vs 59.2; keep for draw reduction, needs clean re-check when idle.
- Ped 0.25: world load stalled twice at "LoadAllRequested took longer than 60 seconds / giving up" (server stable) -> REJECT 0.25.
- KEEP WGPU_PED_DENSITY=0.5 in the final preset (ambient peds only, world still alive; screenshots saved shots/07-ped50).
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 31: file 07 ped density 0.5 kept, 0.25 stalls loading (2026-11-24)
- WGPU_PED_DENSITY hook in node worker writes 7155636 each frame. 0.5: -14% draws (1594->1368), validation +0, no crash. 0.25: reproducible world-load stall (2/2 runs) at streaming flush -> rejected.
- Keep 0.5. Vehicle multipliers not tested (risky timing/ThisFrame; plan prefers WAT but low payoff vs remaining levers).
''')
print('logged')
