# 12 — If it works elsewhere, the bug lives in the difference

## The lesson
When one setup works and another doesn't, the cause is almost never in the shared part. It's in **what is different**: the host, shims, glue code, versions, config. Look there before blaming the shared core.

## What happened here
- `game.wasm` (the shared core) worked in Chrome and failed in Node. Every real bug was in the **Node glue**:
  - Node 22 couldn't parse table64 → use Node 24 (Stage 1).
  - Workers didn't know they were pthreads → `WorkerGlobalScope` shim (Stage 2).
  - `worker.onmessage` (browser API) ≠ `worker.on('message')` (Node API) (Stage 6).
  - `'a+'` file mode can't truncate on Windows → `'r+'` (Stage 8).
  - Missing `-rootdir=/game/` argument (Stage 16).
  - The `onmessage` setter added a **new** listener every time, so messages were delivered twice and a thread crashed (Stage 17).
  - `wasm_input_publish_js` / `wasm_audio_publish_js` returned early on Node, so the start-menu choice and audio were never wired.
- The **native Dawn** shader bug (file 19) is the same pattern: the shaders work with one Dawn build and fail with an older pinned one. The difference (the Dawn revision date) is the bug.

## How to apply
1. Write down what is shared (same binary, same data) and what differs (runtime, shims, versions, args).
2. Rank the differences by how much code we wrote ourselves. **Our own glue is the most likely suspect.**
3. Look for API mismatches: browser vs Node semantics (`onmessage`, `postMessage`, `XMLHttpRequest`, `location`), OS file modes, BigInt vs Number.
4. Look for early returns like `if (process.versions.node) return;`. They switch features off silently.

## One-line rule
**Shared code is innocent until the differences are cleared.**
