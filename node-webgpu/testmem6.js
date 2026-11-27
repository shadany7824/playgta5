const fs = require("fs");
const bytes = fs.readFileSync("E:/gta/playgta5/node-webgpu/mem64.wasm");
console.log("memory64 validate:", WebAssembly.validate(bytes));
try { const m = new WebAssembly.Memory({initial:1n, maximum:10n, address:"i64"}); console.log("MEM64_MEMORY_OK", typeof m.buffer.byteLength, m.buffer.byteLength); } catch(e){ console.log("MEM_ERR", e.message); }
