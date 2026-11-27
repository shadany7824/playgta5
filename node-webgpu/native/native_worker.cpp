#include <node_api.h>
#include <webgpu/webgpu.h>
#include <cstdint>
#include <cstring>
#include <unordered_map>
#include <cstdio>

static uint32_t *U = nullptr;   // wasm memory as uint32 (command stream)
static float    *F = nullptr;  // wasm memory as float32
static size_t    g_memWords = 0;

// ---- N-API bigint/u32 helpers (for WebGPU handles) -------------------------------------------------------
static uint64_t as_ptr(napi_env env, napi_value v) {
  napi_valuetype vt; napi_typeof(env, v, &vt);
  if (vt == napi_bigint) { bool lossless = false; uint64_t p = 0; napi_get_value_bigint_uint64(env, v, &p, &lossless); return p; }
  double d = 0; napi_get_value_double(env, v, &d);
  return static_cast<uint64_t>(d);
}
static uint32_t as_u32v(napi_env env, napi_value v) { uint32_t x = 0; napi_get_value_uint32(env, v, &x); return x; }

// ---- object registry: game object id -> WebGPU handle + byte size ---------------------------------------
struct VbReq { uint32_t slot = 0, instance = 0, stride = 0, last = 0; };
struct GpuObj {
  WGPUBuffer buf = nullptr; WGPUBindGroup bg = nullptr; WGPURenderPipeline pl = nullptr; uint64_t bytes = 0;
  VbReq req[16]; uint32_t nreq = 0;
  uint32_t slots[16]; uint32_t slotCls[16]; uint32_t nslots = 0;
};
static std::unordered_map<uint32_t, GpuObj> g_objs;
static uint64_t g_regPipeCount = 0;
static GpuObj &obj(uint32_t id) { return g_objs[id]; }
static napi_value RegBuffer(napi_env env, napi_callback_info info) {
  size_t argc = 3; napi_value a[3]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  int64_t bytes = 0; napi_get_value_int64(env, a[2], &bytes);
  GpuObj &o = obj(as_u32v(env, a[0])); o.buf = reinterpret_cast<WGPUBuffer>(as_ptr(env, a[1])); o.bytes = (uint64_t)bytes;
  return nullptr;
}
static napi_value RegBG(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  GpuObj &o = obj(as_u32v(env, a[0])); o.bg = reinterpret_cast<WGPUBindGroup>(as_ptr(env, a[1]));
  return nullptr;
}
static napi_value RegPipe(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  uint32_t regid = as_u32v(env, a[0]); uint64_t h = as_ptr(env, a[1]);
  GpuObj &o = obj(regid); o.pl = reinterpret_cast<WGPURenderPipeline>(h); g_regPipeCount++;
  (void)h;
  return nullptr;
}
// regLayoutSlots(id, flat [slot,cls,...]) and regVbReq(id, flat [slot,instance,stride,last,...])
static napi_value RegLayout(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_typedarray_info(env, a[1], nullptr, &len, &data, nullptr, nullptr);
  uint32_t *v = static_cast<uint32_t*>(data);
  GpuObj &o = obj(as_u32v(env, a[0]));
  o.nslots = 0;
  for (size_t i = 0; i + 1 < len && o.nslots < 16; i += 2) { o.slots[o.nslots] = v[i]; o.slotCls[o.nslots] = v[i + 1]; o.nslots++; }
  return nullptr;
}
static napi_value RegVbReq(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_typedarray_info(env, a[1], nullptr, &len, &data, nullptr, nullptr);
  uint32_t *v = static_cast<uint32_t*>(data);
  GpuObj &o = obj(as_u32v(env, a[0]));
  o.nreq = 0;
  for (size_t i = 0; i + 3 < len && o.nreq < 16; i += 4) {
    o.req[o.nreq].slot = v[i]; o.req[o.nreq].instance = v[i+1]; o.req[o.nreq].stride = v[i+2]; o.req[o.nreq].last = v[i+3]; o.nreq++;
  }
  return nullptr;
}
static napi_value DelObj(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_objs.erase(as_u32v(env, a[0]));
  return nullptr;
}

