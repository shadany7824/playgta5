p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
old = """if (typeof BroadcastChannel === 'undefined') {
  globalThis.BroadcastChannel = class { constructor(){} postMessage(){} close(){} addEventListener(){} };
}"""
new = """if (typeof BroadcastChannel === 'undefined') {
  const WLOG = 'E:/gta/playgta5/node-webgpu/engine-log.txt';
  globalThis.BroadcastChannel = class {
    constructor(name){ this.name = name; }
    postMessage(msg){
      try { const txt = (typeof msg === 'string') ? msg : JSON.stringify(msg); require('fs').appendFileSync(WLOG, '[' + this.name + '] ' + txt + '\\n'); } catch(e){}
    }
    close(){} addEventListener(){}
  };
}"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('WIRED worker BroadcastChannel to engine-log.txt')
