p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
old = "  globalThis.Worker = Worker; globalThis.self = globalThis;"
new = "  globalThis.Worker = Worker; globalThis.self = globalThis;\n  globalThis._scriptName = GAME_JS;  // Emscripten sets this only for worker env; main thread needs it for pthread spawn"
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('SET _scriptName')
