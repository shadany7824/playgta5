def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 08 — reflectionQuality=0 test (Stage 33, 2026-11-24): rejected
- True 1080p, ped0.5, all kept levers; refl0 vs refl1: draws 1368 -> 1063 (-22%), TIME draw 103.7 -> 100.0 ms, fps 7.19 -> 7.03 (owner windows open, noisy), passBegins ~54. Screenshot verified (real world, no broken water/sky in that spot).
- Per file 08 pass rule (FPS up >=5%): REJECT. Harness restored -reflectionQuality=1 (backup .bak-refl1). Note: draw reduction exists but no FPS gain in the current CPU-bound path; revisit after file 13 if needed.
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 33: file 08 reflectionQuality=0 rejected (no FPS gain) (2026-11-24)
- refl0 cut draws 22% but fps 7.03 vs 7.19 baseline; no >=5% gain -> restored reflectionQuality=1. Screenshot checked, no visual break.
''')
print('logged')