// ---- render pass + zeros buffer --------------------------------------------------------------------------
static WGPURenderPassEncoder g_pass = nullptr;
static WGPUBuffer g_zero = nullptr;
static uint64_t g_zeroBytes = 0;
static uint64_t stClear = 0, stCopyBuf = 0, stCopyTex = 0, stDispatch = 0, stOccl = 0;
static uint32_t g_passW = 0, g_passH = 0;
static WGPUQueue g_queue = nullptr;
static WGPUCommandEncoder g_encoder = nullptr;
static napi_value SetQueue(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_queue = reinterpret_cast<WGPUQueue>(as_ptr(env, a[0])); return nullptr;
}
static napi_value SetEncoder(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_encoder = reinterpret_cast<WGPUCommandEncoder>(as_ptr(env, a[0])); return nullptr;
}
// clearRT(view, r,g,b,a): one clear render pass, no JS WebGPU calls
static napi_value ClearColor(napi_env env, napi_callback_info info) {
  size_t argc = 5; napi_value a[5]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPUTextureView view = reinterpret_cast<WGPUTextureView>(as_ptr(env, a[0]));
  if (!view || !g_encoder) return nullptr;
  WGPURenderPassColorAttachment c = {};
  c.view = view; c.loadOp = WGPULoadOp_Clear; c.storeOp = WGPUStoreOp_Store;
  double r=0,g=0,b=0,al=0; napi_get_value_double(env,a[1],&r); napi_get_value_double(env,a[2],&g);
  napi_get_value_double(env,a[3],&b); napi_get_value_double(env,a[4],&al);
  c.clearValue = { (float)r,(float)g,(float)b,(float)al };
  WGPURenderPassDescriptor d = {};
  d.colorAttachmentCount = 1; d.colorAttachments = &c;
  WGPURenderPassEncoder rp = wgpuCommandEncoderBeginRenderPass(g_encoder, &d);
  wgpuRenderPassEncoderEnd(rp);
  stClear++;
  return nullptr;
}
// clearDS(view, flags, depth, stencil, hasStencil)
static napi_value ClearDepth(napi_env env, napi_callback_info info) {
  size_t argc = 5; napi_value a[5]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPUTextureView view = reinterpret_cast<WGPUTextureView>(as_ptr(env, a[0]));
  if (!view || !g_encoder) return nullptr;
  uint32_t flags = as_u32v(env, a[1]);
  double dep=0; napi_get_value_double(env,a[2],&dep);
  uint32_t stencil = as_u32v(env, a[3]);
  uint32_t hasStencil = as_u32v(env, a[4]);
  WGPURenderPassDepthStencilAttachment ds = {};
  ds.view = view;
  ds.depthLoadOp = (flags & 1) ? WGPULoadOp_Clear : WGPULoadOp_Load;
  ds.depthStoreOp = WGPUStoreOp_Store; ds.depthClearValue = (float)dep;
  if (hasStencil) {
    ds.stencilLoadOp = (flags & 2) ? WGPULoadOp_Clear : WGPULoadOp_Load;
    ds.stencilStoreOp = WGPUStoreOp_Store; ds.stencilClearValue = stencil;
  }
  WGPURenderPassDescriptor d = {};
  d.depthStencilAttachment = &ds;
  WGPURenderPassEncoder rp = wgpuCommandEncoderBeginRenderPass(g_encoder, &d);
  wgpuRenderPassEncoderEnd(rp);
  stClear++;
  return nullptr;
}
static std::unordered_map<uint32_t, WGPUTexture> g_tex;
static napi_value RegTexture(napi_env env, napi_callback_info info) {
  size_t argc = 3; napi_value a[3]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  int64_t bytes = 0; napi_get_value_int64(env, a[2], &bytes);
  g_tex[as_u32v(env, a[0])] = reinterpret_cast<WGPUTexture>(as_ptr(env, a[1]));
  obj(as_u32v(env, a[0])).bytes = (uint64_t)bytes;
  return nullptr;
}

// uploadBuffer(id, offset, size, dataOff): direct queue.writeBuffer from wasm memory (no JS subarray)
static napi_value UploadBuffer(napi_env env, napi_callback_info info) {
  size_t argc = 4; napi_value a[4]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  uint32_t id = as_u32v(env, a[0]), offset = as_u32v(env, a[1]), size = as_u32v(env, a[2]), dataOff = as_u32v(env, a[3]);
  GpuObj *o = &g_objs[id];
  if (!o->buf || !g_queue) return nullptr;
  const uint8_t *src = reinterpret_cast<const uint8_t*>(U) + dataOff;
  uint32_t n = size & ~3u;
  if (n) wgpuQueueWriteBuffer(g_queue, o->buf, offset, src, n);
  if (size & 3u) {
    uint8_t tail[4] = {0,0,0,0};
    std::memcpy(tail, src + n, size & 3u);
    wgpuQueueWriteBuffer(g_queue, o->buf, offset + n, tail, 4);
  }
  return nullptr;
}

// uploadTexture(id, mip, slice, x, y, z, w, h, d, bpr, rows, size, dataOff): direct queue.writeTexture
static napi_value UploadTexture(napi_env env, napi_callback_info info) {
  size_t argc = 14; napi_value a[14]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  uint32_t v[14]; for (int i = 0; i < 14; i++) v[i] = as_u32v(env, a[i]);
  // v: id, mip, slice, x, y, z, w, h, d, bpr, rows, size, dataOff, originZ(already three?z:slice)
  WGPUTexture tex = g_tex[v[0]];
  if (!tex || !g_queue) return nullptr;
  WGPUTexelCopyTextureInfo dst = {};
  dst.texture = tex; dst.mipLevel = v[1];
  dst.origin.x = v[3]; dst.origin.y = v[4]; dst.origin.z = v[13];
  WGPUExtent3D ext = { v[6], v[7], v[8] };
  WGPUTexelCopyBufferLayout layout = {};
  layout.bytesPerRow = v[9]; layout.rowsPerImage = v[10];
  const void *src = reinterpret_cast<const uint8_t*>(U) + v[12];
  wgpuQueueWriteTexture(g_queue, &dst, src, v[11], &layout, &ext);
  return nullptr;
}
static napi_value SetPass(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_pass = reinterpret_cast<WGPURenderPassEncoder>(as_ptr(env, a[0])); return nullptr;
}
static napi_value SetZero(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_zero = reinterpret_cast<WGPUBuffer>(as_ptr(env, a[0]));
  int64_t z = 0; napi_get_value_int64(env, a[1], &z); g_zeroBytes = (uint64_t)z;
  return nullptr;
}
static napi_value SetPassInfo(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_passW = as_u32v(env, a[0]); g_passH = as_u32v(env, a[1]);
  return nullptr;
}

