w = r'E:\gta\playgta5\node-webgpu\wgpu_wrapper2.js'
s = open(w, encoding='utf-8', errors='replace').read()
old = "setTimeout(() => { try { require('fs').appendFileSync(_LOG, '02A self clean exit\\n'); } catch(e){} process.exit(0); }, 150000);"
assert old in s
s = s.replace(old, '', 1)
old2 = "  if (m && m.__stopProf) { try { require('fs').appendFileSync(_LOG, 'clean exit for CPU profile\\n'); } catch(e){} process.exit(0); }"
new2 = "  if (m && m.memory && !globalThis.__activeTimer) { globalThis.__activeTimer = 1; try { require('fs').appendFileSync(_LOG, 'active worker tid=' + wt.threadId + ' pid=' + process.pid + '\\n'); } catch(e){} setTimeout(() => { try { require('fs').appendFileSync(_LOG, '02A self clean exit active tid=' + wt.threadId + '\\n'); } catch(e){} process.exit(0); }, 150000); }\n" + old2
assert old2 in s
s = s.replace(old2, new2, 1)
open(w, 'w', encoding='utf-8', newline='').write(s)
print('active-worker-only profiler exit')
