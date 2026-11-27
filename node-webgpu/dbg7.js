// Run wgpu worker code in main thread with a fake parentPort to see the real error.
const fs = require('fs');
process.on('uncaughtException', e => { console.log('UNCAUGHT:', e.stack || e); });
process.on('unhandledRejection', e => { console.log('REJECTION:', e && e.stack || e); });
// emulate worker env
globalThis.self = globalThis;
globalThis.location = { search: '', origin: 'http://localhost:8000' };
globalThis.postMessage = (m) => console.log('POSTMSG', JSON.stringify(m).slice(0,100));
globalThis.addEventListener = () => {};
process.env.WGPU_NODE_MODULE = 'E:/gta/playgta5/node-webgpu/node_modules/webgpu';
process.env.WGPU_SHADER_DIR = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
try {
  require('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js');
  console.log('REQUIRED OK');
} catch (e) {
  console.log('REQUIRE THREW:', e.stack || e);
}
setTimeout(() => console.log('STILL ALIVE'), 3000);
