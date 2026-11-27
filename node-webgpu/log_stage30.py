def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)

add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 11 — Internal resolution / upscale test (Stage 30, 2026-11-24)
Setup: TRUE internal sizes (WGPU_WIN_W/H env + -width/-height + SEARCH res all set), display param tested then found inert in Node. Owner had other windows open -> FPS noisy; TIME draw / draws is the reliable metric.
| Internal | FPS (noisy) | draws | TIME draw | us/draw |
|---|---|---|---|---|
| 1920x1080 | 7.53 | 1164 | 96.8 ms | 84.4 |
| 1600x900 | 9.10 | 1118 | 78.3 ms | 70.0 |
| 1440x810 | 8.14 | 1250 | 90.2 ms | 71.9 |
| 1280x720 | 9.76 | 1138 | 68.3 ms | 60.5 |
- Lower internal res cuts draw TIME ~29% (96.8 -> 68.3 ms) but draws barely change (scene variance) -> cost is per-pixel/GPU, not culling (contrary to file 11's Chrome observation).
- KEY FINDING: Node has NO upscale path: present() blit is gated by `if (t && canvasCtx)` and canvasCtx is null in Node ("canvas false" in logs). DISPLAY=1920x1080 is ignored. Screenshots are at internal size. Chrome path DOES have the canvas blit + display upscale.
- Therefore Node's "upscale to 1080p" needs new code: offscreen blit target + readback at display size. Not a config-only change. Reverted display override (worker-boot.js), harness restored 1920x1080.
- No config kept; true native 1080p remains 7.6 FPS (Stage 29).
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 30: file 11 internal-res test done; Node has no upscale path (2026-11-24)
- True internal 1920/1600/1440/1280 all ran with no window-resize, validation +0. Lower res: TIME draw 96.8 -> 68.3 ms (-29%), fps ~7.5 -> ~9.8 (owner windows open, noisy).
- DISPLAY=1920x1080 in worker-boot.js is inert in Node because canvasCtx is null; Chrome has the blit path. Screenshots remain at internal size. Reverted display override; harness restored 1920x1080.
- Implementing Node upscale needs an offscreen present target (new code), not env. Next options: implement Node upscale path, or engine levers 07/08/13.
''')
print('logged')
