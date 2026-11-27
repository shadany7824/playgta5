p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
# Reduce initial memory from 3 GiB to 256 MB; game grows on demand. Keep max 16 GiB for Node24 (supports it).
s = s.replace('INITIAL_MEMORY=3221225472;wasmMemory=new WebAssembly.Memory({initial:BigInt(INITIAL_MEMORY/65536),maximum:262144n,shared:true,address:"i64"})',
              'INITIAL_MEMORY=268435456;wasmMemory=new WebAssembly.Memory({initial:BigInt(INITIAL_MEMORY/65536),maximum:262144n,shared:true,address:"i64"})')
print('patched initial to 256MB')
open(p, 'w', encoding='utf-8', newline='').write(s)
