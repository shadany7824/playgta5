# 14 — Do the math before you promise a target

## The lesson
Turn the goal into numbers: **budget, current cost, needed cut**. That tells you which levers are big enough, and whether the goal is possible at all, before you spend days on it.

## What happened here
Owner goal: 1080p at 20-30 FPS. Current: 12.4 FPS, worker ~80 ms/frame.
```
20 FPS = 50 ms/frame → worker ≤ ~45 ms → cut ~45%
30 FPS = 33 ms/frame → worker ≤ ~30 ms → cut ~63%
cost ≈ draws × µs/draw = ~1,500 × ~40 µs ≈ 60 ms
```
From this:
- 20 FPS is plausible with e.g. ~25% fewer draws **and** ~25% cheaper draws.
- 30 FPS needs a big drop in µs/draw (C++ path: ~1-3 µs/draw) **or** a big cut in draws, **and** the engine itself must be able to produce 30 frames (to be measured).
- Small levers (GC flags, priority) can't reach the goal alone. They're polish.
This is why the plan has file 02 (engine ceiling) before the levers, and why the C++ path is called "the only lever that alone could reach 30".

## How to apply
1. Convert the target to a time budget (ms per frame, ms per request, rows per second...).
2. Break the current cost into a formula (count × unit cost).
3. For each lever, estimate which term it changes and by how much.
4. Check the **other** limits too (here: the engine's own frame time, GPU wait, hardware: 2 cores / HD 620).
5. Be honest: "20 looks reachable, 30 depends on the measurement in file 02" is better than "we'll get 30".

## One-line rule
**If the math doesn't add up on paper, it won't add up in the game.**
