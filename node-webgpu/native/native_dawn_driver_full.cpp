#include <node_api.h>
#include <webgpu/webgpu.h>
#include <cstdint>
#include <cstring>

static uint64_t as_ptr(napi_env env, napi_value v) {
  bool lossless = false; uint64_t p = 0;
  napi_get_value_bigint_uint64(env, v, &p, &lossless);
  return p;
}
static uint32_t as_u32(napi_env env, napi_value v) { uint32_t x = 0; napi_get_value_uint32(env, v, &x); return x; }
static int32_t as_i32(napi_env env, napi_value v) { int32_t x = 0; napi_get_value_int32(env, v, &x); return x; }
static uint64_t as_u64(napi_env env, napi_value v) { int64_t x = 0; napi_get_value_int64(env, v, &x); return static_cast<uint64_t>(x); }
static float as_f32(napi_env env, napi_value v) { double x = 0; napi_get_value_double(env, v, &x); return static_cast<float>(x); }

// Cached state of the current render pass. JS used to do all of this in doDraw() on every
// draw (~1,200 draws/frame). Owning it here removes the per-draw JS work entirely.
struct PassState {
  WGPURenderPassEncoder pass = nullptr;
  WGPURenderPipeline pl = nullptr;
  WGPUBindGroup bg[4] = {};
  uint32_t dyn[4] = {};          // first dynamic offset per group (only group 0/1 are used by the game)
  WGPUBuffer vb[16] = {};
  uint64_t vbo[16] = {};
  WGPUBuffer ib = nullptr;
  uint32_t ibFmt = 0;            // 0 = uint16, 1 = uint32
  uint64_t ibOff = 0;
  float vp[6] = {};
  uint32_t sc[4] = {};
  float bf[4] = {};
  uint32_t sref = 0;
  bool vpSet = false, scSet = false, bfSet = false, srefSet = false;
};
static PassState st;

// stats: how many redundant JS calls we absorbed
static uint64_t statSet = 0, statSkip = 0, statDraw = 0;

static WGPURenderPassEncoder passOf(napi_env env, napi_value v) {
  return reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, v));
}

static napi_value Reset(napi_env env, napi_callback_info info) {
  std::memset(&st, 0, sizeof(st));
  return nullptr;
}

