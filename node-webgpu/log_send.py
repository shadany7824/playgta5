p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = "  globalThis.postMessage = (m) => parentPort.postMessage(m);"
new = """  globalThis.postMessage = (m) => {
    try { const wt = require('worker_threads'); if (wt.workerData && wt.workerData.pthread) require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'SEND cmd=' + (m&&m.cmd) + '\\n'); } catch(e){}
    parentPort.postMessage(m);
  };"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED postMessage logging')
