const fs = require("fs");
const bytes = fs.readFileSync("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/game.wasm");
console.log("Node", process.version, "V8", process.versions.v8);
try {
  WebAssembly.validate(bytes);
  console.log("VALIDATE: true");
} catch(e) { console.log("VALIDATE ERR:", e.message); }
(async () => {
  try {
    const r = await WebAssembly.instantiate(bytes, {});
    console.log("INSTANTIATE OK");
  } catch(e) { console.log("INSTANTIATE ERR:", e.message.slice(0,150)); }
})();
