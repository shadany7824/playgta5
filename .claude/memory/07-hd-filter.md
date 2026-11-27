# 07 — HD upscale/sharpen filter (`?fx=hd`) — added 2026-11-20

## Research findings
- Port already had CSS/SVG compositor filters via `?fx=sharp|pixel|punch`, injected at serve time by `serve_local.py:16-34` (`improve_game_page()`); whitelist at `:25-26`, styles at `:27-29`, SVG filter at `:30-33`.
- True FSR-like upscale would require patching `wgpu_worker.js`: `makeBlit()` at `:2416-2431` has an inline full-screen-triangle WGSL that currently does a 1:1 `textureLoad`; `present()` at `:2646-2663` sets canvas size = back-buffer size, so no GPU upscale happens. Real upscale needs display size plumbed from `index.html` (`wantSize()` `:375-383`) + new sampler/bind group + edge-adaptive shader. Doable but risky; NOT done.
- Web research: FSR1 = EASU (edge-adaptive upscale) + RCAS (contrast-adaptive sharpen), spatial only, no history/ghosting; Babylon.js has FSR1 pipeline, and pmndrs/upscaler has WGSL FSR3 ports. For a 2× 720p→1080p upscale, a CSS unsharp after browser compositing is the cheap approximation.

## What was implemented (safe, reversible)
- `E:\gta\playgta5\serve_local.py`: added `fx=hd` to whitelist; style `html.fx-hd #canvas{filter:url(#fx-hd) saturate(1.04) contrast(1.02);will-change:filter;}`; SVG `<filter id="fx-hd">` with `feConvolveMatrix order="3" kernelMatrix="0 -0.18 0 -0.18 2.42 -0.18 0 -0.18 0"`.
- Original sharp kernel was `0 -0.5 0 -0.5 3 -0.5 0 -0.5 0` with saturate 1.12/contrast 1.06/brightness 1.02 — owner said too sharp; softened 2026-11-20, server restarted detached (PID 11776), verified `2.42` in served HTML, game relaunched.
- Server restart required: killed old PID 10712 + watcher, started detached via WMI → new server PID 12104, watcher 5676. Verified served HTML contains `fx-hd`.
- New launcher `E:\gta\playgta5\Play-Max-HD.cmd`: true max `low=0`, `res=1280x720`, `fps=60`, `slots=5`, all quality args 2, plus `fx=hd`; same Chrome flags + High priority loop as other launchers.
- Verified via screenshot: URL bar shows `...&fx=hd...`, game running with filter active.
- `Play-Max.cmd` was separately edited to `res=1920x1080` per owner's earlier request — NOT the filter path; it will be much slower (~3-4 FPS expected, unverified).
- 2026-11-20 owner wanted a "lens" look that adds no 3D geometry: added post-composite CSS looks `fx=cinema` (soft sharpen + warm sepia + hue), `fx=vivid`, `fx=cool`, `fx=noir` in `serve_local.py`. All are compositor-side filters after the canvas is presented — they do NOT add triangles/draws; FPS cost not separately re-measured (fx=hd was already active in the 16.5 FPS runs). Added to `support/settings.html` "Lens / look filter" dropdown. Verified new classes in served HTML.

## Caveat
`fx=hd` sharpens the already-upscaled canvas in the compositor — it cannot invent detail that 720p never rendered. It makes edges/text look crisper on a 1080p screen; it is NOT real FSR. If the owner wants true FSR, patch `wgpu_worker.js` per Option B above and re-verify isolation + FPS.
