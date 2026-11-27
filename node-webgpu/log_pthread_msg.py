p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
# Add logging to the onmessage setter and addEventListener to see incoming messages in pthread workers
old = """  let _onmessage = null;
  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (fn) parentPort.on('message', (data) => fn({ data })); }
  });"""
new = """  let _onmessage = null;
  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
  const isPthread = (() => { try { return require('worker_threads').workerData && require('worker_threads').workerData.pthread; } catch(e){ return false; } })();
  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (fn) parentPort.on('message', (data) => {
      if (isPthread) { try { require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' keys=' + Object.keys(data||{}).join(',') + '\\n'); } catch(e){} }
      fn({ data });
    }); }
  });"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED pthread message logging')
