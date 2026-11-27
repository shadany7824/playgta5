// minimal memory64 module: (module (memory (export "m") 1 10 i64))
const bytes = new Uint8Array([0,97,115,109,1,0,0,0, 5,5,1, 0x0c, 1, 1, 10, 0,97,115,6]);
try { console.log("memory64 validate:", WebAssembly.validate(bytes)); } catch(e){ console.log("validate err", e.message); }
console.log("Node:", process.version);
console.log("address i64 attempt with big page sizes");
for (const max of [65536, 100000, 131072, 262144]) {
  try { const m = new WebAssembly.Memory({initial:1, maximum:max, shared:true}); console.log(max,"OK"); } catch(e){ console.log(max,"ERR",e.message.slice(0,60)); }
}
