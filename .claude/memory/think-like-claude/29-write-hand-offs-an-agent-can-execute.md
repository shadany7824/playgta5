# 29 — Write hand-offs another agent can execute without guessing

## The lesson
A hand-off is good when a fresh agent with **no memory of this session** can do the next step correctly. That means exact paths, exact commands, exact pass checks and the known traps, not "improve the FPS".

## What a good hand-off in this project contains
Look at `next-steps\STEP-1...md`, `1080p-30fps-engine-plan\`, `19-swizzle-bug-solution\`:
1. **Goal** in one sentence.
2. **Verified starting state** (what already works, with the evidence file).
3. **Exact locations:** file paths, line numbers or grep commands to find them, memory addresses.
4. **The change:** real code or exact args, plus backup instructions.
5. **Run command** with the right runtime (Node 24) and where output goes.
6. **Pass checks:** concrete log lines or numbers ("`start mode: sandbox`", "draws > 500", "0 swizzle errors").
7. **If it fails:** what to look at next.
8. **Rules:** one change per run, no git, log a Stage.
9. **What NOT to do:** traps already hit (don't edit the mirror worker, don't restore the wrong backup, D:/ path doesn't exist).
10. **Report format** back to the owner.

## How to apply
- Before writing a path or a function name, **check it exists** (grep). Hand-offs with invented names waste the next agent's session.
- Mark uncertainty explicitly ("confirm the env var name in the code", "inference, not proven").
- Keep each file focused on one step or lever. Put an index README on top.
- Test any code you put in a hand-off first (lesson 18).

## One-line rule
**Write it so a stranger could do it right the first time.**
