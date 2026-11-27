# 10 — Threads, process priority, GC (small but cheap wins)

## Hardware reality
i3-7100U: **2 cores / 4 threads**. The engine starts ~11 threads (main, RenderThread, DVD/HDD reader + streamer, ResourcePlacement, ControlMgr, gtaSched, audio mixer, StreamingLive, ...) plus the io worker and the wgpu worker. The wgpu worker is the bottleneck (~90% busy). **It must never wait for a core.**

## Levers (one per run)
1. **Process priority:** start node at High priority: `start "" /high /b ..\node24\...\node.exe harness.js` in the `.cmd`, or after start: `wmic process where name="node.exe" CALL setpriority "high priority"`. Don't use Realtime (it can freeze Windows). Measure FPS + worst frame.
2. **Background load:** close Chrome game tabs, downloads, indexing during tests. Record what was running (`tasklist`). Memory 06 has the earlier 2-hour audit of per-process CPU.
3. **Power plan:** Windows "High performance" / "Best performance" while plugged in (laptop CPUs throttle on Balanced). Check `powercfg /getactivescheme`. Report it; ask before changing system settings.
4. **V8 GC in the wgpu worker:** many short-lived objects per draw cause minor GCs. Add to the worker's `execArgv`: `--max-semi-space-size=64` (MB), as its own run. Check the CPU profile (file 02) for "GC" time before and after.
5. **pthread pool size:** memory says `game-node.js` was patched with `pthreadPoolSize=2`. Check the current value (`grep -o "pthreadPoolSize[^,;]*" game-node.js`) and how many engine threads start vs "skipped" (log: `engine thread N` / `engine thread skipped`). Make sure no thread that matters is skipped and nothing waits for a pool worker (that shows up as a slow start). Don't raise it blindly: more threads on 4 logical CPUs can make the wgpu worker lose its core.
6. **Worker yield cadence:** the worker yields every ~2 ms (`1080p-optimization\03-optimization-plan.md` step 4e; tried 2048 in Chrome with no gain). Only re-test on Node if the CPU profile shows time in the yield/event loop.
7. **Affinity (experiment):** letting Windows schedule is usually best. If the profile shows the wgpu worker being preempted, test process affinity (all 4 logical CPUs, which is the default) versus nothing else. Per-thread affinity isn't available from Node. Low priority lever.

## Measure
FPS average **and** worst frame / count of frames > 100 ms. Priority and GC mostly affect smoothness.

## Pass
Keep anything that improves the average ≥ 3% or cuts hitches noticeably without making Windows unresponsive. Put the kept ones into the final `Play-Node-Dawn.cmd`.
