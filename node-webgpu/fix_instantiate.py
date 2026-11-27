p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = """// pthread workers instantiate the wasm themselves: provide instantiateWasm so they don't try to fetch a URL
const _fs = require('fs');
globalThis.Module.instantiateWasm = (imports, done) => {"""
new = """// MAIN thread only needs instantiateWasm (reads wasm from disk).
// pthread workers receive wasmModule via cmd=1 and use `new WebAssembly.Instance(wasmModule)` directly;
// providing instantiateWasm there makes createWasm() async and breaks the cmd=3 ready handshake.
const _fs = require('fs');
const _isPthread = (() => { try { return (require('worker_threads').workerData && require('worker_threads').workerData.pthread); } catch(e){ return false; } })();
if (!_isPthread) globalThis.Module.instantiateWasm = (imports, done) => {"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('FIXED: instantiateWasm only for main thread')
