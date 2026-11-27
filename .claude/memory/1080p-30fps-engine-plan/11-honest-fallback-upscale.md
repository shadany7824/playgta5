# 11 — Honest fallback: near-1080p internal render + GPU upscale to a 1080p screen

## When to use
Only if files 03-10 together can't reach **20 FPS at native 1920x1080**. This is a fallback and must always be **labelled** "internal WxH upscaled to 1080p", never "1080p" (rule U23).

## Why it can help even though we're CPU-bound
The worker cost is per draw, not per pixel. But **the engine draws more at higher resolution**: in Chrome, true 1080p produced ~2x the draws of 960x540 in comparable scenes (memory 10), likely because LOD and screen-size culling depend on resolution (small far objects get dropped at lower res). Lower internal resolution can therefore cut draws as well as GPU pixels.

## What already exists
- GPU upscale in the worker (memory `13-true-gpu-upscale.md`): the canvas/present is configured at the **display** size, and the final blit samples the internal image with a sharpened bilinear filter (5-tap unsharp + grade, memory 12). It's driven by a `display=WxH` parameter. Check how it reaches the Node worker (`loader.js` forwards `?display=`; in Node the wgpu worker reads its own `location.search` set by `worker-boot.js`, currently `''`). You may need to set `display=1920x1080` in the Node worker's search string (in the Node-only setup only).
- Note: in Node there is no visible window until playable step 5 exists, so "display size" means the size of the final present texture / screenshot.

## Runs (one per run, all with the best kept levers from 03-10)
| Internal (`-width/-height`) | Display | Label |
|---|---|---|
| 1920x1080 | 1920x1080 | native (reference) |
| 1600x900 | 1920x1080 | 83% scale |
| 1440x810 | 1920x1080 | 75% scale |
| 1280x720 | 1920x1080 | 67% scale |

## Measure
FPS, draws/frame, plus **screenshots at display size** for each, the same spot, and a crop of a detailed area (text on signs, wires, foliage) to show the owner the sharpness cost. Note that memory 10 measured 960x540 + `fx=hd` ≈ 16 FPS in Chrome. Node should be well above that.

## Deliverable to the owner
A table: `internal res | FPS | draws | screenshot path`, and a clear sentence:
"Native 1080p reaches X FPS with levers [list]. The 20-FPS floor needs internal WxH (Y FPS)." Let the owner choose; don't decide for them.

## Don't
- Don't present upscaled numbers as native 1080p.
- Don't stack the CSS `fx=hd` filter (Chrome path) on top of the WGSL sharpen. One sharpening pass only.
