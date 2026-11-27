import shutil

boot = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
shutil.copyfile(boot, boot + '.bak-heartbeat')
s = open(boot, encoding='utf-8', errors='replace').read()
anchor = "// keepalive so the worker thread does not exit while idle"
add = '''// heartbeat + proxy accounting for pthread workers
try {
  const wt = require('worker_threads');
  const isP = wt.workerData && wt.workerData.pthread;
  if (isP) {
    const HB = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
    let n = 0;
    setInterval(() => { n++; try { require('fs').appendFileSync(HB, 'ALIVE tid=' + wt.threadId + ' n=' + n + '\\n'); } catch(e){} }, 10000);
  }
} catch(e){}

'''
assert anchor in s
s = s.replace(anchor, add + anchor, 1)
open(boot, 'w', encoding='utf-8', newline='').write(s)
print('worker-boot patched')

g = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(g, g + '.bak-proxycnt')
t = open(g, encoding='utf-8', errors='replace').read()
old = 'proxyToMainThread=(funcIndex,emAsmAddr,proxyMode,...callArgs)=>{'
new = ('proxyToMainThread=(funcIndex,emAsmAddr,proxyMode,...callArgs)=>{'
       'if(ENVIRONMENT_IS_PTHREAD){globalThis.__pc=globalThis.__pc||{};globalThis.__pc[funcIndex]=(globalThis.__pc[funcIndex]||0)+1;'
       'if(!globalThis.__pct){const tid=(()=>{try{return require("worker_threads").threadId}catch(e){return 0}})();'
       'globalThis.__pct=setInterval(()=>{const c=globalThis.__pc;globalThis.__pc={};const ks=Object.keys(c);'
       'if(ks.length){let out="PROXY tid="+tid;for(const k of ks)out+=" idx"+k+"="+c[k];'
       'try{require("fs").appendFileSync("E:/gta/playgta5/node-webgpu/pthread-msg-log.txt",out+"\\n")}catch(e){}}},10000);}}')
assert old in t
t = t.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(t)
print('game-node proxy counting patched')
