# 13 — The biggest lever: replace the JS draw path with native C++ (Node addon)

## Why
The bottleneck is ~40 µs of **JavaScript** per draw in the wgpu worker (decode command → look up objects → build state → call dawn.node, which itself converts JS objects to C++). A native Dawn draw with state changes costs roughly **1-3 µs** in C++. If the per-draw path ran in C++, worker time could drop from ~80 ms to ~10-20 ms per frame. **That's the only lever that by itself could reach 30 FPS at 1080p**, if the engine ceiling allows it (file 02 2B).

## What it means
- Write a Node native addon (C++, N-API) that reads the same command ring from wasm shared memory and issues Dawn calls through Dawn's C/C++ API (`webgpu.h` / `dawn::native`). The JS worker keeps only setup and rare work (resource creation, shader/pipeline creation, readbacks, present), and passes object handles to the addon.
- The addon needs access to the **same GPUDevice** that dawn.node created. Research whether dawn.node exposes native handles (`WGPUDevice`). If it doesn't, the addon must own the device and do everything (larger scope).

## Do NOT start building without the owner's OK. First a feasibility report (1-2 sessions):
1. Toolchain: Visual Studio Build Tools + node-gyp/cmake-js on this PC (C: has ~16 GB free; Dawn builds are large, so use D:/E:).
2. Dawn: is a prebuilt Dawn (headers + lib) available for Windows x64, matching dawn.node's version (`webgpu` npm v0.6.2)? Or build Dawn from source (hours on 2 cores).
3. Can a second native module share the device with dawn.node? Read the dawn.node source (`dawn/src/dawn/node`).
4. Prototype size: the hot path is only the per-draw opcodes (`SET_*`, `DRAW*`, `UPLOAD_BUFFER`, pass begin/end). List them from the worker's opcode table (`SCREENSHOT: 9, LOG: 10, CREATE_BUFFER: 11, ...` near the top of `wgpu_worker.js`).
5. Estimate: hours, risk, expected µs/draw. Report to the owner with numbers.

## Cheaper middle step (try first, inside JS)
- Batch work per draw: avoid creating JS objects per call (descriptor objects in `beginRenderPass`, arrays in `setBindGroup` with dynamic offsets). dawn.node has to convert every JS object to C++. Reusing preallocated objects/typed arrays can cut the binding cost. Measure µs/draw before and after (file 09 rules).

## Pass (for the feasibility report)
A clear yes/no with: toolchain status, Dawn availability, device-sharing answer, an effort estimate, and the expected FPS from math (draws × µs).
