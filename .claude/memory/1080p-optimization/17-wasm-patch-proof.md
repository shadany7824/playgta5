# 17 — Proof-of-concept wasm patch succeeded (2026-11-21)

## What was done (copy only, original untouched)
- Source copy: `E:\Malik\game\game-copy.wasm` (original game.wasm untouched).
- Patched WAT: `E:\Malik\game\game-patched.wat` — replaced one function body:
  - before: `(func $GetGameFrame__ (type 21) (result i32) i64.const 12321252 i32.load)`
  - after: `(func $GetGameFrame__ (type 21) (result i32) i32.const 0)`
- Recompiled: `wat2wasm --enable-all` → `E:\Malik\game\game-patched.wasm` (63,201,488 bytes, 0 errors).
- Validated: `wasm-validate --enable-all` → exit 0.
- SHA-256 original copy `11CA8D2C...E83E0`, patched `662F8310...A089A` — genuinely different binary.

## Meaning
This proves we CAN surgically rewrite compiled-engine behavior despite having no C++ source: WAT round-trip → edit one function → recompile → valid wasm. Risk remains: the loader caches/fetches `game.wasm` by URL, so serving a patched binary requires changing the loader's fetch URL/version (as Grand-V PR #38 did).

DO NOT load `game-patched.wasm` in the game: `GetGameFrame` returning 0 is a deliberate proof-of-concept change that would break timing. This is not a performance patch.
