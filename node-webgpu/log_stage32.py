def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 12 — Occlusion culling check (Stage 32, 2026-11-24): ACTIVE, no change
- Enable gate found: 6621392L[0]:ubyte & 1 guards rage_fwScanEntities_IsEntityOccluded (game.dcmp 569946, 573284, 573329). Setup at 3814181-4209: bit0 = occlusion, bit1 = second pass; both required for some paths ((flag&3)==3).
- Runtime proof (node worker logs OCCFLAG every 10s, diag-12-occ-check.txt): 6621392 = 3 on all 31 samples -> soft rasterizer occlusion ENABLED. validation +0.
- No patch needed. File closed.
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 32: file 12 occlusion culling already active (flag=3) (2026-11-24)
- Gate 6621392 bit0/bit1 read every 10s in present(); value 3 throughout 300s true-1080p run. Occlusion culling is NOT broken in the wasm port -> no draw win here. Moved on per plan.
''')
print('logged')
