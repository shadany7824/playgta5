# Handoff: finish the lighting harness on Windows

You are on a Windows PC with a real GPU. The harness is built and tested in a cloud container with no GPU.
Your job is to run it on the GPU, check the gates, record the results, and push. Contract: `docs/DESIGN.md`.

## 1. Setup (once)

```
Setup.cmd
```
Needs Python 3.11+. It creates `.venv`, installs `requirements.txt` and Chromium. Then confirm Vulkan sees the GPU:
```
.venv\Scripts\python -c "import wgpu; [print(a.info['device'], a.info['adapter_type']) for a in wgpu.gpu.enumerate_adapters_sync()]"
.venv\Scripts\python -m pytest -q
```
Expected: your discrete GPU listed, then all tests pass (382 pass in the container).

## 2. Run (in this order)

```
Run-Harness.cmd --phase0 --perf
Inspect.cmd
```
The run takes roughly 1 hour (the Mitsuba references are most of it; they are cached for later runs).
Output: `runs\<time>\` (`runs\LATEST` names it).

## 3. What "pass" means

| Check | File | Pass when |
|---|---|---|
| Phase 0 parity | `phase0\parity.json` | every entry: p99.9 ≤ 1 LSB and mean ≤ 0.1 LSB |
| Phase 0 performance | `phase0\perf.json` | native GPU p50 and p95 ≤ web GPU p50 and p95, same adapter on both sides |
| Gates | `gates.json` | `reference` and `threejs-native` have 0 failed (by-design skips are fine) |
| Run | `report.md` | "Failures" section empty |

If parity fails: open `phase0\sheets\*.png`. Fix the port at its source, following `docs\PHASE0.md` (never re-type
three.js maths by hand), and re-run `.venv\Scripts\python -m tools.parity --run runs\<time>`.

## 4. Record

Add a "Windows GPU run" section to `STATUS.md` with: GPU and driver, parity results, perf gate numbers (web vs
native p50/p95), gates summary, real failures and their causes, and step run times (from `run.json`). Fill the
"Parity results" and "Performance gate" sections of `docs\PHASE0.md` with the same numbers.

## 5. Commit and push

```
git add STATUS.md docs/PHASE0.md
git commit -m "Record Windows GPU run: Phase 0 gates and full comparison"
git push origin claude/amazing-newton-fa70kr
```
`runs\` and `cache\` are gitignored; do not commit them.

## Known (expected, not bugs)

- three.js Lambert ignores rect lights → `cal_rect_plane`, `cal_furnace` are by-design skips for three.js.
- HemisphereLight sky has no occlusion → large direct errors in `occluded_canyon` and courtyard interiors.
- Probe at the camera: underestimates indoor indirect light, counts the sky twice outdoors, SH9 can go negative.
- `future` engine shows as skipped ("not wired"); `docs\FUTURE_ADAPTER.md` is its contract.
- If both a discrete and an integrated GPU exist, check that both `adapter` fields in `phase0\perf.json` name the
  same GPU (`--power high-performance` is the default intent; Chromium cannot pick a GPU by name).

## The game mirror (not needed for the harness)

Only `Launch-Local.cmd` (playing the game) uses it. Extract `mirror.rar` at the repo root so that
`<repo>\mirror\playgta5.com\index.html` exists. Before running the game, verify it:
```
runtime\python.exe check_mirror.py
```
Any CHANGED or EXTRA file means the pack is not the published snapshot: do not run it.
