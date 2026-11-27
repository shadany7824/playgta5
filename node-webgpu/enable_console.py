import shutil
p = r'E:\gta\playgta5\node-webgpu\harness.js'
shutil.copyfile(p, p + '.bak-fullconsole')
s = open(p, encoding='utf-8', errors='replace').read()
old = "const SEARCH = '?log=1&low=1&res=640x360&fps=30&slots=5&mode=sandbox&args=-textureQuality=0,-shadowQuality=-1,-lodScale=0';"
new = "const SEARCH = '?log=1&low=1&res=640x360&fps=30&slots=5&mode=sandbox&console=1&args=-textureQuality=0,-shadowQuality=-1,-lodScale=0';"
assert old in s, 'SEARCH line changed'
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ENABLED full console')
