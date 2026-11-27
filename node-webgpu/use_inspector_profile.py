w = r'E:\gta\playgta5\node-webgpu\wgpu_wrapper2.js'
s = open(w, encoding='utf-8', errors='replace').read()
old = "  if (m && m.memory && !globalThis.__activeTimer) { globalThis.__activeTimer = 1; try { require('fs').appendFileSync(_LOG, 'active worker tid=' + wt.threadId + ' pid=' + process.pid + '\\n'); } catch(e){} setTimeout(() => { try { require('fs').appendFileSync(_LOG, '02A self clean exit active tid=' + wt.threadId + '\\n'); } catch(e){} process.exit(0); }, 150000); }"
new = ("  if (m && m.memory && !globalThis.__activeTimer) { globalThis.__activeTimer = 1;\n"
       "    try {\n"
       "      const inspector = require('inspector');\n"
       "      const sess = new inspector.Session(); sess.connect();\n"
       "      sess.post('Profiler.enable'); sess.post('Profiler.setSamplingInterval', { interval: 1000 }); sess.post('Profiler.start');\n"
       "      require('fs').appendFileSync(_LOG, 'active worker tid=' + wt.threadId + ' pid=' + process.pid + ' inspector started\\n');\n"
       "      setTimeout(() => sess.post('Profiler.stop', (err, data) => {\n"
       "        try {\n"
       "          require('fs').writeFileSync('E:/gta/playgta5/node-webgpu/prof/active-worker.cpuprofile', JSON.stringify(data.profile));\n"
       "          require('fs').appendFileSync(_LOG, '02A worker profile written tid=' + wt.threadId + '\\n');\n"
       "        } catch(e) { require('fs').appendFileSync(_LOG, '02A profile write err ' + e.message + '\\n'); }\n"
       "        process.exit(0);\n"
       "      }), 150000);\n"
       "    } catch(e) { require('fs').appendFileSync(_LOG, 'inspector start err ' + e.message + '\\n'); }\n"
       "  }")
assert old in s
s = s.replace(old, new, 1)
open(w, 'w', encoding='utf-8', newline='').write(s)
print('in-worker inspector profiler installed')