// ============================================================================
// native_worker.cpp — Stage 1 of the GTA worker C++ port.
// Owns the RAGE pipeline STATE and processes the pure state opcodes of the
// command ring directly from wasm memory. Complex ops (create/upload/draw/
// present/etc) are dispatched back to JS through a registered callback.
// The state is mirrored into a flat Int32/Float32 shared buffer that JS reads
// so doDraw() needs no per-state N-API call.
// ============================================================================


// --- flat state mirror (shared with JS) -------------------------------------
// Word layout (uint32 index; floats share the same indices via F[]):
//   0  shader[0]   1  shader[1]   2  shader[2]   3  layout   4  topo
//   5..20 vb slots: 16 slots x 3 words (buf, stride, offset) -> slot k @ 5+k*3
//   53 ib.buf  54 ib.fmt  55 ib.offset
//   56 cb buf/first/num: 3 stages x 16 slots x 3 words = 144 words @ 56..199
//   200 srv: 3 stages x 128 = 384 words @ 200..583
//   584 uav: 3 x 8 = 24 words @ 584..607
//   608 smp: 3 x 16 = 48 words @ 608..655
//   656 rt: 8 x 4 (tex,mip,slice,fmt) = 32 words @ 656..687
//   688 ds: tex,mip,slice,fmt,flags @ 688..692
//   693 blend.id  694 blend.mask  695 factor bits x4 @ 695..698
//   699 dss.id  700 dss.ref  701 rs
//   702 viewport0 floats x6 @ 702..707  708 viewport count
//   710 scissor0 ints x4 @ 710..713  714 scissor count
//   720 pdirty (0/1)
#define W_SHADER0 0
#define W_LAYOUT  3
#define W_TOPO    4
#define W_VB      5
#define W_IB      53
#define W_CB      56
#define W_SRV     200
#define W_UAV     584
#define W_SMP     608
#define W_RT      656
#define W_DS      688
#define W_BLENDID 693
#define W_BLENDR  695
#define W_DSSID   699
#define W_DSSREF  700
#define W_RS      701
#define W_VP      702
#define W_VPN     708
#define W_SC      710
#define W_SCN     714
#define W_PDIRTY  720
static uint32_t *S = nullptr;   // shared state buffer (uint32 view)
static float    *SF = nullptr;  // shared state buffer (float view)
static size_t    Swords = 0;

static void reset_state() {
  if (!S) return;
  for (size_t i = 0; i < Swords; i++) S[i] = 0;
  S[W_SHADER0] = S[W_SHADER0 + 1] = S[W_SHADER0 + 2] = 0;
  S[W_LAYOUT] = 0; S[W_TOPO] = 4;
  S[W_DSSREF] = 0; S[W_RS] = 0;
  SF[W_BLENDR] = SF[W_BLENDR + 1] = SF[W_BLENDR + 2] = SF[W_BLENDR + 3] = 1.0f;
  S[W_BLENDR + 0] = 0x3f800000u; S[W_BLENDR + 1] = 0x3f800000u;
  S[W_BLENDR + 2] = 0x3f800000u; S[W_BLENDR + 3] = 0x3f800000u;
  S[W_BLENDID] = 0; S[W_BLENDR - 1] = 0xffffffffu; // blend mask at 694
  S[W_PDIRTY] = 1;
}

static napi_value Attach(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  // arg0: wasm memory ArrayBuffer (for U/F), arg1: state ArrayBuffer (for S/SF)
  void *md = nullptr, *sd = nullptr; size_t ml = 0, sl = 0;
  napi_get_arraybuffer_info(env, a[0], &md, &ml);
  napi_get_arraybuffer_info(env, a[1], &sd, &sl);
  U = static_cast<uint32_t*>(md); F = static_cast<float*>(md); g_memWords = ml / 4;
  if (S != static_cast<uint32_t*>(sd)) { S = static_cast<uint32_t*>(sd); SF = static_cast<float*>(sd); Swords = sl / 4; reset_state(); }
  return nullptr;
}

// --- JS callback for complex ops -------------------------------------------
static napi_ref g_cbRef = nullptr;
static napi_value SetCallback(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  if (g_cbRef) napi_delete_reference(env, g_cbRef);
  napi_create_reference(env, a[0], 1, &g_cbRef);
  return nullptr;
}

// ---- per-pass WebGPU state cache (owned by C++, dedup across draws) ----------
struct Cache {
  WGPURenderPipeline pl = nullptr;
  WGPUBindGroup bg[2] = {}; uint32_t dyn[2] = {};
  WGPUBuffer vb[16] = {}; uint64_t vbo[16] = {};
  WGPUBuffer ib = nullptr; uint32_t ibFmt = 0; uint64_t ibOff = 0;
  float vp[6] = {}; uint32_t sc[4] = {}; float bf[4] = {}; uint32_t sref = 0;
  bool vpSet = false, scSet = false, bfSet = false, srefSet = false;
};
static Cache st;
static uint64_t stSet = 0, stSkip = 0, stDraw = 0, stClamp = 0, stSkipDraw = 0;
static uint64_t skipNoPl = 0, skipNoIb = 0, skipZero = 0, skipNoArgs = 0;


