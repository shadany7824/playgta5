p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
s = s.replace("const wasmName = m.wasmFile === 'lod50' ? 'game-lod50.wasm' : 'game.wasm';",
              "const wasmName = 'game-lod50.wasm';\t\t// live-cutoff build for both modes", 1)
s = s.replace("locateFile: (p) => B + '/' + (p === 'game.wasm' && m.wasmFile === 'lod50' ? 'game-lod50.wasm' : p),",
              "locateFile: (p) => B + '/' + (p === 'game.wasm' ? 'game-lod50.wasm' : p),", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('Chrome always loads live-cutoff wasm')
