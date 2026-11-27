p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
s = s.replace("const GAME_JS = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.js';",
              "const GAME_JS = 'E:/gta/playgta5/node-webgpu/game-node.js';")
# pthread workers need the boot shim too: set execArgv via NODE_OPTIONS-style? For game.js spawned Workers,
# they inherit execArgv from parent only if set; use env NODE_OPTIONS instead
s = s.replace("const vm = require('vm');", "const vm = require('vm');\nprocess.env.NODE_OPTIONS = '--require ' + path.join(__dirname, 'worker-boot.js');")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('HARNESS: GAME_JS -> game-node.js, NODE_OPTIONS preload set')
