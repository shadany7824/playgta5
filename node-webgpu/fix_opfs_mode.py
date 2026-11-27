# Fix the OPFS shim in worker-boot: ftruncate on 'a+' mode fails EPERM on Windows.
# Open with 'r+' (create empty first if needed), which supports truncate/read/write at offsets.
p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = "              createSyncAccessHandle: () => {\n                let fd = fs.openSync(full, 'a+');"
new = "              createSyncAccessHandle: () => {\n                if (!fs.existsSync(full)) fs.writeFileSync(full, Buffer.alloc(0));\n                let fd = fs.openSync(full, 'r+');"
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('FIXED OPFS file mode a+ -> r+')
