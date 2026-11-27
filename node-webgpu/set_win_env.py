p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "b+424,4),2,1920);Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),3,1080)"
new = "b+424,4),2,+(process.env.WGPU_WIN_W||1920));Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),3,+(process.env.WGPU_WIN_H||1080))"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('win size now env-configurable (WGPU_WIN_W / WGPU_WIN_H)')
