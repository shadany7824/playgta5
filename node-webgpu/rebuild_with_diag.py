# Rebuild game-node.js from clean mirror with only the REAL fixes (no forced Load).
# Fixes: Module-from-globalThis, pthread spawn w/ workerData+boot shim, pool=2, worker.onmessage bridge.
src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js'
dst = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()

fixes = [
    ('var Module=typeof Module!="undefined"?Module:{}',
     'var Module=(typeof globalThis!=="undefined"&&globalThis.Module)?globalThis.Module:(typeof Module!="undefined"?Module:{})'),
    ('worker=new Worker(pthreadMainJs,{name:"em-pthread"})',
     'worker=new Worker(pthreadMainJs,{name:"em-pthread",workerData:{pthread:true},execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})'),
    ('var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);',
     'var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);pthreadPoolSize=2;'),
    ('loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;',
     'loadWasmModuleToWorker:worker=>new Promise(onFinishedLoading=>{'
     'Object.defineProperty(worker,"onmessage",{configurable:true,get(){return worker.__om;},set(f){worker.__om=f;if(worker.on&&!worker.__bridged){worker.__bridged=true;worker.on("message",(d)=>worker.__om&&worker.__om({data:d}));}}});'
     'worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'),
]
for old, new in fixes:
    assert old in s, f'anchor missing: {old[:60]}'
    s = s.replace(old, new, 1)

# DIAGNOSTICS (using globalThis.__diag which harness defines - safe in template literals)
# 1. httpfs manifest import
old = 'function wasm_httpfs_manifest_js(buf,cap){'
new = 'function wasm_httpfs_manifest_js(buf,cap){globalThis.__diag&&globalThis.__diag("MANIFEST called buf="+buf+" cap="+cap+" THREAD="+globalThis.name);'
assert old in s
s = s.replace(old, new, 1)
# 2. httpfs io_start import
old = 'function wasm_httpfs_io_start_js(table){'
new = ('function wasm_httpfs_io_start_js(table){globalThis.__diag&&globalThis.__diag("IO_START called table="+table+" ioWorker="+!!Module["ioWorker"]+" pth="+ENVIRONMENT_IS_PTHREAD+" started="+Module["__ioStarted"]);'
       'if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;'
       'Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)});'
       'globalThis.__diag&&globalThis.__diag("IO_START posted");}')
# need to replace the whole original function (single line up to the next function)
start = s.find(old)
end = s.find('\nfunction ', start)
if end < 0: end = start + 400
s = s[:start] + new + s[end:]
# 3. has_page
s = s.replace('function wasm_has_page_js(){', 'function wasm_has_page_js(){globalThis.__diag&&globalThis.__diag("HAS_PAGE called process="+(typeof process!=="undefined"));', 1)
# 4. module_int
s = s.replace('function wasm_module_int_js(name,defaultValue){', 'function wasm_module_int_js(name,defaultValue){globalThis.__diag&&globalThis.__diag("MODULE_INT called");', 1)

open(dst, 'w', encoding='utf-8', newline='').write(s)
print('REBUILT game-node.js CLEAN + diagnostics, len', len(s))
for k in ['table.get(64n)', 'INIT_MAIN_THREAD', 'FORCED httpfs', 'MANIFEST called', 'IO_START called', 'HAS_PAGE called']:
    print(k, s.count(k))
