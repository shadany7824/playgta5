g = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(g, encoding='utf-8').read()
old = "  onRuntimeInitialized: () => console.log('[harness] runtime initialized'),"
new = """  onRuntimeInitialized: () => {
    console.log('[harness] runtime initialized');
    try {
      const mem = globalThis.__wasmMemory;
      if (mem && mem.buffer) {
        new Uint8Array(mem.buffer)[8321672] = 1;
        globalThis.__diag && globalThis.__diag('FORCED httpfs active byte');
      } else { globalThis.__diag && globalThis.__diag('no __wasmMemory'); }
    } catch(e) { globalThis.__diag && globalThis.__diag('force err ' + e.message); }
  },"""
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('APPLIED force httpfs active in onRuntimeInitialized')
