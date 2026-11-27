p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
anchor = "globalThis.self = globalThis;"
fix = ("globalThis.self = globalThis;\n"
       "// Emscripten pthread detection in Node: no WorkerGlobalScope, so set it + name for pthread workers\n"
       "try { const wt = require('worker_threads'); if (wt.workerData && wt.workerData.pthread) { globalThis.name='em-pthread'; globalThis.WorkerGlobalScope=function(){}; } } catch(e){}")
if 'WorkerGlobalScope' not in s:
    s = s.replace(anchor, fix, 1)
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print('APPLIED pthread detection fix')
else:
    print('already has WorkerGlobalScope')
