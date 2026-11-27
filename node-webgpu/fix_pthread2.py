p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'worker=new Worker(pthreadMainJs,{name:"em-pthread",execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})'
new = 'worker=new Worker(pthreadMainJs,{name:"em-pthread",workerData:{pthread:true},execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})'
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)

# update boot shim to use workerData.pthread
p2 = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
b = open(p2, encoding='utf-8').read()
b = b.replace("if (require('worker_threads').workerData && require('worker_threads').workerData.pthread) globalThis.name = 'em-pthread';", "if (require('worker_threads').workerData && require('worker_threads').workerData.pthread) globalThis.name = 'em-pthread';")
# replace the messy line added previously
import re
b = re.sub(r"try \{ const wd = require\('worker_threads'\);.*?catch\(e\) \{\}", "try { if (require('worker_threads').workerData && require('worker_threads').workerData.pthread) globalThis.name = 'em-pthread'; } catch(e) {}", b, count=1)
open(p2, 'w', encoding='utf-8', newline='').write(b)
print('SET workerData.pthread for pthread workers')