static napi_value SetPipeline(napi_env env, napi_callback_info info) {
  napi_value a[2]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  auto pl = reinterpret_cast<WGPURenderPipeline>(as_ptr(env, a[1]));
  if (st.pass == p && st.pl == pl) { statSkip++; return nullptr; }
  st.pass = p; st.pl = pl; statSet++;
  wgpuRenderPassEncoderSetPipeline(p, pl);
  return nullptr;
}
static napi_value SetBindGroup(napi_env env, napi_callback_info info) {
  napi_value a[4]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  uint32_t idx = as_u32(env, a[1]);
  auto bg = reinterpret_cast<WGPUBindGroup>(as_ptr(env, a[2]));
  void *data = nullptr; size_t len = 0;
  napi_get_typedarray_info(env, a[3], nullptr, &len, &data, nullptr, nullptr);
  uint32_t d = len ? static_cast<const uint32_t *>(data)[0] : 0xffffffffu;
  if (st.pass == p && idx < 4 && st.bg[idx] == bg && st.dyn[idx] == d) { statSkip++; return nullptr; }
  st.pass = p;
  if (idx < 4) { st.bg[idx] = bg; st.dyn[idx] = d; }
  statSet++;
  wgpuRenderPassEncoderSetBindGroup(p, idx, bg, static_cast<uint32_t>(len), static_cast<const uint32_t *>(data));
  return nullptr;
}
static napi_value SetVertexBuffer(napi_env env, napi_callback_info info) {
  napi_value a[4]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  uint32_t slot = as_u32(env, a[1]);
  auto buf = reinterpret_cast<WGPUBuffer>(as_ptr(env, a[2]));
  uint64_t off = as_u64(env, a[3]);
  if (st.pass == p && slot < 16 && st.vb[slot] == buf && st.vbo[slot] == off) { statSkip++; return nullptr; }
  st.pass = p;
  if (slot < 16) { st.vb[slot] = buf; st.vbo[slot] = off; }
  statSet++;
  wgpuRenderPassEncoderSetVertexBuffer(p, slot, buf, off, WGPU_WHOLE_SIZE);
  return nullptr;
}
static napi_value SetIndexBuffer(napi_env env, napi_callback_info info) {
  napi_value a[4]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  auto buf = reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1]));
  uint32_t fmt = as_u32(env, a[2]);
  uint64_t off = as_u64(env, a[3]);
  if (st.pass == p && st.ib == buf && st.ibFmt == fmt && st.ibOff == off) { statSkip++; return nullptr; }
  st.pass = p; st.ib = buf; st.ibFmt = fmt; st.ibOff = off; statSet++;
  wgpuRenderPassEncoderSetIndexBuffer(p, buf, fmt ? WGPUIndexFormat_Uint32 : WGPUIndexFormat_Uint16, off, WGPU_WHOLE_SIZE);
  return nullptr;
}
static napi_value SetViewport(napi_env env, napi_callback_info info) {
  napi_value a[7]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  float v[6]; for (int i = 0; i < 6; i++) v[i] = as_f32(env, a[i + 1]);
  bool same = st.pass == p && st.vpSet;
  if (same) for (int i = 0; i < 6; i++) if (st.vp[i] != v[i]) { same = false; break; }
  if (same) { statSkip++; return nullptr; }
  st.pass = p; st.vpSet = true; for (int i = 0; i < 6; i++) st.vp[i] = v[i]; statSet++;
  wgpuRenderPassEncoderSetViewport(p, v[0], v[1], v[2], v[3], v[4], v[5]);
  return nullptr;
}
static napi_value SetScissor(napi_env env, napi_callback_info info) {
  napi_value a[5]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  uint32_t s[4]; for (int i = 0; i < 4; i++) s[i] = as_u32(env, a[i + 1]);
  bool same = st.pass == p && st.scSet;
  if (same) for (int i = 0; i < 4; i++) if (st.sc[i] != s[i]) { same = false; break; }
  if (same) { statSkip++; return nullptr; }
  st.pass = p; st.scSet = true; for (int i = 0; i < 4; i++) st.sc[i] = s[i]; statSet++;
  wgpuRenderPassEncoderSetScissorRect(p, s[0], s[1], s[2], s[3]);
  return nullptr;
}
static napi_value SetBlend(napi_env env, napi_callback_info info) {
  napi_value a[5]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  float f[4]; for (int i = 0; i < 4; i++) f[i] = as_f32(env, a[i + 1]);
  bool same = st.pass == p && st.bfSet;
  if (same) for (int i = 0; i < 4; i++) if (st.bf[i] != f[i]) { same = false; break; }
  if (same) { statSkip++; return nullptr; }
  st.pass = p; st.bfSet = true; for (int i = 0; i < 4; i++) st.bf[i] = f[i]; statSet++;
  WGPUColor c = { f[0], f[1], f[2], f[3] };
  wgpuRenderPassEncoderSetBlendConstant(p, &c);
  return nullptr;
}
static napi_value SetStencilRef(napi_env env, napi_callback_info info) {
  napi_value a[2]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPURenderPassEncoder p = passOf(env, a[0]);
  uint32_t r = as_u32(env, a[1]);
  if (st.pass == p && st.srefSet && st.sref == r) { statSkip++; return nullptr; }
  st.pass = p; st.srefSet = true; st.sref = r; statSet++;
  wgpuRenderPassEncoderSetStencilReference(p, r);
  return nullptr;
}
static napi_value Draw(napi_env env, napi_callback_info info) {
  napi_value a[5]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  wgpuRenderPassEncoderDraw(passOf(env, a[0]), as_u32(env, a[1]), as_u32(env, a[2]), as_u32(env, a[3]), as_u32(env, a[4]));
  statDraw++;
  return nullptr;
}
static napi_value DrawIndexed(napi_env env, napi_callback_info info) {
  napi_value a[6]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndexed(passOf(env, a[0]), as_u32(env, a[1]), as_u32(env, a[2]), as_u32(env, a[3]), as_i32(env, a[4]), as_u32(env, a[5]));
  statDraw++;
  return nullptr;
}
static napi_value DrawIndirect(napi_env env, napi_callback_info info) {
  napi_value a[3]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndirect(passOf(env, a[0]), reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])), as_u64(env, a[2]));
  statDraw++;
  return nullptr;
}
static napi_value DrawIndexedIndirect(napi_env env, napi_callback_info info) {
  napi_value a[3]; size_t argc = sizeof(a)/sizeof(a[0]); napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  wgpuRenderPassEncoderDrawIndexedIndirect(passOf(env, a[0]), reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])), as_u64(env, a[2]));
  statDraw++;
  return nullptr;
}
static napi_value Stats(napi_env env, napi_callback_info info) {
  napi_value o; napi_create_object(env, &o);
  napi_value v;
  napi_create_double(env, static_cast<double>(statSet), &v); napi_set_named_property(env, o, "set", v);
  napi_create_double(env, static_cast<double>(statSkip), &v); napi_set_named_property(env, o, "skip", v);
  napi_create_double(env, static_cast<double>(statDraw), &v); napi_set_named_property(env, o, "draw", v);
  statSet = statSkip = statDraw = 0;
  return o;
}

static void add(napi_env env, napi_value exports, const char *name, napi_callback fn) {
  napi_value v; napi_create_function(env, nullptr, 0, fn, nullptr, &v); napi_set_named_property(env, exports, name, v);
}
static napi_value Init(napi_env env, napi_value exports) {
  add(env, exports, "reset", Reset);
  add(env, exports, "setPipeline", SetPipeline);
  add(env, exports, "setBindGroup", SetBindGroup);
  add(env, exports, "setVertexBuffer", SetVertexBuffer);
  add(env, exports, "setIndexBuffer", SetIndexBuffer);
  add(env, exports, "setViewport", SetViewport);
  add(env, exports, "setScissor", SetScissor);
  add(env, exports, "setBlend", SetBlend);
  add(env, exports, "setStencilRef", SetStencilRef);
  add(env, exports, "draw", Draw);
  add(env, exports, "drawIndexed", DrawIndexed);
  add(env, exports, "drawIndirect", DrawIndirect);
  add(env, exports, "drawIndexedIndirect", DrawIndexedIndirect);
  add(env, exports, "stats", Stats);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)

