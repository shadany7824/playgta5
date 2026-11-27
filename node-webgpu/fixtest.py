p = r'E:\gta\playgta5\node-webgpu\test_opfs.js'
s = open(p, encoding='utf-8').read()
s = s.replace("let fd = fs.openSync(full, 'a+');", "if (!fs.existsSync(full)) fs.writeFileSync(full, Buffer.alloc(0)); let fd = fs.openSync(full, 'r+');")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('test updated')
