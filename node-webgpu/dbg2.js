const { Worker } = require("worker_threads");
const path = require("path");
const boot = path.join(__dirname, "worker-boot.js");
const w = new Worker("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js", {
  execArgv: ["--require", boot],
  stdout: true, stderr: true,
  env: { ...process.env, WGPU_NODE_MODULE: path.join(__dirname,"node_modules","webgpu"), WGPU_SHADER_DIR: "E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders" }
});
w.stdout.on("data", d => process.stdout.write("[wgpu-out] " + d));
w.stderr.on("data", d => process.stdout.write("[wgpu-err] " + d));
w.on("message", m => console.log("[wgpu-msg]", JSON.stringify(m).slice(0,200)));
w.on("error", e => console.log("[wgpu-error]", e.stack || e.message));
w.on("exit", c => console.log("[wgpu-exit]", c));
setTimeout(() => w.terminate(), 15000);
