p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'
new = 'if(worker.on){worker.on("message",(d)=>worker.__onmessage&&worker.__onmessage({data:d}));} worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'
print('found:', old in s)
s = s.replace(old, new, 1)
# after assigning worker.onmessage, also set __onmessage for our bridge
# patch: worker.onmessage=e=>{...}  -> wrap so assignment sets __onmessage
old2 = 'worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;'
# Already replaced above; now modify the assignment to set __onmessage too
s = s.replace('if(worker.on){worker.on("message",(d)=>worker.__onmessage&&worker.__onmessage({data:d}));} worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;',
              'if(worker.on){worker.on("message",(d)=>worker.__onmessage&&worker.__onmessage({data:d}));} worker.__setOM=(f)=>{worker.__onmessage=f;}; Object.defineProperty(worker,"onmessage",{get(){return worker.__onmessage;},set(f){worker.__onmessage=f;}}); worker.onmessage=e=>{var d=e.data;var cmd=d.cmd;', 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('BRIDGED worker.onmessage -> worker.on("message")')
