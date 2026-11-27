# 16 — Hardware and Windows: cheap real-world wins (owner actions, not code)

These don't need code. The agent should **check and report**. Changing system settings or buying parts is the owner's decision.

## 1. RAM: get full dual-channel (biggest hardware win for an iGPU)
- Memory 00: slot 1 = Samsung **4 GB** DDR4-2133, slot 2 = Kingston **16 GB** DDR4-2133 → Intel **flex mode**: only 8 GB runs dual-channel, the other 12 GB single-channel.
- Intel HD 620 uses system RAM as video memory. Single-channel halves bandwidth for anything that lands in the upper 12 GB.
- Fix: replace the 4 GB stick with a **16 GB DDR4-2133 (or faster, it runs at 2133) SO-DIMM**, ideally the same model as the Kingston → 32 GB full dual-channel.
- Effect: mostly helps when the GPU becomes the limit (GPU wait > 0) and for CPU memory bandwidth. Today we're CPU/JS-bound, so expect a modest gain now and a bigger one after files 03/09/13.

## 2. Power plan and plugged in
- Run on AC power. Check `powercfg /getactivescheme`; "High performance" or "Ultimate performance" (needs enabling) avoids clock drops.
- The i3-7100U has **no turbo** (fixed 2.4 GHz), so power plans matter less than on turbo CPUs. Still verify that the clock doesn't drop below 2.4 GHz during play (Task Manager → CPU speed).

## 3. Thermals and dust
Laptop vents clear, on a hard surface. Check the CPU temperature during a 10-minute run (HWiNFO). Throttling shows as the clock dropping below base.

## 4. Intel graphics driver
Check the HD 620 driver version (`Get-CimInstance Win32_VideoController | select Name,DriverVersion,DriverDate`). Old OEM drivers can have poor D3D12/Vulkan CPU overhead. The newest Intel driver for 7th gen is usually better (Intel's generic driver; the laptop OEM may block it). File 03's backend comparison should be re-run after a driver update.

## 5. Background load (2 cores = every % counts)
During play: close other Chrome tabs, stop downloads, OneDrive sync, Windows Update, indexing, antivirus scans. Consider excluding `E:\gta\playgta5` from real-time antivirus scanning (the game reads thousands of files): owner decision. Memory 06 has the 2-hour per-process CPU audit method; re-run a short version during a Node session.

## 6. Disk
The game mirror is on E: (an **HDD**). Streaming on an HDD causes hitches (file 06). C: is an SSD with only ~16 GB free, too small for the 21 GB mirror. An SSD for E:/D:, or freeing space on C:, would reduce streaming stalls (not average FPS).

## Report
The agent writes the current state of 1-6 (measured values) and the recommended owner actions in `RESULTS.md`, clearly marked "owner action".
