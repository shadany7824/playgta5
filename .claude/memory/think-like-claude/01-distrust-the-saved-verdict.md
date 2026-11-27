# 01 — Distrust the saved verdict until you have checked it yourself

## The lesson
A conclusion written in memory, a ticket or an old log is a **claim**, not a fact. Before you build on it, check it against the raw evidence. Especially when it says "impossible", "hard blocker" or "needs a rebuild".

## What happened here
Memory said: *"HARD BLOCKER: std::call_once is unsupported, the game wasm must be rebuilt with the original toolchain (not available)."* It sounded final: it had web research, a decompile and a quote from the Emscripten docs.
Claude re-checked three things in a few minutes:
1. The quoted doc was about **Wasm Workers**, but this game uses **pthreads** (the logs showed `em-pthread` and the `cmd:1/cmd:3` protocol).
2. The **same game.wasm worked in Chrome**, so the binary couldn't be broken.
3. The real stack trace showed the crash in `operator new`, not in `call_once`.
The verdict was wrong. The real cause turned out to be a missing launch argument (`-rootdir=/game/`), found one run later.

## How to apply
- Read the saved verdict, then ask: **what is the evidence, and does it really prove this exact claim?**
- Find the raw source (log file, stack trace, code line) the verdict is based on and read it yourself.
- Look for a simple contradiction: does it work somewhere else? Does the cited doc match our setup?
- If the verdict holds, say "verified" and why. If not, write a correction into memory (lesson 28).

## Red flags that a verdict needs re-checking
- "Impossible", "blocked", "can't be fixed without X we don't have".
- The proof is a quote from a doc or a forum, not a log line from our own run.
- The verdict was written right after a long, tiring chain of failures.
- Nobody tried the simplest explanation (config, arguments, paths).

## One-line rule
**A verdict is a hypothesis with a timestamp. Re-check it before you build on it.**
