# 12 — "GTA-5-FPS-Booster-2026" repo — AVOID (2026-11-21)

Repo: `github.com/wretchedseal/GTA-5-FPS-Booster-2026-FPS-Optimization`.

## What it actually is
- Only `README.md` + `LICENSE`, 2 commits, 11 stars, 2 forks. **No code.**
- README just sends users to an external forum (`gamex-fps-booster.forumotion.com/f9-gta-5-fps-booster`) to download `Latest Version.zip` and run **`LatestVerison.exe`** (note the typo).
- Claims: "unlock every frame", "no configuration", "works with any hardware", "eliminate stutter" — impossible marketing, no technical detail.

## Why not to use it
- Documented 2026 scam pattern: fake GitHub repos targeting gamers with infostealer/malware downloads (NordVPN, BleepingComputer, Malwarebytes reports on fake emulator/game-tool repos). A random `.exe` from a forum behind a marketing README is exactly that shape.
- Even if legitimate, it targets **native installed GTA V** (Windows, DX11 GPU). Our setup is a browser WebAssembly/WebGPU port with no `GTA5.exe` or `d3d11.dll` to patch.
- Our FPS wall is the JS WebGPU worker replaying ~2000 draws/frame; we already patched it directly.

**Verdict:** do not download or run it. No FPS benefit, real malware risk.
