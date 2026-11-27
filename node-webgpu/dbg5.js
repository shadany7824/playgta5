const { Worker } = require("worker_threads");
const path = require("path");
const w = new Worker("E:/gta/playgta5/node-webgpu/minworker.js", {
  execArgv: ["--require", path.join(__dirname,"worker-boot.js")]
});
w.on("message", m => console.log("MSG", m));
w.on("error", e => console.log("ERROR", e.message));
w.on("exit", c => console.log("EXIT", c));
setTimeout(()=>w.terminate(),5000);
