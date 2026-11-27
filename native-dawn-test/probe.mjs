import { createGPU } from 'webgpu-node';
import { deviceHandle } from 'native-dawn';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const addon = require('./native_dawn_probe.node');

const gpu = createGPU(['enable-dawn-features=disable_symbol_renaming']);
const adapter = await gpu.requestAdapter();
if (!adapter) throw new Error('no adapter');
const device = await adapter.requestDevice();
const handle = deviceHandle(device);
console.log('deviceHandle', handle);
console.log('native buffer ok', addon.probe(handle));
device.destroy();
