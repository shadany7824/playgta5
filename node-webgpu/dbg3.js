require("worker_threads").parentPort.on("error", e=>console.error("PPERR",e));
process.on("uncaughtException", e => { console.error("UNCAUGHT", e.stack || e); });
process.on("unhandledRejection", e => { console.error("REJECTION", e && e.stack || e); });
require("E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/wgpu_worker.js");
console.log("WORKER_MODULE_LOADED");
