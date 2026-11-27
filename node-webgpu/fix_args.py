p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# Fix args: engine expects engine command line flags. Use the same style as browser (args param in URL SEARCH)
old = "  arguments: ['-low', '-res=640x360'],"
new = "  arguments: ['-low', '-res=640x360', '-lodScale=0', '-shadows=-1'],"  # minimal; main thing is data
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('args updated')
