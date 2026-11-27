import shutil
p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read().replace('game-lod50.wasm', 'game-lodlive.wasm')
open(p, 'w', encoding='utf-8', newline='').write(s)
src = r'E:\Malik\game\game-lodlive.wasm'
dst = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game-lodlive.wasm'
shutil.copy2(src, dst)
print('fresh wasm name in place')
