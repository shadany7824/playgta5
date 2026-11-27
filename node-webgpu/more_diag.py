p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# Add periodic status dump
old = "setTimeout(() => { console.log('[harness] 60s watchdog: still running'); }, 60000).unref();"
new = """setInterval(() => {
  console.log('[harness] STATUS t=' + Math.round(process.uptime()) + 's wgpuReady=' + !!globalThis.__wgpuReady + ' engineLog=' + (() => { try { return fs.statSync('E:/gta/playgta5/node-webgpu/engine-log.txt').size; } catch(e){ return -1; } })());
}, 15000).unref();"""
assert old in s
s = s.replace(old, new, 1)
# log wgpu messages with detail
s = s.replace("  console.log('[harness] wgpu msg:', JSON.stringify(m).slice(0,150));",
              "  console.log('[harness] wgpu msg:', typeof m === 'object' ? Object.keys(m).join(',') : String(m).slice(0,80)); if (m && m.ready) globalThis.__wgpuReady = true;")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED periodic status + wgpu msg detail')
