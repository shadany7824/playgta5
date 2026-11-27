import shutil
p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
shutil.copyfile(p, p + '.bak-onmsgfix')
s = open(p, encoding='utf-8', errors='replace').read()
old = """  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (fn) parentPort.on('message', (data) => {
      if (isPthread) { try { let extra=''; if(data && data.cmd===2){ globalThis.__lastStartRoutine=data.start_routine; const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; extra=' sr='+data.start_routine+' arg='+data.arg+' tlen='+tl; } require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' tid=' + require('worker_threads').threadId + extra + '\\n'); } catch(e){} }
      fn({ data });
    }); }
  });"""
new = """  let __bridgeInstalled = false;
  Object.defineProperty(globalThis, 'onmessage', {
    get() { return _onmessage; },
    set(fn) { _onmessage = fn; if (!__bridgeInstalled && fn) { __bridgeInstalled = true; parentPort.on('message', (data) => {
      if (isPthread) { try { let extra=''; if(data && data.cmd===2){ globalThis.__lastStartRoutine=data.start_routine; const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; extra=' sr='+data.start_routine+' arg='+data.arg+' tlen='+tl; } require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' tid=' + require('worker_threads').threadId + extra + '\\n'); } catch(e){} }
      if (_onmessage) _onmessage({ data });
    }); } }
  });"""
assert old in s, 'onmessage block not found'
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('FIXED single-instance onmessage bridge')
