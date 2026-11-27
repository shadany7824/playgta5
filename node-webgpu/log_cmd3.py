p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
L = "require('fs').appendFileSync('E:/gta/playgta5/node-webgpu/pthread-msg-log.txt'"
# Log when main receives cmd:3 (onFinishedLoading)
old = "case 3:onFinishedLoading(worker);break;"
new = "case 3:" + L + ",'MAIN received cmd:3\\n');" + "onFinishedLoading(worker);break;"
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED main cmd:3 logging')
