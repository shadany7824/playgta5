# Create a wrapper worker that applies browser shims, then loads the real wgpu_worker.js
wrapper = r'E:\gta\playgta5\node-webgpu\wgpu_worker_wrapped.js'
content = """// wrapper: apply Node/browser shims then load the real wgpu worker
require('E:/gta/playgta5/node-webgpu/worker-boot.js');
require('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js');
"""
open(wrapper, 'w', encoding='utf-8', newline='').write(content)
print('WROTE wrapper')

# Point WGPU_WORKER env to the wrapper in harness
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
s = s.replace("process.env.WGPU_WORKER = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js';",
              "process.env.WGPU_WORKER = 'E:/gta/playgta5/node-webgpu/wgpu_worker_wrapped.js';")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('HARNESS WGPU_WORKER -> wrapper')
