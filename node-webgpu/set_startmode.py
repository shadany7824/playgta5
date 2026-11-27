# Send the start-mode choice by writing the WasmInputBlock.startMode atomic,
# exactly like index.html does (block base 6583436, startMode at +440 => 6583876).
h = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(h, encoding='utf-8').read()
anchor = "  console.log('[harness] STATUS t='"
insert = """// Start-mode choice (same as browser ?mode=sandbox): write the atomic WasmInputBlock.startMode.
// Block base = 6583436 (from game.dcmp wasm_input_publish_js(6583436L)); startMode = block+440 (index.html installInput).
setInterval(() => {
  const mem = globalThis.__wasmMemory;
  if (!mem || !mem.buffer) return;
  try {
    const START = 6583436 + 440;
    const i32 = new Int32Array(mem.buffer);
    if (Atomics.load(i32, START >> 2) === 0) {
      Atomics.store(i32, START >> 2, 2);  // 2 = Sandbox Mode on GTA V map
      console.log('[harness] wrote startMode=2 at ' + START);
    }
  } catch(e) { console.log('[harness] startMode write err:', e.message); }
}, 500).unref();

""" + anchor
if 'wrote startMode' not in s:
    assert anchor in s, 'anchor missing'
    s = s.replace(anchor, insert, 1)
    open(h, 'w', encoding='utf-8', newline='').write(s)
print('ADDED startMode=2 writer')
