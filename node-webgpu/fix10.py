p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
s = s.replace("process.env.NODE_OPTIONS = '--require ' + path.join(__dirname, 'worker-boot.js');\n", '')
# ensure Worker global set right before game.js load
s = s.replace("  console.log('[harness] starting game.js');",
              "  console.log('[harness] starting game.js');\n  globalThis.Worker = Worker; globalThis.self = globalThis;")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('REMOVED NODE_OPTIONS; ensured Worker global')
