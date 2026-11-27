# 26 — Two failed attempts on the same thing: stop, research, reframe

## The lesson
If the same approach fails twice, a third blind try rarely works. Stop and change the question: **research the exact error**, read the code that decides the behavior, or check the assumption the approach is built on.

## What happened here
- **LOD writes:** writing 1.0, then 1.5 to the LOD global did nothing, twice. Instead of trying 2.0, 3.0, ..., the right move was to read the engine's setter, which revealed the missing flag bit (lesson 11).
- **Swizzle bug:** first try was `enable swizzle_assignment;` → failed (`expected extension`). Instead of trying other spellings, research showed the feature didn't exist yet in our Dawn version. That ended the route and led to the source rewrite.
- **The httpfs chain:** two sessions tried harder and harder patches inside the engine (forced `Load()`, `wasm_has_page_js → 1`). Reframing ("what does the engine try to open?", lesson 05) found the real cause in one run.
- The opposite mistake also counts: calling something "blocked" after one try (owner rule U14).

## How to apply
After the second failure, write down:
1. The exact error text, and search for it (official tracker, docs for **our** version, lesson 08).
2. The assumption the approach depends on. Is it proven?
3. One step *earlier* in the chain that you haven't looked at (lesson 09).
4. A different kind of evidence: a log at a boundary, the crashing function's body, a diff against the working setup.
Then pick the next attempt based on what you learned, not on "maybe a bigger number".

## One-line rule
**The third try should come from new knowledge, not new hope.**
