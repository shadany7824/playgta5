const bytes = new Uint8Array([0,97,115,109,1,0,0,0, 5,5,1, 0x0c,1,1,10,0,97,115]);
console.log("memory64 validate:", WebAssembly.validate(bytes));
