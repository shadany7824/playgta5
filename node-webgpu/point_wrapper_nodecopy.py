p = r'E:\gta\playgta5\node-webgpu\wgpu_wrapper2.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "require('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js');"
new = "require('E:/gta/playgta5/node-webgpu/wgpu_worker_node.js');"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('wrapper points to node-only worker copy')
