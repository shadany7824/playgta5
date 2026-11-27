p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
# Set name to em-pthread so Emscripten detects pthread workers and skips initMemory
old = "globalThis.self = globalThis;"
new = "globalThis.self = globalThis;\n// Emscripten pthread detection: ENVIRONMENT_IS_WORKER && name == 'em-pthread'\nif (require('worker_threads').workerData && require('worker_threads').workerData.pthread) globalThis.name = 'em-pthread';"
# But workerData isn't set by game.js. Instead: detect from the fact that this worker loads game-node.js (not wgpu/io)
# Simplest: always set name=em-pthread for workers spawned by game-node.js; wgpu/io workers have their own files.
# Actually all workers use the boot shim. Set name only if the worker's script is game-node.js:
new = "globalThis.self = globalThis;\ntry { const wd = require('worker_threads'); const f = wd.workerData; if (process.argv[1] && process.argv[1].includes('game-node.js')) globalThis.name = 'em-pthread'; } catch(e) {}"
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('BOOT: set em-pthread name detection')
