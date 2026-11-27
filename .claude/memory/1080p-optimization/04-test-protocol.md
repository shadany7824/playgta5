# 04: A/B test protocol for 1080p changes

## Baseline URL (true 1080p, best known config from note 14)
`http://localhost:8000/?low=0&mode=sandbox&res=1920x1080&fps=60&slots=5&log=1&args=-textureQuality=1,-shadowQuality=0,-reflectionQuality=0,-particleQuality=0,-grassQuality=0,-cityDensity=0,-pedVariety=0,-vehicleVariety=0,-lodScale=0,-pedLodBias=0`
No launcher has this exact URL (checked 2026-11-21). `Play-Final.cmd` = 960x540 + texture 2 / reflection 1 + `fx=hd`. `Play-Max.cmd` = 1920x1080 with every quality setting at 2. The URL above is the `Play-Final.cmd` args with note 14's best 1080p settings (texture 1, reflection 0) and `log=1`. Keep it fixed for every A/B.

## Before every run
1. Server up: `Get-NetTCPConnection -LocalPort 8000 -State Listen` + HTTP 200 on `/__support/` (start detached via WMI, see note 01 / U24).
2. **One game tab only**, close other heavy tabs (Office tabs skewed note 14).
3. Mark `game-log.txt` length. Read only the bytes appended after the mark (`[IO.File]::OpenRead` + `Seek`). The file is 188 MB.
4. Confirm the fresh run: `[page env]` and `world shown` appear after the mark.

## Test A: the change itself
- Load the same save, stand at the **same spot, same camera**, wait 30 s after `world shown` (pipelines warm).
- Collect 3 consecutive `fps:` lines (30 s). Record fps, draws/frame, worker busy, ms/frame, and the stutter line's gpu-wait.
- Revert (or toggle the `?flag`), reload, same spot, 3 lines again.
- A win = mean FPS gain > 1 FPS **and** ms/frame lower at a similar draws/frame.

## Test B: does resolution change the draw count?
Same spot: `res=960x540` vs `res=1920x1080`, nothing else changed. Compare draws/frame. Result goes in `05-measurements.md`.

## Always check
- `validation errors +0` in every fps line.
- Screenshot: image unchanged (no black areas, missing shadows, wrong depth fog).
- `node --check` on the patched file before loading it.

## Never
- Compare different scenes or a menu/title frame (those show 4-15 draws/frame and 15-25 FPS, which is meaningless).
- Present a low-mode or 960x540 number as a 1080p result.
