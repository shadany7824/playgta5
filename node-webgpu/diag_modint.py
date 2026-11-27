g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = 'function wasm_module_int_js(name,defaultValue){globalThis.__diag&&globalThis.__diag("MODULE_INT called");const key=UTF8ToString(Number(name));if(typeof Module!=="undefined"&&Module[key]!==undefined)return Module[key]|0;if(typeof process!=="undefined"&&process.env){const env=process.env[key.toUpperCase()];if(env!==undefined)return parseInt(env,10)|0}return defaultValue}'
new = ('function wasm_module_int_js(name,defaultValue){globalThis.__diag&&globalThis.__diag("MODULE_INT entering");const key=UTF8ToString(Number(name));'
 'let val;if(typeof Module!=="undefined"&&Module[key]!==undefined){val=Module[key]|0;}else if(typeof process!=="undefined"&&process.env&&process.env[key.toUpperCase()]!==undefined){val=parseInt(process.env[key.toUpperCase()],10)|0;}else{val=defaultValue;}'
 'globalThis.__diag&&globalThis.__diag("MODULE_INT key="+key+" val="+val+" default="+defaultValue);return val}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED MODULE_INT key/val diag')
