# 19 — On-screen touch controls added (2026-11-21)

## What was added
- `mirror\playgta5.com\touch-controls.js` — overlay that appears when `?touch=1` or on a touch device. No engine/wasm change.
- `index.html` — one line added before `</body>`: `<script src="/touch-controls.js"></script>` (backup `index.html.bak-touch-20261121`).
- `support\settings.html` — new "5 · Mobile touch" card launching `/?touch=1&low=1&res=800x450&fps=30&slots=5`.

## Controls
- Left pad: W/A/S/D via synthetic keydown/keyup with `code` + `key`.
- Right buttons: JUMP (Space), ENTER (F), FIRE (mouse button 0), AIM (button 2), RUN (ShiftLeft), RELOAD (R).
- Camera: touch-drag anywhere on the canvas dispatches synthetic `mousemove` with clientX/clientY, using a virtual cursor initialized at canvas center.

## Verification
- `node --check` clean for both the new JS and the index module script.
- Visually confirmed on PC with `?touch=1`: buttons visible at bottom-left/right over the loading screen.
- Real touch behavior not yet tested on a phone.

## Remaining mobile blockers
Phone still needs a reachable server (current binds 127.0.0.1), HTTPS with a trusted LAN cert (WebGPU/SharedArrayBuffer secure context), and Chrome Android 133+ (WebGPU + Memory64). iPhone Safari has WebGPU but no Memory64. Performance on phone likely very poor.
