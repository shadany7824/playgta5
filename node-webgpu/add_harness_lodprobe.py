from pathlib import Path
p = Path(r'E:\gta\playgta5\node-webgpu\harness.js')
s = p.read_text(encoding='utf-8', errors='replace')
if '__wasmInstance' not in s:
    s = s.replace('done(r.instance, r.module);', 'globalThis.__wasmInstance = r.instance; done(r.instance, r.module);', 1)
if 'lodprobe' not in s:
    marker = "io.on('message', (m) => { if (m && m.loaded) maybeStart('io loaded'); });\n"
    s = s.replace(marker, marker + "setInterval(() => { const e = globalThis.__wasmInstance && globalThis.__wasmInstance.exports; console.error('[lodprobe] hits=' + (e && e.gta_lod_hits ? e.gta_lod_hits.value : 'n/a') + ' cutoff=' + (e && e.gta_lod_cutoff ? e.gta_lod_cutoff.value : 'n/a')); }, 10000);\n", 1)
p.write_text(s, encoding='utf-8', newline='')
print('harness lod probe added')
