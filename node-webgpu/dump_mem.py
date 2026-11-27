# Add a diagnostic to harness: on process-level error, dump strings around key addresses from wasm memory
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# Insert a function to read wasm memory strings and call it from onAbort
old = "  onAbort: (what) => console.error('[harness] ABORT', what),"
new = """  onAbort: (what) => {
    console.error('[harness] ABORT', what);
    try {
      const hb = Buffer.from(globalThis.Module.HEAPU8 ? globalThis.Module.HEAPU8.buffer : (globalThis.HEAPU8 ? globalThis.HEAPU8.buffer : new ArrayBuffer(0)));
      for (const a of [3234064, 25029104, 25029072, 25030368, 25029784, 3123153, 8638616, 12162288, 12162240]) {
        if (a >= 0 && a + 200 < hb.length) {
          const chunk = hb.subarray(a, a + 160);
          const str = chunk.toString('utf8').split('\\0')[0].replace(/[^\\x20-\\x7e]/g, '.');
          console.error('[harness] MEM@' + a + ': ' + str);
        }
      }
    } catch(e) { console.error('[harness] mem dump failed:', e.message); }
  },"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED memory dump on abort')
