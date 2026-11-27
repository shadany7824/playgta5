# STEP-1 full fix: Node branch of wasm_input_publish_js writes startMode + winW/winH + focus,
# exactly as next-steps/STEP-1-loading-screen-choice.md prescribes.
g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = ('function wasm_input_publish_js(block){'
       'if(typeof process!=="undefined"&&process.versions&&process.versions.node){'
       'const b=Number(block);globalThis.__inputBlock=b;'
       'try{Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+256,10),6,1);'
       'globalThis.__diag&&globalThis.__diag("STARTMODE written block="+b);}'
       'catch(e){globalThis.__diag&&globalThis.__diag("STARTMODE err "+e.message);}'
       'return;}'
       'postMessage({input:{memory:wasmMemory,block:Number(block)}})}')
new = ('function wasm_input_publish_js(block){'
       'if(typeof process!=="undefined"&&process.versions&&process.versions.node){'
       'const b=Number(block);globalThis.__inputBlock=b;'
       'try{'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),2,640);'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+424,4),3,360);'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+256,10),6,1);'
       'globalThis.__diag&&globalThis.__diag("INPUT block="+b+" startMode=2 win=640x360 focus=1");'
       '}catch(e){globalThis.__diag&&globalThis.__diag("INPUT err "+e.message);}'
       'return;}'
       'postMessage({input:{memory:wasmMemory,block:Number(block)}})}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('APPLIED full STEP-1 fix')
