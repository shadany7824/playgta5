import shutil

# 1) patched wasm into mirror (same name the toggle already fetches)
shutil.copy2(r'E:\Malik\game\game-lodlive.wasm',
             r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game-lod50.wasm')
print('mirror wasm updated with runtime cutoff export')

# 2) loader.js: store instance + handle live settings messages
p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "'use strict';\nlet started = false;"
new = ("'use strict';\nlet started = false;\nlet wasmInstance = null;\n"
       "self.addEventListener('message', (ev) => {\n"
       "\tconst d = ev.data || {};\n"
       "\tif (d.lodCutoff !== undefined && wasmInstance && wasmInstance.exports.gta_lod_cutoff) {\n"
       "\t\twasmInstance.exports.gta_lod_cutoff.value = +d.lodCutoff;\n"
       "\t}\n"
       "\tif (d.pedDensity !== undefined && wasmInstance && wasmInstance.exports.memory) {\n"
       "\t\tnew DataView(wasmInstance.exports.memory.buffer).setFloat32(7155636, +d.pedDensity, true);\n"
       "\t}\n"
       "});")
assert old in s
s = s.replace(old, new, 1)
old2 = "\t\t\t\t\tdone(r.instance, r.module);"
new2 = "\t\t\t\t\twasmInstance = r.instance;\n\t\t\t\t\tdone(r.instance, r.module);"
assert old2 in s
s = s.replace(old2, new2, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('loader.js live settings wired')

# 3) harness: load live-cutoff wasm, set initial cutoff from env
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
s = s.replace('E:/Malik/game/game-lod50b.wasm', 'E:/Malik/game/game-lodlive.wasm', 1)
old3 = "globalThis.__wasmMemory = imports.memory; done(r.instance, r.module);"
new3 = ("globalThis.__wasmMemory = imports.memory; "
        "if (r.instance.exports.gta_lod_cutoff) r.instance.exports.gta_lod_cutoff.value = +(process.env.WGPU_LOD_CUTOFF || 50); "
        "done(r.instance, r.module);")
assert old3 in s
s = s.replace(old3, new3, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('harness loads live-cutoff wasm')
