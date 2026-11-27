import shutil
p = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(p, p + '.bak-sandbox2')
s = open(p, encoding='utf-8', errors='replace').read()
old = 'Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);'
new = 'Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,1);'
print('found:', old in s)
s = s.replace(old, new, 1)
s = s.replace('startMode=2 win=640x360', 'startMode=1 win=640x360', 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('SWITCHED to story mode (1)')
