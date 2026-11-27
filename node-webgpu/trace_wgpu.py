s = open(r'E:\gta\playgta5\node-webgpu\game-node.js', encoding='utf-8', errors='replace').read()
i = s.find('wgpuWorker')
# find all occurrences
import re
for m in list(re.finditer(r'wgpuWorker', s))[:5]:
    print('=== occurrence at', m.start(), '===')
    print(s[max(0,m.start()-300):m.start()+400].replace('\n',' ')[:700])
    print()
