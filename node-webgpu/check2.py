s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
for k in ['self.location', 'importScripts', 'BroadcastChannel', 'wgpuWorker', 'ioWorker', 'wgpuShaderUrl', 'Module["canvas"]', 'Module.canvas', 'ENVIRONMENT_IS_NODE', 'require(', 'postMessage', 'onmessage']:
    print('%-24s %d' % (k, s.count(k)))
print()
import re
for m in list(re.finditer('wgpuWorker', s))[:6]:
    print('...', s[max(0,m.start()-130):m.start()+190].replace('\n',' ')[:320])
