# 24 — Run long jobs in the background, and keep working

## The lesson
Scans, builds and game runs that take minutes should run **in the background** with their output going to a file. Meanwhile, do the work that doesn't depend on the result. Never kill a long job with a short timeout and then conclude "it doesn't work".

## What happened here
- An earlier session's PowerShell scan over all shaders **timed out at 120 s** and the check was left open (file 19, risk #3).
- Today the same kind of scan (Node script over 4,808 files on the HDD) took ~5 minutes. It ran in the background. Claude checked that the process was alive (it showed low CPU because it was waiting on the disk, which is normal for an HDD), then wrote the solution files while waiting, and used the result when it finished.
- The second scan (applying the fixed function to all shaders) also ran in the background while this lessons folder was written.
- Game runs: the harness is started with an explicit timeout (150-300 s) and output to `diag-*.txt`, then the file is read after the run.

## How to apply
- Estimate the duration (files × disk speed, build size, run length). If more than ~1-2 minutes, background it.
- Always write output to a file (`> E:\gta\_tmp_claude\x.out 2>&1`).
- Check it's alive if it's quiet: process list + CPU time. Low CPU on an HDD job is normal.
- Don't poll in a tight loop. Wait for the completion notice, or check at sensible intervals.
- Work on the independent parts meanwhile (docs, the next file, the test plan).
- If a job is killed by a timeout, the result is "unknown", not "failed". Re-run with a longer limit.

## One-line rule
**Slow is fine. Killed-too-early-and-guessed is not.**
