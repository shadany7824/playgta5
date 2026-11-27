# Try to call Load() (wasm func 192) via the indirect function table after runtime init.
# The table maps function indices; func 192 should be callable if it's in the table.
# We'll find its table index by scanning table entries and matching... but table.get returns JS wrappers
# without index info. Alternative: patch game-node to call __wasm_call_ctors + directly call Load through
# a synthetic import. Simplest hack: force the httpfs-active byte via memory write after init.

g = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(g, encoding='utf-8').read()
old = "    console.log('[harness] runtime initialized');"
new = """    console.log('[harness] runtime initialized');
    // Force httpfs active byte = 1 so the engine uses the io worker (Load() would set this).
    // Address 8321672L = 8321672. HEAPU8 is internal, but Module exports wasmMemory via instantiateWasm.
    try {
      const mem = globalThis.__wasmMemory;
      if (mem && mem.buffer) {
        const view = new Uint8Array(mem.buffer);
        view[8321672] = 1;
        globalThis.__diag && globalThis.__diag('FORCED httpfs active byte at 8321672');
      } else { globalThis.__diag && globalThis.__diag('no __wasmMemory to set httpfs active'); }
    } catch(e) { globalThis.__diag && globalThis.__diag('force httpfs err: ' + e.message); }"""
if 'FORCED httpfs' not in s:
    s = s.replace(old, new, 1)
    # expose wasmMemory in instantiateWasm
    s = s.replace("WebAssembly.instantiate(bytes, imports).then((r) => done(r.instance, r.module))",
                  "WebAssembly.instantiate(bytes, imports).then((r) => { globalThis.__wasmMemory = imports.memory; done(r.instance, r.module); })", 1)
    open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED force httpfs active')
