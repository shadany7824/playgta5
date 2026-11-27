s = open(r'E:\gta\playgta5\node-webgpu\worker-boot.js', encoding='utf-8', errors='replace').read()
old = """  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (fn) parentPort.on('message', (data) => {
      if (isPthread) { try { require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' keys=' + Object.keys(data||{}).join(',') + '\\n'); } catch(e){} }
      fn({ data });
    }); }
  });"""
new = """  let __bridgeInstalled = false;
  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (!__bridgeInstalled && fn) { __bridgeInstalled = true; parentPort.on('message', (data) => {
      if (isPthread) { try { require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' keys=' + Object.keys(data||{}).join(',') + '\\n'); } catch(e){} }
      if (_onmessage) _onmessage({ data });
    }); } }
  });"""
assert old in s, 'onmessage block not found'
s = s.replace(old, new, 1)
open(r'E:\gta\playgta5\node-webgpu\worker-boot.js', 'w', encoding='utf-8', newline='').write(s)
print('FIXED single-instance onmessage bridge')
