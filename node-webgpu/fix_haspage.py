g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = 'function wasm_has_page_js(){return typeof process!=="undefined"&&process.versions&&process.versions.node?0:1}'
new = 'function wasm_has_page_js(){return 1}'
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('PATCHED wasm_has_page_js -> 1 (engine will use httpfs/io worker)')