static inline void CSetPipe(WGPURenderPipeline pl) {
  if (st.pl == pl) { stSkip++; return; }
  st.pl = pl; stSet++; wgpuRenderPassEncoderSetPipeline(g_pass, pl);
}
static inline void CSetBG(uint32_t i, WGPUBindGroup bg, uint32_t dyn) {
  if (i < 2 && st.bg[i] == bg && st.dyn[i] == dyn) { stSkip++; return; }
  if (i < 2) { st.bg[i] = bg; st.dyn[i] = dyn; }
  stSet++; uint32_t d[1] = { dyn };
  wgpuRenderPassEncoderSetBindGroup(g_pass, i, bg, bg ? 1u : 0u, bg ? d : nullptr);
}
static inline void CSetVB(uint32_t slot, WGPUBuffer buf, uint64_t off) {
  if (slot < 16 && st.vb[slot] == buf && st.vbo[slot] == off) { stSkip++; return; }
  if (slot < 16) { st.vb[slot] = buf; st.vbo[slot] = off; }
  stSet++; wgpuRenderPassEncoderSetVertexBuffer(g_pass, slot, buf, off, WGPU_WHOLE_SIZE);
}
static inline void CSetIB(WGPUBuffer buf, uint32_t fmt, uint64_t off) {
  if (st.ib == buf && st.ibFmt == fmt && st.ibOff == off) { stSkip++; return; }
  st.ib = buf; st.ibFmt = fmt; st.ibOff = off; stSet++;
  wgpuRenderPassEncoderSetIndexBuffer(g_pass, buf, fmt ? WGPUIndexFormat_Uint32 : WGPUIndexFormat_Uint16, off, WGPU_WHOLE_SIZE);
}
static inline void CSetVP(float *v) {
  bool same = st.vpSet; if (same) for (int i = 0; i < 6; i++) if (st.vp[i] != v[i]) { same = false; break; }
  if (same) { stSkip++; return; }
  st.vpSet = true; for (int i = 0; i < 6; i++) st.vp[i] = v[i]; stSet++;
  wgpuRenderPassEncoderSetViewport(g_pass, v[0], v[1], v[2], v[3], v[4], v[5]);
}
static inline void CSetSC(uint32_t *s) {
  bool same = st.scSet; if (same) for (int i = 0; i < 4; i++) if (st.sc[i] != s[i]) { same = false; break; }
  if (same) { stSkip++; return; }
  st.scSet = true; for (int i = 0; i < 4; i++) st.sc[i] = s[i]; stSet++;
  wgpuRenderPassEncoderSetScissorRect(g_pass, s[0], s[1], s[2], s[3]);
}
static inline void CSetBlend(float *f) {
  bool same = st.bfSet; if (same) for (int i = 0; i < 4; i++) if (st.bf[i] != f[i]) { same = false; break; }
  if (same) { stSkip++; return; }
  st.bfSet = true; for (int i = 0; i < 4; i++) st.bf[i] = f[i]; stSet++;
  WGPUColor c = { f[0], f[1], f[2], f[3] }; wgpuRenderPassEncoderSetBlendConstant(g_pass, &c);
}
static inline void CSetSRef(uint32_t r) {
  if (st.srefSet && st.sref == r) { stSkip++; return; }
  st.srefSet = true; st.sref = r; stSet++; wgpuRenderPassEncoderSetStencilReference(g_pass, r);
}

