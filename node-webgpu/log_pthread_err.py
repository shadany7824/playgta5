p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
# add global error capture for pthread workers to the msg log
old = "  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';"
new = """  const PTHLOG = 'E:/gta/playgta5/node-webgpu/pthread-msg-log.txt';
  if (isPthread) {
    process.on('uncaughtException', e => { try { require('fs').appendFileSync(PTHLOG, 'UNCAUGHT: ' + (e.stack||e) + '\\n'); } catch(x){} });
    process.on('unhandledRejection', e => { try { require('fs').appendFileSync(PTHLOG, 'REJECTION: ' + ((e&&e.stack)||e) + '\\n'); } catch(x){} });
  }"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED pthread error capture')
