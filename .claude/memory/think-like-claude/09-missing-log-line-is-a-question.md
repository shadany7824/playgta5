# 09 — A missing log line is a question, not an answer

## The lesson
When an expected log line never appears ("X was never called"), that tells you **where the flow stopped**, not **why**. Don't jump to a deep conclusion. Ask: *what had to happen before X, and did it happen?*

## What happened here
After the first correction, a session added diagnostics to the web file system imports (`MANIFEST`, `IO_START`) and saw that **they were never called**. It concluded: *"the gate is inside the wasm, needs a high-risk WAT patch"*.
But "never called" had a simple reason: the engine never asked for a `/game/...` path, because it was looking at `E:/P1/gta5/...` (missing `-rootdir`). The import was never reached because the step **before** it took a different branch.
The right question was: *what decides whether this import is called?* Answer: `rage_fiDeviceLocal_Open` checks for the `/game/` prefix (lessons 06 and 07).

## How to apply
1. Write the chain of steps that should lead to the missing line (A → B → C → X).
2. Add a cheap log at each earlier step, or read the code that decides the branch.
3. Find the **last step that happened** and the **first that didn't**. The bug is between them.
4. Only after that, decide whether the cause is deep (binary, compiler) or shallow (input, config, path).

## Typical reasons a line is missing
- A condition before it took the other branch (prefix check, flag, mode).
- The code runs on another thread/process whose logs go elsewhere.
- Your log helper doesn't exist in that context (lesson 10).
- The function was never reached because an earlier step failed quietly (returns -1, swallowed error).

## One-line rule
**"Never called" means look one step earlier.**
