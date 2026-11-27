p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
old = """if (typeof BroadcastChannel === 'undefined') {
  globalThis.BroadcastChannel = class { constructor(){} postMessage(){} close(){} addEventListener(){} };
}"""
new = """if (typeof BroadcastChannel === 'undefined') {
  const LOG = 'E:/gta/playgta5/node-webgpu/engine-log.txt';
  globalThis.BroadcastChannel = class {
    constructor(name){ this.name = name; }
    postMessage(msg){
      try {
        const txt = (typeof msg === 'string') ? msg : JSON.stringify(msg);
        fs.appendFileSync(LOG, '[' + this.name + '] ' + txt + '\\n');
      } catch(e){}
    }
    close(){} addEventListener(){}
  };
  fs.writeFileSync('E:/gta/playgta5/node-webgpu/engine-log.txt', '');
}"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('WIRED BroadcastChannel to engine-log.txt')
