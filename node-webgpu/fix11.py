p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
add = '''
// pthread workers: set Module so game.js's `var Module` picks it up via global scope
if (typeof globalThis.Module === 'undefined') {
  globalThis.Module = {};
}
globalThis.Module.mainScriptUrlOrBlob = 'E:/gta/playgta5/node-webgpu/game-node.js';
globalThis.Module.wgpuShaderUrl = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
'''
if 'mainScriptUrlOrBlob' not in s:
    s = s.replace("globalThis.self = globalThis;", "globalThis.self = globalThis;\n" + add, 1)
    open(p, 'w', encoding='utf-8', newline='').write(s)
print('BOOT: added Module.mainScriptUrlOrBlob shim')
