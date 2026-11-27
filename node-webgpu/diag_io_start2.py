# Add a global diag function in harness that game-node.js can call without inline require
# (avoids the template-literal syntax break from earlier attempts)
h = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(h, encoding='utf-8').read()
if '__diag' not in s:
    s = s.replace("globalThis.self = globalThis;",
                  "globalThis.self = globalThis;\nglobalThis.__diag = (s) => { try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', s + '\\n'); } catch(e){} };", 1)
    open(h, 'w', encoding='utf-8', newline='').write(s)
print('harness __diag added')

# Now patch game-node.js wasm_httpfs_io_start_js to call globalThis.__diag
g = r'E:\gta\playgta5\node-webgpu\game-node.js'
gs = open(g, encoding='utf-8', errors='replace').read()
old = 'function wasm_httpfs_io_start_js(table){if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)})}'
new = 'function wasm_httpfs_io_start_js(table){globalThis.__diag&&globalThis.__diag("IO_START called table="+table+" ioWorker="+!!Module["ioWorker"]);if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)});globalThis.__diag&&globalThis.__diag("IO_START posted")}'
print('found:', old in gs)
gs = gs.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(gs)
print('game-node IO_START diag added')
