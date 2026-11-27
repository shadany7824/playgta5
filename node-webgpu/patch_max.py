src = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(src, encoding='utf-8', errors='replace').read()
s2 = s.replace('maximum:262144,shared:true,address:"i64"', 'maximum:65536,shared:true,address:"i64"')
print('replaced:', s != s2)
open(src, 'w', encoding='utf-8', newline='').write(s2)
