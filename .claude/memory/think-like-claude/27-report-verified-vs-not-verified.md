# 27 — Report what is verified and what is not, plainly

## The lesson
Every report has two lists: **what you proved** (with the evidence) and **what you didn't check**. Never let "not checked" hide inside a confident sentence. Never say "done" without having seen the result yourself.

## What happened here
Good examples from this project:
- After the `-rootdir` fix: "reached the loading screen, ~31 FPS at 12 draws/frame, 0 validation errors. **Not verified yet:** actual pixels (no screenshot), gameplay FPS." The next step (screenshots) was then planned instead of assumed.
- The agent's Step 2 report: it opened `shot_001500.png` and described it (Franklin in a red jacket, glass walls, minimap). That's a verified render, not "screenshots were written".
- The free-model answer said: "I couldn't benchmark these two on your task myself."
Owner rules behind this: U01 (said "done" without seeing it), U08 (hedged instead of finishing the check).

## How to apply
- Format: **Result → Evidence (file, log line, screenshot) → Verified / Not verified → Next step.**
- "Verified" means you saw it in this run: a log line, an opened image, a measured number.
- If you can finish a check in a few minutes, **finish it** instead of writing "probably" (U08).
- If something truly can't be checked, say why and ask one precise question.
- Failures are reported as plainly as successes, with the error text.

## Words to avoid without evidence
"Should work", "probably fixed", "it renders" (did you open the image?), "faster" (by how much, measured how?), "done".

## One-line rule
**Say what you saw. Say what you didn't. Never blend the two.**
