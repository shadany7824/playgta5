import re
DCMP = r'E:\Malik\game\game.dcmp'
INDEX = r'E:\gta\playgta5\.claude\memory\engine-code-map\engine-function-index.tsv'
OUT = r'E:\gta\playgta5\.claude\memory\engine-code-map\verification-bodies.md'

idx = open(INDEX, encoding='utf-8').read().split('\n')
lines = open(DCMP, encoding='utf-8', errors='replace').readlines()

names = [
 'RageDirect3DDeviceContext11_DrawIndexed','rage_fwBaseEntityContainer_SetLodDistCached',
 'EntityDetails_GetLODDist','CLodMgr_StartSlodModeCb','rage_grcDevice_DrawIndexedPrimitive',
 'rage_dlCmdNewDrawList_ExecuteStatic','rage_dlDrawListMgr_AdjustFragmentLOD',
 'rage_fwRenderPhase_DrawListPrologue','rage_fwScan_AddCullShape','rage_fwDrawData_AddToDrawList',
 'CLodScale_SetGlobalScaleFromScript','CLodScale_SetRemappingFromScript','CLodMgr_OverrideLodDist',
 'streaming_commands_CommandOverrideLodScaleThisFrame','CCutSceneCameraEntity_GetMapLodScale',
 'CSettingsManager_GetSettings','CSettingsManager_ApplySettings','CTimeCycle_ApplyLodScaleModifiers',
 'rage_grcBegin','rage_grcVertex','rage_grcEnd','rage_grcDevice_DrawVertices',
 'rage_grcBatcher_Reserve','rage_grcBatcher_RenderInternal','rage_fwScanNodes_ProcessEntityContainer',
 'CSettingsManager_GetSafeModeSettings','rage_grcDrawSingleQuadf','rage_dlCmdEndDraw_ExecuteStatic'
]

# precompute all function spans from index
spans = {}
for l in idx:
    p = l.split('\t')
    if len(p) >= 2 and p[1].isdigit():
        spans.setdefault(p[0], int(p[1]))

starts = sorted(spans.values())
o = []
o.append('# Verification: exact function bodies (2026-11-23)\n')
o.append('Programmatically extracted from game.dcmp using the verified index. Each function printed start -> next function definition. This is the evidence behind the "read" claims.\n')
for name in names:
    ln = spans.get(name)
    if ln is None:
        o.append('\n## %s : NOT FOUND IN INDEX\n' % name); continue
    end = ln + 1
    for i in range(ln, len(lines)):
        if i + 1 > ln and lines[i].startswith('function '):
            end = i + 1; break
    size = end - ln
    o.append('\n## %s — lines %d..%d (%d lines)\n' % (name, ln, end-1, size))
    if size <= 140:
        for i in range(ln, end):
            o.append(lines[i-1].rstrip()[:240])
    else:
        o.append('[too large: %d lines — print header + only relevant lines]\n' % size)
        for i in range(ln, min(ln+8, end)):
            o.append(lines[i-1].rstrip()[:240])
        o.append('... [body omitted] ...')
        for i in range(ln, end):
            t = lines[i-1]
            if re.search(r'call_indirect|Draw|loop |while |Atomic|12484544|19446852|23318984', t):
                o.append('L%d: %s' % (i, t.rstrip()[:220]))

open(OUT, 'w', encoding='utf-8').write('\n'.join(o))
print('SAVED', OUT)
for name in names:
    ln = spans.get(name)
    if ln:
        end = ln+1
        for i in range(ln, len(lines)):
            if i+1 > ln and lines[i].startswith('function '): end = i+1; break
        print('%-52s %6d lines' % (name, end-ln))
