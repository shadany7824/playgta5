wrapper = r'E:\gta\playgta5\node-webgpu\wgpu_worker_wrapped.js'
content = """// wrapper: apply Node/browser shims then load the real wgpu worker
const _LOG = 'E:/gta/playgta5/node-webgpu/wgpu-wrapper-log.txt';
require('fs').appendFileSync(_LOG, 'wrapper starting\\n');
process.on('uncaughtException', e => require('fs').appendFileSync(_LOG, 'UNCAUGHT: ' + (e.stack||e) + '\\n'));
process.on('unhandledRejection', e => require('fs').appendFileSync(_LOG, 'REJECTION: ' + ((e&&e.stack)||e) + '\\n'));
try {
  require('E:/gta/playgta5/node-webgpu/worker-boot.js');
  require('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js');
  require('fs').appendFileSync(_LOG, 'wrapper loaded real worker\\n');
} catch(e) { require('fs').appendFileSync(_LOG, 'LOAD ERR: ' + (e.stack||e) + '\\n'); }
"""
open(wrapper, 'w', encoding='utf-8', newline='').write(content)
print('WROTE wrapper with logging')
