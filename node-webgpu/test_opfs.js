globalThis.navigator = {};
const fs = require('fs'), path = require('path');
const R = 'E:/gta/playgta5/node-webgpu/opfs-store';
fs.mkdirSync(R, { recursive: true });
navigator.storage = {
  getDirectory: async () => ({
    getDirectoryHandle: async (name) => {
      const d = path.join(R, name);
      fs.mkdirSync(d, { recursive: true });
      return {
        getFileHandle: async (fname) => {
          const full = path.join(d, fname);
          return {
            createSyncAccessHandle: () => {
              if (!fs.existsSync(full)) fs.writeFileSync(full, Buffer.alloc(0)); let fd = fs.openSync(full, 'r+');
              return {
                read(buf, opts) { return fs.readSync(fd, buf, 0, buf.length, opts.at || 0); },
                write(buf, opts) { return fs.writeSync(fd, buf, 0, buf.length, opts.at || 0); },
                truncate(s) { fs.ftruncateSync(fd, s); },
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
(async () => {
  const root = await navigator.storage.getDirectory();
  const dir = await root.getDirectoryHandle('gamedata');
  const s = await (await dir.getFileHandle('store.bin')).createSyncAccessHandle();
  s.truncate(0);
  s.write(new Uint8Array([1,2,3]), { at: 0 });
  console.log('SIZE', s.getSize());
  const b = new Uint8Array(3);
  s.read(b, { at: 0 });
  console.log('READ', Array.from(b));
  s.close();
})().catch(e => console.log('ERR', e.message));
