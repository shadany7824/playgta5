@echo off
set WGPU_SHOT_EVERY=0
set WGPU_DAWN_FLAGS=enable-dawn-features=disable_symbol_renaming,backend=d3d11
"E:\gta\playgta5\node24\node_modules\node\bin\node.exe" "E:\gta\playgta5\node-webgpu\harness.js" > "E:\gta\playgta5\node-webgpu\diag-03-d4.txt" 2>&1
