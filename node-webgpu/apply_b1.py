# Apply Claude's B1 fix exactly: write startMode inside wasm_input_publish_js's Node branch.
# Rebuild from the current game-node.js (which has all real fixes) by replacing that one function.
g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = 'function wasm_input_publish_js(block){if(typeof process!=="undefined"&&process.versions&&process.versions.node)return;postMessage({input:{memory:wasmMemory,block:Number(block)}})}'
new = ('function wasm_input_publish_js(block){'
       'if(typeof process!=="undefined"&&process.versions&&process.versions.node){'
       'const b=Number(block);globalThis.__inputBlock=b;'
       'try{Atomics.store(new Int32Array(wasmMemory.buffer,b+440,1),0,2);'
       'Atomics.store(new Int32Array(wasmMemory.buffer,b+256,10),6,1);'
       'globalThis.__diag&&globalThis.__diag("STARTMODE written block="+b);}'
       'catch(e){globalThis.__diag&&globalThis.__diag("STARTMODE err "+e.message);}'
       'return;}'
       'postMessage({input:{memory:wasmMemory,block:Number(block)}})}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('APPLIED B1 startMode fix')
