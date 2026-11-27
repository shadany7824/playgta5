p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
s = s.replace("new Worker(wgpuWorkerPath, { env: process.env })", "new Worker(wgpuWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] })")
s = s.replace("new Worker(ioWorkerPath, { env: process.env })", "new Worker(ioWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] })")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('UPDATED harness with worker preload')
