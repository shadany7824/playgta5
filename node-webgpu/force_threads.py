p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);'
new = 'var pthreadPoolSize=Math.min(160,navigator.hardwareConcurrency<=2?28:36+4*navigator.hardwareConcurrency);pthreadPoolSize=2;'
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('FORCED pthreadPoolSize=2')
