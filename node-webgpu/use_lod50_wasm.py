p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm')"
new = "fs.readFileSync('E:/Malik/game/game-lod50.wasm')"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('harness now loads game-lod50.wasm')
