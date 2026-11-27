s = open(r'E:\gta\playgta5\node-webgpu\game-node.js', encoding='utf-8', errors='replace').read()
# find "loaded === 2" or the worker ready counting
for key in ['loaded===2', 'loaded == 2', '++loaded', 'addRunDependency("loading-workers")', 'loadWasmModuleToAllWorkers']:
    i = s.find(key)
    print('===', key, 'at', i, '===')
    if i >= 0:
        print(s[max(0,i-300):i+300].replace('\n',' ')[:600])
        print()
