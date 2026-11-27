s = open(r'E:\gta\playgta5\node-webgpu\game-node.js', encoding='utf-8', errors='replace').read()
import re
for m in list(re.finditer(r'Worker', s))[:8]:
    print('...', s[max(0,m.start()-80):m.start()+80].replace('\n',' ')[:160])
