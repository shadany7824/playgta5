p = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = 'worker=new Worker(pthreadMainJs,{name:"em-pthread"})'
new = 'worker=new Worker(pthreadMainJs,{name:"em-pthread",execArgv:["--require","E:/gta/playgta5/node-webgpu/worker-boot.js"]})'
print('old found:', old in s)
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('PATCHED pthread spawn with boot shim')
