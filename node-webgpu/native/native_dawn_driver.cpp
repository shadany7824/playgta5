#include <node_api.h>
#include <webgpu/webgpu.h>
#include <cstdint>

static uint64_t as_ptr(napi_env env, napi_value v) {
  bool lossless = false;
  uint64_t p = 0;
  napi_get_value_bigint_uint64(env, v, &p, &lossless);
  return p;
}
static uint32_t as_u32(napi_env env, napi_value v) {
  uint32_t x = 0;
  napi_get_value_uint32(env, v, &x);
  return x;
}
static int32_t as_i32(napi_env env, napi_value v) {
  int32_t x = 0;
  napi_get_value_int32(env, v, &x);
  return x;
}
static uint64_t as_u64(napi_env env, napi_value v) {
  int64_t x = 0;
  napi_get_value_int64(env, v, &x);
  return static_cast<uint64_t>(x);
}

static napi_value SetPipeline(napi_env env, napi_callback_info info) {
  napi_value a[2]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderSetPipeline(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                   reinterpret_cast<WGPURenderPipeline>(as_ptr(env, a[1])));
  return nullptr;
}
static napi_value SetBindGroup(napi_env env, napi_callback_info info) {
  napi_value a[4]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_typedarray_info(env, a[3], nullptr, &len, &data, nullptr, nullptr);
  wgpuRenderPassEncoderSetBindGroup(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                    as_u32(env, a[1]), reinterpret_cast<WGPUBindGroup>(as_ptr(env, a[2])),
                                    static_cast<uint32_t>(len), static_cast<const uint32_t *>(data));
  return nullptr;
}
static napi_value SetVertexBuffer(napi_env env, napi_callback_info info) {
  napi_value a[4]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderSetVertexBuffer(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                       as_u32(env, a[1]), reinterpret_cast<WGPUBuffer>(as_ptr(env, a[2])),
                                       as_u64(env, a[3]), WGPU_WHOLE_SIZE);
  return nullptr;
}
static napi_value SetIndexBuffer(napi_env env, napi_callback_info info) {
  napi_value a[4]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  WGPUIndexFormat fmt = as_u32(env, a[2]) ? WGPUIndexFormat_Uint32 : WGPUIndexFormat_Uint16;
  wgpuRenderPassEncoderSetIndexBuffer(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                      reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])), fmt, as_u64(env, a[3]), WGPU_WHOLE_SIZE);
  return nullptr;
}
static napi_value Draw(napi_env env, napi_callback_info info) {
  napi_value a[5]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderDraw(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                            as_u32(env, a[1]), as_u32(env, a[2]), as_u32(env, a[3]), as_u32(env, a[4]));
  return nullptr;
}
static napi_value DrawIndexed(napi_env env, napi_callback_info info) {
  napi_value a[6]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndexed(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                   as_u32(env, a[1]), as_u32(env, a[2]), as_u32(env, a[3]),
                                   as_i32(env, a[4]), as_u32(env, a[5]));
  return nullptr;
}
static napi_value DrawIndirect(napi_env env, napi_callback_info info) {
  napi_value a[3]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndirect(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                    reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])), as_u64(env, a[2]));
  return nullptr;
}
static napi_value DrawIndexedIndirect(napi_env env, napi_callback_info info) {
  napi_value a[3]; napi_get_cb_info(env, info, nullptr, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndexedIndirect(reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])),
                                           reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])), as_u64(env, a[2]));
  return nullptr;
}

static void add(napi_env env, napi_value exports, const char *name, napi_callback fn) {
  napi_value v;
  napi_create_function(env, nullptr, 0, fn, nullptr, &v);
  napi_set_named_property(env, exports, name, v);
}
static napi_value Init(napi_env env, napi_value exports) {
  add(env, exports, "setPipeline", SetPipeline);
  add(env, exports, "setBindGroup", SetBindGroup);
  add(env, exports, "setVertexBuffer", SetVertexBuffer);
  add(env, exports, "setIndexBuffer", SetIndexBuffer);
  add(env, exports, "draw", Draw);
  add(env, exports, "drawIndexed", DrawIndexed);
  add(env, exports, "drawIndirect", DrawIndirect);
  add(env, exports, "drawIndexedIndirect", DrawIndexedIndirect);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
