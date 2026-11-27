const { Worker } = require("worker_threads");
const path = require("path");
const w = new Worker("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js", {
  execArgv: ["--require", path.join(__dirname,"worker-boot.js")],
  env: { ...process.env, WGPU_NODE_MODULE: path.join(__dirname,"node_modules","webgpu"), WGPU_SHADER_DIR: "E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders" },
  stdout: true, stderr: true
});
let out = "";
w.stdout.on("data", d => { out += d.toString(); });
w.stderr.on("data", d => { out += d.toString(); });
w.on("error", e => console.log("ERROR", e.stack||e.message));
w.on("exit", c => { console.log("EXIT", c); console.log("OUTPUT:", out.slice(0,3000)); });
setTimeout(() => w.terminate(), 10000);
