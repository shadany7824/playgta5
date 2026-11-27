# Add fetch logging to worker-boot for the io worker (workerData.ioWorker flag)
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# Mark the io worker with workerData so boot shim can detect it
old = "const io = new Worker(ioWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });"
new = "const io = new Worker(ioWorkerPath, { env: process.env, workerData: { ioWorker: true }, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });"
print('found io worker:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)

# Add fetch logging in worker-boot for io worker
p2 = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
b = open(p2, encoding='utf-8').read()
shim = r'''
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
'''
if 'IO FETCH' not in b:
    b = b.replace("// keepalive so the worker thread does not exit while idle", shim + "\n// keepalive so the worker thread does not exit while idle", 1)
    open(p2, 'w', encoding='utf-8', newline='').write(b)
print('ADDED io fetch logging')
