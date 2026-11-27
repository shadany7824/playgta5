g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = 'globalThis.__diag&&globalThis.__diag("INIT_MAIN_THREAD done")}'
new = ('globalThis.__diag&&globalThis.__diag("INIT_MAIN_THREAD done");'
       'try{if(globalThis.__wasmMemory&&globalThis.__wasmMemory.buffer){new Uint8Array(globalThis.__wasmMemory.buffer)[8321672]=1;globalThis.__diag&&globalThis.__diag("FORCED httpfs active byte in init_main_thread")}}catch(e){globalThis.__diag&&globalThis.__diag("force err "+e.message)}}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED force in init_main_thread')
