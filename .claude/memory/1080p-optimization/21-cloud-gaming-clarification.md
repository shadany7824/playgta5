# 21 — Cloud-gaming clarification (2026-11-21)

## Owner's intent
Owner wants the **laptop to run the game** and the phone to just stream it — true cloud-gaming style — not the current setup where the phone downloads/runs the 63 MB wasm over LAN.

## Why current LAN HTTPS page is not that
`https://192.168.1.35:8000/?touch=1...` still executes the whole wasm engine in the phone's browser. It needs WebGPU + Memory64 on the phone and hits the same draw-call wall on a much weaker CPU/GPU. It is remote *hosting of files*, not streaming of rendered frames.

## Correct approach
- **Sunshine (host on PC) + Moonlight (client app on phone)** — free/open source. Sunshine captures the laptop screen, encodes video (Intel QuickSync supported on Skylake+ iGPUs like HD 620), Moonlight sends input back.
- **Steam Link + Steam Remote Play** — also free; can stream non-Steam shortcuts (unsupported but commonly works via Big Picture). Needs Steam installed/signed in.
- A browser page cannot do this alone; it needs host software + a client app.

## Hardware caveats
- i3-7100U / HD 620: QuickSync is available (Skylake+), but the CPU is already 95-100% busy running the game; encoding may add latency/lower FPS. Current game at 720p high is ~7-9 FPS, upscale preset ~16 FPS — streaming that will feel laggy.
- Sunshine docs (Nov 2026) list Windows 11+ for host; Moonlight setup guide says Windows 10 or 11. Windows 10 19045 here — may need an older Sunshine build or Steam Link instead.
- Host install + firewall requires admin; my earlier attempt to add a firewall rule failed with Access denied.

## Next step
Ask owner which route they want (Sunshine+Moonlight vs Steam Link) and phone OS before installing anything.
