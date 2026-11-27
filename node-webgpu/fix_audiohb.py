import shutil
p = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(p, p + '.bak-audiohb')
s = open(p, encoding='utf-8', errors='replace').read()
old = ('globalThis.__audioTimer=setInterval(()=>{try{const read=Atomics.load(hdr,1),write=Atomics.load(hdr,0);'
       'const avail=(write-read)>>>0;if(!avail)return;Atomics.store(hdr,1,(read+avail)|0);Atomics.add(hdr,3,1);}catch(e){}},10);')
new = ('globalThis.__audioTimer=setInterval(()=>{try{const now=Date.now();if(globalThis.__audioLast===undefined)globalThis.__audioLast=now;'
       'const dt=now-globalThis.__audioLast;globalThis.__audioLast=now;let ticks=Math.round(dt*375/1000);if(ticks<1)ticks=1;'
       'const read=Atomics.load(hdr,1),write=Atomics.load(hdr,0);const avail=(write-read)>>>0;'
       'if(avail)Atomics.store(hdr,1,(read+avail)|0);Atomics.add(hdr,3,ticks);}catch(e){}},10);')
print('found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('PATCHED audio heartbeat clock')
