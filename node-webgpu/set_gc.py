p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });"
new = "execArgv: ['--require', path.join(__dirname, 'worker-boot.js'), '--max-semi-space-size=64'] });"
assert s.count(old) == 2, 'expected wgpu + io workers'
assert '--max-semi-space-size' not in s
open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('GC semi-space 64MB added to wgpu worker only')
