from pathlib import Path

# --- index.html: remove LOD/ped panel and its init fields ---
p = Path(r'E:\gta\playgta5\mirror\playgta5.com\index.html')
s = p.read_text(encoding='utf-8', errors='replace')
s = s.replace('globalThis.__gtaWorker = worker;\n', '', 1)
s = s.replace("\t\twasmFile: q.get('wasm') === 'lod50' ? 'lod50' : '',\t\t// ?wasm=lod50: 50m near-full-detail LOD build (diagnostic A/B)\n", '', 1)
s = s.replace("\t\tlodCutoff: q.get('wasm') === 'lod50' ? 50 : 0,\t\t// initial LOD mode (0 = fast LOD 0.3 everywhere, 50 = sharp under 50m)\n", '', 1)
marker = '// ---- live settings bar (always visible) ----'
if marker in s:
    start = s.index(marker)
    end = s.index('</script>', start)
    s = s[:start] + s[end:]
panel_start = s.find('<div id="gtaPanel"')
if panel_start != -1:
    depth = 0
    i = panel_start
    while i < len(s):
        if s.startswith('<div', i):
            depth += 1
            i += 4
        elif s.startswith('</div>', i):
            depth -= 1
            i += 6
            if depth == 0:
                break
        else:
            i += 1
    s = s[:panel_start] + s[i:]
assert 'gtaPanel' not in s and 'lodCutoff' not in s and '__gtaWorker' not in s
p.write_text(s, encoding='utf-8', newline='')

# --- loader.js: remove LOD/ped handling, load original game.wasm ---
p = Path(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js')
s = p.read_text(encoding='utf-8', errors='replace')
for line in [
    "let pendingLodCutoff = null;\n",
    "let pendingPedDensity = null;\n",
    "const dbgLog = (t) => { try { fetch('/log', { method: 'POST', body: '[lod] ' + t }).catch(() => {}); } catch (e) {} };\n",
]:
    s = s.replace(line, '', 1)
start = s.find("self.addEventListener('message', (ev) => {\n\tconst d = ev.data || {};")
if start != -1:
    end = s.index('});\n', start) + 4
    s = s[:start] + s[end:]
s = s.replace("\t\t\t\t\twasmInstance = r.instance;\n\t\t\t\t\tif (pendingLodCutoff !== null && r.instance.exports.gta_lod_cutoff) { r.instance.exports.gta_lod_cutoff.value = pendingLodCutoff; dbgLog('applied pending cutoff=' + pendingLodCutoff); } else dbgLog('no cutoff applied, pending=' + pendingLodCutoff);\n\t\t\t\t\tif (pendingPedDensity !== null && r.instance.exports.memory) new DataView(r.instance.exports.memory.buffer).setFloat32(7155636, pendingPedDensity, true);\n",
              "\t\t\t\t\twasmInstance = r.instance;\n", 1)
s = s.replace("const wasmName = 'game-lodlive.wasm';\t\t// live-cutoff build for both modes", "const wasmName = 'game.wasm';")
s = s.replace("locateFile: (p) => B + '/' + (p === 'game.wasm' ? 'game-lodlive.wasm' : p)", "locateFile: (p) => B + '/' + p")
assert 'lodCutoff' not in s and 'pedDensity' not in s and 'game-lodlive.wasm' not in s
p.write_text(s, encoding='utf-8', newline='')

# --- harness: original wasm ---
p = Path(r'E:\gta\playgta5\node-webgpu\harness.js')
s = p.read_text(encoding='utf-8', errors='replace')
s = s.replace("E:/Malik/game/game-lodlive.wasm", "E:/Malik/game/game.wasm")
p.write_text(s, encoding='utf-8', newline='')
print('LOD panel, live handlers and patched-wasm references removed')
