# 13 — Measure where the time goes before you optimize anything

## The lesson
Optimization without a measurement is guessing. First find **which part takes the time**, then attack that part. Otherwise you'll speed up something that wasn't slow.

## What happened here
- In Chrome, four optimization attempts (WAT recompile, folding clears, yield 2048, depth-view proxy) **all failed to raise FPS**. They targeted parts that weren't the main cost.
- The Node 1080p run then gave a clear breakdown per frame (`diag-step3-1080.txt`):
  ```
  worker busy 83-93% (~80 ms/frame)
  TIME draw ~60-63 ms, bind groups ~10 ms, pipelines 2-7 ms, present ~3 ms
  ~1,350-1,570 draws/frame → ~40 µs per draw
  GPU wait 0
  ```
  That says: **the CPU work of encoding draws in JavaScript is the wall**, not the GPU, not the pixels. So the plan targets fewer draws (engine LOD, density, occlusion) and cheaper draws (Dawn flags, state dedup, C++ path), not shaders or resolution.

## How to apply
1. Get a breakdown: per-phase timers (like the worker's `TIME` field), a CPU profiler (`node --cpu-prof`, Chrome DevTools), or counters.
2. Ask: **is it CPU or GPU?** (GPU wait 0 = CPU-bound.) Is it one thread or many?
3. Rank the parts by time. Work on the top one. A 50% win on a 5% part is only 2.5%.
4. Re-measure after every change with the same setup (lesson 15).

## Questions to answer before optimizing
- What is the frame budget? (30 FPS = 33 ms, 20 FPS = 50 ms)
- Which part is over budget and by how much?
- Does the part scale with draws, pixels, or objects?

## One-line rule
**Profile first. Guessing is how four patches fail in a row.**
