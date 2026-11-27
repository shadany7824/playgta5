src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js'
dst = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()
old = 'wasmMemory=new WebAssembly.Memory({initial:BigInt(INITIAL_MEMORY/65536),maximum:262144n,shared:true,address:"i64"})'
new = 'wasmMemory=new WebAssembly.Memory({initial:INITIAL_MEMORY/65536,maximum:262144,shared:true,address:"i64"})'
print('old found:', old in s)
s = s.replace(old, new, 1)
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('WROTE', dst)
# verify the patched memory creation works in isolation
