s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
import re
# Find allocateUnusedWorker context
i = s.find('allocateUnusedWorker')
print('=== around allocateUnusedWorker ===')
print(s[i-600:i+300])
print()
for key in ['mainScriptUrlOrBlob', 'workerUrl', 'WGPU_WORKER', 'new Worker(']:
    print('%-24s %d' % (key, s.count(key)))
