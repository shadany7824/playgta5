p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
# Add Worker/global shims at very top (Node mode) so pthread workers spawned from this file can run
prefix = ('// Node harness shims\n'
          'if (typeof process !== "undefined" && process.versions && process.versions.node) {\n'
          '  if (typeof globalThis.self === "undefined") globalThis.self = globalThis;\n'
          '  if (typeof globalThis.Worker === "undefined") globalThis.Worker = require("worker_threads").Worker;\n'
          '  if (typeof globalThis.postMessage === "undefined" && require("worker_threads").parentPort) globalThis.postMessage = (m) => require("worker_threads").parentPort.postMessage(m);\n'
          '  if (typeof globalThis.BroadcastChannel === "undefined") globalThis.BroadcastChannel = class { constructor(){} postMessage(){} close(){} addEventListener(){} };\n'
          '}\n')
if 'Node harness shims' not in s[:400]:
    s = prefix + s
    open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED Node shims prefix to game-node.js')
