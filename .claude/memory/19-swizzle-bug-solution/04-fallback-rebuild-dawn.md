# 04 — Fallback (only if the WGSL rewrite can't clear all errors): native-dawn on a newer Dawn

## When
Only if file 03's T4/T5 still fail because of **Tint bugs other than this swizzle bug**, which the source rewrite can't fix. Ask the owner first: this is hours of build work and several GB of disk.

## Why it could work
The `native-dawn` package ships its build files: `CMakeLists.txt`, `scripts/*.mjs`, `src/`, and `upstream.json` with the Dawn revision (`1e975e28...`, 2026-08-22). Changing the revision to one **after the 2026-09-01 fix (CL 338555 / cherry-pick 338975)** and rebuilding gives a Dawn with the fix.

## Steps (research before running anything)
1. Read `native-dawn-test\node_modules\native-dawn\README.md` and `scripts\*.mjs`: how is Dawn fetched and built (depot_tools? cmake + ninja? which compiler)? Write the steps down.
2. Pick the Dawn revision: the newest Dawn commit that's at least a few weeks old and includes CL 338555 (check on `dawn.googlesource.com/dawn/+log`). Avoid a much newer Dawn: the `webgpu.h` C API changes over time, and `native_dawn_driver.node` (our C++ driver) may need edits to compile against it.
3. Toolchain on this PC: Visual Studio Build Tools (C++), CMake, Ninja, Python, Git. Check what's installed and ask the owner before installing anything.
4. **Disk:** C: is full (0 GB). Put the Dawn checkout and build on **E:** (`E:\gta\dawn-build\`), and point TEMP/TMP at E: for the build shell. A Dawn checkout + Release build needs roughly 10-20 GB.
5. **Time:** building Dawn on a 2-core i3 is slow (could be several hours). Build Release only, D3D12 (+ D3D11 if wanted) backends, no tests/samples.
6. Rebuild `native_dawn_driver.node` against the new `webgpu_dawn.dll` + headers. Copy the new DLLs (`webgpu_dawn.dll`, `dxcompiler.dll`, `dxil.dll`) where the harness loads them. Keep the old files as `*.bak-dawn-1e975e28`.
7. Test with file 03 T4 → T6, **without** the swizzle flatten first (`WGPU_FLATTEN_SWIZZLE=0`). That proves the new Dawn fixed it.

## Pass
0 Tint errors, draws > 500, validation +0, same screenshot, FPS ≥ the JS baseline.

## Don't
- Don't mix DLLs from different Dawn revisions.
- Don't overwrite `node24\wgpu\node_modules\webgpu` (the working JS-path Dawn). It stays as the safe fallback.
