#include <node_api.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

// harness_native.cpp â€” the harness we created, in C++.
// Owns: env setup, browser shims (self/location/navigator/BroadcastChannel/XMLHttpRequest),
// wasm ring init, startMode/forceHttpfs writes, status logging, and the synthetic wgpu start.
// JS is left with only the Emscripten glue that needs WebAssembly.instantiate.

static const char *ENV_SETUP =
  "process.env.WGPU_NODE_MODULE='E:/gta/playgta5/native-dawn-test/node_modules/native-dawn';"
  "process.env.WGPU_SHADER_DIR='E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';"
  "process.env.WGPU_WORKER='E:/gta/playgta5/node-webgpu/wgpu_wrapper2.js';";

static const char *LOG_PATH = "E:/gta/playgta5/node-webgpu/engine-log.txt";
static const char *DIAG_PATH = "E:/gta/playgta5/node-webgpu/pthread-msg-log.txt";

static void hlog(const char *s) { fprintf(stderr, "HARNESS_CPP %s\n", s); }

// env setup via Function(...)
static napi_value SetupEnv(napi_env env, napi_callback_info info) {
  hlog("SetupEnv enter");
  napi_value global, Function, fnArg, ctorArgs[1], setupFn, undefined;
  napi_get_global(env, &global);
  napi_get_undefined(env, &undefined);
  napi_get_named_property(env, global, "Function", &Function);
  napi_create_string_utf8(env, ENV_SETUP, NAPI_AUTO_LENGTH, &fnArg);
  ctorArgs[0] = fnArg;
  napi_new_instance(env, Function, 1, ctorArgs, &setupFn);
  napi_call_function(env, undefined, setupFn, 0, nullptr, nullptr);
  hlog("SetupEnv done");
  return nullptr;
}

// no-op function for addEventListener/removeEventListener
static napi_value Noop(napi_env env, napi_callback_info info) { return nullptr; }

// XMLHttpRequest shim: constructor sets nothing; open(method,url) stores url on `this` via a JS setter.
// We implement open/send as C functions that read `this.url` and call the JS callbacks.
static napi_value XhrOpen(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_value thisv;
  napi_get_cb_info(env, info, &argc, a, &thisv, nullptr);
  napi_value url = argc > 1 ? a[1] : a[0];
  napi_set_named_property(env, thisv, "__url", url);
  return nullptr;
}
static napi_value XhrSend(napi_env env, napi_callback_info info) {
  napi_value thisv; napi_get_cb_info(env, info, nullptr, nullptr, &thisv, nullptr);
  napi_value urlv; napi_get_named_property(env, thisv, "__url", &urlv);
  char buf[1024]; size_t len = 0; napi_get_value_string_utf8(env, urlv, buf, sizeof(buf), &len);
  // strip http://localhost:8000/ prefix -> mirror path
  std::string p(buf);
  const std::string prefix = "http://localhost:8000/";
  if (p.rfind(prefix, 0) == 0) p = p.substr(prefix.size());
  std::string local = "E:/gta/playgta5/mirror/playgta5.com/" + p;
  std::string text;
  int status = 404;
  FILE *f = fopen(local.c_str(), "rb");
  if (f) {
    char chunk[4096]; size_t n;
    while ((n = fread(chunk, 1, sizeof(chunk), f)) > 0) text.append(chunk, n);
    fclose(f); status = 200;
  }
  napi_value resp, st;
  napi_create_string_utf8(env, text.c_str(), NAPI_AUTO_LENGTH, &resp);
  napi_create_int32(env, status, &st);
  napi_set_named_property(env, thisv, "responseText", resp);
  napi_set_named_property(env, thisv, "status", st);
  // call onload / onreadystatechange if present
  napi_value cb;
  if (napi_get_named_property(env, thisv, "onload", &cb) == napi_ok) {
    napi_valuetype t; napi_typeof(env, cb, &t);
    if (t == napi_function) napi_call_function(env, thisv, cb, 0, nullptr, nullptr);
  }
  if (napi_get_named_property(env, thisv, "onreadystatechange", &cb) == napi_ok) {
    napi_valuetype t; napi_typeof(env, cb, &t);
    if (t == napi_function) {
      napi_value rs; napi_create_int32(env, 4, &rs);
      napi_set_named_property(env, thisv, "readyState", rs);
      napi_call_function(env, thisv, cb, 0, nullptr, nullptr);
    }
  }
  return nullptr;
}
static napi_value XhrCtor(napi_env env, napi_callback_info info) {
  napi_value thisv; napi_get_cb_info(env, info, nullptr, nullptr, &thisv, nullptr);
  napi_value open, send;
  napi_create_function(env, "open", NAPI_AUTO_LENGTH, XhrOpen, nullptr, &open);
  napi_create_function(env, "send", NAPI_AUTO_LENGTH, XhrSend, nullptr, &send);
  napi_set_named_property(env, thisv, "open", open);
  napi_set_named_property(env, thisv, "send", send);
  return thisv;
}

