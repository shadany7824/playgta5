# 02 — Read the real stack trace, frame by frame

## The lesson
The stack trace tells you **where** the program died. Read every frame from the top. Don't jump to the function you already suspected.

## What happened here
An earlier session believed the crash came from `std::call_once`. The actual log (`node-webgpu\pthread-msg-log.txt`, lines 10-13) said:
```
LOAD ERR RuntimeError: null function or function signature mismatch
  at operator new(unsigned long)   wasm-function[100]
  at (anonymous namespace)::Load() wasm-function[192]
  at game-node.js:1:125790
```
The top frame is **`operator new`**, the memory allocator, called from `Load()`, which was called from **our own JavaScript**. There is no `call_once` frame at all. Reading the three lines was enough to see that the theory didn't match.
Later, the real crash (`RuntimeError: unreachable at CFileMgr::MountAudioPacks`) was read the same way. The top frame named the exact function, and reading that function (lesson 06) gave the cause.

## How to apply
1. Copy the full error and stack into your notes. Never paraphrase it.
2. Read the **top frame**: that's where it failed. Write its name and number.
3. Read the **next frames**: who called it, and was the call path normal or something we forced?
4. Read the **bottom frames**: which part of *our* code started this chain?
5. Compare with your theory. If your suspected function isn't in the stack, your theory is probably wrong.

## Special cases
- `unreachable` in wasm usually means an assert/abort the engine itself hit on purpose. Look just before the `unreachable` in the decompile for an error message.
- "null function or function signature mismatch" means an indirect call through an empty table slot, often because something wasn't initialized in this context.
- If our own file (`game-node.js`, `harness.js`) is in the stack, ask whether we caused this call path.

## One-line rule
**Believe the stack, not the story.**
