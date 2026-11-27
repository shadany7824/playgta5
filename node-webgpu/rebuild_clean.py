# Rebuild game-node.js cleanly from mirror with ONLY the essential fixes:
# 1. Module from globalThis (pthread workers see main's Module)
# 2. pthread spawn with workerData.pthread + boot shim execArgv
# 3. pthreadPoolSize=2 (memory)
# 4. worker.onmessage -> .on('message') bridge for cmd:3 handshake
# NO logging (logging patches broke the template literal)
src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js'
dst = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()

# fix 1: Module from globalThis
old = 'var Module=typeof Module!="undefined"?Module:{}'
new = 'var Module=(typeof globalThis!=="undefined"&&globalThis.Module)?globalThis.Module:(typeof Module!="undefined"?Module:{})'
assert old in s, 'fix1 anchor missing'
s = s.replace(old, new, 1)

# fix 2: pthread spawn with workerData + boot shim
old = 'worker=new Worker(pthreadMainJs,{name:"em-pthread"})'
new = 'worker=new Worker(pthreadMainJs,{name:"em-pthread",workerData:{pthread:true},execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})'
assert old in s, 'fix2 anchor missing'
s = s.replace(old, new, 1)

# fix 3: pthreadPoolSize=2
old = 'var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);'
new = 'var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);pthreadPoolSize=2;'
assert old in s, 'fix3 anchor missing'
s = s.replace(old, new, 1)

# fix 4: worker.onmessage bridge (Node uses .on('message'))
old = 'loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'
new = ('loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{'
       'Object.defineProperty(worker,"onmessage",{configurable:true,get(){return worker.__om;},set(f){worker.__om=f;if(worker.on&&!worker.__bridged){worker.__bridged=true;worker.on("message",(d)=>worker.__om&&worker.__om({data:d}));}}});'
       'worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;')
assert old in s, 'fix4 anchor missing'
s = s.replace(old, new, 1)

open(dst, 'w', encoding='utf-8', newline='').write(s)
print('REBUILT CLEAN game-node.js, len', len(s))
