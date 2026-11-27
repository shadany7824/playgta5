for (const o of [
  {initial:49152, maximum:262144, address:"i64"},
  {initial:49152, address:"i64"},
  {initial:49152, maximum:65536, shared:true, address:"i64"},
]) {
  try { const m=new WebAssembly.Memory(o); console.log("OK", JSON.stringify(o), m.buffer.byteLength); }
  catch(e){ console.log("ERR", JSON.stringify(o), e.message.slice(0,70)); }
}
