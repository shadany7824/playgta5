p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "globalThis.location = { search: '', origin: 'http://localhost:8000', href: '' };"
new = "globalThis.location = { search: '?display=1920x1080', origin: 'http://localhost:8000', href: '' };"
assert old in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('worker display=1920x1080 set')
