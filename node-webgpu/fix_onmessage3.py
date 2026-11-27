p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'
new = ('loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{'
       'Object.defineProperty(worker,"onmessage",{configurable:true,get(){return worker.__om;},set(f){worker.__om=f;if(worker.on&&!worker.__bridged){worker.__bridged=true;worker.on("message",(d)=>worker.__om&&worker.__om({data:d}));}}});'
       'worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;')
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('CLEAN BRIDGE at loadWasmModuleToWorker')
