const vm=require("vm"); const {Worker}=require("worker_threads");
globalThis.Worker = Worker;
globalThis.foo = 42;
try { console.log(vm.runInThisContext("typeof Worker + ' ' + typeof foo")); } catch(e){ console.log("ERR",e.message); }