// BroadcastChannel shim: postMessage appends "[name] msg" to engine-log.txt
static napi_value BcPost(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_value thisv;
  napi_get_cb_info(env, info, &argc, a, &thisv, nullptr);
  napi_value namev; napi_get_named_property(env, thisv, "name", &namev);
  char name[256] = {0}; napi_get_value_string_utf8(env, namev, name, sizeof(name), nullptr);
  char msg[4096] = {0}; napi_get_value_string_utf8(env, a[0], msg, sizeof(msg), nullptr);
  FILE *f = fopen(LOG_PATH, "a");
  if (f) { fprintf(f, "[%s] %s\n", name, msg); fclose(f); }
  return nullptr;
}
static napi_value BcCtor(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_value thisv;
  napi_get_cb_info(env, info, &argc, a, &thisv, nullptr);
  if (argc > 0) napi_set_named_property(env, thisv, "name", a[0]);
  napi_value post, noop;
  napi_create_function(env, "postMessage", NAPI_AUTO_LENGTH, BcPost, nullptr, &post);
  napi_create_function(env, "close", NAPI_AUTO_LENGTH, Noop, nullptr, &noop);
  napi_set_named_property(env, thisv, "postMessage", post);
  napi_set_named_property(env, thisv, "close", noop);
  napi_set_named_property(env, thisv, "addEventListener", noop);
  return thisv;
}

// Install all browser shims on globalThis. Called first by harness.js.
static napi_value InstallShims(napi_env env, napi_callback_info info) {
  hlog("InstallShims enter");
  napi_value global;
  napi_get_global(env, &global);
  // self = globalThis
  napi_set_named_property(env, global, "self", global);
  // location object
  napi_value loc, s;
  napi_create_object(env, &loc);
  napi_create_string_utf8(env, "?log=1&low=0&res=1920x1080&fps=0&slots=5&mode=sandbox&args=-textureQuality=2,-shadowQuality=0,-reflectionQuality=1,-particleQuality=0,-grassQuality=0,-cityDensity=0,-lodScale=0", NAPI_AUTO_LENGTH, &s);
  napi_set_named_property(env, loc, "search", s);
  napi_create_string_utf8(env, "http://localhost:8000", NAPI_AUTO_LENGTH, &s);
  napi_set_named_property(env, loc, "origin", s);
  napi_create_string_utf8(env, "http://localhost:8000/", NAPI_AUTO_LENGTH, &s);
  napi_set_named_property(env, loc, "href", s);
  napi_set_named_property(env, global, "location", loc);
  // addEventListener / removeEventListener
  napi_value noop; napi_create_function(env, "noop", NAPI_AUTO_LENGTH, Noop, nullptr, &noop);
  napi_set_named_property(env, global, "addEventListener", noop);
  napi_set_named_property(env, global, "removeEventListener", noop);
  // navigator.hardwareConcurrency = 2
  napi_value nav, hc;
  if (napi_get_named_property(env, global, "navigator", &nav) != napi_ok || nav == nullptr) {
    napi_create_object(env, &nav); napi_set_named_property(env, global, "navigator", nav);
  }
  napi_create_int32(env, 2, &hc); napi_set_named_property(env, nav, "hardwareConcurrency", hc);
  // BroadcastChannel + XMLHttpRequest constructors
  napi_value bc, xhr;
  napi_create_function(env, "BroadcastChannel", NAPI_AUTO_LENGTH, BcCtor, nullptr, &bc);
  napi_create_function(env, "XMLHttpRequest", NAPI_AUTO_LENGTH, XhrCtor, nullptr, &xhr);
  napi_set_named_property(env, global, "BroadcastChannel", bc);
  napi_set_named_property(env, global, "XMLHttpRequest", xhr);
  // clear engine log
  FILE *f = fopen(LOG_PATH, "w"); if (f) fclose(f);
  hlog("InstallShims done");
  return nullptr;
}

