# 03 — A forced call outside the normal flow is not evidence

## The lesson
If you call an internal function by hand (from a debugger, from JS, from a test harness) **outside its normal context**, any crash you get may come from the missing context, not from the bug you are hunting.

## What happened here
To "test" the file-system init, a session called the engine's `Load()` function directly from JavaScript with `table.get(64n)` on the main thread, before the engine had set up its own state. It crashed with `null function or function signature mismatch` inside `operator new`. That crash was then used as **proof** that `std::call_once` was broken.
But the engine's allocator (`operator new` → RAGE's allocator through a vtable) was never set up for that hand-made call. The crash was **created by the experiment**. The real engine never calls `Load()` that way.

## How to apply
- Before forcing a call, ask: *what state does this function expect?* (thread, allocator, initialized globals, arguments).
- If it crashes, first suspect the experiment. Write "forced-call crash, not normal-flow evidence".
- Prefer **observing the normal flow**: add a log line inside the import or function and let the program call it naturally (lessons 05 and 09).
- Remove forced-call experiments from the code before the next real test. They can hide the real failure or cause new ones.

## Questions to ask yourself
- Would the program ever call this function this way by itself?
- Am I on the same thread the engine uses for this?
- Are the arguments real, or did I invent them?
- If this crash went away, would it prove anything about the real bug?

## One-line rule
**Test the real path. A crash you created proves only that you created it.**
