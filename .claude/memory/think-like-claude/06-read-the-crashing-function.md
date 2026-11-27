# 06 — Read the function that crashed, all of it

## The lesson
When the stack names a function, **open its code and read the whole body**, especially the lines just before the crash point. The code usually says exactly which condition failed.

## What happened here
The crash was `RuntimeError: unreachable at CFileMgr::MountAudioPacks`. Claude dumped that one function from the 191 MB decompile:
```
awk 'NR>=4333012{print; if(/^}/) exit}' E:\Malik\game\game.dcmp
```
Every `unreachable` in it came right after:
```
if (eqz(rage_fiPackfile_Init(...))) { ... rage_diagErrorf(8367352L, 3128086L, ...); unreachable; }
```
So the engine aborts **on purpose** when a pack file can't be opened. Decoding string `3128086` gave "Unable to find critical archive '%s'". The question changed from "why does the engine crash" to "why can't it open this file", which is much easier.
Then the file-open function (`rage_fiDeviceLocal_Open`) showed that the web file system is only used for paths starting with `/game/` (lesson 07).

## How to apply
1. Get the function name/number from the stack (lesson 02).
2. Find it in the code index (`engine-code-map\engine-function-index.tsv` → line number) and dump only that function.
3. Find every crash/abort point (`unreachable`, `abort`, `throw`, `assert`) and read the condition right before each one.
4. Follow the failing call one level down (here `rage_fiPackfile_Init` → `rage_fiDevice_GetDevice` / `rage_fiDeviceLocal_Open`).
5. Stop when you find a concrete condition you can test (a path prefix, a flag, a null check).

## Tips for decompiled code
- Numbers like `3128086L` are memory addresses of strings/globals: decode them (lesson 07).
- `call_indirect` = a virtual or function-pointer call. Its target depends on data.
- Don't read 1,000 functions. Read the one in the stack, then one level down.

## One-line rule
**The crash line is the answer key. Read the lines right above it.**
