s = open(r'E:\gta\playgta5\node-webgpu\game-node.js', encoding='utf-8', errors='replace').read()
i = s.find('async loadWasmModuleToWorker')
print('=== loadWasmModuleToWorker at', i, '===')
print(s[i:i+900].replace('\n',' ')[:900])
