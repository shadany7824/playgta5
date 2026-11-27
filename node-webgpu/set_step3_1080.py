import shutil

h = r'E:\gta\playgta5\node-webgpu\harness.js'
shutil.copyfile(h, h + '.bak-step3-1080')
s = open(h, encoding='utf-8', errors='replace').read()
old_search = "const SEARCH = '?log=1&low=1&res=640x360&fps=30&slots=5&mode=sandbox&console=1&args=-textureQuality=0,-shadowQuality=-1,-lodScale=0';"
new_search = "const SEARCH = '?log=1&low=0&res=1920x1080&fps=0&slots=5&mode=sandbox&args=-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=0';"
assert old_search in s
s = s.replace(old_search, new_search, 1)
old_args = "  arguments: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', '-pc:nosocialclub', '-nonetwork', '-output', '-width=640', '-height=360', '-forceResolution', '-textureQuality=0', '-shadowQuality=-1', '-lodScale=0', '-frameLimit=2'],"
new_args = "  arguments: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', '-pc:nosocialclub', '-nonetwork', '-output', '-width=1920', '-height=1080', '-forceResolution', '-textureQuality=2', '-shadowQuality=0', '-reflectionQuality=1', '-particleQuality=0', '-grassQuality=0', '-cityDensity=0', '-lodScale=0', '-frameLimit=0'],"
assert old_args in s
s = s.replace(old_args, new_args, 1)
open(h, 'w', encoding='utf-8', newline='').write(s)
print('harness.js patched for STEP-3 1080p (screenshots off, console off, uncapped)')

g = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(g, g + '.bak-step3-sandbox')
t = open(g, encoding='utf-8', errors='replace').read()
old = 'Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,1);'
new = 'Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);'
assert old in t
t = t.replace(old, new, 1)
t = t.replace('startMode=1 win=640x360', 'startMode=2 win=1920x1080', 1)
t = t.replace('new Int32Array(wasmMemory.buffer,b+424,4),0,640', 'new Int32Array(wasmMemory.buffer,b+424,4),0,1920', 1)
t = t.replace('new Int32Array(wasmMemory.buffer,b+424,4),1,360', 'new Int32Array(wasmMemory.buffer,b+424,4),1,1080', 1)
open(g, 'w', encoding='utf-8', newline='').write(t)
print('game-node.js patched: sandbox mode + 1920x1080 input block')
