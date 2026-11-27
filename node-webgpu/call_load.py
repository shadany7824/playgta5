g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
# find where wasmExports/table is assigned after createWasm; add Load() call via table at index 64
old = 'var wasmExports;if(!ENVIRONMENT_IS_PTHREAD){createWasm().then(()=>run())}'
new = ('var wasmExports;if(!ENVIRONMENT_IS_PTHREAD){createWasm().then(()=>{'
       'try{const tbl=wasmExports["__indirect_function_table"];globalThis.__diag&&globalThis.__diag("TABLE len="+tbl.length);'
       'const loadFn=tbl.get(64);globalThis.__diag&&globalThis.__diag("LOAD_FN="+typeof loadFn);'
       'if(loadFn){loadFn();globalThis.__diag&&globalThis.__diag("LOAD CALLED OK");}'
       '}catch(e){globalThis.__diag&&globalThis.__diag("LOAD ERR "+(e.stack||e.message));}'
       'run()})}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED Load() direct call via table index 64')
