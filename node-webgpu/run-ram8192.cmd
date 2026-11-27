@echo off
set GAMERESOURCEMB=8192
set WGPU_LOD_CUTOFF=0
set WGPU_DAWN_FLAGS=enable-dawn-features=disable_symbol_renaming
set WGPU_ASYNC_PIPELINES=1
set WGPU_PIPELINE_SEED=E:/gta/playgta5/node-webgpu/pipeline-seed.json
"E:\gta\playgta5\node24\node_modules\node\bin\node.exe" "E:\gta\playgta5\node-webgpu\harness.js" > "E:\gta\playgta5\node-webgpu\diag-ram8192.txt" 2>&1

