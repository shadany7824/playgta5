@echo off
set WGPU_SHOT_EVERY=300
set WGPU_SHOT_PREFIX=E:/gta/playgta5/node-webgpu/shots/11-1920/shot_
set WGPU_DAWN_FLAGS=enable-dawn-features=disable_symbol_renaming
set WGPU_ASYNC_PIPELINES=1
set WGPU_PIPELINE_SEED=E:/gta/playgta5/node-webgpu/pipeline-seed.json
"E:\gta\playgta5\node24\node_modules\node\bin\node.exe" "E:\gta\playgta5\node-webgpu\harness.js" > "E:\gta\playgta5\node-webgpu\diag-11-1920.txt" 2>&1

