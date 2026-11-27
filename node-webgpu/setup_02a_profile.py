import shutil, os

h = r'E:\gta\playgta5\node-webgpu\harness.js'
shutil.copyfile(h, h + '.bak-cpuprofile')
s = open(h, encoding='utf-8', errors='replace').read()
old = "const wgpu = new Worker(wgpuWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });"
new = "const wgpu = new Worker(wgpuWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js'), '--cpu-prof', '--cpu-prof-dir=E:/gta/playgta5/node-webgpu/prof', '--cpu-prof-interval=1000'] });"
assert old in s
s = s.replace(old, new, 1)
anchor = "console.log('[harness] waiting for workers...');"
assert anchor in s
s = s.replace(anchor, "setTimeout(() => { console.log('[harness] 02A: requesting clean wgpu worker exit for CPU profile'); try { wgpu.postMessage({ __stopProf: true }); } catch(e){} setTimeout(() => process.exit(0), 6000); }, 240000);\n" + anchor, 1)
open(h, 'w', encoding='utf-8', newline='').write(s)
print('harness.js: cpu-prof flags + clean stop at 240 s')

w = r'E:\gta\playgta5\node-webgpu\wgpu_wrapper2.js'
shutil.copyfile(w, w + '.bak-cpuprofile')
t = open(w, encoding='utf-8', errors='replace').read()
old2 = "if (wt.parentPort) wt.parentPort.on('message', (m) => {\n  try { require('fs').appendFileSync(_LOG, 'MSG keys: ' + Object.keys(m||{}).join(',') + '\\n'); } catch(e){}\n});"
new2 = "if (wt.parentPort) wt.parentPort.on('message', (m) => {\n  try { require('fs').appendFileSync(_LOG, 'MSG keys: ' + Object.keys(m||{}).join(',') + '\\n'); } catch(e){}\n  if (m && m.__stopProf) { try { require('fs').appendFileSync(_LOG, 'clean exit for CPU profile\\n'); } catch(e){} process.exit(0); }\n});"
assert old2 in t
t = t.replace(old2, new2, 1)
open(w, 'w', encoding='utf-8', newline='').write(t)
print('wgpu_wrapper2.js: clean exit handler')

os.makedirs(r'E:\gta\playgta5\node-webgpu\prof', exist_ok=True)
print('prof dir ready')
