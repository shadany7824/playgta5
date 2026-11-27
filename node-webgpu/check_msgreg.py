import re
s = open(r'E:\gta\playgta5\node-webgpu\game-node.js', encoding='utf-8', errors='replace').read()
for pat in ["addEventListener('message'", 'addEventListener("message"', 'onmessage', 'handleMessage']:
    ms = [m.start() for m in re.finditer(re.escape(pat), s)][:8]
    print(pat, ms)
i = s.find('handleMessage')
print('---handleMessage impl---')
if i >= 0:
    print(s[max(0, i - 400):i + 1400])
