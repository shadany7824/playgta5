const { create, globals } = require("E:/gta/playgta5/node-webgpu/node_modules/webgpu");
Object.assign(globalThis, globals);
(async () => {
  const gpu = create([]);
  const adapter = await gpu.requestAdapter({ powerPreference: "high-performance" });
  if (!adapter) { console.log("NO_ADAPTER"); return; }
  console.log("ADAPTER_OK", JSON.stringify(adapter.info || {}));
  const device = await adapter.requestDevice();
  console.log("DEVICE_OK");
})().catch(e => console.log("ERROR", e.message));
