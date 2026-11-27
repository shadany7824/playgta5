// preload for worker_threads: browser-style globals the port's workers expect
'use strict';
const { parentPort } = require('worker_threads');
globalThis.self = globalThis;
// Emscripten pthread detection in Node: no WorkerGlobalScope, so set it + name for pthread workers
try { const wt = require('worker_threads'); if (wt.workerData && wt.workerData.pthread) { globalThis.name='em-pthread'; globalThis.WorkerGlobalScope=function(){}; } } catch(e){}
try { Object.defineProperty(globalThis.navigator, 'hardwareConcurrency', { value: 2, configurable: true }); } catch(e) {}

// pthread workers: set Module so game.js's `var Module` picks it up via global scope
if (typeof globalThis.Module === 'undefined') {
  globalThis.Module = {};
}
globalThis.Module.mainScriptUrlOrBlob = 'E:/gta/playgta5/node-webgpu/game-node.js';
globalThis.Module.wgpuShaderUrl = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
// MAIN thread only needs instantiateWasm (reads wasm from disk).
// pthread workers receive wasmModule via cmd=1 and use `new WebAssembly.Instance(wasmModule)` directly;
// providing instantiateWasm there makes createWasm() async and breaks the cmd=3 ready handshake.
const _fs = require('fs');
const _isPthread = (() => { try { return (require('worker_threads').workerData && require('worker_threads').workerData.pthread); } catch(e){ return false; } })();
if (!_isPthread) globalThis.Module.instantiateWasm = (imports, done) => {
  const PTHLOG2 = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
  try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm called\n'); } catch(e){}
  const bytes = _fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm');
  WebAssembly.instantiate(bytes, imports).then((r) => { try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm OK\n'); } catch(e){} done(r.instance, r.module); }).catch((e) => { try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm ERR: ' + e.message + '\n'); } catch(e){} });
  return {};
};

// location with query params (wgpu worker reads log/slots/display flags from its own URL)
globalThis.location = { search: '', origin: 'http://localhost:8000', href: '' };
globalThis.self.location = globalThis.location;
// postMessage/onmessage bridging to worker_threads
if (parentPort) {
  globalThis.postMessage = (m) => {
    try { const wt = require('worker_threads'); if (wt.workerData && wt.workerData.pthread) require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'SEND cmd=' + (m&&m.cmd) + '\n'); } catch(e){}
    parentPort.postMessage(m);
  };
  globalThis.addEventListener = (ev, fn) => { if (ev === 'message') parentPort.on('message', (data) => fn({ data })); };
  let _onmessage = null;
  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
  const isPthread = (() => { try { return require('worker_threads').workerData && require('worker_threads').workerData.pthread; } catch(e){ return false; } })();
  if (isPthread) {
    process.on('uncaughtException', e => { try { const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; require('fs').appendFileSync(PTHLOG, 'UNCAUGHT tid=' + require('worker_threads').threadId + ' tlen=' + tl + ' sr=' + globalThis.__lastStartRoutine + ' :: ' + (e.stack||e) + '\n'); } catch(x){} });
    process.on('unhandledRejection', e => { try { require('fs').appendFileSync(PTHLOG, 'REJECTION: ' + ((e&&e.stack)||e) + '\n'); } catch(x){} });
  }
  let __bridgeInstalled = false;
  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (!__bridgeInstalled && fn) { __bridgeInstalled = true; parentPort.on('message', (data) => {
      if (isPthread) { try { let extra=''; if(data && data.cmd===2){ globalThis.__lastStartRoutine=data.start_routine; const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; extra=' sr='+data.start_routine+' arg='+data.arg+' tlen='+tl; } require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' tid=' + require('worker_threads').threadId + extra + '\n'); } catch(e){} }
      if (_onmessage) _onmessage({ data });
    }); } }
  });
}
if (typeof BroadcastChannel === 'undefined') {
  const WLOG = 'E:/gta/playgta5/node-webgpu/engine-log.txt';
  globalThis.BroadcastChannel = class {
    constructor(name){ this.name = name; }
    postMessage(msg){
      try { const txt = (typeof msg === 'string') ? msg : JSON.stringify(msg); require('fs').appendFileSync(WLOG, '[' + this.name + '] ' + txt + '\n'); } catch(e){}
    }
    close(){} addEventListener(){}
  };
}

// ---- Node OPFS shim (browser-only File System Access API used by io_worker.js) ----
try {
  const fs = require('fs');
  const path = require('path');
  const OPFS_ROOT = 'E:/gta/playgta5/node-webgpu/opfs-store';
  fs.mkdirSync(OPFS_ROOT, { recursive: true });
  if (!globalThis.navigator) globalThis.navigator = {};
  globalThis.navigator.storage = {
    getDirectory: async () => ({
      getDirectoryHandle: async (name) => {
        const d = path.join(OPFS_ROOT, name);
        fs.mkdirSync(d, { recursive: true });
        return {
          getFileHandle: async (fname) => {
            const full = path.join(d, fname);
            return {
              createSyncAccessHandle: () => {
                if (!fs.existsSync(full)) fs.writeFileSync(full, Buffer.alloc(0));
                let fd = fs.openSync(full, 'r+');
                return {
                  read(buf, opts) { const n = fs.readSync(fd, buf, 0, buf.length, opts.at || 0); return n; },
                  write(buf, opts) { return fs.writeSync(fd, buf, 0, buf.length, opts.at || 0); },
                  truncate(size) { fs.ftruncateSync(fd, size); },
                  getSize() { return fs.fstatSync(fd).size; },
                  flush() { fs.fsyncSync(fd); },
                  close() { fs.closeSync(fd); }
                };
              }
            };
          }
        };
      }
    })
  };
  if (typeof globalThis.indexedDB === 'undefined') {
    globalThis.indexedDB = { open: () => ({ onupgradeneeded:null, onerror:null, onsuccess:null, result:{ createObjectStore(){}, transaction(){ return { objectStore(){ return { openCursor(){ return { onsuccess:null }; } }; } }; } } }) };
  }
} catch(e) { console.error('[boot] OPFS shim error:', e.message); }


// Log io worker fetch activity
try { const wt=require('worker_threads'); if (wt.workerData && wt.workerData.ioWorker) {
  const _of = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO FETCH ' + String(url).slice(0,120) + '\n'); } catch(e){}
    const r = await _of(url, init);
    try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO FETCH RESULT ' + r.status + '\n'); } catch(e){}
    return r;
  };
}} catch(e){}


try { const wt=require('worker_threads'); if (wt.workerData && wt.workerData.ioWorker) {
  process.on('uncaughtException', e => { try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO UNCAUGHT: ' + (e.stack||e) + '\n'); } catch(x){} });
  process.on('unhandledRejection', e => { try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO REJECTION: ' + ((e&&e.stack)||e) + '\n'); } catch(x){} });
}} catch(e){}

// heartbeat + proxy accounting for pthread workers
try {
  const wt = require('worker_threads');
  const isP = wt.workerData && wt.workerData.pthread;
  if (isP) {
    const HB = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
    let n = 0;
    setInterval(() => { n++; try { require('fs').appendFileSync(HB, 'ALIVE tid=' + wt.threadId + ' n=' + n + '\n'); } catch(e){} }, 10000);
  }
} catch(e){}

// keepalive so the worker thread does not exit while idle
const _keep = setInterval(() => {}, 1000);
globalThis.__workerKeepAlive = _keep;
