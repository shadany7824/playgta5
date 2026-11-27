import shutil
w = r'E:\gta\playgta5\node-webgpu\wgpu_wrapper2.js'
shutil.copyfile(w, w + '.bak-02a-selftimer')
s = open(w, encoding='utf-8', errors='replace').read()
anchor = "process.on('uncaughtException', e => require('fs').appendFileSync(_LOG, 'UNCAUGHT: ' + (e.stack||e) + '\\n'));"
assert anchor in s
s = s.replace(anchor, anchor + "\nsetTimeout(() => { try { require('fs').appendFileSync(_LOG, '02A self clean exit\\n'); } catch(e){} process.exit(0); }, 150000);", 1)
open(w, 'w', encoding='utf-8', newline='').write(s)
print('wrapper self-exit at 150 s added')
