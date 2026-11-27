p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
old = "  mainScriptUrlOrBlob: GAME_JS,"
new = """  mainScriptUrlOrBlob: GAME_JS,
  // Node: load game.wasm from disk (Emscripten's default fetch fails without a browser)
  instantiateWasm: (imports, done) => {
    const bytes = fs.readFileSync('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm');
    WebAssembly.instantiate(bytes, imports).then((r) => done(r.instance, r.module)).catch((e) => console.error('[harness] wasm instantiate failed:', e.message));
    return {};
  },"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED instantiateWasm from disk')
