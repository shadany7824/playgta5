const m = new WebAssembly.Memory({initial:49152, maximum:262144, shared:true, address:"i64"});
console.log("MEM_OK byteLength:", m.buffer.byteLength, "type:", typeof m.buffer.byteLength);
const a = new Int8Array(m.buffer); console.log("TYPED_ARRAY_OK", a.length);
