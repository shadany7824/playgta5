# Think like Claude: 30 lessons for code agents

Written 2026-11-25 by Claude, for every code agent that works on this project (and any other project of the owner).
Every lesson comes from **something that really happened in this project**: a wrong verdict, a bug that hid, a fix that worked. They are not theory.

**How to use:** read 01-12 before any debugging, 13-17 before any optimization or number, 18-30 before you report or hand off. When stuck, open file 30 (the one-page checklist).

## Part A — Finding the real cause (debugging)
| # | Lesson |
|---|---|
| 01 | [01-distrust-the-saved-verdict.md](01-distrust-the-saved-verdict.md) |
| 02 | [02-read-the-real-stack-trace.md](02-read-the-real-stack-trace.md) |
| 03 | [03-forced-calls-are-not-evidence.md](03-forced-calls-are-not-evidence.md) |
| 04 | [04-diff-against-the-working-version.md](04-diff-against-the-working-version.md) |
| 05 | [05-log-the-real-inputs.md](05-log-the-real-inputs.md) |
| 06 | [06-read-the-crashing-function.md](06-read-the-crashing-function.md) |
| 07 | [07-decode-magic-numbers.md](07-decode-magic-numbers.md) |
| 08 | [08-match-the-doc-to-your-exact-setup.md](08-match-the-doc-to-your-exact-setup.md) |
| 09 | [09-missing-log-line-is-a-question.md](09-missing-log-line-is-a-question.md) |
| 10 | [10-prove-your-instrument-works.md](10-prove-your-instrument-works.md) |
| 11 | [11-read-the-whole-function-not-the-name.md](11-read-the-whole-function-not-the-name.md) |
| 12 | [12-when-it-works-elsewhere-the-difference-is-the-bug.md](12-when-it-works-elsewhere-the-difference-is-the-bug.md) |

## Part B — Numbers and speed
| # | Lesson |
|---|---|
| 13 | [13-measure-before-you-optimize.md](13-measure-before-you-optimize.md) |
| 14 | [14-do-the-bottleneck-math.md](14-do-the-bottleneck-math.md) |
| 15 | [15-compare-like-with-like.md](15-compare-like-with-like.md) |
| 16 | [16-compute-every-number-twice.md](16-compute-every-number-twice.md) |
| 17 | [17-labels-must-match-the-settings.md](17-labels-must-match-the-settings.md) |

## Part C — Changing code safely
| # | Lesson |
|---|---|
| 18 | [18-test-your-own-code-first.md](18-test-your-own-code-first.md) |
| 19 | [19-one-change-per-run.md](19-one-change-per-run.md) |
| 20 | [20-backup-and-know-the-way-back.md](20-backup-and-know-the-way-back.md) |
| 21 | [21-look-for-what-already-exists.md](21-look-for-what-already-exists.md) |
| 22 | [22-protect-what-already-works.md](22-protect-what-already-works.md) |
| 23 | [23-know-the-environment-traps.md](23-know-the-environment-traps.md) |
| 24 | [24-long-jobs-run-in-the-background.md](24-long-jobs-run-in-the-background.md) |

## Part D — Judgment, honesty, hand-off
| # | Lesson |
|---|---|
| 25 | [25-check-live-facts-not-blogs.md](25-check-live-facts-not-blogs.md) |
| 26 | [26-two-fails-then-research.md](26-two-fails-then-research.md) |
| 27 | [27-report-verified-vs-not-verified.md](27-report-verified-vs-not-verified.md) |
| 28 | [28-keep-memory-true.md](28-keep-memory-true.md) |
| 29 | [29-write-hand-offs-an-agent-can-execute.md](29-write-hand-offs-an-agent-can-execute.md) |
| 30 | [30-the-one-page-checklist.md](30-the-one-page-checklist.md) |

Related rule files: `C:\Users\HP\.claude\mistakes\README.md` (U01-U25), `C:\Users\HP\.claude\always-rules.txt`.
