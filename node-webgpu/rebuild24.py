# Revert game-node.js from the Node22 hacks; rebuild clean patched copy for Node24
src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js'
dst = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()

# Node24 supports memory64 natively with full range; keep original BigInt constructor (no patch needed)
# But Node24 WebAssembly.Memory may still want Numbers - test showed validate OK; keep original for now.

# Only fix the Module shadowing (global scope) + pthread execArgv + Worker global
s = s.replace('var Module=typeof Module!="undefined"?Module:{}',
              'var Module=(typeof globalThis!=="undefined"&&globalThis.Module)?globalThis.Module:(typeof Module!="undefined"?Module:{})', 1)
s = s.replace('worker=new Worker(pthreadMainJs,{name:"em-pthread"})',
              'worker=new Worker(pthreadMainJs,{name:"em-pthread",execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})', 1)
# Node shims prefix
prefix = ('// Node harness shims\n'
          'if (typeof process !== "undefined" && process.versions && process.versions.node) {\n'
          '  if (typeof globalThis.self === "undefined") globalThis.self = globalThis;\n'
          '  if (typeof globalThis.Worker === "undefined") globalThis.Worker = require("worker_threads").Worker;\n'
          '  if (typeof globalThis.postMessage === "undefined" && require("worker_threads").parentPort) globalThis.postMessage = (m) => require("worker_threads").parentPort.postMessage(m);\n'
          '  if (typeof globalThis.BroadcastChannel === "undefined") globalThis.BroadcastChannel = class { constructor(){} postMessage(){} close(){} addEventListener(){} };\n'
          '}\n')
s = prefix + s
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('REBUILT game-node.js for Node24 (original memory, shims only)')
