// Thin JS glue for the C++ harness (harness_native.node).
// All harness logic — env, browser shims, XHR, BroadcastChannel, ring init, startMode,
// forceHttpfs, diagnostics — lives in native C++. JS only keeps Node APIs that have no
// equivalent in the addon: worker_threads, vm, WebAssembly.instantiate, timers.
'use strict';
const path = require('path');
const { Worker } = require('worker_threads');
const fs = require('fs');
const vm = require('vm');
const h = require('./harness_native.node');

// C++ sets env + all browser shims (self, location, navigator, addEventListener,
// BroadcastChannel, XMLHttpRequest). Verified by HARNESS_CPP logs.
h.setupEnv();
h.installShims();
globalThis.performance = globalThis.performance || require('perf_hooks').performance;
globalThis.Worker = globalThis.Worker || Worker;
globalThis.__diag = (s) => h.diag(s);

const wgpuWorkerPath = process.env.WGPU_WORKER;
const ioWorkerPath = 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/io_worker.js';
let gameStarted = false;
const maybeStart = (who) => {
  console.log('[harness] worker signal:', who);
  if (gameStarted) return;
  gameStarted = true;
  console.log('[harness] starting game.js');
  globalThis._scriptName = GAME_JS;
  try { globalThis.require = require; vm.runInThisContext(fs.readFileSync(GAME_JS, 'utf8'), { filename: GAME_JS }); } catch (e) { console.error('[harness] game.js load error:', e.stack || e); }
};

const wgpu = new Worker(wgpuWorkerPath, { env: process.env, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });
wgpu.unref();
wgpu.on('error', (e) => console.error('[harness] wgpu worker error:', e.message));
wgpu.on('message', (m) => { if (m && m.ready) globalThis.__wgpuReady = true; });
const io = new Worker(ioWorkerPath, { env: process.env, workerData: { ioWorker: true }, execArgv: ['--require', path.join(__dirname, 'worker-boot.js')] });
io.unref();
io.on('error', (e) => console.error('[harness] io worker error:', e.message));
io.on('message', (m) => { if (m && m.loaded) maybeStart('io loaded'); });

// Synthetic wgpu start: C++ initializes the ring header in wasm memory.
setTimeout(() => {
  const mem = globalThis.__wasmMemory;
  if (!mem) { console.log('[harness] no wasm memory for wgpu start'); return; }
  const RING = 0x70000000;
  h.initRing(mem.buffer, RING, 33554432);
  wgpu.postMessage({ memory: mem, ring: RING, size: 33554432, dbg: 0,
                     shaderUrl: 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders', shotEvery: 0 });
  console.log('[harness] sent synthetic wgpu start, ring=0x' + RING.toString(16));
}, 2000);

io.postMessage({ init: true, base: 'http://localhost:8000/data/', noStore: false, record: false, trace: false, log: false, noHints: false, bootset: 'bootset_low.json' });

// ---- Module config (Emscripten glue — must stay JS) ----
const GAME_JS = 'E:/gta/playgta5/node-webgpu/game-node.js';
globalThis.Module = {
  arguments: ['-rootdir=/game/', '-wgpu', '-nodisplaycalibration', '-noSocialClub', '-pc:nosocialclub', '-nonetwork', '-output', '-width=1920', '-height=1080', '-forceResolution', '-textureQuality=2', '-shadowQuality=0', '-reflectionQuality=1', '-particleQuality=0', '-grassQuality=0', '-cityDensity=0', '-lodScale=0', '-frameLimit=0'],
  wgpuWorker: wgpu,
  ioWorker: io,
  wgpuShaderUrl: 'E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders',
  mainScriptUrlOrBlob: GAME_JS,
  instantiateWasm: (imports, done) => {
    const bytes = fs.readFileSync('E:/Malik/game/game-lodlive-fixed2.wasm');
    WebAssembly.instantiate(bytes, imports).then((r) => { globalThis.__wasmMemory = imports.memory; if (r.instance.exports.gta_lod_cutoff) r.instance.exports.gta_lod_cutoff.value = +(process.env.WGPU_LOD_CUTOFF || 50); done(r.instance, r.module); }).catch((e) => console.error('[harness] wasm instantiate failed:', e.message));
    return {};
  },
  fullConsole: false, remoteLog: true, wgpuShotEvery: 0,
  locateFile: (p) => path.join('E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed', p),
  onRuntimeInitialized: () => {
    console.log('[harness] runtime initialized');
    try {
      const mem = globalThis.__wasmMemory;
      if (mem && mem.buffer) h.forceHttpfs(mem.buffer, 8321672);
      else globalThis.__diag('no __wasmMemory');
    } catch (e) { globalThis.__diag('force err ' + e.message); }
  },
  onAbort: (what) => console.error('[harness] ABORT', what),
  onExit: (code) => console.log('[harness] EXIT', code),
  noInitialRun: false,
};

console.log('[harness] waiting for workers...');
setInterval(() => {
  const mem = globalThis.__wasmMemory;
  if (!mem || !mem.buffer) return;
  try { h.writeStartMode(mem.buffer, 6583436 + 440); } catch (e) { console.log('[harness] startMode write err:', e.message); }
}, 500).unref();
setInterval(() => {
  console.log('[harness] STATUS t=' + Math.round(process.uptime()) + 's wgpuReady=' + !!globalThis.__wgpuReady + ' engineLog=' + (() => { try { return fs.statSync('E:/gta/playgta5/node-webgpu/engine-log.txt').size; } catch(e){ return -1; } })());
}, 15000).unref();
