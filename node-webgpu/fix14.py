p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = "globalThis.Module.wgpuShaderUrl = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';"
new = """globalThis.Module.wgpuShaderUrl = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
// pthread workers instantiate the wasm themselves: provide instantiateWasm so they don't try to fetch a URL
const _fs = require('fs');
globalThis.Module.instantiateWasm = (imports, done) => {
  const bytes = _fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm');
  WebAssembly.instantiate(bytes, imports).then((r) => done(r.instance, r.module)).catch((e) => console.error('[boot] wasm instantiate failed:', e.message));
  return {};
};"""
assert old in s
s = s.replace(old, new, 1)
# also limit hardwareConcurrency in workers
s = s.replace("globalThis.self = globalThis;", "globalThis.self = globalThis;\ntry { Object.defineProperty(globalThis.navigator, 'hardwareConcurrency', { value: 2, configurable: true }); } catch(e) {}", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('BOOT: added instantiateWasm + hardwareConcurrency')
