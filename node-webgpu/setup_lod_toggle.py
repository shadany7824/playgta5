import shutil

src = r'E:\Malik\game\game-lod50b.wasm'
dst = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game-lod50.wasm'
shutil.copy2(src, dst)
print('copied patched wasm into mirror:', dst)

p = r'E:\gta\playgta5\mirror\playgta5.com\index.html'
s = open(p, encoding='utf-8', errors='replace').read()
old = "\t\tshotEvery: +(q.get('shot') || 0),"
new = "\t\tshotEvery: +(q.get('shot') || 0),\n\t\twasmFile: q.get('wasm') === 'lod50' ? 'lod50' : '',\t\t// ?wasm=lod50: 50m near-full-detail LOD build (diagnostic A/B)"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('index.html passes wasmFile')

p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "try { res = await fetch(B + '/game.wasm'); } catch (e) { err = e; }"
new = "const wasmName = m.wasmFile === 'lod50' ? 'game-lod50.wasm' : 'game.wasm';\n\t\t\ttry { res = await fetch(B + '/' + wasmName); } catch (e) { err = e; }"
assert old in s
s = s.replace(old, new, 1)
old2 = "\t\t\tlocateFile: (p) => B + '/' + p,"
new2 = "\t\t\tlocateFile: (p) => B + '/' + (p === 'game.wasm' && m.wasmFile === 'lod50' ? 'game-lod50.wasm' : p),"
assert old2 in s
s = s.replace(old2, new2, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('loader.js supports ?wasm=lod50')
