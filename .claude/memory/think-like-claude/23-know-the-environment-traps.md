# 23 — Know the environment traps before they waste a session

## The lesson
Many "bugs" are environment problems: the wrong runtime version, a full disk, a missing folder, a slow drive, a process that died with the shell. Check them first and write them down, so no one hits them twice.

## Traps in this project (all real)
| Trap | Symptom | Fix |
|---|---|---|
| PATH `node` is v22 | `invalid table elements limits flags`, `Cannot convert a BigInt value to a number` | Always use `E:\gta\playgta5\node24\node_modules\node\bin\node.exe` (v24) |
| **C: drive full** (0 GB) | Temp files vanish, tools fail, the session scratchpad is unusable | Put temp/build files on E: (`E:\gta\_tmp_claude\`) |
| Default screenshot path `D:/wasm_tmp/` | No PNGs appear | Set `WGPU_SHOT_PREFIX` to an E: folder |
| Server started with `Start-Process` from an agent shell | Server dies when the shell ends (U24) | Start detached with WMI `Win32_Process.Create`, verify with a separate call |
| HDD (E:) | Scanning 4,808 shader files takes ~5 minutes, a 120 s timeout kills it | Run long scans in the background (lesson 24) |
| Two Chrome game tabs | FPS halves | Close extras before measuring |
| `console=1` / diag logging left on | Slower runs, huge logs | Turn off for benchmarks |
| Windows file modes | `EPERM ftruncate` with `'a+'` | Use `'r+'` |

## How to apply
- At the start of a session: check the runtime version, disk space (`df -h` / `Get-PSDrive`), the server (`curl .../manifest.json` → 200), and leftover processes (`tasklist`).
- When a strange error appears, ask "environment?" before "code?".
- Every new trap goes into memory (this table, or the project README) the same day.

## One-line rule
**Check the ground before you blame the building.**
