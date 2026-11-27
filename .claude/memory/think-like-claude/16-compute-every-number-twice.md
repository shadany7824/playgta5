# 16 — Compute every number you report twice, two different ways

## The lesson
Your own script can be wrong (wrong lines, wrong window, double counting). Before you report a number, **recompute it a second, independent way** and check that both agree.

## Where this matters here
- FPS averages from `[wgpu] fps:` lines: compute with a script **and** check a few lines by hand. Make sure the window is the steady part (draws > 500, `pipelines +0/+1`), not the loading screen (12 draws/frame at "31 FPS" means the loading screen, not the game).
- Scan counts: two different shader scans gave **24,300** and **20,984** chained swizzles. Different regexes count different things (identifier bases vs any base). Both agreed on the important part (0 scalar bases, 0 assignment targets), and the note says why the totals differ instead of hiding it.
- µs per draw = TIME draw ÷ draws/frame: check that the units match (ms/frame vs per-10 s totals).
- The owner's general rule U02 came from a real ×11 aggregation bug: looping over N items and summing the same unfiltered total each time.

## How to apply
1. Compute with your script.
2. Recompute another way: by hand for 2-3 samples, a different tool, or a sanity ratio (total ÷ count ≈ expected per-item value).
3. If they differ, find out why **before** reporting.
4. Report the method: "average of last 12 steady samples, script + manual check".

## Sanity checks that catch most errors
- Does the number fit the physics? (12 draws/frame is a menu, not a city.)
- Total ÷ items ≈ a believable per-item value?
- Same order of magnitude as the last measurement of the same thing?

## One-line rule
**One calculation is a guess. Two that agree are a number.**
