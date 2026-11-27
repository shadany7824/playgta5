try {
  const m = new WebAssembly.Memory({ initial: BigInt(49152), maximum: 262144n, shared: true, address: "i64" });
  console.log("MEMORY_OK byteLength:", m.buffer.byteLength, typeof m.buffer.byteLength);
  const a = new Int8Array(m.buffer);
  console.log("INT8ARRAY_OK", a.length);
} catch(e) { console.log("ERROR:", e.message, e.stack.split("\n")[0]); }
