#include <node_api.h>
#include <webgpu/webgpu.h>
#include <cstdint>

static napi_value Probe(napi_env env, napi_callback_info info) {
  size_t argc = 1;
  napi_value args[1];
  if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) != napi_ok) return nullptr;
  bool lossless = false;
  uint64_t ptr = 0;
  if (napi_get_value_bigint_uint64(env, args[0], &ptr, &lossless) != napi_ok) return nullptr;
  WGPUDevice device = reinterpret_cast<WGPUDevice>(static_cast<uintptr_t>(ptr));

  WGPUBufferDescriptor desc = {};
  desc.size = 256;
  desc.usage = WGPUBufferUsage_CopyDst | WGPUBufferUsage_Uniform;
  WGPUBuffer buffer = wgpuDeviceCreateBuffer(device, &desc);
  bool ok = buffer != nullptr;
  if (buffer) {
    wgpuBufferDestroy(buffer);
    wgpuBufferRelease(buffer);
  }

  napi_value out;
  napi_get_boolean(env, ok, &out);
  return out;
}

static napi_value Init(napi_env env, napi_value exports) {
  napi_value fn;
  napi_create_function(env, nullptr, 0, Probe, nullptr, &fn);
  napi_set_named_property(env, exports, "probe", fn);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
