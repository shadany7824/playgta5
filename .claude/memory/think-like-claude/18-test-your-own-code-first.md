# 18 — Test your own code before you hand it to anyone

## The lesson
Code you just wrote, even ten clean-looking lines, has bugs you can't see by reading it. **Run it on real cases (including the tricky ones) before you give it to an agent, a user or production.**

## What happened here (today)
Claude wrote a `flattenSwizzles()` function to work around the native Dawn shader bug and put it in the solution file. Before handing it over, it ran a 10-case unit test. Result:
```
FAIL single "v.xyzw.xy.x" got v.xyzw.xy.x want v.x
single 9/10
```
The bug: in "single" mode the regex `\.([xyzw]{1,4})\.([xyzw]{1,4})` first consumed `.xyzw.xy`, skipped it (outer not single), and the global replace then **jumped past** the overlapping `.xy.x`, so the real trigger stayed in the shader. The fix: a separate regex for single mode that only matches a one-letter outer swizzle. After that: **10/10 in both modes.** Then it ran the fixed function over all 4,808 real shaders.
Without the test, the agent would have applied a fix that silently missed nested cases, and the bug would have "come back" in other scenes.

## How to apply
1. Write the expected input → output table **before** you test (include the nasty cases: nesting, overlap, boundaries, invalid input).
2. Run it. Every failure is a gift.
3. Then run on **real data** (all shaders, a real log, a real DB copy), not only examples.
4. Put the test script path in the hand-off, so the next person can re-run it.
5. Especially test: regex with global replace (overlaps!), loops that must terminate, off-by-one, empty input.

## One-line rule
**If you haven't run it, it doesn't work yet.**
