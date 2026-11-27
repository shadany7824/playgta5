p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
s = s.replace("let wasmInstance = null;", "let wasmInstance = null;\nlet pendingLodCutoff = null;\nlet pendingPedDensity = null;", 1)
s = s.replace("\tif (d.lodCutoff !== undefined && wasmInstance && wasmInstance.exports.gta_lod_cutoff) {\n\t\twasmInstance.exports.gta_lod_cutoff.value = +d.lodCutoff;\n\t}",
              "\tif (d.lodCutoff !== undefined) {\n"
              "\t\tpendingLodCutoff = +d.lodCutoff;\n"
              "\t\tif (wasmInstance && wasmInstance.exports.gta_lod_cutoff) wasmInstance.exports.gta_lod_cutoff.value = pendingLodCutoff;\n"
              "\t}", 1)
s = s.replace("\tif (d.pedDensity !== undefined && wasmInstance && wasmInstance.exports.memory) {\n\t\tnew DataView(wasmInstance.exports.memory.buffer).setFloat32(7155636, +d.pedDensity, true);\n\t}",
              "\tif (d.pedDensity !== undefined) {\n"
              "\t\tpendingPedDensity = +d.pedDensity;\n"
              "\t\tif (wasmInstance && wasmInstance.exports.memory) new DataView(wasmInstance.exports.memory.buffer).setFloat32(7155636, pendingPedDensity, true);\n"
              "\t}", 1)
s = s.replace("\t\t\t\t\twasmInstance = r.instance;\n",
              "\t\t\t\t\twasmInstance = r.instance;\n"
              "\t\t\t\t\tif (pendingLodCutoff !== null && r.instance.exports.gta_lod_cutoff) r.instance.exports.gta_lod_cutoff.value = pendingLodCutoff;\n"
              "\t\t\t\t\tif (pendingPedDensity !== null && r.instance.exports.memory) new DataView(r.instance.exports.memory.buffer).setFloat32(7155636, pendingPedDensity, true);\n", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('loader pending settings added')

p = r'E:\gta\playgta5\mirror\playgta5.com\index.html'
s = open(p, encoding='utf-8', errors='replace').read()
# initial mode from URL
old = "\t\twasmFile: q.get('wasm') === 'lod50' ? 'lod50' : '',\t\t// ?wasm=lod50: 50m near-full-detail LOD build (diagnostic A/B)"
new = old + "\n\t\tlodCutoff: q.get('wasm') === 'lod50' ? 50 : 0,\t\t// initial LOD mode (0 = fast LOD 0.3 everywhere, 50 = sharp under 50m)"
assert old in s
s = s.replace(old, new, 1)
# panel HTML before </body>
panel = '''\n<div id="gtaPanel" style="display:none;position:fixed;top:70px;right:18px;z-index:99999;background:rgba(8,10,14,.94);color:#eef;font:14px Arial,sans-serif;padding:14px 16px;border:2px solid #49b;border-radius:10px;min-width:260px;box-shadow:0 4px 24px #000">
  <div style="font-size:16px;font-weight:bold;margin-bottom:8px">GTA settings (Ctrl+S)</div>
  <div style="opacity:.8;margin-bottom:6px">LOD - near object detail</div>
  <button data-lod="0" style="margin:2px;padding:6px 10px">FAST (0.3, ~7.6 FPS)</button>
  <button data-lod="50" style="margin:2px;padding:6px 10px">SHARP (50m, ~5.6 FPS)</button>
  <div style="opacity:.8;margin:10px 0 6px">Ambient pedestrians</div>
  <button data-ped="0.5" style="margin:2px;padding:6px 10px">PED 0.5</button>
  <button data-ped="1" style="margin:2px;padding:6px 10px">PED 1.0</button>
  <div id="gtaPanelStatus" style="opacity:.7;margin-top:10px">Mode: loading...</div>
  <button id="gtaPanelClose" style="margin-top:10px;padding:6px 10px">Close</button>
</div>\n'''
s = s.replace('</body>', panel + '</body>', 1)
# panel JS before final </script> (the one at line 604)
js = '''
// ---- live settings panel (Ctrl+S) ----
const gtaPanel = document.getElementById('gtaPanel');
const gtaStatus = document.getElementById('gtaPanelStatus');
addEventListener('keydown', (e) => {
  if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault();
    gtaPanel.style.display = gtaPanel.style.display === 'none' ? 'block' : 'none';
  }
});
for (const b of document.querySelectorAll('[data-lod]')) b.addEventListener('click', () => {
  const v = +b.dataset.lod;
  worker.postMessage({ lodCutoff: v });
  gtaStatus.textContent = 'LOD: ' + (v ? 'sharp under 50m' : 'fast (0.3 everywhere)');
  gtaPanel.style.display = 'none';
});
for (const b of document.querySelectorAll('[data-ped]')) b.addEventListener('click', () => {
  const v = +b.dataset.ped;
  worker.postMessage({ pedDensity: v });
  gtaStatus.textContent = 'Ped density: ' + v;
  gtaPanel.style.display = 'none';
});
document.getElementById('gtaPanelClose').addEventListener('click', () => { gtaPanel.style.display = 'none'; });
'''
idx = s.rfind('</script>')
assert idx > 0
s = s[:idx] + js + s[idx:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('index.html Ctrl+S panel added')
