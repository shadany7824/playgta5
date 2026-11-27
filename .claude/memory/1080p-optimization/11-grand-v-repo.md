# 11 — SebasKitten/Grand-V repo check (2026-11-21)

Repo: `github.com/SebasKitten/Grand-V` — 467 stars, 119 forks, 31 commits, Rust.

## What it actually contains
Only `.github/`, `LauncherApp/` (Rust native host: HTTP server, LAN/HTTPS hosting, multiplayer relay, asset downloader), `README.md`, and a logo. **No game assets, no mirror, no engine code.** README: "We do not supply, distribute, or host any game data, mirror files, or proprietary assets."

It is the same browser port family (WASM memory64 + WebGPU, RAGE reverse-engineered), with a friendlier Rust launcher. Features: Story/Sandbox, separate saves, graphics settings, controller/touch, experimental multiplayer, frame caps 24/30/60/120. System req: modern 4-core CPU, 8 GB low-memory / 16 GB+, WebGPU adapter.

## Issues checked (GitHub API)
17 issues. Relevant: #41 white screen, #33 black screen on old AMD + WebGPU compatibility mode (BGRA8UnormSrgb unsupported), #36/#30 Snapmatic photo crash, #35 incomplete assets, #20 "Low-RAM Fidelity" proposal. **#20 explicitly states**: "The public Grand-V repository currently contains launcher/server code and troubleshooting docs. The actual game package/renderer is external... launcher-only changes cannot fix game RAM usage or GPU frame time."

## Verdict
No FPS fix and no engine source. It confirms the same wall: the renderer/game is external, and the public repo is launcher-only. Our local E:\gta\playgta5 has the actual mirror/workers we already patched; this repo adds nothing for draw-call reduction.