// ============================================================================
// draw(pWord, vpid, ipid, plid, foldV, foldI): one N-API crossing executes the WHOLE
// per-draw encoding: pipeline/bind groups, vertex/index buffers with D3D-style
// zero-read clamping, dynamic state, and the draw call. S (flat state) holds the
// state; g_objs maps game ids to GPU handles. pWord is the draw command's word index.
// Returns the number of draws actually issued (0 if skipped).
// ============================================================================
static napi_value Draw(napi_env env, napi_callback_info info) {
  size_t argc = 7; napi_value a[7]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  uint32_t pWord  = as_u32v(env, a[0]);
  uint32_t lid    = as_u32v(env, a[1]);
  uint32_t plid   = as_u32v(env, a[2]);
  uint32_t foldV  = as_u32v(env, a[3]);
  uint32_t foldI  = as_u32v(env, a[4]);
  uint32_t vpid   = as_u32v(env, a[5]);
  uint32_t ipid   = as_u32v(env, a[6]);
  (void)vpid; (void)ipid;

  uint32_t *cmd = U + pWord;
  uint32_t kind = cmd[0], count = cmd[1], inst = cmd[2], start = cmd[3];
  int32_t  baseVertex = (int32_t)cmd[4], startInstance = cmd[5];
  uint32_t indexed = (kind >= 4) || ((kind & 1u) != 0);

  GpuObj &lay = g_objs[lid];
  GpuObj &pl  = g_objs[plid];
  if (!pl.pl) { stSkipDraw++; skipNoPl++; return nullptr; }
  CSetPipe(pl.pl);

  GpuObj *bg0 = nullptr, *bg1 = nullptr;
  auto it0 = g_objs.find(0xffffffffu), it1 = g_objs.find(0xfffffffeu);
  if (it0 != g_objs.end() && it0->second.bg) bg0 = &it0->second;
  if (it1 != g_objs.end() && it1->second.bg) bg1 = &it1->second;
  CSetBG(0, bg0 ? bg0->bg : nullptr, 0);
  CSetBG(1, bg1 ? bg1->bg : nullptr, 0);

  uint64_t vbAvail[16]; for (int i = 0; i < 16; i++) vbAvail[i] = 0;
  for (uint32_t si = 0; si < lay.nslots; si++) {
    uint32_t slot = lay.slots[si], cls = lay.slotCls[si];
    uint32_t *v = S + W_VB + slot * 3;
    uint32_t bufId = v[0], stride = v[1], off = (uint32_t)v[2];
    GpuObj *o = bufId ? &g_objs[bufId] : nullptr;
    WGPUBuffer gpu = (o && o->buf) ? o->buf : g_zero;
    uint64_t bytes = (o && o->buf) ? o->bytes : g_zeroBytes;
    uint64_t shift = 0;
    if (cls == 1) { if (foldI) shift = (uint64_t)startInstance * stride; }
    else if (foldV) shift = (uint64_t)(indexed ? baseVertex : (int32_t)start) * stride;
    int64_t vo = (int64_t)off + (int64_t)shift; if (vo < 0) vo = 0;
    uint64_t voff = (uint64_t)vo;
    CSetVB(slot, gpu, voff);
    vbAvail[slot] = bytes > voff ? bytes - voff : 0;
  }

  uint64_t ibMax = 0xffffffffull;
  if (indexed) {
    uint32_t ibId = S[W_IB], ifmt = S[W_IB + 1], ioff = S[W_IB + 2];
    GpuObj *ib = ibId ? &g_objs[ibId] : nullptr;
    if (!ib || !ib->buf) { stSkipDraw++; skipNoIb++; return nullptr; }
    CSetIB(ib->buf, ifmt == 57 ? 0 : 1, ioff);
    uint64_t bpp = ifmt == 57 ? 2 : 4;
    ibMax = ib->bytes > ioff ? (ib->bytes - ioff) / bpp : 0;
    if (ibMax > start) ibMax -= start; else ibMax = 0;
  }

  float *vpf = &SF[W_VP]; if (S[W_VPN]) CSetVP(vpf);
  uint32_t sc[4];
  if (S[W_SCN] && S[W_RS]) {
    uint32_t x0 = S[W_SC] < g_passW ? S[W_SC] : g_passW;
    uint32_t y0 = S[W_SC+1] < g_passH ? S[W_SC+1] : g_passH;
    uint32_t x1 = S[W_SC + 2] > x0 ? S[W_SC + 2] : x0; if (x1 > g_passW) x1 = g_passW;
    uint32_t y1 = S[W_SC+3] > y0 ? S[W_SC+3] : y0; if (y1 > g_passH) y1 = g_passH;
    sc[0]=x0; sc[1]=y0; sc[2]=x1-x0; sc[3]=y1-y0;
  } else { sc[0]=0; sc[1]=0; sc[2]=g_passW; sc[3]=g_passH; }
  CSetSC(sc);
  CSetBlend(&SF[W_BLENDR]);
  CSetSRef(S[W_DSSREF]);

  uint32_t dCount = count, dInst = inst;
  uint32_t vFirst = (indexed || foldV) ? 0 : start;
  uint32_t iFirst = foldI ? 0 : startInstance;
  for (uint32_t i = 0; i < pl.nreq; i++) {
    VbReq &r = pl.req[i];
    uint64_t avail = vbAvail[r.slot];
    uint64_t n = avail < r.last ? 0 : (r.stride ? (avail - r.last) / r.stride + 1 : 0xffffffffull);
    if (r.instance) { if (dInst > n - iFirst) dInst = (uint32_t)(n - iFirst); }
    else if (!indexed) { if (dCount > n - vFirst) dCount = (uint32_t)(n - vFirst); }
  }
  if (indexed && dCount > ibMax) dCount = (uint32_t)ibMax;
  if (dCount == 0 || dInst == 0) {
    stSkipDraw++; skipZero++;
    return nullptr;
  }
  if (dCount != count || dInst != inst) stClamp++;

  if (kind >= 4) {
    GpuObj *args = &g_objs[cmd[1]];
    if (!args->buf) { stSkipDraw++; skipNoArgs++; return nullptr; }
    wgpuRenderPassEncoderDrawIndexedIndirect(g_pass, args->buf, cmd[2]);
  } else if (indexed) {
    wgpuRenderPassEncoderDrawIndexed(g_pass, dCount, dInst, start, foldV ? 0 : baseVertex, iFirst);
  } else {
    wgpuRenderPassEncoderDraw(g_pass, dCount, dInst, vFirst, iFirst);
  }
  stDraw++;
  napi_value r; napi_create_uint32(env, 1, &r); return r;
}

