# 01 — Rules and test protocol (read before ANY lever)

## Non-negotiable rules
1. **One lever per run.** Never bundle (mistake U22: bundled tuning crashed the live launcher).
2. **Back up before every edit**: `<file>.bak-<lever>-<date>`. Run `node --check` on edited JS. For wasm: `wasm-validate --enable-all`.
3. **Never touch the files the Chrome launchers use** (`mirror\playgta5.com\...`) for Node experiments. Make Node-only copies (see file 09 for the worker copy). Chrome must keep working.
4. **No "done/faster" without numbers from the log**, and a screenshot for anything that can change the image.
5. **Never present a lower-quality number as "max 1080p"** (U23). Every result states resolution + all quality args.
6. No git commit/push (owner's git).
7. Two failed attempts on the same lever → research (web + decompile) before a third (U14).

## Fixed test setup (so runs are comparable)
- Harness: `E:\gta\playgta5\node-webgpu\harness.js`, Node 24: `..\node24\node_modules\node\bin\node.exe harness.js`.
- Baseline args (harness.js line ~102): `-width=1920 -height=1080 -textureQuality=2 -shadowQuality=0 -reflectionQuality=1 -particleQuality=0 -grassQuality=0 -cityDensity=0 -lodScale=0 -frameLimit=0` plus the browser base args (`-rootdir=/game/` etc.). Don't remove `-rootdir=/game/`.
- Same start mode and spawn every run (currently story, startMode=1; if switched to sandbox=2, re-measure the baseline).
- Screenshots **off** for FPS runs (`WGPU_SHOT_EVERY` unset). `console=1` in harness SEARCH costs time: keep it the same for every run (better: off).
- Server :8000 up (200 on `/data/manifest.json`). No other node.exe / Chrome game tab running (`tasklist`).
- Run 300 s. **Ignore everything before the world is stable** (draws/frame > 500 and `pipelines +0/+1`).

## What to record (from `[wgpu] fps:` lines, every 10 s)
`fps`, `draws/frame`, `submits/frame`, `TIME draw/up/bg/pipe/ensure/present/shader`, `worker busy % (ms/frame)`, `passBegins/f`, `clears/f`, `validation errors`, and from the stutter line: `gpu wait`, worst frame.
Use the **last 12 steady samples**. Compute the average **twice** (a script and a manual check, rule U02).

## Comparability
- Compare only runs whose draws/frame differ by ≤ 15%, **unless the lever's whole point is to cut draws** (files 05-08). Then report both FPS and draws, and **attach screenshots before/after** so the owner can judge the visual cost.
- Also report **µs per draw = TIME draw ÷ draws** to see whether a lever made draws cheaper (03, 09) or just fewer (05-08).

## Logging
- Every run = new `## Stage N` in `engine-code-map\ERROR-TRACE.md`: lever, exact change (file:line / address / flag), result table, verdict (keep / revert).
- Kept levers go into a running table in `1080p-30fps-engine-plan\RESULTS.md` (create it): `# | lever | FPS before → after | draws before → after | µs/draw | visual cost | kept?`.
- Reverted levers: restore from the backup and run once to confirm you're back to baseline.

## Stop conditions
- If GPU wait > 0 appears, the GPU is now a limit; note it, and resolution/shadows become the levers.
- If a lever needs a big rewrite (multi-worker, render bundles), **stop and ask the owner** with numbers.
