# 04 — When a working version exists, diff against it first

## The lesson
If the same program works in another setup (Chrome vs Node, prod vs local, old vs new), **list every difference** in how it is started and fed: arguments, environment variables, config, URL query, files, versions. The bug is almost always in that list.

## What happened here
The game crashed in Node but worked in Chrome. Three sessions looked deep inside the engine (call_once, "a gate inside the wasm").
The browser starts the engine in `mirror\playgta5.com\index.html` with:
```
args: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', ..., '-nonetwork', '-width=..', ...]
```
The Node harness (`harness.js` line 102) passed only `['-low', '-res=640x360']`. The engine even printed `Unknown option 'low'`, and nobody acted on that warning.
Adding `-rootdir=/game/` fixed the crash in one run. The engine reached the loading screen, then the world.

## How to apply
1. Find where the working setup starts the program (launcher, page, script). Copy its exact arguments/config.
2. Find the same place in the broken setup.
3. Write both side by side. Every difference is a suspect.
4. Make the broken one match the working one, **one difference at a time** if they're many (lesson 19), or all at once if they're clearly "missing basics" like a root path.
5. Read startup warnings: `Unknown option`, `missing`, `fallback to default`. They point straight at config mistakes.

## Where differences hide
- Command-line arguments and their order.
- Environment variables (`process.env`), current working directory.
- Query strings forwarded or not forwarded (the loader whitelisted only some params, memory runtime-lod-write-result).
- Files loaded from a different path (mirror vs dev copy).
- Runtime version (Node 22 vs Node 24 broke on BigInt/table64).

## One-line rule
**Before you open the engine, open the launcher.**
