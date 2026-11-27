const fs=require("fs"); const bytes=fs.readFileSync("E:/gta/playgta5/node-webgpu/mem64.wasm");
console.log("validate:", WebAssembly.validate(bytes));
for (const o of [
  {initial:1, maximum:10, address:"i64"},
  {initial:1n, maximum:10n, address:"i64"},
  {initial:1, maximum:10, address:"i64", shared:true},
  {initial:1n, maximum:10n, address:"i64", shared:false},
]) {
  try { const m=new WebAssembly.Memory(o); console.log(JSON.stringify(o), "=> OK byteLength:", m.buffer.byteLength, typeof m.buffer.byteLength); }
  catch(e){ console.log(JSON.stringify(o), "=> ERR", e.message.slice(0,60)); }
}