// ============================================================================
// Stages 6/7/8: copy ops, compute dispatch, occlusion queries (gated by JS flags).
// ============================================================================
static napi_value CopyBuffer(napi_env env, napi_callback_info info) {
  size_t argc = 5; napi_value a[5]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  if (!g_encoder) return nullptr;
  GpuObj *s = &g_objs[as_u32v(env,a[0])], *d = &g_objs[as_u32v(env,a[1])];
  if (!s->buf || !d->buf) return nullptr;
  int64_t so=0,do_=0,sz=0; napi_get_value_int64(env,a[2],&so); napi_get_value_int64(env,a[3],&do_); napi_get_value_int64(env,a[4],&sz);
  wgpuCommandEncoderCopyBufferToBuffer(g_encoder, s->buf, (uint64_t)so, d->buf, (uint64_t)do_, (uint64_t)sz); stCopyBuf++;
  return nullptr;
}
static napi_value CopyTexture(napi_env env, napi_callback_info info) {
  size_t argc = 8; napi_value a[8]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  if (!g_encoder) return nullptr;
  WGPUTexture s = g_tex[as_u32v(env,a[0])], d = g_tex[as_u32v(env,a[1])];
  if (!s || !d) return nullptr;
  uint32_t sm=as_u32v(env,a[2]), sl=as_u32v(env,a[3]), dm=as_u32v(env,a[4]), dl=as_u32v(env,a[5]);
  uint32_t w=as_u32v(env,a[6]), h=as_u32v(env,a[7]);
  WGPUTexelCopyTextureInfo src={}; src.texture=s; src.mipLevel=sm; src.origin.z=sl;
  WGPUTexelCopyTextureInfo dst={}; dst.texture=d; dst.mipLevel=dm; dst.origin.z=dl;
  WGPUExtent3D ext={w,h,1};
  wgpuCommandEncoderCopyTextureToTexture(g_encoder,&src,&dst,&ext); stCopyTex++;
  return nullptr;
}
static WGPUComputePipeline g_cp = nullptr;
static WGPUBindGroup g_cbg = nullptr;
static WGPUComputePassEncoder g_cpass = nullptr;
static uint32_t g_cdyn = 0;
static uint64_t g_dispatchLogged = 0;
static napi_value SetCompute(napi_env env, napi_callback_info info) {
  size_t argc = 4; napi_value a[4]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  g_cp  = reinterpret_cast<WGPUComputePipeline>(as_ptr(env,a[0]));
  g_cbg = reinterpret_cast<WGPUBindGroup>(as_ptr(env,a[1]));
  g_cpass = reinterpret_cast<WGPUComputePassEncoder>(as_ptr(env,a[2]));
  g_cdyn = argc > 3 ? as_u32v(env,a[3]) : 0;
  if (g_dispatchLogged++ < 2) fprintf(stderr, "SETCOMPUTE cp=%llu bg=%llu pass=%llu dyn=%u\n", (unsigned long long)(uintptr_t)g_cp, (unsigned long long)(uintptr_t)g_cbg, (unsigned long long)(uintptr_t)g_cpass, g_cdyn);
  return nullptr;
}
static napi_value Dispatch(napi_env env, napi_callback_info info) {
  size_t argc = 3; napi_value a[3]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  if (!g_cpass || !g_cp) return nullptr;
  wgpuComputePassEncoderSetPipeline(g_cpass, g_cp);
  if (g_cbg) { uint32_t d[1] = { g_cdyn }; wgpuComputePassEncoderSetBindGroup(g_cpass, 0, g_cbg, g_cdyn ? 1u : 0u, g_cdyn ? d : nullptr); }
  wgpuComputePassEncoderDispatchWorkgroups(g_cpass, as_u32v(env,a[0]),as_u32v(env,a[1]),as_u32v(env,a[2])); stDispatch++;
  return nullptr;
}
// Stage: MSAA resolve — beginRenderPass with colorAttachment.view=sv, resolveTarget=dv, end.
static uint64_t stResolve = 0;
static napi_value ResolvePass(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  WGPUTextureView sv = reinterpret_cast<WGPUTextureView>(as_ptr(env,a[0]));
  WGPUTextureView dv = reinterpret_cast<WGPUTextureView>(as_ptr(env,a[1]));
  if (!sv || !dv || !g_encoder) return nullptr;
  WGPURenderPassColorAttachment c = {};
  c.view = sv; c.resolveTarget = dv; c.loadOp = WGPULoadOp_Load; c.storeOp = WGPUStoreOp_Discard;
  WGPURenderPassDescriptor d = {}; d.colorAttachmentCount = 1; d.colorAttachments = &c;
  if (stResolve < 2) fprintf(stderr, "RESOLVE sv=%llu dv=%llu enc=%llu\n", (unsigned long long)(uintptr_t)sv, (unsigned long long)(uintptr_t)dv, (unsigned long long)(uintptr_t)g_encoder);
  WGPURenderPassEncoder rp = wgpuCommandEncoderBeginRenderPass(g_encoder, &d);
  wgpuRenderPassEncoderEnd(rp);
  stResolve++;
  return nullptr;
}
static napi_value BeginOcclusion(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  if (g_pass) { wgpuRenderPassEncoderBeginOcclusionQuery(g_pass, as_u32v(env,a[0])); stOccl++; }
  return nullptr;
}
static napi_value EndOcclusion(napi_env env, napi_callback_info info) {
  if (g_pass) wgpuRenderPassEncoderEndOcclusionQuery(g_pass);
  return nullptr;
}

