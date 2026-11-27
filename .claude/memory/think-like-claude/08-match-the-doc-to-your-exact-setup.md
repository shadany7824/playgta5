# 08 — Match every doc, issue and forum answer to your exact setup

## The lesson
A doc quote is only evidence if it describes **your exact mode, version and platform**. Many tools have several modes with different rules. Check that the doc's mode is yours before you trust it.

## What happened here (twice)
1. **Emscripten:** the quote *"std::call_once is not available"* came from the **Wasm Workers** API page. This game is built with **pthreads**, a different threading mode where `call_once` works. The quote was true, but about a different setup. It led to a wrong "hard blocker".
2. **Dawn / Tint:** the agent tried `enable swizzle_assignment;` to dodge a shader-compiler bug. It failed with `expected extension` because that WGSL feature only exists in Dawn from **2026-08-27**, and our pinned Dawn is from **2026-08-22**. The fix was real, but for a newer version.

## How to apply
Before using any external source, write down:
- **Mode/flavor:** pthreads vs Wasm Workers; D3D12 vs Vulkan; dev build vs release.
- **Version:** the exact version/commit we run (e.g. `native-dawn` 0.1.6 → Dawn rev `1e975e28`, 2026-08-22). Compare it with the date/version the fix or feature landed.
- **Platform:** Windows vs Linux, Node vs browser, x64 vs arm64.
- Does the doc's example look like our code/logs? If not, be careful.

## How to find our exact version
- Package metadata (`package.json`, `upstream.json`).
- Startup logs (adapter/backend info, runtime version).
- `node --version`: PATH node was 22 and broke, the bundled Node 24 works.
- Git object/commit dates when a dependency pins a revision.

## One-line rule
**A true answer for a different setup is a wrong answer for yours.**
