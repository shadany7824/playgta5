def add(p, t):
    open(p, 'a', encoding='utf-8').write(t)
add(r'E:\gta\playgta5\.claude\memory\1080p-30fps-engine-plan\RESULTS.md', '''
## 10 — Threads/priority/GC (Stage 35, 2026-11-24): no change kept
- GC flag --max-semi-space-size=64: rejected by Node 24 in worker execArgv (ERR_WORKER_INVALID_EXEC_ARGV); via NODE_OPTIONS the run stalled at startup (settings.xml path) -> dropped. Harness execArgv restored (no backup existed; reverted manually, node --check OK).
- Power plan observed: HoneCtrl's Power Plan (not High performance) - owner action, not changed. Process priority not raised (owner actively using other windows; would starve them).
''')
add(r'E:\gta\playgta5\.claude\memory\engine-code-map\ERROR-TRACE.md', '''
## Stage 35: file 10 GC flag failed (Node rejects in worker execArgv; NODE_OPTIONS stalls) (2026-11-24)
- No change kept; harness restored. Owner windows active -> priority/power not touched. Moved on to file 14.
''')
print('logged')
