p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
L = "require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt'"
# Add logging inside cmd=1 handler at key points
old = "wasmMemory=msgData.wasmMemory;updateMemoryViews();wasmModule=msgData.wasmModule;createWasm();run();startWorker()"
new = ("wasmMemory=msgData.wasmMemory;updateMemoryViews();wasmModule=msgData.wasmModule;"
       + L + ",'before createWasm\\n');"
       + "createWasm();"
       + L + ",'after createWasm wasmExports='+(typeof wasmExports)+'\\n');"
       + "run();"
       + L + ",'after run\\n');"
       + "startWorker()")
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED step logging in cmd=1 handler')
