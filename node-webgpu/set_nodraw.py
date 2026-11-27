p = r'E:\gta\playgta5\node-webgpu\wgpu_worker_node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "function doDraw(p) {\n\t// kind (0 draw, 1 indexed, 2 instanced, 3 indexed instanced)"
new = "function doDraw(p) {\n\tif (isNode && process.env.WGPU_NODRAW === '1') return;\t\t// engine-ceiling diagnostic (file 02 2B)\n\t// kind (0 draw, 1 indexed, 2 instanced, 3 indexed instanced)"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('no-draw diagnostic installed')
