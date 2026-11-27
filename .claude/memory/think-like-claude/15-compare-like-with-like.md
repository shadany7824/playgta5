# 15 — Compare like with like, or the comparison means nothing

## The lesson
An A/B test is only valid if **everything except the one thing you test is the same**: settings, scene, load, caps, measurement window. Otherwise you're measuring the difference in conditions.

## What happened here
- The fair 1080p test (Stage 19) compared Node vs Chrome with **the same resolution, quality args, mode, uncapped FPS**, and checked that draws/frame were within **2.8%** (1,344 vs 1,382). Only then was "+104%" accepted.
- Traps that were avoided or caught:
  - Screenshot runs showed ~21 FPS, but screenshots add readbacks (~0.8 submits/frame), so those numbers were **not** used for the A/B.
  - Scene variance is huge: the same preset gave 10.6 FPS in a light scene and 6.5 FPS at 2,640 draws. FPS without draws/frame is meaningless.
  - Capped vs uncapped: comparing a 30-capped run with an uncapped one just shows the cap.
  - An extra Chrome game tab doubles the load (memory 01).

## How to apply
- Fix the setup in writing (resolution, all args, mode, spawn point, duration, warm-up to ignore).
- Record the "context" numbers with the result: draws/frame, worker busy %, GPU wait.
- Accept a comparison only if the context matches (±15% draws). If the lever's purpose is to cut draws, report both draws and FPS **plus screenshots**.
- Warm-up: ignore the first ~30 s (shader compiles, streaming).
- Check background load (`tasklist`) before each run.

## One-line rule
**Same setup, one change, or it's not a test.**
