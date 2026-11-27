src = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js'
dst = r'E:\gta\playgta5\node-webgpu\wgpu_worker_dbg.js'
s = open(src, encoding='utf-8', errors='replace').read()
wrap = ('process.on("uncaughtException", e => require("fs").writeSync(2, "UNCAUGHT: " + (e.stack||e) + "\\n"));\n'
        'process.on("unhandledRejection", e => require("fs").writeSync(2, "REJECTION: " + ((e&&e.stack)||e) + "\\n"));\n')
s = s.replace("'use strict';", "'use strict';\n" + wrap, 1)
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('WRAPPED', len(s))
