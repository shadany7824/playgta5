import shutil
p = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(p, p + '.bak-memstate')
s = open(p, encoding='utf-8', errors='replace').read()
anchor = 'globalThis.__diag&&globalThis.__diag("INPUT block="+b+" startMode=2 win=640x360 focus=1");'
watch = ('if(!globalThis.__memWatch){globalThis.__memWatch=setInterval(()=>{try{const i32=new Int32Array(wasmMemory.buffer);'
         'globalThis.__diag&&globalThis.__diag("MEMSTATE userMusic="+Atomics.load(i32,15938320>>2)+" dbPtr="+Atomics.load(i32,15938288>>2)+" lookup="+new Uint8Array(wasmMemory.buffer)[15938304]);'
         '}catch(e){globalThis.__diag&&globalThis.__diag("MEMSTATE err "+e.message);}},10000);}')
print('found:', anchor in s)
s = s.replace(anchor, anchor + watch, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED MEMSTATE watch')
