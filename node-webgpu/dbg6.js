const { Worker } = require("worker_threads");
const path = require("path");
const w = new Worker("E:/gta/playgta5/node-webgpu/wgpu_worker_dbg.js", {
  execArgv: ["--require", path.join(__dirname,"worker-boot.js")],
  env: { ...process.env, WGPU_NODE_MODULE: path.join(__dirname,"node_modules","webgpu"), WGPU_SHADER_DIR: "E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders" },
  stdout: true, stderr: true
});
let out=""; w.stdout.on("data",d=>out+=d); w.stderr.on("data",d=>out+=d);
w.on("error",e=>console.log("ERROR",e.message));
w.on("message",m=>console.log("MSG",JSON.stringify(m).slice(0,150)));
w.on("exit",c=>{console.log("EXIT",c);console.log("OUT:",out.slice(0,2500));});
setTimeout(()=>w.terminate(),10000);
