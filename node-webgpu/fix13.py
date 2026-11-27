p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# limit hardwareConcurrency so pthread pool is small (28 instead of 52)
s = s.replace("globalThis.self = globalThis;", "globalThis.self = globalThis;\ntry { Object.defineProperty(globalThis.navigator, 'hardwareConcurrency', { value: 2, configurable: true }); } catch(e) {}", 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('SET hardwareConcurrency=2')
