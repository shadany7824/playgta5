# 10 — rage-engine-formats repo check (2026-11-21)

Repo: `github.com/Kalmarv/rage-engine-formats` (GPL-3.0, Rust 1.99+, 0.3.0 Nov 2026, ~10k SLoC).

## What it is
A **read-only Rust library** that parses GTA V RAGE file formats:
- RPF7 archives (nested, NG/AES ciphers — keys supplied by caller, none included)
- RSC7 resources → system/graphics pages
- Drawables/fragments/dictionaries: `.ydr`, `.yft`, `.ydd` (models, geometry, shaders, skeletons, lights)
- Texture dictionaries `.ytd`, collisions `.ybn`, clips `.ycd`, META/`.ymap`/`.ytyp`, Legacy `.fxc`, Enhanced `SGD2` shader DB, XML/RBF/gtxd.

## Limits (from docs/guarantees.md)
- **No writers** — cannot modify or repack any file.
- Does not ship/derive keys; needs the user's native GTA V install + key material.
- Does not decode pixels or render; a drawable is vertex/index buffers + shader params.
- Reads GTA V only; Enhanced layouts for resources, Legacy only for `.fxc`.

## Verdict for our FPS goal
Not a solution. It is a file-format inspector for asset-conversion work (`primase`), not engine source, not a code optimizer. It cannot reduce the ~2000 draws/frame the compiled wasm engine emits, and we cannot edit game assets through it (no writers; browser mirror is precompiled/hash-verified). Our bottleneck is the WebGPU worker replaying draw commands (note 01/14), not asset format knowledge.

Possible niche use: count geometry/shaders in drawables to understand why a scene has many draws — only if we had a native install + keys. We don't.
