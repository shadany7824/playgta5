def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)

add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## CRITICAL correction (Stage 29, 2026-11-24): all previous runs were 640x360, not 1080p!
- Discovery: game-node.js wasm_input_publish_js wrote win=640x360 into the input block (b+424 indices 2,3) while its diag string falsely said win=1920x1080. Engine log confirmed "window resized to 640x360 (was 1920x1080)" in EVERY prior run. Screenshots 640x360. All Stage 17-28 FPS numbers are 640x360-internal numbers, mislabelled as 1080p.
- Fix: wrote 1920/1080 to the input block (backup game-node.js.bak-win640). Verified: no resize line, no validation errors.
- TRUE 1080p baseline (final kept levers D1+seed+async+LOD0.3): 7.60 FPS, 1594 draws, TIME draw 94.12 ms, us/draw 59.2, worstAvg 444ms, pipeline stalls 0. (vs mislabelled 640x360 run 10.38 FPS, 1495 draws, 48.3 us/draw).
- File 11 upscale test invalid (display= param also forced 640x360); reverted display override (worker-boot.js.bak-display).
- Real target gap: 7.6 FPS -> 20 FPS needs ~2.6x. Must re-baseline resolution-dependent levers at true 1080p.
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 29: CRITICAL - prior 1080p runs were 640x360 (winWH patch lied) (2026-11-24)
- Root cause: game-node.js wrote 640/360 to WasmInputBlock window size while logging win=1920x1080; engine resized itself to 640x360. Evidence: window-resize log line and 640x360 screenshots.
- Fixed: write 1920/1080 (backup game-node.js.bak-win640). Verified no resize line.
- TRUE 1080p with all kept levers: 7.60 FPS / 1594 draws / 94.12 ms draw / 59.2 us/draw, validation +0.
- Consequence: Stage 19-28 FPS numbers are 640x360 numbers (still valid as relative A/Bs at that resolution). Goal 20-30 FPS at native 1080p now needs 2.6-4x. File 11 upscale is now much more attractive.
- Rule: always parse the engine window-resize log line and screenshot dimensions before calling a run 1080p.
''')
print('logged')
