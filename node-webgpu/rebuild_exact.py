src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js'
dst = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()

# Real fixes (Stages 2-6, 8)
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
for old,new in fixes:
    assert old in s, f'missing {old[:50]}'
    s = s.replace(old,new,1)

# Diagnostics via exact full-function replacement
old_manifest = 'function wasm_httpfs_manifest_js(buf,cap){if(typeof XMLHttpRequest==="undefined")return-1;'
new_manifest = 'function wasm_httpfs_manifest_js(buf,cap){globalThis.__diag&&globalThis.__diag("MANIFEST called buf="+buf+" cap="+cap+" thread="+globalThis.name);if(typeof XMLHttpRequest==="undefined"){globalThis.__diag&&globalThis.__diag("MANIFEST no XHR");return-1;}'
assert old_manifest in s; s = s.replace(old_manifest,new_manifest,1)

old_start = 'function wasm_httpfs_io_start_js(table){if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)})}'
new_start = ('function wasm_httpfs_io_start_js(table){globalThis.__diag&&globalThis.__diag("IO_START called table="+table+" ioWorker="+!!Module["ioWorker"]+" pth="+ENVIRONMENT_IS_PTHREAD+" started="+Module["__ioStarted"]);'
 'if(ENVIRONMENT_IS_PTHREAD||!Module["ioWorker"]||Module["__ioStarted"])return;Module["__ioStarted"]=true;'
 'Module["ioWorker"].postMessage({memory:wasmMemory,table:Number(table)});'
 'globalThis.__diag&&globalThis.__diag("IO_START posted");}')
assert old_start in s; s = s.replace(old_start,new_start,1)

old_page = 'function wasm_has_page_js(){return typeof process!=="undefined"&&process.versions&&process.versions.node?0:1}'
new_page = 'function wasm_has_page_js(){globalThis.__diag&&globalThis.__diag("HAS_PAGE called");return typeof process!=="undefined"&&process.versions&&process.versions.node?0:1}'
assert old_page in s; s = s.replace(old_page,new_page,1)

old_int = 'function wasm_module_int_js(name,defaultValue){const key=UTF8ToString(Number(name));'
new_int = 'function wasm_module_int_js(name,defaultValue){globalThis.__diag&&globalThis.__diag("MODULE_INT called");const key=UTF8ToString(Number(name));'
assert old_int in s; s = s.replace(old_int,new_int,1)

open(dst,'w',encoding='utf-8',newline='').write(s)
print('REBUILT clean+diag, len',len(s))
for k in ['table.get(64n)','INIT_MAIN_THREAD','FORCED httpfs','MANIFEST called','IO_START called','HAS_PAGE called','wasm_userdata_put_js']:
    print(k, s.count(k))
