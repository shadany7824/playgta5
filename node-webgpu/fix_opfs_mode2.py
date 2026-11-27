p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = "                let fd = fs.openSync(full, 'a+');"
new = "                if (!fs.existsSync(full)) fs.writeFileSync(full, Buffer.alloc(0));\n                let fd = fs.openSync(full, 'r+');"
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('APPLIED r+ fix to worker-boot.js')
