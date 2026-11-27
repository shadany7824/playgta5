# 28 — Keep memory true: correct it, don't just add to it

## The lesson
Memory is only useful if it's **current and correct**. When a saved conclusion turns out wrong, edit the old text (mark it retracted, point to the correction) the same day. A wrong verdict left in memory will mislead the next agent.

## What happened here
- The "std::call_once HARD BLOCKER" was in `CURRENT-PROBLEM.md`, `ERROR-TRACE.md` Stage 13, the README and `engine-code-map/README.md`. When it was disproved, **every copy** was changed: Stage 13 retitled "RETRACTED — see Stage 14", the blocker line replaced, the README status rewritten. A grep for "HARD BLOCK" confirmed no stale copy was left.
- The status box at the top of `CURRENT-PROBLEM.md` always says the newest truth first ("SOLVED ...", "NEXT GOAL ..."), with history below.
- Each solved problem got a "how it was solved" file (memory 16), so the method is kept, not just the fix.
- Mistakes were turned into universal rules in `~/.claude/mistakes/` (U13 got the call_once case and a new rule line).
Owner rule U15: stale memory → verify vs live; edit old lines; fix first, log after.

## How to apply
- After every stage: update the top status, then the detailed log.
- When you disprove something: grep memory for the old claim and fix **all** copies.
- Mark history clearly ("earlier investigation, superseded by ...").
- Put facts in one place and link to it instead of copying it into five files (copies go stale).
- Write absolute dates ("2026-11-25"), never "yesterday".

## One-line rule
**Wrong memory is worse than no memory. Fix it everywhere, the same day.**
