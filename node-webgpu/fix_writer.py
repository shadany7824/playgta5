p = r'E:\gta\playgta5\node-webgpu\harness.js'
lines = open(p, encoding='utf-8').read().split('\n')
# Replace the malformed block (0-indexed lines 132..149 = file lines 133..150)
fixed = [
 "console.log('[harness] waiting for workers...');",
 "// Start-mode choice (same as browser ?mode=sandbox): write atomic WasmInputBlock.startMode.",
 "// Block base 6583436 (game.dcmp wasm_input_publish_js(6583436L)); startMode = block+440 (index.html installInput).",
 "setInterval(() => {",
 "  const mem = globalThis.__wasmMemory;",
 "  if (!mem || !mem.buffer) return;",
 "  try {",
 "    const START = 6583436 + 440;",
 "    const i32 = new Int32Array(mem.buffer);",
 "    if (Atomics.load(i32, START >> 2) === 0) {",
 "      Atomics.store(i32, START >> 2, 2);  // 2 = Sandbox Mode on GTA V map",
 "      console.log('[harness] wrote startMode=2 at ' + START);",
 "    }",
 "  } catch(e) { console.log('[harness] startMode write err:', e.message); }",
 "}, 500).unref();",
 "setInterval(() => {",
 "  console.log('[harness] STATUS t=' + Math.round(process.uptime()) + 's wgpuReady=' + !!globalThis.__wgpuReady + ' engineLog=' + (() => { try { return fs.statSync('E:/gta/playgta5/node-webgpu/engine-log.txt').size; } catch(e){ return -1; } })());",
 "}, 15000).unref();",
]
out = lines[:132] + fixed
open(p, 'w', encoding='utf-8', newline='').write('\n'.join(out))
print('FIXED harness startMode block')
