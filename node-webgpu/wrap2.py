p = r'E:\gta\playgta5\node-webgpu\wgpu_worker_dbg.js'
s = open(p, encoding='utf-8', errors='replace').read()
handler = 'process.on("uncaughtException",e=>require("fs").writeSync(2,"UNCAUGHT: "+(e.stack||e)+"\\n"));\n'
if 'UNCAUGHT:' not in s[:200]:
    s = handler + s
    open(p, 'w', encoding='utf-8', newline='').write(s)
print('HANDLER AT TOP, len', len(s))
