import shutil
h = r'E:\gta\playgta5\node-webgpu\harness.js'
shutil.copyfile(h, h + '.bak-02a-150')
s = open(h, encoding='utf-8', errors='replace').read()
s = s.replace('}, 240000);\nconsole.log(\'[harness] waiting for workers...\');', '}, 150000);\nconsole.log(\'[harness] waiting for workers...\');', 1)
open(h, 'w', encoding='utf-8', newline='').write(s)
print('stop timer -> 150 s')
