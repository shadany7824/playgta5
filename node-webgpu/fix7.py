p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# add vm require at top
s = s.replace("const fs = require('fs');", "const fs = require('fs');\nconst vm = require('vm');", 1)
# replace require(GAME_JS) with global-scope execution
old = "  try { require(GAME_JS); } catch (e) { console.error('[harness] game.js load error:', e.stack || e); }"
new = "  try { globalThis.require = require; vm.runInThisContext(fs.readFileSync(GAME_JS, 'utf8'), { filename: GAME_JS }); } catch (e) { console.error('[harness] game.js load error:', e.stack || e); }"
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('SWITCHED to vm.runInThisContext (global scope)')
