# 19 — One change per run

## The lesson
Change **one thing**, run, measure, then decide to keep or revert. If you change three things and the result changes, you don't know which one did it, and a crash can't be traced.

## What happened here
- Owner rule U22 came from bundling several untested tuning changes into the live launcher, which caused a fatal crash.
- The post-FX experiment (memory 11) changed seven args at once (`-postFX=0,-fxaa=0,-tessellation=0,...`). FPS got **worse** (12.7-13.2 vs 16.5), and it's still unknown which arg caused it.
- The solved stages worked the other way: Stage 16 changed only the args line and proved `-rootdir=/game/`. Stage 17 changed only the `onmessage` bridge and proved the duplicate-delivery fix. Each stage has one change and one result, so each one is trustworthy.

## How to apply
- Write down the change before you run: file:line, old → new.
- Run the same test setup (lesson 15).
- Record the result as its own stage (ERROR-TRACE `## Stage N`).
- Keep or revert. If you revert, run once more to confirm you're back to baseline.
- Exception: clearly connected parts of **one** fix (e.g. a function and its single call site) count as one change. Unrelated tweaks never do.

## When you're tempted to bundle
- "It's just a flag": flags crash too (`skip_validation` can crash on a bad call).
- "I'm sure both help": then proving them one by one is cheap.
- "Runs take long": a wrong bundle costs more runs to untangle.

## One-line rule
**One change, one run, one verdict.**
