p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
# Remove the late declaration at line 41
late = "  const isPthread = (() => { try { return require('worker_threads').workerData && require('worker_threads').workerData.pthread; } catch(e){ return false; } })();\n"
s = s.replace(late, '', 1)
# Add declaration right after PTHLOG (before the if that uses it)
old = "  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';\n"
new = "  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';\n  const isPthread = (() => { try { return require('worker_threads').workerData && require('worker_threads').workerData.pthread; } catch(e){ return false; } })();\n"
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('MOVED isPthread declaration before use')
