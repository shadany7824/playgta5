p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'var Module=typeof Module!="undefined"?Module:{}'
new = 'var Module=(typeof globalThis!=="undefined"&&globalThis.Module)?globalThis.Module:(typeof Module!="undefined"?Module:{})'
print('old found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('PATCHED Module detection to use globalThis.Module')
