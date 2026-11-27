def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## Live in-game LOD settings panel (Stage 37, 2026-11-24)
- Built WASM with exported mutable global `gta_lod_cutoff` (default 50m) controlling the 50m near-full-detail patch in LODDrawable_CalcLODLevelAndCrossfade + ProxyLod variant (backup chain: game.wat -> game-lodlive.wat/wasm via wat2wasm --enable-threads --enable-memory64 --enable-annotations, validated).
- Chrome: loader.js stores instance, applies pending cutoff/ped density, always loads fresh game-lodlive.wasm (cache-bust name). index.html: initial cutoff from ?wasm=lod50 (50) else 0, plus Ctrl+S overlay panel with FAST/SHARP and PED 0.5/1.0 buttons. Backups: loader.js.bak-livepanel, index.html.bak-lodtoggle.
- Launcher: LOD-Settings.cmd -> Play-Chrome-Fast.cmd / Play-Chrome-Sharp.cmd -> Launch-Chrome-Mode.cmd (Chrome 1080p sandbox). Ctrl+S toggles the panel live; no game restart needed for LOD/ped changes.
- Node verification: harness loads game-lodlive.wasm, WGPU_LOD_CUTOFF env sets initial value; 150s run with cutoff=0: 14 fps samples, validation +0 -> export works.
- FPS tradeoff as measured: cutoff=0 (fast) ~7.6 FPS vs cutoff=50 (sharp near) ~5.6-6.7 FPS.
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 37: Ctrl+S in-game live settings panel added (2026-11-24)
- Exported WASM global gta_lod_cutoff lets the page switch the 50m LOD behavior live; ped density global 7155636 writable from loader. Panel in index.html, listener in loader.js, fresh wasm file name for cache safety. Verified Node boot with cutoff=0 (validation +0).
''')
print('logged')
