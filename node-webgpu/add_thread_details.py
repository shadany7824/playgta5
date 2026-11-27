import shutil

g = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(g, g + '.bak-tablelog')
s = open(g, encoding='utf-8', errors='replace').read()
old = '__indirect_function_table=wasmTable=wasmExports["__indirect_function_table"]}'
new = '__indirect_function_table=wasmTable=wasmExports["__indirect_function_table"];globalThis.__wasmTable=wasmTable;}'
assert old in s
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('game-node table exposed')

b = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
shutil.copyfile(b, b + '.bak-tablelog')
t = open(b, encoding='utf-8', errors='replace').read()
old2 = "if (isPthread) { try { require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' keys=' + Object.keys(data||{}).join(',') + '\\n'); } catch(e){} }"
new2 = ("if (isPthread) { try { let extra=''; if(data && data.cmd===2){ globalThis.__lastStartRoutine=data.start_routine; "
        "const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; extra=' sr='+data.start_routine+' arg='+data.arg+' tlen='+tl; } "
        "require('fs').appendFileSync(PTHLOG, 'PTH MSG cmd=' + (data&&data.cmd) + ' tid=' + require('worker_threads').threadId + extra + '\\n'); } catch(e){} }")
assert old2 in t, 'pth msg line not found'
t = t.replace(old2, new2, 1)
old3 = "process.on('uncaughtException', e => { try { require('fs').appendFileSync(PTHLOG, 'UNCAUGHT: ' + (e.stack||e) + '\\n'); } catch(x){} });"
new3 = ("process.on('uncaughtException', e => { try { const tl=(globalThis.__wasmTable&&globalThis.__wasmTable.length)||-1; "
        "require('fs').appendFileSync(PTHLOG, 'UNCAUGHT tid=' + require('worker_threads').threadId + ' tlen=' + tl + ' sr=' + globalThis.__lastStartRoutine + ' :: ' + (e.stack||e) + '\\n'); } catch(x){} });")
assert old3 in t
t = t.replace(old3, new3, 1)
open(b, 'w', encoding='utf-8', newline='').write(t)
print('worker-boot thread details patched')
