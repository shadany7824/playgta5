const m = new WebAssembly.Memory({ initial: 49152n, maximum: 262144n, shared: true, address: "i64" });
console.log("buffer type:", m.buffer.constructor.name);
console.log("byteLength:", m.buffer.byteLength, "typeof:", typeof m.buffer.byteLength);
try { console.log("slice:", m.buffer.slice(0,4).length); } catch(e){ console.log("slice err:", e.message); }
try { console.log("resize:", typeof m.buffer.resize); } catch(e){}
