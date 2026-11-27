# 01: What limits true 1080p (proved from game-log.txt, 2026-11-21)

Source: last ~60 MB of `E:\gta\playgta5\game-log.txt`, `[wgpu] fps:` lines with 1400-2000 draws/frame + the `stutter:` line after each.

## Numbers (true 1920x1080, all worker patches from note 14 active)
| fps | draws/frame | submits/frame | worker busy | ms/frame busy |
|---|---|---|---|---|
| 7.3 | 1841 | 2.2 | 92% | 124.7 |
| 8.3 | 1922 | 1.7 | 95% | 114.6 |
| 7.9 | 1943 | 1.7 | 94% | 118.4 |
| 7.4 | 1996 | 1.6 | 94% | 127.7 |
| 7.8 | 2018 | 1.7 | 96% | 121.3 |
| 8.4 | 1441 | 1.6 | 87% | 101.6 |

Worst-frame breakdown at 1080p (stutter line, ms: idle/pipeline/modules/uploads/**gpu wait**/submit):
`204: 17/0/0/0/0/5`, `193: 0/0/0/0/0/0`, `188: 0/0/0/6/0/5`. So **GPU wait = 0 ms** and **worker idle ≈ 0**.

## What this proves
1. **The JS GPU worker is the wall, not the HD 620 GPU.** The worker never waits on the GPU (`gpu wait 0`) and is never idle. It spends ~120 ms of CPU time per frame turning engine commands into WebGPU calls.
2. **Cost per draw ≈ 60 µs** (120 ms ÷ ~2000 draws), including the ~12 other commands per draw (constant-buffer uploads, state sets). The code comments say ~25,000 commands per frame.
3. Submits are already low (1.6-1.7/frame after readback batching), so submit count is not the problem any more.
4. Pipelines +0 and bind groups +77..528 per 10 s: pipeline compiles are not the problem; bind-group creation is small.
5. Pipeline from engine → worker: the engine emits more draws at 1080p (about 2000) than at 960x540 (about 1200). **Not proved whether that's resolution or scene.** Test it first (04, test B).

## Why fewer pixels didn't help before
960x540 → 800x450 gave no gain (note 02). That fits: pixel count barely matters because the CPU-side worker, not GPU fill, sets the frame time. 1080p is slower mainly because it **draws more** (if B confirms it) and some passes scale with pixels (depth proxies, clears: see 02).

## Machine context (from 00)
i3-7100U = 2 cores / 4 threads. The engine (wasm threads), this GPU worker, the IO worker and Chrome's GPU process all share 4 threads. Any CPU the engine burns is CPU the worker can't have.
