# Add an OPFS + indexedDB shim to worker-boot.js for the io worker (Node has no browser File System Access API)
p = r'E:\gta\playgta5\node-webgpu\worker-boot.js'
s = open(p, encoding='utf-8').read()
shim = r'''
// ---- Node OPFS shim (browser-only File System Access API used by io_worker.js) ----
try {
  const fs = require('fs');
  const path = require('path');
  const OPFS_ROOT = 'E:/gta/playgta5/node-webgpu/opfs-store';
  fs.mkdirSync(OPFS_ROOT, { recursive: true });
  if (!globalThis.navigator) globalThis.navigator = {};
  globalThis.navigator.storage = {
    getDirectory: async () => ({
      getDirectoryHandle: async (name) => {
        const d = path.join(OPFS_ROOT, name);
        fs.mkdirSync(d, { recursive: true });
        return {
          getFileHandle: async (fname) => {
            const full = path.join(d, fname);
            return {
              createSyncAccessHandle: () => {
                let fd = fs.openSync(full, 'a+');
                return {
                  read(buf, opts) { const n = fs.readSync(fd, buf, 0, buf.length, opts.at || 0); return n; },
                  write(buf, opts) { return fs.writeSync(fd, buf, 0, buf.length, opts.at || 0); },
                  truncate(size) { fs.ftruncateSync(fd, size); },
                  getSize() { return fs.fstatSync(fd).size; },
                  flush() { fs.fsyncSync(fd); },
                  close() { fs.closeSync(fd); }
                };
              }
            };
          }
        };
      }
    })
  };
  if (typeof globalThis.indexedDB === 'undefined') {
    globalThis.indexedDB = { open: () => ({ onupgradeneeded:null, onerror:null, onsuccess:null, result:{ createObjectStore(){}, transaction(){ return { objectStore(){ return { openCursor(){ return { onsuccess:null }; } }; } }; } } }) };
  }
} catch(e) { console.error('[boot] OPFS shim error:', e.message); }
'''
anchor = "// keepalive so the worker thread does not exit while idle"
if 'Node OPFS shim' not in s:
    s = s.replace(anchor, shim + '\n' + anchor, 1)
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print('ADDED OPFS shim')
else:
    print('already has OPFS shim')
