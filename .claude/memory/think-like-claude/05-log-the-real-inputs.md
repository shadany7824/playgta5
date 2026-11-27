# 05 — Log the real inputs at the lowest level you can reach

## The lesson
Don't guess what the program is trying to do: **print it**. One log line at the right place (a system call, an import, an API boundary) often ends days of theory.

## What happened here
The engine couldn't open its audio packs. Instead of reading more engine code, Claude added **one line** to the two file system calls in `game-node.js`:
```js
// inside ___syscall_openat and ___syscall_stat64, after the path is decoded
globalThis.__diag && globalThis.__diag("PATH openat " + path);
```
One run later the log said:
```
PATH openat E:/P1/gta5/build/dev_ng/x64/audio/audio.rpf
```
That's Rockstar's internal dev path, not the `/game/...` path the web file system serves. That single line pointed straight to the missing root argument (lesson 04).

## How to apply
- Find the **narrowest boundary** where the input passes through: syscalls (`open`, `stat`), imports from wasm to JS, HTTP requests, DB queries, API calls.
- Log the actual value (path, URL, SQL, arguments), not "called".
- Keep it cheap and removable: behind a flag or an existing `__diag` helper, with a backup of the file.
- Run once, read the values, then decide.
- Remove or gate the logging after (it can slow everything: one line per file open = thousands of lines).

## Good boundaries in this project
- `___syscall_openat` / `___syscall_stat64` → which files the engine wants.
- `wasm_httpfs_manifest_js`, `wasm_httpfs_io_start_js` → whether the web file system starts.
- `wasm_input_publish_js`, `wasm_audio_publish_js` → whether input and audio are wired.
- The `[wgpu] fps:` line → what the GPU worker does per frame.

## One-line rule
**One printed value beats ten theories.**
