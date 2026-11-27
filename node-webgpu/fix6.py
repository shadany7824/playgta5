p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
old = "  fullConsole: false,"
new = "  mainScriptUrlOrBlob: GAME_JS,\n  fullConsole: false,"
assert old in s
s = s.replace(old, new, 1)
# also set _scriptName fallback via location.href already set; add scriptDirectory help
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ADDED mainScriptUrlOrBlob')
