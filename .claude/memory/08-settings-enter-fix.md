# 08 — Settings confirmation: Enter tap lost at low FPS (fixed 2026-11-20)

## Symptom
Owner: in-game Settings -> Graphics, after changing a setting the save-confirmation dialog hangs; pressing Enter on "Yes" does nothing.

## Root cause (proved by code, not guessed)
- `mirror\playgta5.com\index.html:538-559` input bridge sends key state to the engine as VK bytes in shared memory; the engine samples that state **once per rendered frame**.
- At max graphics this PC runs ~7 FPS (~140 ms/frame). A normal Enter tap (~50-100 ms) can be set on keydown and cleared on keyup entirely between two frame samples, so the Scaleform menu never sees it. Same risk for Backspace/Escape/arrows/Space and mouse clicks.

## Fix applied
- Backup first: `mirror\playgta5.com\index.html.bak-20261120`.
- Patched `installInput()` keyup handler: UI keys (`Enter`, `NumpadEnter`, `Backspace`, `Escape`, `Space`, arrows) are latched for **250 ms** after keyup instead of cleared immediately; `setTimeout` checks `held` so a real re-press still works. Movement keys unchanged.
- Syntax checked: extracted full `<script type="module">` → `node --check` clean.
- Verified served page contains `LATCH_MS`, and reloaded the game tab (Ctrl+R) so the new input bridge is live.

## Owner instructions
- Try the save dialog again with a normal Enter tap; if still stubborn, hold Enter ~0.5 s or click "Yes" with the mouse after clicking the canvas.
- `Shift+P` switches keyboard mode if the menu appears to ignore the keyboard.
- Do NOT clear site data (would lose saves).

## If it still fails
Restart with `log=1` and read `[page input] keydown Enter vk=13 hasFocus=... engineFocus=...` from `game-log.txt` to see whether the event reaches the page; then check whether the engine sample lands.
