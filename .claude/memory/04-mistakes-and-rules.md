# 04 — Mistakes made in this project → universal rules

1. **Tested low-mode visual overrides while the owner asked for MAX FPS.** Rule: when the owner names a mode ("max", "high", "quality"), verify the exact URL/flag that defines it (`low=0` vs `low=1`) BEFORE running multi-minute benchmarks. Do not silently substitute an easier preset and present its numbers as the answer.
2. **Started the game server with `Start-Process` from a tool shell → it died when the shell exited** (Chrome showed `ERR_CONNECTION_REFUSED`, no log written). Rule: background services launched from an agent shell must be detached via WMI `Win32_Process.Create` (or a scheduled task); verify with `Get-NetTCPConnection` + HTTP 200 in a later tool call, not just in the same one.
3. **Reported 4 GB RAM from an early check after the machine had been upgraded to 20 GB.** Rule: for hardware claims, re-read live at the moment of the claim; note when the value changed mid-session.
4. **Read FPS lines from the old tail of `game-log.txt` and mistook them for a fresh run.** Rule: mark file length before a run and read only appended bytes; confirm `[page env]` / `world shown` from that run.
5. **Drew a RAM conclusion from a single screenshot while two game tabs were open.** Rule: close duplicate tabs before benchmarking; one game instance only.

Core mistakes index entries to check: U01 (verify), U05 (stale version), U13 (wrong root cause), U15 (stale memory), U22 (untested tuning).
