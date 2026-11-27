p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
L = "require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt'"
old = 'function wasm_httpfs_io_start_js(table){if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)})}'
new = 'function wasm_httpfs_io_start_js(table){' + L + ",'IO START CALLED table='+table+'\\n');" + 'if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)})' + L + ",'IO START posted\\n');" + '}'
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED io start logging')
