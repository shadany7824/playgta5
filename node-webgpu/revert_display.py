p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "search: '?display=1920x1080'"
new = "search: ''"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('display override reverted')
