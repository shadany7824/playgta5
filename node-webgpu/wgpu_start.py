# Send a synthetic wgpu worker start message from the harness, with a 32MB ring allocated
# in the wasm memory at a high unused address (0x70000000 = 1873781248, within 3GB).
# This tests the wgpu/Dawn handshake independently of the mount problem.
h = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(h, encoding='utf-8').read()
old = "// io_worker.js needs an init message before it sends {loaded:true}"
new = """// Synthetic wgpu start: allocate ring in wasm memory and start the worker directly.
// (normally the engine's wasm_gpu_Init() does this; we bypass it to test the Dawn path)
setTimeout(() => {
  const mem = globalThis.__wasmMemory;
  if (!mem) { console.log('[harness] no wasm memory for wgpu start'); return; }
  const RING = 0x70000000;  // ~1.8 GB into the 3 GB wasm memory, unused region
  const u8 = new Uint8Array(mem.buffer);
  const i32 = new Int32Array(mem.buffer);
  u8.fill(0, RING, RING + 64);         // clear ring header
  i32[(RING) >> 2] = RING + 64;         // head
  i32[(RING + 4) >> 2] = RING + 64;     // tail
  i32[(RING + 5) >> 2] = 1;             // sleeping flag
  wgpu.postMessage({ memory: mem, ring: RING, size: 33554432, dbg: 0,
                     shaderUrl: 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders', shotEvery: 0 });
  console.log('[harness] sent synthetic wgpu start, ring=0x' + RING.toString(16));
}, 2000);

""" + old
assert old in s
s = s.replace(old, new, 1)
open(h, 'w', encoding='utf-8', newline='').write(s)
print('ADDED synthetic wgpu start')