// ============================================================================
// processNext(tail, head, base): walk the ring [tail, head). Handle consecutive
// pure state opcodes internally (no N-API crossing per command); STOP at the
// first complex op and return {tail, op, p, n} for JS to execute (it can await).
// Returns an object; op=-1 means the whole range was consumed as state.
// ============================================================================
static napi_value ProcessNext(napi_env env, napi_callback_info info) {
  size_t argc = 3; napi_value a[3]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  uint32_t tail = 0;
  napi_get_value_uint32(env, a[0], &tail);
  uint32_t head = 0;
  napi_get_value_uint32(env, a[1], &head);
  uint32_t ringBaseWords = 0;
  napi_get_value_uint32(env, a[2], &ringBaseWords);

  uint32_t *base = U + ringBaseWords;
  uint32_t retOp = 0xffffffffu, retP = 0, retN = 0;

  while (tail != head) {
    uint32_t *c = base + (tail >> 2);
    uint32_t op = c[0], n = c[1];
    uint32_t *p = c + 2;
    bool isState = false;

    switch (op) {
      case 0: case 2: isState = true; break;              // NOP / INIT
      case 18: {                                         // SET_SHADER
        uint32_t st = p[0], id = p[1];
        if (S[W_SHADER0 + st] != id) { S[W_SHADER0 + st] = id; S[W_PDIRTY] = 1; }
        isState = true; break;
      }
      case 19: {                                         // SET_INPUT_LAYOUT
        if (S[W_LAYOUT] != p[0]) { S[W_LAYOUT] = p[0]; S[W_PDIRTY] = 1; }
        isState = true; break;
      }
      case 20: {                                         // SET_TOPOLOGY
        if (S[W_TOPO] != p[0]) { S[W_TOPO] = p[0]; S[W_PDIRTY] = 1; }
        isState = true; break;
      }
      case 21: {                                         // SET_VERTEX_BUFFERS
        uint32_t s = p[0], c2 = p[1];
        for (uint32_t i = 0; i < c2 && s + i < 16; i++) {
          uint32_t *v = S + W_VB + (s + i) * 3;
          uint32_t nb = p[2 + i * 3], ns = p[3 + i * 3];
          if (v[0] != nb || v[1] != ns) S[W_PDIRTY] = 1;
          v[0] = nb; v[1] = ns; v[2] = p[4 + i * 3];
        }
        isState = true; break;
      }
      case 22: {                                         // SET_INDEX_BUFFER
        if (S[W_IB + 1] != p[1] || S[W_IB] != p[0]) S[W_PDIRTY] = 1;
        S[W_IB] = p[0]; S[W_IB + 1] = p[1]; S[W_IB + 2] = p[2];
        isState = true; break;
      }
      case 23: {                                         // SET_CBUFFERS
        S[722 + p[0]]++;  // bindEpoch[stage]
        uint32_t st = p[0], s = p[1], c2 = p[2];
        for (uint32_t i = 0; i < c2 && s + i < 16; i++) {
          uint32_t *v = S + W_CB + st * 48 + (s + i) * 3;
          v[0] = p[3 + i * 3]; v[1] = p[4 + i * 3]; v[2] = p[5 + i * 3];
        }
        isState = true; break;
      }
      case 24: {                                         // SET_SRVS
        uint32_t st = p[0], s = p[1], c2 = p[2];
        bool ch = false;
        for (uint32_t i = 0; i < c2 && s + i < 128; i++) { uint32_t o = W_SRV + st * 128 + s + i; if (S[o] != p[3 + i]) { ch = true; S[o] = p[3 + i]; } }
        if (ch) { S[722 + st]++; S[726 + st]++; }  // bindEpoch + srvEpoch
        isState = true; break;
      }
      case 25: {                                         // SET_SAMPLERS
        S[722 + p[0]]++;  // bindEpoch[stage]
        uint32_t st = p[0], s = p[1], c2 = p[2];
        for (uint32_t i = 0; i < c2 && s + i < 16; i++) S[W_SMP + st * 16 + s + i] = p[3 + i];
        isState = true; break;
      }
      case 26: {                                         // SET_RENDER_TARGETS
        for (uint32_t i = 0; i < 8; i++) {
          uint32_t *r = S + W_RT + i * 4;
          r[0] = p[i * 4]; r[1] = p[i * 4 + 1]; r[2] = p[i * 4 + 2]; r[3] = p[i * 4 + 3];
        }
        uint32_t *d = S + W_DS;
        d[0] = p[32]; d[1] = p[33]; d[2] = p[34]; d[3] = p[35]; d[4] = p[36];
        S[W_PDIRTY] = 1;
        S[721]++;  // rt change counter -> JS invalidates rtKey
        isState = true; break;
      }
      case 27: {                                         // SET_BLEND
        if (S[W_BLENDID] != p[0]) S[W_PDIRTY] = 1;
        S[W_BLENDID] = p[0];
        S[W_BLENDR]     = *reinterpret_cast<uint32_t*>(&((float*)p)[1]);
        S[W_BLENDR + 1] = *reinterpret_cast<uint32_t*>(&((float*)p)[2]);
        S[W_BLENDR + 2] = *reinterpret_cast<uint32_t*>(&((float*)p)[3]);
        S[W_BLENDR + 3] = *reinterpret_cast<uint32_t*>(&((float*)p)[4]);
        S[W_BLENDR - 1] = p[5]; // mask
        isState = true; break;
      }
      case 28: {                                         // SET_DEPTH_STENCIL
        if (S[W_DSSID] != p[0]) S[W_PDIRTY] = 1;
        S[W_DSSID] = p[0]; S[W_DSSREF] = p[1];
        isState = true; break;
      }
      case 29: {                                         // SET_RASTER
        if (S[W_RS] != p[0]) S[W_PDIRTY] = 1;
        S[W_RS] = p[0];
        isState = true; break;
      }
      case 30: {                                         // SET_VIEWPORTS
        uint32_t c2 = p[0]; S[W_VPN] = c2;
        for (uint32_t i = 0; i < c2 && i < 1; i++)
          for (uint32_t k = 0; k < 6; k++) S[W_VP + k] = *reinterpret_cast<uint32_t*>(&((float*)p)[1 + i * 6 + k]);
        isState = true; break;
      }
      case 31: {                                         // SET_SCISSORS
        uint32_t c2 = p[0]; S[W_SCN] = c2;
        for (uint32_t i = 0; i < c2 && i < 1; i++)
          for (uint32_t k = 0; k < 4; k++) S[W_SC + k] = p[1 + i * 4 + k];
        isState = true; break;
      }
      case 38: {                                         // SET_UAVS
        S[722 + p[0]]++;  // bindEpoch[stage]
        uint32_t st = p[0], s = p[1], c2 = p[2];
        for (uint32_t i = 0; i < c2 && s + i < 8; i++) S[W_UAV + st * 8 + s + i] = p[3 + i];
        isState = true; break;
      }
      case 33: reset_state(); isState = true; break;     // CLEAR_STATE
      default: break;
    }

    if (!isState) {
      // Complex op: return it to JS without consuming it here.
      retOp = op; retP = static_cast<uint32_t>(p - U); retN = n;
      break;
    }
    tail += n * 4 + 8;
  }

  napi_value out; napi_create_object(env, &out);
  napi_value v;
  napi_create_uint32(env, tail, &v); napi_set_named_property(env, out, "tail", v);
  napi_create_uint32(env, retOp, &v); napi_set_named_property(env, out, "op", v);
  napi_create_uint32(env, retP, &v); napi_set_named_property(env, out, "p", v);
  napi_create_uint32(env, retN, &v); napi_set_named_property(env, out, "n", v);
  return out;
}

