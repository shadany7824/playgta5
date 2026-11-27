p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = "try { if (require('worker_threads').workerData && require('worker_threads').workerData.pthread) globalThis.name = 'em-pthread'; } catch(e) {}"
new = "try { if (require('worker_threads').workerData && require('worker_threads').workerData.pthread) { globalThis.name = 'em-pthread'; globalThis.WorkerGlobalScope = function(){}; } } catch(e) {}"
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('SET WorkerGlobalScope for pthread workers')
