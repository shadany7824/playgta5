p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
if 'const dbgLog' not in s:
    s = s.replace("let pendingPedDensity = null;", "let pendingPedDensity = null;\nconst dbgLog = (t) => { try { fetch('/log', { method: 'POST', body: '[lod] ' + t }).catch(() => {}); } catch (e) {} };")
    s = s.replace("\t\tpendingLodCutoff = +d.lodCutoff;", "\t\tpendingLodCutoff = +d.lodCutoff;\n\t\tdbgLog('message lodCutoff=' + pendingLodCutoff + ' instance=' + !!wasmInstance);")
    s = s.replace("if (wasmInstance && wasmInstance.exports.gta_lod_cutoff) wasmInstance.exports.gta_lod_cutoff.value = pendingLodCutoff;", "if (wasmInstance && wasmInstance.exports.gta_lod_cutoff) { wasmInstance.exports.gta_lod_cutoff.value = pendingLodCutoff; dbgLog('applied live cutoff=' + pendingLodCutoff); }")
    s = s.replace("if (pendingLodCutoff !== null && r.instance.exports.gta_lod_cutoff) r.instance.exports.gta_lod_cutoff.value = pendingLodCutoff;", "if (pendingLodCutoff !== null && r.instance.exports.gta_lod_cutoff) { r.instance.exports.gta_lod_cutoff.value = pendingLodCutoff; dbgLog('applied pending cutoff=' + pendingLodCutoff); } else dbgLog('no cutoff applied, pending=' + pendingLodCutoff);")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('loader LOD logging added')
