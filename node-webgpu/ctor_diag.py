# The wasm global is_runtime_thread starts at 0 and should be set to 1 by the engine's
# static constructor via emscripten_init_main_thread_js. If that path isn't running in Node,
# we can force it from JS using the exported set_thread_state (c param = is_runtime_thread).
# But we need thread_ptr too. Better: call __wasm_call_ctors explicitly and verify.
# Let's first check if the ctors export exists and call it.

g = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(g, encoding='utf-8').read()
anchor = "  onRuntimeInitialized: () => console.log('[harness] runtime initialized'),"
new = """  onRuntimeInitialized: () => {
    console.log('[harness] runtime initialized');
    try {
      const ctors = globalThis.Module._wasm_call_ctors || (typeof wasmExports !== 'undefined' && wasmExports !== null ? null : null);
      globalThis.__diag && globalThis.__diag('CTOR check done');
    } catch(e) { globalThis.__diag && globalThis.__diag('CTOR err ' + e.message); }
  },"""
if 'CTOR check' not in s:
    s = s.replace(anchor, new, 1)
    open(g, 'w', encoding='utf-8', newline='').write(s)
print('harness updated')
