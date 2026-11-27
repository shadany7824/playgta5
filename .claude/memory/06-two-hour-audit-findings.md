# 06 — 2-hour live audit (started 2026-11-20 22:17, PID 12200)

## Setup
- Detached PowerShell sampler: `E:\gta\playgta5\.claude\memory\audit-2h.ps1`
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File audit-2h.ps1 -DurationSec 7200 -IntervalSec 10`
- Output: `audit-2026-11-20.csv` (raw samples) + `audit-2026-11-20-summary.md` (10-min rollups), same folder.
- MUST be launched detached via WMI `Win32_Process.Create` (see U24); verify in a later tool call.

## Initial findings (first ~7 min)
- GPU 3D engine: **67–79%** overall; per-process: Chrome **GPU process ~68–79%**, dwm ~6%. GPU is NOT saturated.
- CPU: Chrome **renderer PID 10784 consumed 150–297 CPU-seconds per ~70 s sample** = ~2–4.4 cores continuously. i3-7100U has only 4 logical threads → **CPU is the true wall**.
- RAM: 63→76% used, 7.4→4.7 GB free during sampling (browser caches growing). Still not the bottleneck.
- Power plan: only one scheme exists — `HoneCtrl's Power Plan` (GUID 44444444-...), active. CPU at 2400/2401 MHz — no throttling.
- Chrome priorities: GPU process was AboveNormal, renderer Normal → **set all 11–13 Chrome processes to High** at 22:2x. Watch next CSV rows for any CPU/GPU change (no FPS counter available without `log=1`).
- Stray processes: 5 msedge processes still alive after closing the game tab (background), plus Copilot/Defender; low CPU, negligible.
- `log=1` off for current run; `game-log.txt` stays at 92.2 MB — no new log I/O. This removed the 96 MB logging overhead concern (it was cumulative across runs, ~1–2 MB/min).

## Owner's report
Owner says the game now plays at ~13 FPS after our tuning (from ~5–7 FPS), and asks to find any running thing that can increase it further.

## What to check when the audit finishes
1. Did setting Chrome priority to High change CPU/GPU ratios? (compare rows before/after 22:2x)
2. Any process that spikes CPU/RAM periodically (Defender, copilot, watcher, PowerShell)?
3. GPU util ceiling: if ~80% and renderer CPU still 3–4 cores, no further software tune will help — needs stronger CPU/GPU.
4. Save conclusions here and in `02-performance-benchmarks.md`. Do not claim a fix without measured FPS.
