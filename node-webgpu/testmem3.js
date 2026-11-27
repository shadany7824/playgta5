const variants = [
  {name:"number-num", o:{initial:49152, maximum:262144, shared:true, address:"i64"}},
  {name:"bigint-num", o:{initial:49152n, maximum:262144, shared:true, address:"i64"}},
  {name:"num-bigint", o:{initial:49152, maximum:262144n, shared:true, address:"i64"}},
  {name:"bigint-noaddr", o:{initial:49152n, maximum:262144n, shared:true}},
  {name:"number-noaddr", o:{initial:49152, maximum:262144, shared:true}},
];
for (const v of variants) {
  try { const m = new WebAssembly.Memory(v.o); console.log(v.name, "OK", typeof m.buffer.byteLength, m.buffer.byteLength); }
  catch(e) { console.log(v.name, "ERR", e.message.slice(0,70)); }
}
