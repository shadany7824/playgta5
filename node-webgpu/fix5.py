p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
s = s.replace("globalThis.crypto = globalThis.crypto || require('crypto').webcrypto;\n", '')
open(p, 'w', encoding='utf-8', newline='').write(s)
print('REMOVED crypto line')
