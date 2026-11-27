const { Worker } = require("worker_threads");
const path = require("path");
const boot = path.join(__dirname, "worker-boot.js");
function test(file, initMsg, label) {
  const w = new Worker(file, { execArgv: ["--require", boot], env: { ...process.env, WGPU_NODE_MODULE: path.join(__dirname,"node_modules","webgpu"), WGPU_SHADER_DIR: "E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders" } });
  w.on("message", m => console.log(label, "MSG", JSON.stringify(m).slice(0,150)));
  w.on("error", e => console.log(label, "ERROR", e.message));
  w.on("exit", c => console.log(label, "EXIT", c));
  if (initMsg) w.postMessage(initMsg);
  setTimeout(() => w.terminate(), 12000);
}
test("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/io_worker.js", { init:true, base:"http://localhost:8000/data/", noStore:false, bootset:"bootset_low.json" }, "IO:");
test("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js", null, "WGPU:");
