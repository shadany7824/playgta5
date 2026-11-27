p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = """globalThis.Module.instantiateWasm = (imports, done) => {
  const bytes = _fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm');
  WebAssembly.instantiate(bytes, imports).then((r) => done(r.instance, r.module)).catch((e) => console.error('[boot] wasm instantiate failed:', e.message));
  return {};
};"""
new = """globalThis.Module.instantiateWasm = (imports, done) => {
  const PTHLOG2 = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
  try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm called\\n'); } catch(e){}
  const bytes = _fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm');
  WebAssembly.instantiate(bytes, imports).then((r) => { try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm OK\\n'); } catch(e){} done(r.instance, r.module); }).catch((e) => { try { _fs.appendFileSync(PTHLOG2, 'instantiateWasm ERR: ' + e.message + '\\n'); } catch(e){} });
  return {};
};"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED instantiateWasm logging')