static void add(napi_env env, napi_value exports, const char *name, napi_callback fn) {
  napi_value v; napi_create_function(env, nullptr, 0, fn, nullptr, &v); napi_set_named_property(env, exports, name, v);
}
static napi_value Init(napi_env env, napi_value exports) {
  add(env, exports, "attach", Attach);
  add(env, exports, "setCallback", SetCallback);
  add(env, exports, "processNext", ProcessNext);
  add(env, exports, "regBuffer", RegBuffer);
  add(env, exports, "regBG", RegBG);
  add(env, exports, "regPipe", RegPipe);
  add(env, exports, "delObj", DelObj);
  add(env, exports, "setPass", SetPass);
  add(env, exports, "setZero", SetZero);
  add(env, exports, "setPassInfo", SetPassInfo);
  add(env, exports, "copyBuffer", CopyBuffer);
  add(env, exports, "copyTexture", CopyTexture);
  add(env, exports, "setCompute", SetCompute);
  add(env, exports, "dispatch", Dispatch);
  add(env, exports, "resolvePass", ResolvePass);
  add(env, exports, "beginOcclusion", BeginOcclusion);
  add(env, exports, "endOcclusion", EndOcclusion);
  add(env, exports, "setQueue", SetQueue);
  add(env, exports, "setEncoder", SetEncoder);
  add(env, exports, "clearColor", ClearColor);
  add(env, exports, "clearDepth", ClearDepth);
  add(env, exports, "regTexture", RegTexture);
  add(env, exports, "uploadBuffer", UploadBuffer);
  add(env, exports, "uploadTexture", UploadTexture);
  add(env, exports, "resetCache", [](napi_env e, napi_callback_info) -> napi_value { std::memset(&st, 0, sizeof(st)); return nullptr; });
  add(env, exports, "regLayout", RegLayout);
  add(env, exports, "regVbReq", RegVbReq);
  add(env, exports, "draw", Draw);
  add(env, exports, "stats", [](napi_env e, napi_callback_info) -> napi_value {
    napi_value o; napi_create_object(e, &o); napi_value v;
    napi_create_double(e, (double)stSet, &v); napi_set_named_property(e, o, "set", v);
    napi_create_double(e, (double)stSkip, &v); napi_set_named_property(e, o, "skip", v);
    napi_create_double(e, (double)stDraw, &v); napi_set_named_property(e, o, "draw", v);
    napi_create_double(e, (double)stClear, &v); napi_set_named_property(e, o, "clear", v); stClear = 0;
    napi_create_double(e, (double)stCopyBuf, &v); napi_set_named_property(e, o, "copyBuf", v); stCopyBuf = 0;
    napi_create_double(e, (double)stCopyTex, &v); napi_set_named_property(e, o, "copyTex", v); stCopyTex = 0;
    napi_create_double(e, (double)stDispatch, &v); napi_set_named_property(e, o, "dispatch", v); stDispatch = 0;
    napi_create_double(e, (double)stOccl, &v); napi_set_named_property(e, o, "occl", v); stOccl = 0;
    napi_create_double(e, (double)stResolve, &v); napi_set_named_property(e, o, "resolve", v); stResolve = 0;
    napi_create_double(e, (double)stClamp, &v); napi_set_named_property(e, o, "clamp", v);
    napi_create_double(e, (double)stSkipDraw, &v); napi_set_named_property(e, o, "skipDraw", v);
    napi_create_double(e, (double)g_regPipeCount, &v); napi_set_named_property(e, o, "regPipe", v);
    napi_create_double(e, (double)g_objs.size(), &v); napi_set_named_property(e, o, "objs", v);
    napi_create_double(e, (double)skipNoPl, &v); napi_set_named_property(e, o, "noPl", v);
    napi_create_double(e, (double)skipNoIb, &v); napi_set_named_property(e, o, "noIb", v);
    napi_create_double(e, (double)skipZero, &v); napi_set_named_property(e, o, "zero", v);
    napi_create_double(e, (double)skipNoArgs, &v); napi_set_named_property(e, o, "noArgs", v);
    skipNoPl = skipNoIb = skipZero = skipNoArgs = 0;
    stSet = stSkip = stDraw = stClamp = stSkipDraw = 0; return o;
  });
  add(env, exports, "reset", [](napi_env e, napi_callback_info) -> napi_value { reset_state(); std::memset(&st, 0, sizeof(st)); return nullptr; });
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
