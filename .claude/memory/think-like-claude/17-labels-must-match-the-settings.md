# 17 — A result's label must match its exact settings

## The lesson
"Max", "1080p", "high", "fixed" are claims about settings. Every reported number must carry the **exact** settings it was measured with, and must never be labelled with a stronger setting than it really had.

## What happened here
- Owner rule U23 came from a real mistake: an easier preset was benchmarked when the owner asked for **MAX**, and its numbers were presented as the answer.
- True MAX in this project is a specific recipe: `-textureQuality=2,-shadowQuality=2,-reflectionQuality=2,-particleQuality=2,-grassQuality=2,-cityDensity=2,-lodScale=2,-pedVariety=2,-vehicleVariety=2` (memory 01). The 1080p tests so far used texture 2 / shadow 0 / reflection 1 / rest 0. That's "1080p optimized", **not** "1080p max".
- Rendering at 960x540 and upscaling to a 1920x1080 window looks 1080p-sized but is **not** native 1080p. The plan's file 11 forces the label "internal WxH upscaled to 1080p".

## How to apply
- Write the full settings next to every number: resolution (internal + output), all quality args, FPS cap, mode, scene.
- Use the owner's names only when the settings match their definition exactly. If unsure, use plain descriptions ("1080p, shadows off").
- When a goal can't be met at the named setting, say so and show what **can** be met, labelled honestly. Let the owner choose.
- In tables, keep separate rows for each preset. Never merge them into one "best" number.

## One-line rule
**The label is part of the result. A wrong label makes the whole result false.**
