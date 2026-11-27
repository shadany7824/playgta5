# PlayGTA5 — download, play, and troubleshoot

> **Archival note:** This repository is the archival V1 port of the original browser game. V2 of Grand-V is at https://github.com/SebasKitten/Grand-V . Discord: https://discord.gg/MzFABxxSq7

[**Download installer ZIP**](https://github.com/alihammoud21/playgta5/releases/download/full-game-v1/PlayGTA5-Installer.zip) · [Installation](#download-and-play-on-windows) · [Mac](#download-and-play-on-mac) · [Higher-FPS setup](#performance--higher-fps) · [Report a problem](https://github.com/alihammoud21/playgta5/issues/new/choose)

**Want controllers, cheats, and the experimental development map?** Use the separate [**PlayGTA5 Enhanced** repository](https://github.com/alihammoud21/playgta5-enhanced). It reuses this installation and adds a launcher, standard-gamepad input bridge, cheat-code entry panel, and access to the existing `env_test` level. These are experimental additions; they are not Michael's unreleased source or a promise of 200 FPS. This main repo remains the download, verification, compatibility, and hosting path.

Download the complete browser-game snapshot, including **all 12,482 files in the `mirror` folder**. This is a compiled client snapshot, not the original game-engine source code.

The game data is approximately **21.2 GB (19.7 GiB)**. It is included in the repository's **GitHub Release downloads**, not ordinary Git commits, because some individual game files exceed GitHub's 100 MiB Git limit. **Code → Download ZIP alone does not contain the game data.**

**Use `Download-Game.cmd` after extracting the repository ZIP to install every part automatically. Part 01 alone is not playable.** “Online” in this guide means a website serving the browser game; it does not add GTA Online or multiplayer.

| Current status | What has been checked |
| --- | --- |
| Full download | Fresh installation: 12,527 game/runtime files passed SHA-256 verification. |
| Windows / Mac launch tools | Automated installation/server checks passed; Mac gameplay still needs hardware testing. |
| Public game hosting | Vercel deployments are disabled. The replacement full-site upload failed and is being retried; no new link is gameplay-verified yet. |
| Black world / GPU device loss | Reports remain under investigation; basic WebGPU checks do not prove world rendering. |
| FPS | Presets below reduce rendering load. No universal 90–200 FPS result has been measured for this release. |

## Stuck at 66%? Check this first

In **Chrome**, open `chrome://settings/system`, turn **Use graphics acceleration when available** **ON**, then click **Relaunch**. In **Edge**, open Settings → System and performance, enable the equivalent graphics acceleration setting, then restart Edge. Reopen the game after restarting the browser.

Chrome disables WebGPU when graphics acceleration is switched off ([Chrome troubleshooting guide](https://developer.chrome.com/docs/web-platform/webgpu/troubleshooting-tips)). This can fix one cause of a loading freeze; **66% is not a diagnosis**, and this does not fix every GPU/driver or missing-file error. If it still stops, open `http://localhost:8000/__support/`, copy the diagnostics, and report the **first red console error** after reloading. Check the troubleshooting section below before downloading the game again.

## Download and play on Windows

1. Download [**PlayGTA5-Installer.zip**](https://github.com/alihammoud21/playgta5/releases/download/full-game-v1/PlayGTA5-Installer.zip), extract it completely, and open its `PlayGTA5` folder. This small ZIP contains the current installers and help tools; the next step downloads the game. Cloning this repository or using **Code → Download ZIP** also works.
2. Double-click **`Download-Game.cmd`** in the extracted folder. It downloads every game archive from [the full-game release](https://github.com/alihammoud21/playgta5/releases/tag/full-game-v1), checks SHA-256 checksums, and extracts the complete mirror and bundled Python runtime. Keep the window open until it says **Download complete**. If interrupted, run it again to resume.
3. Double-click **`Launch-Local.cmd`**. Keep its server window open while playing.
4. Your browser opens **http://localhost:8000/__support/**. Review the compatibility checks, then choose the **lower-memory 720p / 30 FPS** launch option. Choose **Story Mode** or **Sandbox Mode** in the game. If your default browser is not Chrome or Edge, paste the local address into one of them.
5. Click the game to capture the mouse and enable sound. Press **Esc** to release the mouse. Close the server window when finished.

No Python installation, Netlify account, subscription, or API key is needed on Windows. The game runs on your own computer; this repository is not an online game-hosting service.

## Download and play on Mac

1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/macos/) and a current Chrome or Edge browser.
2. Download and extract [**PlayGTA5-Installer.zip**](https://github.com/alihammoud21/playgta5/releases/download/full-game-v1/PlayGTA5-Installer.zip). Open Terminal in its `PlayGTA5` folder.
3. Run `bash Download-Game.command`. All release archives are downloaded with resume support and verified with SHA-256. Only game assets are extracted on Mac; the Windows runtime and old release helpers are skipped.
4. Run `bash Launch-Local.command`. Keep Terminal open while playing. Open **http://localhost:8000/__support/** in Chrome or Edge and start with the lower-memory option.
5. Run `bash Verify-Game.command` to verify installed assets. Press **Ctrl+C** in the server terminal to stop playing.

The launch/download scripts work with native Python on both Apple Silicon and Intel; Rosetta and the Windows executable are not required. **Mac gameplay is experimental and has not been validated on Mac hardware.** A working Python server does not establish GPU/renderer compatibility. Check the browser report and share any rendering errors in the issue tracker.

For double-click launching, first run `chmod +x ./*.command` in that folder. If Finder will not open a script, use the Terminal commands above after reviewing the scripts; no system security setting needs to be disabled.

## Update an existing installation

Download the installer ZIP above (or the latest repository ZIP) and copy its helper files **and the `support` folder** into your existing installation, replacing old helpers. Keep `mirror`, `runtime`, and your browser saves. The installer preserves current helpers instead of extracting older copies from release archives. Do not extract the original release helpers over the update.

## Requirements

- 64-bit Windows for the bundled runtime; a recent **Chrome or Edge with WebGPU and hardware acceleration** enabled.
- The engine requires **WebAssembly Memory64** as well as WebGPU. Use a current browser; older versions can fail before rendering. The compatibility report checks Memory64 support.
- A capable GPU and sufficient memory. Tested locally on an RTX 3070 / 32 GB RAM computer; performance on other hardware is not guaranteed.
- About **25 GB free space** for automatic installation. Allow **45 GB** if keeping all manually downloaded ZIP files alongside the extracted game.
- Internet access for the initial roughly 21 GB download. The local game server serves the downloaded assets afterward.
- First world loading and shader preparation can take several minutes. Do not close the tab just because progress appears slow.

For lower-memory loading, try **http://localhost:8000/?low=1&fps=30&res=1280x720**. This reduces rendering load; it is a troubleshooting option, not a guaranteed fix for every GPU.

## Performance / higher FPS

Open **http://localhost:8000/__support/** for clickable presets. Start with **720p / 60**, compare the same location after shader preparation, and use **540p** if the GPU struggles. A 60 FPS cap allows a higher rate than the compatibility profile's 30 cap; it cannot make a slow device achieve 60.

| Preset | Local launch link | Tradeoff |
| --- | --- | --- |
| Compatibility | [720p / 30](http://localhost:8000/?low=1&fps=30&res=1280x720&shadows=0) | Lower load and a conservative frame cap. |
| Performance | [540p / 60](http://localhost:8000/?low=1&fps=60&res=960x540&shadows=0) | Fewer pixels, softer image. |
| Balanced | [720p / 60](http://localhost:8000/?low=1&fps=60&res=1280x720&shadows=0) | Start here after compatibility checks pass. |
| 1080p light | [1080p / 60](http://localhost:8000/?low=1&fps=60&res=1920x1080&shadows=0) | Sharper image; more GPU work. |
| Benchmark | [540p / uncapped](http://localhost:8000/?low=1&fps=0&res=960x540&shadows=0) | Measures headroom; can increase heat and power use. |

Every preset uses the existing `low=1` scene/texture settings with shadows off. Add `shadows=1` to compare low-quality shadows. The engine already enables its fast script interpreter and suppresses noisy script logs; these are existing optimizations, not new benchmark results. Lowering resolution from 1080p to 720p reduces rendered pixel count by about 56%, but FPS also depends on the CPU, GPU, shader compilation and asset streaming.

For a useful comparison, record **GPU/driver, browser version, resolution, low/shadow settings, FPS cap, mode, save/location and observed FPS/stalls**. Keep the same scene and let first-load shader work settle. Check the active GPU in `chrome://gpu` / `edge://gpu`, close other GPU-heavy tabs, and keep graphics acceleration enabled. More reserved RAM is not automatically faster. An uncapped setting does not create a 200 FPS guarantee.

Do not treat missing assets, a 66% audio-metadata stall, or a black world as an FPS problem. Use the troubleshooting steps below first.

## Manual download

Open [Releases → Full game v1](https://github.com/alihammoud21/playgta5/releases/tag/full-game-v1). Download **every `playgta5-part-*.zip` file** and **`file-inventory.json`**. These are independent ZIP archives, not split fragments: extract **all** of them into the **same empty folder**, and put `file-inventory.json` there too. One archive contains the launcher and runtime; the others contain the remaining mirror files. All parts are required.

**After extracting all 14 parts**, copy the latest repository's helper files and `support` folder into that installation, replacing the older release helpers. This provides the current launcher, troubleshooting page, and verifier. Keep `mirror` and `runtime`. If your browser says “Site wasn't available” for a ZIP, that part has not finished downloading; the inventory file cannot replace it.

The final folder should contain:

```text
Launch-Local.cmd
Start-Local.ps1
serve_local.py
runtime/
  python.exe
mirror/
  playgta5.com/
    index.html
    b/
    data/
```

Double-click `Launch-Local.cmd`. Do not open `index.html` directly: WebGPU workers, cross-origin isolation, and game-data reads require the included HTTP server.

## Verify the files

Run **`Verify-Game.cmd`** (Windows) or **`bash Verify-Game.command`** (Mac) after installation. It checks every game asset against the published SHA-256 inventory, plus the bundled runtime on Windows. Updated helper files are deliberately excluded because the inventory describes the original release. `python3 verify_game.py --all` also checks legacy helpers and will report expected differences after an update. Verification reads about 21 GB and can take a few minutes. Release ZIP checksums are listed in `SHA256SUMS.txt`.

The downloader does not overwrite existing files with different contents. If you have modified the game, download into a new empty folder instead.

## Other operating systems

On Linux, use Python 3.11+ with `python3 download_game.py`, then `python3 serve_local.py --open`. Browser/GPU support varies; Linux gameplay has not been validated. The bundled `runtime/python.exe` is Windows-only.

## Online hosting and availability

**The old Vercel link is currently disabled (HTTP 402 / `DEPLOYMENT_DISABLED`).** The full deployment succeeded, but the approximately 21 GB game exceeded the account's **10 GB Hobby deployment-storage allowance**. The account notification confirmed the storage limit. This was a hosting-capacity problem, not a missing game file or a timed expiry. The complete game does not fit on that free Vercel plan. See [Vercel's storage-limit announcement](https://vercel.com/changelog/hobby-projects-now-retain-fewer-deployments-to-free-up-storage).

The repository's Vercel configuration now publishes only the small help site in `public/`; it no longer rebuilds the 21 GB game on every push. This change alone does not remove existing deployment storage or reactivate a disabled account. Old large deployments must be reviewed in the Vercel dashboard before that URL can be restored.

A **Cloudflare Pages static deployment is being validated**. Its current free limits allow 20,000 files with a maximum of 25 MiB each, and static requests are free and unlimited ([limits](https://developers.cloudflare.com/pages/platform/limits/), [pricing](https://developers.cloudflare.com/pages/functions/pricing/)). `build_pages.py` verifies the downloaded mirror and splits large assets into 4 MiB pieces. The browser loader reconstructs byte ranges using cached pieces; it does not depend on a server implementing HTTP Range, paid R2 storage, or Pages Functions. Generated output stays out of Git.

To build after downloading the game:

```sh
python3 build_pages.py
npx wrangler@4.149.0 pages deploy pages-output --project-name YOUR_PROJECT --branch main
```

Building needs roughly **20 GB additional free disk space** alongside the local installation. The generated game uses HTTPS and COOP/COEP headers for WebGPU and shared-memory workers. Hosted defaults are lower-memory, 720p, and 30 FPS; explicit `low`, `res`, and `fps` URL parameters override them. The support page is at `/__support/`, with download instructions at `/help/`.

No free host can promise permanent availability or a guaranteed month of service. Provider limits, account status, policies, and rights-holder requests still apply. The release downloads and local launcher remain a fallback that does not depend on the public game website being online. A successful upload or network check does not certify gameplay on every GPU, Mac, or Android device.

## Troubleshooting

For a useful issue report, include the **exact launch URL, last loading message, first console exception, failed Network request/status, verification result, GPU/driver, installed RAM, browser/OS and mode**. Review the compatibility report before posting. A percentage or red console-message count alone does not identify the cause.

- **Missing mirror / blank page:** finish downloading and extracting every release part. Run `Verify-Game.cmd`.
- **Address already in use:** another server is using port 8000. Use its existing tab, close that server, or run `runtime\python.exe serve_local.py --port 8001 --open`.
- **WebGPU unavailable:** update Chrome/Edge and your graphics driver; enable browser hardware acceleration.
- **Out of memory / tab crash:** close other tabs and applications, then try the lower-memory URL above.
- **“No progress” despite free disk space:** disk space, system RAM, and GPU memory are different resources. The loading timer does not identify the cause. Updated launch helpers display a neutral stall message and a **Help / browser checks** link. Share the last loading step and first error rather than deleting files or buying RAM based on the timer.
- **`memory access out of bounds`:** this is a WebAssembly memory-access error, not proof of insufficient physical RAM. Verify the files and capture the first error/stack trace, your installed RAM and GPU, mode/map, and the action or loading step that triggered it. The browser's memory estimate is not a measurement of installed RAM. See [issue #9](https://github.com/alihammoud21/playgta5/issues/9).
- **Stuck at 24%:** first distinguish the installer's download percentage from the in-game loading percentage. Confirm all 14 parts installed, run verification, then collect the first red console error and any failed Network request with its HTTP status. See [issue #10](https://github.com/alihammoud21/playgta5/issues/10).
- **Low FPS:** start at `?low=1&fps=30&res=1280x720`. If stable, compare `?low=1&fps=60&res=1280x720` or `?low=1&fps=60&res=960x540` in the same place after shader preparation. The `fps` value is a cap, not a performance guarantee. Check the active GPU in `chrome://gpu` / `edge://gpu`. Native GTA V and this browser build can perform differently.
- **LAN / port forwarding:** the supplied server binds to `127.0.0.1`. A plain `http://<PC-IP>:8000` address does not get localhost's secure-context exception. Remote hosting needs trusted HTTPS and the isolation headers; forwarding a port or changing browsers alone does not supply them. Use the public HTTPS site or a correctly configured HTTPS reverse proxy. Android gameplay remains untested.
- **Graphics device lost / `DXGI_ERROR_DEVICE_HUNG`:** this reports a GPU device failure. Close all game tabs, stop the game server with Ctrl+C, then restart once. Update the browser and GPU driver (macOS updates include its drivers), and check `chrome://gpu` or `edge://gpu` for hardware acceleration and Problems Detected. Try the lower-memory 720p link. Do not change Windows TDR registry settings or enable unsafe browser flags. If it persists, post your GPU model, OS/browser versions, when it happens, and the first console error to [issue #1](https://github.com/alihammoud21/playgta5/issues/1). The exact cause is still under investigation.
- **Black world but audio/map/menu work:** verify the files, try the lower-memory link, and compare Story and Sandbox. Open developer tools (F12 on Windows, Option+Command+I on Mac), capture the first shader/WebGPU error and any failed asset request, and post them with the compatibility report to [issue #2](https://github.com/alihammoud21/playgta5/issues/2). HUD rendering alone does not prove that world rendering is working. Do not delete saves as a first troubleshooting step.
- **Download failure:** rerun `Download-Game.cmd`. Completed, verified archives are remembered. Available disk space and network restrictions can affect downloading.
- **No vehicle engine sound / broken minimap:** click the game to unlock browser audio and check tab mute. If other sounds work, identify an affected vehicle/location and any failed audio/texture request. Verify files and compare Story/Sandbox. Include a minimap screenshot and first error in [issue #13](https://github.com/alihammoud21/playgta5/issues/13); a confirmed fix is still pending.
- **Story restarts at the prologue:** use the same browser profile and exact origin, remove `newgame=1`, and check whether a manual save appears in the game's Load Game menu before closing. Private browsing, cleared site storage, and another port/hostname can give a separate or temporary save store. The current compatibility report includes storage usage/quota; keep your browser data while investigating [issue #11](https://github.com/alihammoud21/playgta5/issues/11). No save-import compatibility is claimed.
- **Saves after changing websites:** browser storage is separate for each origin. Moving from Vercel to Pages, or between a website and localhost, does not automatically transfer saves. Keep the old browser data; do not clear it as a first troubleshooting step.
- **Windows security warning:** distinguish an unsigned/unrecognized-app (SmartScreen) warning from a named antivirus detection. Record the exact warning, threat name if shown, affected filename, and download URL. Do not run a file that has a malware detection, disable antivirus, add exclusions, or restore a quarantined file just to launch the game. Matching SHA-256 checksums confirm the published bytes; they do not prove that a file is harmless.

The compatibility page checks WebAssembly Memory64, basic WebGPU device creation, shared-memory/isolation support, and a four-byte range read of the real WebAssembly file. It does **not** test every shader or certify gameplay. Diagnostics stay in your browser until you choose to copy and share them. See [Chrome's WebGPU troubleshooting guide](https://developer.chrome.com/docs/web-platform/webgpu/troubleshooting-tips) for browser checks.

## Development checks

Run `python3 -m unittest discover -s tests -v`, `node --check support/check.js`, and `bash -n mac-launcher.sh`. Tests cover the installer bundle, preservation/resume, checksums, unsafe paths, isolation headers, range reads, both batch formats, malformed requests, hosted startup checks, and cached piece reconstruction. With Node 24+, `node tests/check_hosted_transport.cjs https://YOUR_PROJECT.pages.dev` checks deployed headers, cross-piece ranges, the complete engine checksum, streaming compilation, and real 404 responses against the local mirror. This is a network/engine test, not a gameplay test. An existing mirror can be tested without copying it: `python3 serve_local.py --root /path/to/playgta5.com --port 8001 --open`.
