import shutil
p = r'E:\gta\playgta5\node-webgpu\harness.js'
shutil.copyfile(p, p + '.bak-statusmem')
s = open(p, encoding='utf-8', errors='replace').read()
old = "[harness] STATUS t=' + Math.round(process.uptime()) + 's wgpuReady=' + !!globalThis.__wgpuReady + ' engineLog=' + (() => { try { return fs.statSync('E:/gta/playgta5/node-webgpu/engine-log.txt').size; } catch(e){ return -1; } })()"
new = old + " + (() => { try { const m=globalThis.__wasmMemory; if(!m||!m.buffer) return ' mem=?'; const i32=new Int32Array(m.buffer); return ' mem: userMusicState='+Atomics.load(i32,15938320>>2)+' dbPtrLo='+Atomics.load(i32,15938288>>2)+' lookup='+new Uint8Array(m.buffer)[15938304]; } catch(e){ return ' mem err'; } })()"
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED mem status')