// initRing(wasmMemoryArrayBuffer, ringByteOffset, sizeBytes): clear header, set head/tail/sleeping.
static napi_value InitRing(napi_env env, napi_callback_info info) {
  size_t argc = 3; napi_value a[3]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_arraybuffer_info(env, a[0], &data, &len);
  size_t ring = 0, size = 0;
  double dv=0; napi_get_value_double(env, a[1], &dv); ring=(size_t)dv;
  dv=0; napi_get_value_double(env, a[2], &dv); size=(size_t)dv;
  if (!data || ring + 64 > len) { hlog("InitRing bad args"); return nullptr; }
  uint8_t *mem = static_cast<uint8_t*>(data);
  std::memset(mem + ring, 0, 64);
  int32_t *i32 = reinterpret_cast<int32_t*>(mem + ring);
  i32[0] = (int32_t)(ring + 64);  // head
  i32[1] = (int32_t)(ring + 64);  // tail
  i32[5] = 1;                     // sleeping flag
  char m[128]; snprintf(m, sizeof(m), "InitRing done ring=0x%zx size=%zu", ring, size); hlog(m);
  return nullptr;
}

// writeStartMode(wasmMemoryArrayBuffer, addr): store 2 (Sandbox) if zero (atomics via plain store ok here).
static napi_value WriteStartMode(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_arraybuffer_info(env, a[0], &data, &len);
  size_t addr = 0; double adv=0; napi_get_value_double(env, a[1], &adv); addr=(size_t)adv;
  if (!data || addr + 4 > len) return nullptr;
  int32_t *slot = reinterpret_cast<int32_t*>(static_cast<uint8_t*>(data) + addr);
  if (*slot == 0) *slot = 2;
  return nullptr;
}
// forceHttpfs(wasmMemoryArrayBuffer, addr): write byte 1
static napi_value ForceHttpfs(napi_env env, napi_callback_info info) {
  size_t argc = 2; napi_value a[2]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  void *data = nullptr; size_t len = 0;
  napi_get_arraybuffer_info(env, a[0], &data, &len);
  size_t addr = 0; double adv=0; napi_get_value_double(env, a[1], &adv); addr=(size_t)adv;
  if (!data || addr >= len) return nullptr;
  static_cast<uint8_t*>(data)[addr] = 1;
  hlog("ForceHttpfs done");
  return nullptr;
}
// diag(s): append to pthread-msg-log.txt
static napi_value Diag(napi_env env, napi_callback_info info) {
  size_t argc = 1; napi_value a[1]; napi_get_cb_info(env, info, &argc, a, nullptr, nullptr);
  char s[2048] = {0}; napi_get_value_string_utf8(env, a[0], s, sizeof(s), nullptr);
  FILE *f = fopen(DIAG_PATH, "a"); if (f) { fprintf(f, "%s\n", s); fclose(f); }
  return nullptr;
}

static void add(napi_env env, napi_value exports, const char *name, napi_callback fn) {
  napi_value v; napi_create_function(env, nullptr, 0, fn, nullptr, &v); napi_set_named_property(env, exports, name, v);
}
static napi_value Init(napi_env env, napi_value exports) {
  add(env, exports, "setupEnv", SetupEnv);
  add(env, exports, "installShims", InstallShims);
  add(env, exports, "initRing", InitRing);
  add(env, exports, "writeStartMode", WriteStartMode);
  add(env, exports, "forceHttpfs", ForceHttpfs);
  add(env, exports, "diag", Diag);
  hlog("harness_native module init");
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)

