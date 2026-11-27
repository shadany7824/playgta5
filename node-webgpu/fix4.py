p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
anchor = "if (typeof BroadcastChannel === 'undefined') {"
shim = """// main-thread browser shims game.js needs
globalThis.addEventListener = globalThis.addEventListener || function(){};
globalThis.removeEventListener = globalThis.removeEventListener || function(){};
globalThis.Worker = globalThis.Worker || Worker;
globalThis.crypto = globalThis.crypto || require('crypto').webcrypto;
"""
s = s.replace(anchor, shim + anchor, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED main-thread shims')
