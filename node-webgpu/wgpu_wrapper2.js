// wrapper with message logging
const _LOG = 'E:/gta/playgta5/node-webgpu/wgpu-wrapper-log.txt';
const wt = require('worker_threads');
require('fs').appendFileSync(_LOG, 'wrapper2 loaded\n');
require('E:/gta/playgta5/node-webgpu/worker-boot.js');
// Log incoming messages before the real worker's onmessage handler is set
if (wt.parentPort) wt.parentPort.on('message', (m) => {
  try { require('fs').appendFileSync(_LOG, 'MSG keys: ' + Object.keys(m||{}).join(',') + '\n'); } catch(e){}
});
process.on('uncaughtException', e => require('fs').appendFileSync(_LOG, 'UNCAUGHT: ' + (e.stack||e) + '\n'));
require('E:/gta/playgta5/node-webgpu/wgpu_worker_node.js');
