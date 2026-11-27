g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
s = s.replace('const loadFn=tbl.get(64);', 'const loadFn=tbl.get(64n);')
open(g, 'w', encoding='utf-8', newline='').write(s)
print('FIXED table.get(64n)')
