# 10 — Prove your instrument works before you trust its silence

## The lesson
Before concluding "the log shows X never happens", prove that the **logger itself works in that place**. A broken logger and a never-called function look exactly the same: an empty log.

## What happened here
When `MANIFEST` and `IO_START` never appeared, Claude first checked whether `globalThis.__diag` even worked on that thread. It did: other diag lines from the same thread (`MODULE_INT key=keepThreads val=0`, `MODULE_INT key=gameResourceMB val=1024`) were in the same log file. So the silence was real, and it was safe to move on to "why isn't it called?" (lesson 09).
The opposite risk was real too. The pthread workers load `worker-boot.js`, and only `harness.js` had the `XMLHttpRequest` shim. A function running in a worker could silently return -1 because a global was missing there, and nothing would log it.

## How to apply
- Next to every "never happens" claim, show one line from the **same logger, same thread/process, same run** that did print.
- If none exists, add a canary: log "diag alive" at the start of that thread or function.
- Check where each thread's/process's output goes (separate files, stdout vs stderr, worker streams).
- For screenshots and counters, the same rule applies: prove that the counter increments and the screenshot path exists (the default `D:/wasm_tmp/` path did **not** exist here).

## Checklist
- [ ] Did any line from this logger appear in this run?
- [ ] Is the logger defined in this thread/worker?
- [ ] Is the output file the one I'm reading, from this run (timestamps)?
- [ ] Did I empty the log file before the run, so old lines don't fool me?

## One-line rule
**Silence only counts if the microphone is on.**
