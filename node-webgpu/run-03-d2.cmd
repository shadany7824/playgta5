@echo off
set WGPU_SHOT_EVERY=0
set WGPU_DAWN_FLAGS=enable-dawn-features=skip_validation
"E:\gta\playgta5\node24\node_modules\node\bin\node.exe" "E:\gta\playgta5\node-webgpu\harness.js" > "E:\gta\playgta5\node-webgpu\diag-03-d2.txt" 2>&1
