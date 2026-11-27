# 30 — The one-page checklist (print this in your head)

## Before you debug
- [ ] Re-check any saved verdict against raw evidence (01)
- [ ] Copy the exact error + full stack; read the top frame first (02)
- [ ] Is our own forced/test code in the stack? Then it's not evidence (03)
- [ ] Does it work elsewhere? List every difference in launch args/env/versions (04, 12)
- [ ] Log the real inputs at the lowest boundary (syscall, import, API) (05)
- [ ] Open the crashing function; read the lines right before the abort (06)
- [ ] Decode magic numbers (text, string addresses, floats) (07)
- [ ] Does every doc/issue match our exact mode + version + platform? (08)
- [ ] A missing log line → look one step earlier (09)
- [ ] Prove the logger works on that thread in that run (10)
- [ ] Read setters and readers fully: flags, max/min, per-frame resets (11)

## Before you optimize or report a number
- [ ] Measure the breakdown first; CPU or GPU? which part? (13)
- [ ] Turn the target into a time budget and a needed cut (14)
- [ ] Same setup, one change, draws/frame within ±15% (15)
- [ ] Compute every number twice, two ways (16)
- [ ] Label = the exact settings; never "max/1080p" for less (17)

## Before you change code
- [ ] Unit-test your own code, including nasty cases; then real data (18)
- [ ] One change per run (19)
- [ ] Backup with a clear name; write the way back (20)
- [ ] Grep for an existing tool/flag/feature first (21)
- [ ] Work on a copy if the file is shared with the working setup (22)
- [ ] Right runtime (Node 24), disk space (C: full → E:), server up, no stray processes (23)
- [ ] Long jobs in the background with output to a file (24)

## Before you recommend, report or hand off
- [ ] Changing facts checked live today (versions, availability, free tiers) (25)
- [ ] After two fails: research and reframe, don't just retry (26)
- [ ] Report = result → evidence → verified / not verified → next step (27)
- [ ] Memory updated everywhere, wrong claims retracted (28)
- [ ] Hand-off has exact paths, commands, pass checks, traps (29)
- [ ] No git / publish / outward action without the owner's yes

## The three questions that solved most problems here
1. **What exactly does the program try to do?** (log it)
2. **What is different from where it works?** (diff it)
3. **What does the code right before the failure check?** (read it)
