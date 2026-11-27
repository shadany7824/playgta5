# 00 — Verified machine facts (live check 2026-11-20)

Source: `Get-CimInstance Win32_Processor / Win32_VideoController / Win32_PhysicalMemory / Win32_OperatingSystem`

- CPU: **Intel Core i3-7100U @ 2.40 GHz — 2 cores / 4 logical threads** (soldered, cannot upgrade)
- GPU: **Intel HD Graphics 620** (integrated, shared system RAM; WebGPU through Chrome)
- RAM: **20 GB total** = slot 1 Samsung **4 GB** DDR4-2133 (`M471A5244CB0-CTD`) + slot 2 Kingston **16 GB** DDR4-2133 (`K1CXP8-MIF`). 2 slots used, max 32 GB.
  - Mismatched sizes → Intel **flex mode**: only 8 GB dual-channel, other 12 GB single-channel. For full dual-channel: replace the 4 GB stick with a matching 16 GB.
  - First check earlier in the session reported 4 GB — the 16 GB stick was added between checks (owner upgraded RAM mid-session).
- Drives: C: 118.7 GB total / ~16 GB free (SSD), D: 477.5 GB / ~404 GB free (HDD), E: 454 GB / ~356 GB free (HDD). Game mirror lives on E: (~21 GB).
- Windows: Windows 10 (19045), PowerShell 5.1.
- Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe` (installed, running).
- Task Manager screenshot (2026-11-20): CPU 100%, GPU 50%, RAM ~47% at that moment.

**Hardware floor:** HD 620 + 2 cores cannot do max graphics at playable FPS in this wasm/WebGPU port. RAM is NOT the bottleneck (11+ GB free even during the heaviest runs).
