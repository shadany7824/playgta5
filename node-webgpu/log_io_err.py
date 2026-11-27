# Add error capture for io worker
p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
shim = r'''
try { const wt=require('worker_threads'); if (wt.workerData && wt.workerData.ioWorker) {
  process.on('uncaughtException', e => { try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO UNCAUGHT: ' + (e.stack||e) + '\n'); } catch(x){} });
  process.on('unhandledRejection', e => { try { require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt', 'IO REJECTION: ' + ((e&&e.stack)||e) + '\n'); } catch(x){} });
}} catch(e){}
'''
if 'IO UNCAUGHT' not in s:
    s = s.replace("// keepalive so the worker thread does not exit while idle", shim + "\n// keepalive so the worker thread does not exit while idle", 1)
    open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED io error capture')
