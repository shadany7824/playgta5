p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
old = "const io = new Worker(ioWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });\nio.unref();\nio.on('error', (e) => console.error('[harness] io worker error:', e.message));\nio.on('message', (m) => { if (m && m.loaded) maybeStart(); });"
new = "const io = new Worker(ioWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });\nio.unref();\nio.on('error', (e) => console.error('[harness] io worker error:', e.message));\nio.on('message', (m) => { if (m && m.loaded) maybeStart(); });\n// io_worker.js needs an init message before it sends {loaded:true}\nio.postMessage({ init: true, base: 'http://localhost:8000/data/', noStore: false, record: false, trace: false, log: false, noHints: false, bootset: 'bootset_low.json' });"
assert old in s, 'io block not found'
s = s.replace(old, new, 1)
# also remove the bogus wgpuWorker init post in maybeStart (wgpu sends loaded on its own at script end)
s = s.replace("  globalThis.Module.wgpuWorker.postMessage({ type: 'init' });  // harmless if ignored\n", "")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('UPDATED: io init sent, removed bogus wgpu init')
