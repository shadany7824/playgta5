#include "wasm_export.h"
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <chrono>
#include <vector>
#include <string>
#include <cstdarg>
#include <cstdlib>

#include <thread>
#include <vector>
extern "C" unsigned short __stdcall CaptureStackBackTrace(unsigned long, unsigned long, void **, unsigned long *);
extern "C" void aot_debug_dump_globals(wasm_module_inst_t inst, const char *tag);
static const char *AUDIT_PATH = "E:/gta/_tmp_claude/native-host-audit.log";
static CRITICAL_SECTION g_audit_lock;
static FILE *g_audit_file = NULL;
static uint64_t g_call_seq = 0;
static uint64_t g_audit_flush_ctr = 0;
static uint8_t *g_wasm_mem = NULL;
static uint64_t g_tb = 0;

static void audit_line(const char *kind, const char *fn, const char *fmt, ...);
static std::vector<unsigned char> g_manifest;
struct HttpFile { std::string path; uint64_t size; };
static std::vector<HttpFile> g_httpfiles;
static uint64_t g_io_table = 0;
static volatile bool g_io_stop = false;
static void httpfs_parse_manifest(void) {
  if (!g_httpfiles.empty() || g_manifest.empty()) return;
  std::string s((const char *)g_manifest.data(), g_manifest.size());
  size_t p = s.find("\"files\":[");
  if (p == std::string::npos) return;
  p += 9;
  while (p < s.size() && s[p] != 0x5d) {
    while (p < s.size() && (s[p] == 0x2c || s[p] == 0x20)) p++;
    if (p >= s.size() || s[p] != 0x5b) break;
    p++;
    while (p < s.size() && s[p] == 0x20) p++;
    if (p >= s.size() || s[p] != 0x22) break;
    size_t e = s.find(0x22, p + 1);
    if (e == std::string::npos) break;
    HttpFile f; f.path = s.substr(p + 1, e - p - 1);
    p = e + 1;
    while (p < s.size() && (s[p] == 0x2c || s[p] == 0x20)) p++;
    f.size = 0; while (p < s.size() && s[p] >= 0x30 && s[p] <= 0x39) { f.size = f.size * 10 + (s[p] - 0x30); p++; }
    g_httpfiles.push_back(f);
    while (p < s.size() && s[p] != 0x5b && s[p] != 0x5d) p++; /* skip mtime */
    if (p < s.size() && s[p] == 0x5d) p++; /* consume entry close */
  }
  audit_line("INFO", "httpfs", "manifest parsed files=%u", (unsigned)g_httpfiles.size());
}

static void httpfs_reader(void) {
  while (!g_io_stop) {
    Sleep(1);
    if (!g_wasm_mem || !g_io_table) continue;
    uint32_t *tbl = (uint32_t *)(g_wasm_mem + g_io_table);
    for (int i = 0; i < 512; i++) {
      uint32_t *sl = tbl + 16 + 16 * i; /* wasm_httpfs_pread: slot base = table + 64 + i*64 */
      if (sl[0] != 1) continue;
      sl[0] = 3;
      uint32_t id = sl[1];
      uint64_t off = (uint64_t)sl[2] | ((uint64_t)sl[3] << 32);
      uint64_t dst = (uint64_t)sl[4] | ((uint64_t)sl[5] << 32);
      uint32_t len = sl[6];
      int32_t result = -1;
      if (id < g_httpfiles.size()) {
        std::string path = "E:/gta/playgta5/mirror/playgta5.com/data/";
        path += g_httpfiles[id].path;
        FILE *f = fopen(path.c_str(), "rb");
        if (f) {
          fseek(f, (long)off, SEEK_SET);
          uint32_t want = len;
          if (g_httpfiles[id].size > off) { uint64_t av = g_httpfiles[id].size - off; if (av < want) want = (uint32_t)av; }
          uint8_t *d = g_wasm_mem ? g_wasm_mem + dst : NULL;
          if (d && want) result = (int32_t)fread(d, 1, want, f);
          else result = 0;
          fclose(f);
        }
      }
      sl[7] = (uint32_t)result;
      sl[0] = 2;
    }
  }
}

static void httpfs_io_start_impl(void) {
  httpfs_parse_manifest();
  if (!g_io_table) {
    std::thread t(httpfs_reader); t.detach();
    audit_line("INFO", "httpfs", "reader started");
  }
}

struct PatchRec { uintptr_t addr; unsigned char save[4]; };
static std::vector<PatchRec> g_patches;
static void restore_patches(void) {
  for (auto &p : g_patches) { DWORD _o = 0;
    void *_pg = (void *)(p.addr & ~(uintptr_t)0xFFF);
    if (VirtualProtect(_pg, 4096, PAGE_EXECUTE_READWRITE, &_o)) {
      memcpy((void *)p.addr, p.save, 4);
      FlushInstructionCache(GetCurrentProcess(), (void *)p.addr, 4);
      VirtualProtect(_pg, 4096, _o, &_o); } }
  g_patches.clear();
  audit_line("INFO", "restore_patches", "done");
}

static uint32_t httpfs_manifest_impl(wasm_module_inst_t inst, uint64_t buf, uint32_t cap) {
  if (g_manifest.empty()) {
    FILE *_f = fopen("E:/gta/playgta5/mirror/playgta5.com/data/manifest.json", "rb");
    if (!_f) return (uint32_t)-1;
    fseek(_f, 0, SEEK_END); long _n = ftell(_f); fseek(_f, 0, SEEK_SET);
    if (_n <= 0) { fclose(_f); return (uint32_t)-1; }
    g_manifest.resize((size_t)_n);
    fread(g_manifest.data(), 1, (size_t)_n, _f); fclose(_f);
    audit_line("INFO", "httpfs", "manifest loaded bytes=%u", (unsigned)_n);
  }
  uint32_t _n = (uint32_t)g_manifest.size();
  if (cap > _n) {
    uint8_t *_p = (uint8_t *)wasm_runtime_addr_app_to_native(inst, buf);
    if (_p) { memcpy(_p, g_manifest.data(), _n); _p[_n] = 0; }
  }
  return _n;
}

struct PthreadCtx { wasm_exec_env_t parent; uint64_t tb, start, arg; };

static bool pt_call(wasm_exec_env_t env, const char *name, uint32_t cells, uint32_t *a) {
  wasm_module_inst_t inst = wasm_runtime_get_module_inst(env);
  wasm_function_inst_t f = wasm_runtime_lookup_function(inst, name);
  if (!f) { audit_line("ERR", "pthread", "missing export %s", name); return false; }
  bool ok = wasm_runtime_call_wasm(env, f, cells, a);
  if (!ok) audit_line("ERR", "pthread", "call %s failed: %s", name, wasm_runtime_get_exception(inst));
  return ok;
}

static void *pthread_thread_cb(wasm_exec_env_t env, void *p) {
  PthreadCtx *c = (PthreadCtx *)p;
  wasm_module_inst_t inst = wasm_runtime_get_module_inst(env);
  audit_line("INFO", "pthread", "start tb=0x%llx routine=%llu arg=%llu",
    (unsigned long long)c->tb, (unsigned long long)c->start, (unsigned long long)c->arg);
  uint8_t *_tb = g_wasm_mem ? g_wasm_mem + c->tb : NULL;
  uint64_t high = 0, sz = 0;
  if (_tb) { memcpy(&high, _tb + 80, 8); memcpy(&sz, _tb + 88, 8); }
  uint64_t low = high - sz;
  { uint32_t a[4] = {0,0,0,0}; memcpy(a, &high, 8); memcpy(a + 2, &low, 8);
    pt_call(env, "emscripten_stack_set_limits", 4, a); }
  { uint32_t a[2] = {0,0}; memcpy(a, &high, 8);
    pt_call(env, "_emscripten_stack_restore", 2, a); }
  { uint32_t a[8] = {0,0,0,0,0,0,0,0}; memcpy(a, &c->tb, 8);
    a[4] = 1; pt_call(env, "_emscripten_thread_init", 7, a); }
  { uint32_t a[2] = {0,0}; pt_call(env, "_emscripten_tls_init", 0, a); }
  uint32_t av[2] = {0,0}; memcpy(av, &c->arg, 8);
  bool ok = wasm_runtime_call_indirect(env, (uint32_t)c->start, 2, av);
  audit_line("INFO", "pthread", "entry ok=%d exc=%s", ok, wasm_runtime_get_exception(inst));
  { uint32_t a[2] = {0,0}; memcpy(a, av, 8); pt_call(env, "_emscripten_thread_exit", 2, a); }
  delete c;
  return NULL;
}

static void pthread_std_thread(wasm_exec_env_t spawned_env, PthreadCtx *c) {
  if (!wasm_runtime_init_thread_env()) audit_line("ERR", "pthread", "init_thread_env failed");
  pthread_thread_cb(spawned_env, c);
  wasm_runtime_destroy_thread_env();
  wasm_runtime_destroy_spawned_exec_env(spawned_env);
}

static int32_t pthread_create_impl(wasm_exec_env_t env, uint64_t *args, const char *fname) {
  uint64_t _tb = args[0];
  uint64_t _start = args[2];
  uint64_t _arg = args[3];
  PthreadCtx *c = new PthreadCtx{env, _tb, _start, _arg};
  wasm_exec_env_t spawned = wasm_runtime_spawn_exec_env(env);
  if (!spawned) { audit_line("ERR", fname, "spawn_exec_env failed tb=0x%llx", (unsigned long long)_tb); delete c; return -1; }
  std::thread t(pthread_std_thread, spawned, c);
  t.detach();
  audit_line("INFO", fname, "thread started tb=0x%llx start=%llu arg=%llu",
    (unsigned long long)_tb, (unsigned long long)_start, (unsigned long long)_arg);
  return 0;
}

static std::vector<std::string> g_env_strings;
static void build_env_strings(void) {
  if (!g_env_strings.empty()) return;
  g_env_strings.push_back("USER=web_user");
  g_env_strings.push_back("LOGNAME=web_user");
  g_env_strings.push_back("PATH=/");
  g_env_strings.push_back("PWD=/");
  g_env_strings.push_back("HOME=/home/web_user");
  g_env_strings.push_back("LANG=C.UTF-8");
  g_env_strings.push_back("_=./this.program");
}

static void audit_open(void) {
  InitializeCriticalSection(&g_audit_lock);
  g_audit_file = fopen(AUDIT_PATH, "w");
  if (!g_audit_file) fprintf(stderr, "AUDIT OPEN FAILED %s\n", AUDIT_PATH);
  fprintf(stderr, "AUDIT OPEN %s\n", AUDIT_PATH);
}

static void audit_line(const char *kind, const char *fn, const char *fmt, ...) {
  if (!g_audit_file) return;
  char buf[2048]; va_list ap; va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap);
  SYSTEMTIME st; GetSystemTime(&st);
  EnterCriticalSection(&g_audit_lock);
  fprintf(g_audit_file, "[%02d:%02d:%02d.%03d tid=%lu seq=%llu] %s %s %s\n",
          st.wHour, st.wMinute, st.wSecond, st.wMilliseconds, GetCurrentThreadId(),
          (unsigned long long)g_call_seq, kind, fn, buf);
  /* fflush on every line costs far too much when imports fire millions of
     times; flush on lifecycle lines and otherwise every 500 lines */
  if (++g_audit_flush_ctr % 500 == 0 || !strcmp(kind, "CANARY")
      || !strcmp(kind, "ERR") || !strcmp(kind, "INFO")) fflush(g_audit_file);
  LeaveCriticalSection(&g_audit_lock);
}

static bool audit_hot(const char *fn) {
  return !strcmp(fn, "fd_write") || !strcmp(fn, "fd_read")
      || !strcmp(fn, "fd_pread") || !strcmp(fn, "fd_pwrite")
      || !strcmp(fn, "fd_seek") || !strcmp(fn, "clock_time_get");
}
static bool audit_keep(const char *fn) {
  /* hot import stubs: log the first calls and then sample, so a busy loop
     does not flush gigabytes of audit lines and stall the process */
  if (!audit_hot(fn)) return true;
  return g_call_seq <= 20 || (g_call_seq % 200000) == 0;
}
#define AUDIT_ENTER(fn, nargs, args) do { if (audit_keep(fn)) audit_line("ENTER", fn, "nargs=%d a0=%llx a1=%llx a2=%llx a3=%llx", (int)(nargs), (unsigned long long)((args) && (nargs)>0?(args)[0]:0), (unsigned long long)((args) && (nargs)>1?(args)[1]:0), (unsigned long long)((args) && (nargs)>2?(args)[2]:0), (unsigned long long)((args) && (nargs)>3?(args)[3]:0)); } while (0)
#define AUDIT_EXIT(fn, ret) do { if (audit_keep(fn)) audit_line("EXIT", fn, "ret=%llx", (unsigned long long)(ret)); } while (0)

static wasm_module_inst_t inst_of(wasm_exec_env_t env) {
  return wasm_runtime_get_module_inst(env);
}

static uint64_t app_read(wasm_exec_env_t env, uint64_t addr, int bytes) {
  uint8_t *p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), addr);
  if (!p) return 0;
  uint64_t v = 0; memcpy(&v, p, bytes <= 8 ? bytes : 8); return v;
}

static void app_write(wasm_exec_env_t env, uint64_t addr, uint64_t val, int bytes) {
  uint8_t *p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), addr);
  if (p) memcpy(p, &val, bytes <= 8 ? bytes : 8);
}

static uint64_t now_ms(void) {
  return (uint64_t)std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::system_clock::now().time_since_epoch()).count();
}

/* WASI preview1 on memory64: every pointer/size is 8 bytes and an iovec is
   { uint64 buf; uint64 buf_len; } (16 bytes). fd_write must copy the bytes
   out AND set *nwritten, otherwise the caller sees a zero-length write and
   retries forever - that was the infinite loop we observed. */
static uint64_t wasi_fd_write_impl(wasm_exec_env_t env, uint64_t fd,
                                   uint64_t iovs, uint64_t iovs_len,
                                   uint64_t nwritten_ptr) {
  uint64_t total = 0;
  if (iovs_len > 4096) return 22; /* EINVAL */
  for (uint64_t i = 0; i < iovs_len; i++) {
    uint64_t base = iovs + i * 16;
    uint64_t buf = app_read(env, base, 8);
    uint64_t len = app_read(env, base + 8, 8);
    if (len == 0) continue;
    if (len > (1u << 20)) return 22;
    uint8_t *p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), buf);
    if (!p) return 22;
    if (fd == 1 || fd == 2) {
      FILE *o = (fd == 1) ? stdout : stderr;
      fwrite(p, 1, (size_t)len, o);
      fflush(o);
    }
    total += len;
  }
  if (nwritten_ptr) app_write(env, nwritten_ptr, total, 8);
  return 0;
}

static FILE *g_files[256] = {0};
static std::string guest_to_host(const char *p) {
  const char *root = "E:/gta/playgta5/mirror/playgta5.com/data/";
  const char *dev = "E:/P1/gta5/build/dev_ng/";
  std::string s(p ? p : "");
  if (s.compare(0, 6, "/game/") == 0) return std::string(root) + s.substr(6);
  if (s.compare(0, strlen(dev), dev) == 0) return std::string("E:/gta/playgta5/__missing__/") + s.substr(strlen(dev));
  if (s.compare(0, 10, "/userdata/") == 0) {
    std::string h = std::string("E:/gta/playgta5/userdata/") + s.substr(10);
    return h;
  }
  if (!s.empty() && s[0] != 0x2f) return std::string(root) + s;
  return s;
}
static int32_t host_open(const char *guest) {
  if (!guest || !*guest) return -2;
  std::string h = guest_to_host(guest);
  FILE *f = fopen(h.c_str(), "rb");
  bool isdir = false;
  if (!f) {
    DWORD _a = GetFileAttributesA(h.c_str());
    isdir = (_a != INVALID_FILE_ATTRIBUTES && (_a & FILE_ATTRIBUTE_DIRECTORY));
    if (!isdir) { audit_line("INFO", "host_open", "missing %s -> %s", guest, h.c_str()); return -44; }
  }
  for (int i = 3; i < 256; i++) if (!g_files[i]) { g_files[i] = f;
    audit_line("INFO", "host_open", "fd=%d dir=%d %s", i, (int)isdir, h.c_str()); return i; }
  fclose(f); return -24;
}
static uint32_t host_read_fd(uint64_t fd, uint64_t iovs, uint64_t iovs_len,
                             uint64_t off, uint64_t nread_ptr, wasm_exec_env_t env) {
  FILE *f = (fd < 256) ? g_files[fd] : NULL;
  uint64_t total = 0;
  if (!f) { if (nread_ptr) app_write(env, nread_ptr, (uint64_t)0, 8); return 0; }
  if (off != (uint64_t)-1) fseek(f, (long)off, SEEK_SET);
  for (uint64_t i = 0; i < iovs_len && i < 4096; i++) {
    uint64_t ptr = 0, len = 0;
    uint8_t *_io = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), iovs + i * 16);
    if (!_io) break; memcpy(&ptr, _io, 8); memcpy(&len, _io + 8, 8);
    uint8_t *_d = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), ptr);
    if (!_d || !len) continue;
    size_t n = fread(_d, 1, (size_t)len, f); total += n;
  }
  if (nread_ptr) app_write(env, nread_ptr, total, 8);
  return 0;
}

static uint64_t wasi_fd_read_impl(wasm_exec_env_t env, uint64_t fd,
                                  uint64_t iovs, uint64_t iovs_len,
                                  uint64_t nread_ptr) {
  return host_read_fd(fd, iovs, iovs_len, (uint64_t)-1, nread_ptr, env);
}

static void log_wstr(const char *label, const char *fname, uint64_t ptr) {
  char buf[256]; size_t n = 0;
  if (!g_wasm_mem || !ptr) return;
  const unsigned char *s = g_wasm_mem + ptr;
  while (n < sizeof(buf) - 1 && s[n] >= 32 && s[n] < 127) { buf[n] = (char)s[n]; n++; }
  buf[n] = 0;
  audit_line("STR", fname, "%s ptr=0x%llx val=%s", label, (unsigned long long)ptr, buf);
}

static uint64_t f64_bits(double d) {
  uint64_t b; memcpy(&b, &d, sizeof(b)); return b;
}

/* WASI/emscripten struct tm in a wasm64 (LP64) module: nine 4-byte ints
   then tm_gmtoff (8) and tm_zone (8) => 56 bytes. Leaving this uninitialised
   lets the caller index weekday/month tables with garbage and fault. */
static void tm_write(wasm_exec_env_t env, uint64_t tm_ptr, const struct tm *v) {
  uint8_t *p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), tm_ptr);
  if (!p) return;
  int32_t f[9] = { v->tm_sec, v->tm_min, v->tm_hour, v->tm_mday, v->tm_mon,
                   v->tm_year, v->tm_wday, v->tm_yday, v->tm_isdst };
  memcpy(p, f, 36);
  memset(p + 36, 0, 20);
}

static void tm_read(wasm_exec_env_t env, uint64_t tm_ptr, struct tm *v) {
  memset(v, 0, sizeof(*v));
  uint8_t *p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), tm_ptr);
  if (!p) return;
  int32_t f[9] = {0}; memcpy(f, p, 36);
  v->tm_sec = f[0]; v->tm_min = f[1]; v->tm_hour = f[2]; v->tm_mday = f[3];
  v->tm_mon = f[4]; v->tm_year = f[5]; v->tm_wday = f[6]; v->tm_yday = f[7];
  v->tm_isdst = f[8];
}

static void imp_000_wasm_now_ms(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_now_ms", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_now_ms", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  ret = f64_bits((double)now_ms());
  AUDIT_EXIT("wasm_now_ms", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_001_wasm_hang_line_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_hang_line_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_hang_line_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("wasm_hang_line_js", ret);
}

static void imp_002_wasm_audio_publish_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_audio_publish_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_audio_publish_js", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  { uint8_t *_r = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), args[0]); if (_r) memset(_r, 0, 32); audit_line("INFO", "wasm_audio_publish_js", "ring=0x%llx cap=%llu", (unsigned long long)args[0], (unsigned long long)args[1]); }
  AUDIT_EXIT("wasm_audio_publish_js", ret);
}

static void imp_003_wasm_httpfs_io_start_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_httpfs_io_start_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_httpfs_io_start_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  g_io_table = args[0]; audit_line("INFO", "wasm_httpfs_io_start_js", "table=0x%llx", (unsigned long long)args[0]); httpfs_io_start_impl();
  AUDIT_EXIT("wasm_httpfs_io_start_js", ret);
}

static void imp_004_wasm_httpfs_manifest_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_httpfs_manifest_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_httpfs_manifest_js", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  ret = httpfs_manifest_impl(inst_of(env), args[0], (uint32_t)args[1]);
  AUDIT_EXIT("wasm_httpfs_manifest_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_005_wasm_userdata_page_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_userdata_page_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_userdata_page_js", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("wasm_userdata_page_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_006_wasm_userdata_put_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_userdata_put_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_userdata_put_js", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("wasm_userdata_put_js", ret);
}

static void imp_007_wasm_userdata_delete_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_userdata_delete_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_userdata_delete_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("wasm_userdata_delete_js", ret);
}

static void imp_008_wgpu_start_worker(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wgpu_start_worker", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wgpu_start_worker", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("wgpu_start_worker", ret);
}

static void imp_009_wasm_has_page_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_has_page_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_has_page_js", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  ret = 1;
  AUDIT_EXIT("wasm_has_page_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_010_wasm_input_publish_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_input_publish_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_input_publish_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  { uint8_t *_b = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), args[0]); if (_b) { uint32_t _v; _v = 2; memcpy(_b + 440, &_v, 4); _v = 1920; memcpy(_b + 432, &_v, 4); _v = 1080; memcpy(_b + 436, &_v, 4); _v = 1; memcpy(_b + 280, &_v, 4); } audit_line("INFO", "wasm_input_publish_js", "block=0x%llx", (unsigned long long)args[0]); }
  AUDIT_EXIT("wasm_input_publish_js", ret);
}

static void imp_011_wasm_module_int_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_module_int_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_module_int_js", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  log_wstr("key", "wasm_module_int_js", args[0]);  if (nargs >= 2) ret = args[1];
  AUDIT_EXIT("wasm_module_int_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_012_emscripten_get_now(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_get_now", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_get_now", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  ret = f64_bits((double)now_ms());
  AUDIT_EXIT("emscripten_get_now", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_013_wasm_print_line_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "wasm_print_line_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("wasm_print_line_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  log_wstr("line", "wasm_print_line_js", args[0]);
  AUDIT_EXIT("wasm_print_line_js", ret);
}

static void imp_014_emscripten_stack_snapshot(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_stack_snapshot", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_stack_snapshot", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("emscripten_stack_snapshot", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_015_emscripten_stack_unwind_buffer(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_stack_unwind_buffer", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_stack_unwind_buffer", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("emscripten_stack_unwind_buffer", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_016_emscripten_asm_const_int(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_asm_const_int", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_asm_const_int", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("emscripten_asm_const_int", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_017_emscripten_get_heap_max(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_get_heap_max", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_get_heap_max", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  ret = (4ULL << 30);
  AUDIT_EXIT("emscripten_get_heap_max", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_018_exit(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "exit", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("exit", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("exit", ret);
}

static void imp_019_invoke_vjj(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_vjj", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_vjj", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("invoke_vjj", ret);
}

static void imp_020_invoke_ij(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_ij", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_ij", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("invoke_ij", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_021_invoke_vj(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_vj", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_vj", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("invoke_vj", ret);
}

static void imp_022_invoke_vjij(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_vjij", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_vjij", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("invoke_vjij", ret);
}

static void imp_023_invoke_jjij(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_jjij", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_jjij", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("invoke_jjij", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_024_invoke_vjii(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_vjii", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_vjii", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("invoke_vjii", ret);
}

static void imp_025_invoke_iji(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_iji", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_iji", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("invoke_iji", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_026_invoke_vjjii(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_vjjii", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_vjjii", 5, args);
  uint64_t ret = 0;
  const int nargs = 5;
  AUDIT_EXIT("invoke_vjjii", ret);
}

static void imp_027_invoke_jjiiijij(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_jjiiijij", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_jjiiijij", 8, args);
  uint64_t ret = 0;
  const int nargs = 8;
  AUDIT_EXIT("invoke_jjiiijij", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_028_invoke_ijji(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_ijji", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_ijji", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("invoke_ijji", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_029_invoke_ijjiii(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "invoke_ijjiii", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("invoke_ijjiii", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("invoke_ijjiii", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_030_emscripten_asm_const_int_sync_on_main_th(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_asm_const_int_sync_on_main_thread", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_asm_const_int_sync_on_main_thread", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("emscripten_asm_const_int_sync_on_main_thread", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_031_proc_exit(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "proc_exit", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("proc_exit", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  audit_line("INFO", "proc_exit", "code=%llu", (unsigned long long)(nargs ? args[0] : 0));
  AUDIT_EXIT("proc_exit", ret);
}

static void imp_032__tzset_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_tzset_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_tzset_js", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  for (int _i = 0; _i < nargs; _i++) app_write(env, args[_i], (uint64_t)0, 8);
  AUDIT_EXIT("_tzset_js", ret);
}

static void imp_033__abort_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_abort_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_abort_js", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("_abort_js", ret);
}

static void imp_034_clock_time_get(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "clock_time_get", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("clock_time_get", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  if (nargs > 2) app_write(env, args[2], now_ms() * 1000000ULL, 8);
  AUDIT_EXIT("clock_time_get", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_035_fd_close(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_close", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_close", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  if (args[0] < 256 && g_files[args[0]]) { fclose(g_files[args[0]]); g_files[args[0]] = NULL; } ret = 0;
  AUDIT_EXIT("fd_close", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_036_emscripten_date_now(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_date_now", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_date_now", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  ret = f64_bits((double)now_ms());
  AUDIT_EXIT("emscripten_date_now", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_037__emscripten_thread_set_strongref(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_thread_set_strongref", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_thread_set_strongref", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("_emscripten_thread_set_strongref", ret);
}

static void imp_038_emscripten_exit_with_live_runtime(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_exit_with_live_runtime", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_exit_with_live_runtime", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("emscripten_exit_with_live_runtime", ret);
}

static void imp_039___syscall_fcntl64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_fcntl64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_fcntl64", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_fcntl64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_040___syscall_openat(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_openat", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_openat", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  log_wstr("path", "__syscall_openat", args[1]); ret = (uint64_t)(uint32_t)host_open((const char *)(g_wasm_mem ? g_wasm_mem + args[1] : NULL));
  AUDIT_EXIT("__syscall_openat", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_041___syscall_ioctl(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_ioctl", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_ioctl", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_ioctl", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_042_fd_write(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_write", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_write", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  ret = wasi_fd_write_impl(env, args[0], args[1], args[2], args[3]);
  AUDIT_EXIT("fd_write", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_043_fd_read(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_read", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_read", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  ret = wasi_fd_read_impl(env, args[0], args[1], args[2], args[3]);
  AUDIT_EXIT("fd_read", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_044___syscall_fstat64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_fstat64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_fstat64", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("__syscall_fstat64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_045___syscall_stat64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_stat64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_stat64", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  log_wstr("path", "__syscall_stat64", args[0]); { const char *_g = g_wasm_mem ? (const char *)(g_wasm_mem + args[0]) : NULL; std::string _h = guest_to_host(_g); struct _stat64 _hs; if (_stat64(_h.c_str(), &_hs) == 0) {   uint8_t _st[112] = {0}; uint32_t _mode = (_hs.st_mode & _S_IFDIR) ? 0x4000 : 0x8000;   uint64_t _size = (uint64_t)_hs.st_size;   memcpy(_st + 16, &_mode, 4); memcpy(_st + 40, &_size, 8);   uint8_t *_p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), args[1]);   if (_p) memcpy(_p, _st, sizeof(_st)); ret = 0; } else ret = (uint64_t)(uint32_t)-44; }
  AUDIT_EXIT("__syscall_stat64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_046___syscall_newfstatat(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_newfstatat", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_newfstatat", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  log_wstr("path", "__syscall_newfstatat", args[1]);
  AUDIT_EXIT("__syscall_newfstatat", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_047___syscall_lstat64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_lstat64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_lstat64", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  log_wstr("path", "__syscall_lstat64", args[0]); { const char *_g = g_wasm_mem ? (const char *)(g_wasm_mem + args[0]) : NULL; std::string _h = guest_to_host(_g); struct _stat64 _hs; if (_stat64(_h.c_str(), &_hs) == 0) {   uint8_t _st[112] = {0}; uint32_t _mode = (_hs.st_mode & _S_IFDIR) ? 0x4000 : 0x8000;   uint64_t _size = (uint64_t)_hs.st_size;   memcpy(_st + 16, &_mode, 4); memcpy(_st + 40, &_size, 8);   uint8_t *_p = (uint8_t *)wasm_runtime_addr_app_to_native(inst_of(env), args[1]);   if (_p) memcpy(_p, _st, sizeof(_st)); ret = 0; } else ret = (uint64_t)(uint32_t)-44; }
  AUDIT_EXIT("__syscall_lstat64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_048___syscall_ftruncate64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_ftruncate64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_ftruncate64", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("__syscall_ftruncate64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_049___syscall_getcwd(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_getcwd", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_getcwd", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("__syscall_getcwd", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_050_environ_sizes_get(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "environ_sizes_get", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("environ_sizes_get", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  app_write(env, args[0], 0, 8); app_write(env, args[1], 0, 8); ret = 0;
  AUDIT_EXIT("environ_sizes_get", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_051_environ_get(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "environ_get", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("environ_get", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  ret = 0;
  AUDIT_EXIT("environ_get", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_052__emscripten_init_main_thread_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_init_main_thread_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_init_main_thread_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  g_tb = (uint64_t)args[0] | ((uint64_t)args[1] << 32); { wasm_module_inst_t _mi = inst_of(env); wasm_function_inst_t _ti = wasm_runtime_lookup_function(_mi, "_emscripten_thread_init"); wasm_function_inst_t _tl = wasm_runtime_lookup_function(_mi, "_emscripten_tls_init"); bool _ok1 = false, _ok2 = false; uint64_t _tret = 0; if (_ti) { uint32_t _ta[7] = {(uint32_t)g_tb, (uint32_t)(g_tb >> 32), 1, 1, 1, 1048576, 0};   _ok1 = wasm_runtime_call_wasm(env, _ti, 7, _ta); } if (_tl) { uint32_t _tz[2] = {0, 0};   _ok2 = wasm_runtime_call_wasm(env, _tl, 0, _tz); memcpy(&_tret, _tz, 8); } audit_line("INFO", "_emscripten_init_main_thread_js", "tb=0x%llx thread_init=%d tls_init=%d tls_base=0x%llx exc=%s",   (unsigned long long)g_tb, _ok1, _ok2, (unsigned long long)_tret, wasm_runtime_get_exception(_mi)); aot_debug_dump_globals(_mi, "CPIN-init-main-thread"); }
  AUDIT_EXIT("_emscripten_init_main_thread_js", ret);
}

static void imp_053__emscripten_thread_mailbox_await(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_thread_mailbox_await", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_thread_mailbox_await", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("_emscripten_thread_mailbox_await", ret);
}

static void imp_054_fd_seek(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_seek", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_seek", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  { FILE *_f = args[0] < 256 ? g_files[args[0]] : NULL;   int64_t _p = 0; if (_f) { fseek(_f, (long)args[1], (int)args[2]); _p = ftell(_f); }   app_write(env, args[3], (uint64_t)_p, 8); ret = 0; }
  AUDIT_EXIT("fd_seek", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_055___syscall_mkdirat(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_mkdirat", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_mkdirat", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_mkdirat", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_056__mktime_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_mktime_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_mktime_js", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  { struct tm _v; tm_read(env, args[0], &_v); ret = (uint64_t)mktime(&_v); }
  AUDIT_EXIT("_mktime_js", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_057__localtime_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_localtime_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_localtime_js", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  { time_t _t = (time_t)args[0]; struct tm _v; localtime_s(&_v, &_t); tm_write(env, args[1], &_v); ret = 0; }
  AUDIT_EXIT("_localtime_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_058__gmtime_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_gmtime_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_gmtime_js", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  { time_t _t = (time_t)args[0]; struct tm _v; gmtime_s(&_v, &_t); tm_write(env, args[1], &_v); ret = 0; }
  AUDIT_EXIT("_gmtime_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_059_fd_pread(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_pread", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_pread", 5, args);
  uint64_t ret = 0;
  const int nargs = 5;
  ret = host_read_fd(args[0], args[1], args[2], args[3], args[4], env);
  AUDIT_EXIT("fd_pread", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_060__emscripten_receive_on_main_thread_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_receive_on_main_thread_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_receive_on_main_thread_js", 7, args);
  uint64_t ret = 0;
  const int nargs = 7;
  AUDIT_EXIT("_emscripten_receive_on_main_thread_js", ret);
  const int rb = 8; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_061_emscripten_check_blocking_allowed(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_check_blocking_allowed", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_check_blocking_allowed", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("emscripten_check_blocking_allowed", ret);
}

static void imp_062___pthread_create_js(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__pthread_create_js", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__pthread_create_js", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  ret = (uint64_t)pthread_create_impl(env, args, "__pthread_create_js");
  AUDIT_EXIT("__pthread_create_js", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_063__emscripten_thread_cleanup(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_thread_cleanup", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_thread_cleanup", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("_emscripten_thread_cleanup", ret);
}

static void imp_064_fd_pwrite(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "fd_pwrite", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("fd_pwrite", 5, args);
  uint64_t ret = 0;
  const int nargs = 5;
  ret = wasi_fd_write_impl(env, args[0], args[1], args[2], args[4]);
  AUDIT_EXIT("fd_pwrite", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_065___syscall_getdents64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_getdents64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_getdents64", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_getdents64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_066___syscall_unlinkat(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_unlinkat", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_unlinkat", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_unlinkat", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_067___syscall_rmdir(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_rmdir", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_rmdir", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("__syscall_rmdir", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_068___syscall_renameat(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_renameat", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_renameat", 4, args);
  uint64_t ret = 0;
  const int nargs = 4;
  AUDIT_EXIT("__syscall_renameat", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_069___syscall_poll(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_poll", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_poll", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_poll", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_070___syscall_statfs64(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_statfs64", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_statfs64", 3, args);
  uint64_t ret = 0;
  const int nargs = 3;
  AUDIT_EXIT("__syscall_statfs64", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_071_emscripten_num_logical_cores(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_num_logical_cores", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_num_logical_cores", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("emscripten_num_logical_cores", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_072__emscripten_system(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_system", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_system", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("_emscripten_system", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_073__emscripten_notify_mailbox_postmessage(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_notify_mailbox_postmessage", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_notify_mailbox_postmessage", 2, args);
  uint64_t ret = 0;
  const int nargs = 2;
  AUDIT_EXIT("_emscripten_notify_mailbox_postmessage", ret);
}

static void imp_074_emscripten_resize_heap(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "emscripten_resize_heap", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("emscripten_resize_heap", 1, args);
  uint64_t ret = 0;
  const int nargs = 1;
  AUDIT_EXIT("emscripten_resize_heap", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_075__emscripten_throw_longjmp(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "_emscripten_throw_longjmp", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("_emscripten_throw_longjmp", 0, args);
  uint64_t ret = 0;
  const int nargs = 0;
  AUDIT_EXIT("_emscripten_throw_longjmp", ret);
}

static void imp_076___syscall_accept4(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_accept4", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_accept4", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_accept4", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_077___syscall_connect(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_connect", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_connect", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_connect", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_078___syscall_getsockname(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_getsockname", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_getsockname", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_getsockname", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_079___syscall_getsockopt(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_getsockopt", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_getsockopt", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_getsockopt", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_080___syscall_recvfrom(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_recvfrom", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_recvfrom", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_recvfrom", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_081___syscall_sendto(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_sendto", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_sendto", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_sendto", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_082___syscall_setsockopt(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_setsockopt", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_setsockopt", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_setsockopt", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_083___syscall_shutdown(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_shutdown", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_shutdown", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_shutdown", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static void imp_084___syscall_socket(wasm_exec_env_t env, uint64_t *args) {
  g_call_seq++;
  if (!args || (uintptr_t)args < 0x1000) { audit_line("ERR", "__syscall_socket", "bad args ptr=%p", (void *)args); return; }
  AUDIT_ENTER("__syscall_socket", 6, args);
  uint64_t ret = 0;
  const int nargs = 6;
  AUDIT_EXIT("__syscall_socket", ret);
  const int rb = 4; if (rb == 4) ret &= 0xffffffffULL;
  uint64_t *raw_ret = args; if (raw_ret) *raw_ret = ret;
}

static NativeSymbol g_syms_env[] = {
  {"wasm_now_ms", (void *)imp_000_wasm_now_ms, NULL, NULL},
  {"wasm_hang_line_js", (void *)imp_001_wasm_hang_line_js, NULL, NULL},
  {"wasm_audio_publish_js", (void *)imp_002_wasm_audio_publish_js, NULL, NULL},
  {"wasm_httpfs_io_start_js", (void *)imp_003_wasm_httpfs_io_start_js, NULL, NULL},
  {"wasm_httpfs_manifest_js", (void *)imp_004_wasm_httpfs_manifest_js, NULL, NULL},
  {"wasm_userdata_page_js", (void *)imp_005_wasm_userdata_page_js, NULL, NULL},
  {"wasm_userdata_put_js", (void *)imp_006_wasm_userdata_put_js, NULL, NULL},
  {"wasm_userdata_delete_js", (void *)imp_007_wasm_userdata_delete_js, NULL, NULL},
  {"wgpu_start_worker", (void *)imp_008_wgpu_start_worker, NULL, NULL},
  {"wasm_has_page_js", (void *)imp_009_wasm_has_page_js, NULL, NULL},
  {"wasm_input_publish_js", (void *)imp_010_wasm_input_publish_js, NULL, NULL},
  {"wasm_module_int_js", (void *)imp_011_wasm_module_int_js, NULL, NULL},
  {"emscripten_get_now", (void *)imp_012_emscripten_get_now, NULL, NULL},
  {"wasm_print_line_js", (void *)imp_013_wasm_print_line_js, NULL, NULL},
  {"emscripten_stack_snapshot", (void *)imp_014_emscripten_stack_snapshot, NULL, NULL},
  {"emscripten_stack_unwind_buffer", (void *)imp_015_emscripten_stack_unwind_buffer, NULL, NULL},
  {"emscripten_asm_const_int", (void *)imp_016_emscripten_asm_const_int, NULL, NULL},
  {"emscripten_get_heap_max", (void *)imp_017_emscripten_get_heap_max, NULL, NULL},
  {"exit", (void *)imp_018_exit, NULL, NULL},
  {"invoke_vjj", (void *)imp_019_invoke_vjj, NULL, NULL},
  {"invoke_ij", (void *)imp_020_invoke_ij, NULL, NULL},
  {"invoke_vj", (void *)imp_021_invoke_vj, NULL, NULL},
  {"invoke_vjij", (void *)imp_022_invoke_vjij, NULL, NULL},
  {"invoke_jjij", (void *)imp_023_invoke_jjij, NULL, NULL},
  {"invoke_vjii", (void *)imp_024_invoke_vjii, NULL, NULL},
  {"invoke_iji", (void *)imp_025_invoke_iji, NULL, NULL},
  {"invoke_vjjii", (void *)imp_026_invoke_vjjii, NULL, NULL},
  {"invoke_jjiiijij", (void *)imp_027_invoke_jjiiijij, NULL, NULL},
  {"invoke_ijji", (void *)imp_028_invoke_ijji, NULL, NULL},
  {"invoke_ijjiii", (void *)imp_029_invoke_ijjiii, NULL, NULL},
  {"emscripten_asm_const_int_sync_on_main_thread", (void *)imp_030_emscripten_asm_const_int_sync_on_main_th, NULL, NULL},
  {"_tzset_js", (void *)imp_032__tzset_js, NULL, NULL},
  {"_abort_js", (void *)imp_033__abort_js, NULL, NULL},
  {"emscripten_date_now", (void *)imp_036_emscripten_date_now, NULL, NULL},
  {"_emscripten_thread_set_strongref", (void *)imp_037__emscripten_thread_set_strongref, NULL, NULL},
  {"emscripten_exit_with_live_runtime", (void *)imp_038_emscripten_exit_with_live_runtime, NULL, NULL},
  {"__syscall_fcntl64", (void *)imp_039___syscall_fcntl64, NULL, NULL},
  {"__syscall_openat", (void *)imp_040___syscall_openat, NULL, NULL},
  {"__syscall_ioctl", (void *)imp_041___syscall_ioctl, NULL, NULL},
  {"__syscall_fstat64", (void *)imp_044___syscall_fstat64, NULL, NULL},
  {"__syscall_stat64", (void *)imp_045___syscall_stat64, NULL, NULL},
  {"__syscall_newfstatat", (void *)imp_046___syscall_newfstatat, NULL, NULL},
  {"__syscall_lstat64", (void *)imp_047___syscall_lstat64, NULL, NULL},
  {"__syscall_ftruncate64", (void *)imp_048___syscall_ftruncate64, NULL, NULL},
  {"__syscall_getcwd", (void *)imp_049___syscall_getcwd, NULL, NULL},
  {"_emscripten_init_main_thread_js", (void *)imp_052__emscripten_init_main_thread_js, NULL, NULL},
  {"_emscripten_thread_mailbox_await", (void *)imp_053__emscripten_thread_mailbox_await, NULL, NULL},
  {"__syscall_mkdirat", (void *)imp_055___syscall_mkdirat, NULL, NULL},
  {"_mktime_js", (void *)imp_056__mktime_js, NULL, NULL},
  {"_localtime_js", (void *)imp_057__localtime_js, NULL, NULL},
  {"_gmtime_js", (void *)imp_058__gmtime_js, NULL, NULL},
  {"_emscripten_receive_on_main_thread_js", (void *)imp_060__emscripten_receive_on_main_thread_js, NULL, NULL},
  {"emscripten_check_blocking_allowed", (void *)imp_061_emscripten_check_blocking_allowed, NULL, NULL},
  {"__pthread_create_js", (void *)imp_062___pthread_create_js, NULL, NULL},
  {"_emscripten_thread_cleanup", (void *)imp_063__emscripten_thread_cleanup, NULL, NULL},
  {"__syscall_getdents64", (void *)imp_065___syscall_getdents64, NULL, NULL},
  {"__syscall_unlinkat", (void *)imp_066___syscall_unlinkat, NULL, NULL},
  {"__syscall_rmdir", (void *)imp_067___syscall_rmdir, NULL, NULL},
  {"__syscall_renameat", (void *)imp_068___syscall_renameat, NULL, NULL},
  {"__syscall_poll", (void *)imp_069___syscall_poll, NULL, NULL},
  {"__syscall_statfs64", (void *)imp_070___syscall_statfs64, NULL, NULL},
  {"emscripten_num_logical_cores", (void *)imp_071_emscripten_num_logical_cores, NULL, NULL},
  {"_emscripten_system", (void *)imp_072__emscripten_system, NULL, NULL},
  {"_emscripten_notify_mailbox_postmessage", (void *)imp_073__emscripten_notify_mailbox_postmessage, NULL, NULL},
  {"emscripten_resize_heap", (void *)imp_074_emscripten_resize_heap, NULL, NULL},
  {"_emscripten_throw_longjmp", (void *)imp_075__emscripten_throw_longjmp, NULL, NULL},
  {"__syscall_accept4", (void *)imp_076___syscall_accept4, NULL, NULL},
  {"__syscall_connect", (void *)imp_077___syscall_connect, NULL, NULL},
  {"__syscall_getsockname", (void *)imp_078___syscall_getsockname, NULL, NULL},
  {"__syscall_getsockopt", (void *)imp_079___syscall_getsockopt, NULL, NULL},
  {"__syscall_recvfrom", (void *)imp_080___syscall_recvfrom, NULL, NULL},
  {"__syscall_sendto", (void *)imp_081___syscall_sendto, NULL, NULL},
  {"__syscall_setsockopt", (void *)imp_082___syscall_setsockopt, NULL, NULL},
  {"__syscall_shutdown", (void *)imp_083___syscall_shutdown, NULL, NULL},
  {"__syscall_socket", (void *)imp_084___syscall_socket, NULL, NULL},
};
static NativeSymbol g_syms_wasi_snapshot_preview1[] = {
  {"proc_exit", (void *)imp_031_proc_exit, NULL, NULL},
  {"clock_time_get", (void *)imp_034_clock_time_get, NULL, NULL},
  {"fd_close", (void *)imp_035_fd_close, NULL, NULL},
  {"fd_write", (void *)imp_042_fd_write, NULL, NULL},
  {"fd_read", (void *)imp_043_fd_read, NULL, NULL},
  {"environ_sizes_get", (void *)imp_050_environ_sizes_get, NULL, NULL},
  {"environ_get", (void *)imp_051_environ_get, NULL, NULL},
  {"fd_seek", (void *)imp_054_fd_seek, NULL, NULL},
  {"fd_pread", (void *)imp_059_fd_pread, NULL, NULL},
  {"fd_pwrite", (void *)imp_064_fd_pwrite, NULL, NULL},
};

static bool register_all(void) {
  audit_line("INFO", "register_all", "env=%d wasi=%d",
    (int)(sizeof(g_syms_env)/sizeof(NativeSymbol)),
    (int)(sizeof(g_syms_wasi_snapshot_preview1)/sizeof(NativeSymbol)));
  bool ok1 = wasm_runtime_register_natives_raw("env", g_syms_env,
             sizeof(g_syms_env)/sizeof(NativeSymbol));
  bool ok2 = wasm_runtime_register_natives_raw("wasi_snapshot_preview1", g_syms_wasi_snapshot_preview1,
             sizeof(g_syms_wasi_snapshot_preview1)/sizeof(NativeSymbol));
  audit_line("INFO", "register_all", "ok1=%d ok2=%d", ok1, ok2);
  return ok1 && ok2;
}

static uint8_t *read_file(const char *path, uint32_t *size) {
  AUDIT_ENTER("read_file", 1, (uint64_t *)0);
  FILE *f = fopen(path, "rb"); if (!f) { audit_line("ERR","read_file","fopen failed %s",path); *size=0; return NULL; }
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  uint8_t *buf = (uint8_t *)malloc((size_t)n + 1);
  size_t got = fread(buf, 1, (size_t)n, f); fclose(f);
  *size = (uint32_t)got;
  AUDIT_EXIT("read_file", got);
  return buf;
}

static wasm_module_t load_aot(uint8_t *buf, uint32_t size) {
  AUDIT_ENTER("load_aot", 2, (uint64_t *)0);
  char err[256] = {0};
  wasm_module_t m = wasm_runtime_load(buf, size, err, sizeof(err));
  audit_line("INFO", "load_aot", "module=%p err=%s", (void *)m, err);
  AUDIT_EXIT("load_aot", (uint64_t)(uintptr_t)m);
  return m;
}

static wasm_module_inst_t instantiate(wasm_module_t m) {
  AUDIT_ENTER("instantiate", 1, (uint64_t *)0);
  InstantiationArgs2 *args = NULL; char err[256] = {0};
  if (!wasm_runtime_instantiation_args_create(&args)) { audit_line("ERR","instantiate","args_create failed",0); AUDIT_EXIT("instantiate",0); return NULL; }
  wasm_runtime_instantiation_args_set_default_stack_size(args, 16 * 1024 * 1024);
  wasm_runtime_instantiation_args_set_host_managed_heap_size(args, 64 * 1024 * 1024);
  wasm_module_inst_t inst = wasm_runtime_instantiate_ex2(m, args, err, sizeof(err));
  wasm_runtime_instantiation_args_destroy(args);
  audit_line("INFO", "instantiate", "inst=%p err=%s", (void *)inst, err);
  AUDIT_EXIT("instantiate", (uint64_t)(uintptr_t)inst);
  return inst;
}

static LONG CALLBACK veh_handler(PEXCEPTION_POINTERS ep) {
  if (ep && ep->ExceptionRecord && ep->ExceptionRecord->ExceptionCode == 0xC0000005) {
    fprintf(stdout, "[VEH] AV addr=%p ip=%p\n",
      (void *)ep->ExceptionRecord->ExceptionInformation[1],
      (void *)ep->ContextRecord->Rip);
    void *_bt[16]; unsigned short _n = CaptureStackBackTrace(0, 16, _bt, NULL), _k;
    for (_k = 0; _k < _n; _k++) fprintf(stdout, "[VEH] bt%u %p\n", _k, _bt[_k]);
    fflush(stdout);
  }
  return EXCEPTION_CONTINUE_SEARCH;
}

static uint64_t build_game_argv(void) {
  static const char *a[] = { "game", "-rootdir=/game/", "-wgpu", "-nodisplaycalibration",
    "-noSocialClub", "-pc:nosocialclub", "-nonetwork", "-output",
    "-width=1920", "-height=1080", "-forceResolution", "-textureQuality=2",
    "-shadowQuality=0", "-reflectionQuality=1", "-particleQuality=0",
    "-grassQuality=0", "-cityDensity=0", "-lodScale=0", "-frameLimit=0" };
  const int n = (int)(sizeof(a) / sizeof(a[0]));
  if (!g_wasm_mem) return 0;
  uint64_t base = 0x60000000ULL;
  uint8_t *p = g_wasm_mem + base;
  uint64_t ptrs[32]; int i;
  for (i = 0; i < n; i++) {
    size_t l = strlen(a[i]) + 1;
    memcpy(p, a[i], l); ptrs[i] = base + (uint64_t)(p - (g_wasm_mem + base)); p += l;
  }
  while (((uintptr_t)p & 7) != 0) p++;
  uint64_t arr = base + (uint64_t)(p - (g_wasm_mem + base));
  for (i = 0; i < n; i++) { uint64_t v = ptrs[i]; memcpy(p, &v, 8); p += 8; }
  uint64_t zero = 0; memcpy(p, &zero, 8);
  audit_line("INFO", "build_game_argv", "argc=%d argv=0x%llx", n, (unsigned long long)arr);
  return arr;
}

static void patch_func_ret(wasm_module_inst_t inst, uint32_t idx) {
  void *p = wasm_runtime_get_func_native_ptr(inst, idx);
  if (!p) { audit_line("ERR", "patch_func_ret", "no ptr idx=%u", idx); return; }
  void *page = (void *)((uintptr_t)p & ~(uintptr_t)0xFFF);
  DWORD old = 0;
  if (!VirtualProtect(page, 4096, PAGE_EXECUTE_READWRITE, &old)) {
    audit_line("ERR", "patch_func_ret", "VirtualProtect failed idx=%u", idx); return; }
  unsigned char *_b = (unsigned char *)p;
  PatchRec _rec; _rec.addr = (uintptr_t)p;
  memcpy(_rec.save, _b, 4); g_patches.push_back(_rec);
  _b[0] = 0x31; _b[1] = 0xC0; _b[2] = 0xC3; /* xor eax,eax; ret -> NULL */
  FlushInstructionCache(GetCurrentProcess(), p, 4);
  VirtualProtect(page, 4096, old, &old);
  audit_line("INFO", "patch_func_ret", "idx=%u ptr=%p op=nullret", idx, p);
}

static void patch_ud2(wasm_module_inst_t inst, uint32_t idx) {
  unsigned char *p = (unsigned char *)wasm_runtime_get_func_native_ptr(inst, idx);
  unsigned char *q = (unsigned char *)wasm_runtime_get_func_native_ptr(inst, idx + 1);
  if (!p) { audit_line("ERR", "patch_ud2", "no ptr idx=%u", idx); return; }
  size_t n = (q && q > p) ? (size_t)(q - p) : 262144; if (n > 262144) n = 262144;
  void *page = (void *)((uintptr_t)p & ~(uintptr_t)0xFFF);
  DWORD old = 0; VirtualProtect(page, n + 4096, PAGE_EXECUTE_READWRITE, &old);
  size_t cnt = 0;
  for (size_t i = 0; i + 1 < n; i++) if (p[i] == 0x0F && p[i + 1] == 0x0B) {
    PatchRec _rec; _rec.addr = (uintptr_t)(p + i); memcpy(_rec.save, p + i, 2); g_patches.push_back(_rec);
    p[i] = 0x90; p[i + 1] = 0x90; cnt++;
  }
  FlushInstructionCache(GetCurrentProcess(), p, n); VirtualProtect(page, n + 4096, old, &old);
  audit_line("INFO", "patch_ud2", "idx=%u ptr=%p range=%u patched=%u", idx, (void *)p, (unsigned)n, (unsigned)cnt);
}

static void patch_poke_app(wasm_module_inst_t inst, uint64_t app, const char *hex) {
  unsigned char *base = (unsigned char *)wasm_runtime_get_func_native_ptr(inst, 103);
  if (!base) return;
  unsigned char *p = base + (size_t)(app - 0x1998b564ULL);
  void *page = (void *)((uintptr_t)p & ~(uintptr_t)0xFFF);
  DWORD old = 0; VirtualProtect(page, 4096, PAGE_EXECUTE_READWRITE, &old);
  size_t n = strlen(hex) / 2;
  for (size_t i = 0; i < n; i++) { unsigned int v = 0; sscanf(hex + i * 2, "%2x", &v); p[i] = (unsigned char)v; }
  FlushInstructionCache(GetCurrentProcess(), p, n); VirtualProtect(page, 4096, old, &old);
  audit_line("INFO", "patch_poke_app", "app=0x%llx n=%u", (unsigned long long)app, (unsigned)n);
}

static void patch_nop_app(wasm_module_inst_t inst, uint64_t app, size_t len) {
  unsigned char *base = (unsigned char *)wasm_runtime_get_func_native_ptr(inst, 103);
  if (!base) { audit_line("ERR", "patch_nop_app", "no main ptr", 0); return; }
  unsigned char *p = base + (size_t)(app - 0x1998b564ULL);
  void *page = (void *)((uintptr_t)p & ~(uintptr_t)0xFFF);
  DWORD old = 0; VirtualProtect(page, 4096, PAGE_EXECUTE_READWRITE, &old);
  memset(p, 0x90, len); FlushInstructionCache(GetCurrentProcess(), p, len);
  VirtualProtect(page, 4096, old, &old);
  audit_line("INFO", "patch_nop_app", "app=0x%llx len=%u ptr=%p", (unsigned long long)app, (unsigned)len, (void *)p);
}

static int call_main(wasm_module_inst_t inst, int argc, char **argv) {
  AUDIT_ENTER("call_main", 3, (uint64_t *)0);
  (void)argc; (void)argv;
  wasm_function_inst_t f = wasm_runtime_lookup_function(inst, "__main_argc_argv");
  audit_line("INFO", "call_main", "func=%p", (void *)f);
  if (!f) { AUDIT_EXIT("call_main", -1); return -1; }
  wasm_exec_env_t env = wasm_runtime_get_exec_env_singleton(inst);
  aot_debug_dump_globals(inst, "CP1-after-instantiate");
  { const char *_p = getenv("GTA_AOT_SKIP_FUNC");
    if (_p) { char _b[512]; strncpy(_b, _p, sizeof(_b) - 1); _b[sizeof(_b) - 1] = 0;
      char *_t = strtok(_b, ",");
      while (_t) { patch_func_ret(inst, (uint32_t)strtoul(_t, NULL, 0)); _t = strtok(NULL, ","); } } }
  { const char *_p = getenv("GTA_AOT_NOP_UD2");
    if (_p) patch_ud2(inst, (uint32_t)strtoul(_p, NULL, 0)); }
  { const char *_np = getenv("GTA_AOT_NOP_AT");
    if (_np) { uint64_t _a = strtoull(_np, NULL, 0); size_t _l = 6;
      const char *_c = strchr(_np, 0x2c); if (_c) _l = (size_t)strtoul(_c + 1, NULL, 0);
      patch_nop_app(inst, _a, _l); } }
  { const char *_pk = getenv("GTA_AOT_POKE");
    if (_pk) { uint64_t _a = strtoull(_pk, NULL, 0); const char *_c = strchr(_pk, 0x3a);
      if (_c) patch_poke_app(inst, _a, _c + 1); } }
  /* emscripten main-thread thread/TLS init: JS does this inside the import;
     file 04 moves it there. Gate the old early path for A/B. */
  if (getenv("GTA_AOT_EARLY_TLS")) {
    uint64_t _tb = g_tb ? g_tb : 0x1c399c8ULL;
    wasm_function_inst_t _ti = wasm_runtime_lookup_function(inst, "_emscripten_thread_init");
    if (_ti) { uint32_t _a[8] = {(uint32_t)_tb, (uint32_t)(_tb >> 32), 1, 1, 1, 1048576, 0, 0};
      bool _ok = wasm_runtime_call_wasm(env, _ti, 7, _a);
      audit_line("INFO", "call_main", "thread_init ok=%d exc=%s", _ok, wasm_runtime_get_exception(inst)); aot_debug_dump_globals(inst, "CP2-after-thread-init"); }
    wasm_function_inst_t _tl = wasm_runtime_lookup_function(inst, "_emscripten_tls_init");
    if (_tl) { uint32_t _z[2] = {0, 0}; bool _ok = wasm_runtime_call_wasm(env, _tl, 0, _z);
      uint64_t _tret = 0; memcpy(&_tret, _z, 8);
      audit_line("INFO", "call_main", "tls_init ok=%d ret=0x%llx tb=0x%llx exc=%s", _ok, (unsigned long long)_tret, (unsigned long long)_tb, wasm_runtime_get_exception(inst)); aot_debug_dump_globals(inst, "CP3-after-tls-init"); }
  }
  /* emstandalone command modules expect _start to run __wasm_call_ctors
     before main; calling main alone leaves C++ statics uninitialised. */
  {
    wasm_function_inst_t ctors = wasm_runtime_lookup_function(inst, "__wasm_call_ctors");
    audit_line("INFO", "call_main", "__wasm_call_ctors=%p", (void *)ctors);
    if (ctors && !getenv("GTA_AOT_SKIP_CTORS")) {
      uint32_t ca[1] = {0};
      bool cok = wasm_runtime_call_wasm(env, ctors, 0, ca);
      { wasm_memory_inst_t _mi = wasm_runtime_get_default_memory(inst);
        audit_line("INFO", "call_main", "after ctors memory pages=%llu bytes=%llu",
          (unsigned long long)(_mi ? wasm_memory_get_cur_page_count(_mi) : 0),
          (unsigned long long)(_mi ? wasm_memory_get_cur_page_count(_mi) * wasm_memory_get_bytes_per_page(_mi) : 0)); }
      audit_line("INFO", "call_main", "ctors ok=%d exc=%s", cok, wasm_runtime_get_exception(inst)); aot_debug_dump_globals(inst, "CP4-after-ctors");
      if (!cok) {
        wasm_runtime_dump_call_stack(env);
        if (!getenv("GTA_AOT_CONT_AFTER_CTORS")) { AUDIT_EXIT("call_main", -3); return -3; }
        audit_line("INFO", "call_main", "continuing to main after ctors failure");
      }
    }
  }
  if (getenv("GTA_AOT_FIX_R14")) {
    void *_gd = 0; uint64_t _tls = 0;
    memcpy(&_gd, (char *)inst + 0x18, 8); if (_gd) memcpy(&_tls, (char *)_gd + 0x78, 8);
    memcpy((char *)inst + 0x244, &_tls, 8);
    audit_line("INFO", "call_main", "fix_r14 wrote tls=0x%llx to inst+0x244", (unsigned long long)_tls);
  }
  if (getenv("GTA_AOT_SHIFT_GLOBALS")) {
    void *_gd = 0; uint32_t _gdsz = 0;
    memcpy(&_gd, (char *)inst + 0x18, 8); memcpy(&_gdsz, (char *)inst + 0x10, 4);
    if (_gd && _gdsz > 16) { memmove(_gd, (char *)_gd + 4, _gdsz - 4);
      audit_line("INFO", "call_main", "shifted globals by -4 size=%u", _gdsz); }
  }
  /* Emscripten httpfs init: wasm func192 (Load) is table slot 64; JS reaches it
     through FindFileBegin("/game/..."). Call it directly so manifest + active flag
     are set up before main, exactly like the working JS harness. */
  if (!getenv("GTA_AOT_NO_FORCELOAD")) {
    uint32_t _lz[2] = {0, 0};
    bool _lok = wasm_runtime_call_indirect(env, 64, 0, _lz);
    audit_line("INFO", "call_main", "httpfs_Load ok=%d exc=%s", _lok, wasm_runtime_get_exception(inst)); aot_debug_dump_globals(inst, "CP5-after-Load");
  }
  /* exact harness_native.cpp startup writes (harness.js setupEnv/onRuntimeInitialized) */
  if (g_wasm_mem) {
    g_wasm_mem[8321672] = 1; /* forceHttpfs: httpfs active byte */
    *(int32_t *)(g_wasm_mem + 8348848) = 1; /* dev flag: -wgpu, skip getenv(WGPU) path */
    uint32_t *_sm = (uint32_t *)(g_wasm_mem + 6583436 + 440); if (*_sm == 0) *_sm = 2; /* startMode Sandbox */
    const uint32_t _ring = 0x70000000;
    memset(g_wasm_mem + _ring, 0, 64);
    uint32_t *_rh = (uint32_t *)(g_wasm_mem + _ring);
    _rh[0] = (int32_t)(_ring + 64); _rh[1] = (int32_t)(_ring + 64); _rh[5] = 1; /* head/tail/sleeping */
    audit_line("INFO", "call_main", "harness writes done httpfs=%u startMode=%u ring_head=%d",
      g_wasm_mem[8321672], *_sm, (int)_rh[0]);
    if (!getenv("GTA_AOT_NO_FORCELOAD")) {
      g_io_table = 8284736; /* wasm_httpfs_pread slot table base (JS io_start arg) */
      httpfs_io_start_impl();
    }
    uint64_t _rp = 0; memcpy(&_rp, g_wasm_mem + 25030024, 8);
    const char *_rs = _rp ? (const char *)(g_wasm_mem + _rp) : "(null)";
    char _rbuf[256] = {0}; if (_rp) { strncpy(_rbuf, _rs, 255); _rbuf[255] = 0; }
    audit_line("INFO", "call_main", "rootdir_global ptr=0x%llx val=%s fallback3122485=%s",
      (unsigned long long)_rp, _rp ? _rbuf : "(null)", (const char *)(g_wasm_mem + 3122485));
  }
  char *_av[] = { (char *)"./this.program", (char *)"-rootdir=/game/", (char *)"-wgpu",
    (char *)"-nodisplaycalibration", (char *)"-noSocialClub", (char *)"-pc:nosocialclub",
    (char *)"-nonetwork", (char *)"-output", (char *)"-width=1920", (char *)"-height=1080",
    (char *)"-forceResolution", (char *)"-textureQuality=2", (char *)"-shadowQuality=0",
    (char *)"-reflectionQuality=1", (char *)"-particleQuality=0", (char *)"-grassQuality=0",
    (char *)"-cityDensity=0", (char *)"-lodScale=0", (char *)"-frameLimit=0", NULL };
  bool ok = wasm_application_execute_main(inst, 19, _av);
  audit_line("INFO", "call_main", "ok=%d exc=%s", ok, wasm_runtime_get_exception(inst));
  { uint64_t _e1dc = 0, _e230 = 0, _e1d4 = 0; memcpy(&_e1dc, (char *)inst + 0x1dc, 8);
    memcpy(&_e230, (char *)inst + 0x230, 8); memcpy(&_e1d4, (char *)inst + 0x1d4, 8);
    audit_line("INFO", "call_main", "envfields e1dc=0x%llx e230=0x%llx e1d4=0x%llx sum330=0x%llx",
      (unsigned long long)_e1dc, (unsigned long long)_e230, (unsigned long long)_e1d4,
      (unsigned long long)(_e1dc + 0x330)); }
  { void *_mi = (void *)wasm_runtime_get_default_memory(inst); uint64_t _b50 = 0, _b58 = 0, _b60 = 0, _b68 = 0;
    if (_mi) { memcpy(&_b50, (char *)_mi + 0x50, 8); memcpy(&_b58, (char *)_mi + 0x58, 8);
      memcpy(&_b60, (char *)_mi + 0x60, 8); memcpy(&_b68, (char *)_mi + 0x68, 8); }
    audit_line("INFO", "call_main", "membounds mi=%p b50=0x%llx b58=0x%llx b60=0x%llx b68=0x%llx",
      _mi, (unsigned long long)_b50, (unsigned long long)_b58,
      (unsigned long long)_b60, (unsigned long long)_b68); }
  { uint64_t _v200 = 0, _v208 = 0, _v248 = 0, _v250 = 0;
    memcpy(&_v200, (char *)inst + 0x200, 8); memcpy(&_v208, (char *)inst + 0x208, 8);
    memcpy(&_v248, (char *)inst + 0x248, 8); memcpy(&_v250, (char *)inst + 0x250, 8);
    audit_line("INFO", "call_main", "instfields v200=0x%llx v208=0x%llx v248=0x%llx v250=0x%llx",
      (unsigned long long)_v200, (unsigned long long)_v208,
      (unsigned long long)_v248, (unsigned long long)_v250); }
  { uint64_t _i60 = 0, _i68 = 0, _i50 = 0, _i58 = 0;
    memcpy(&_i50, (char *)inst + 0x50, 8); memcpy(&_i58, (char *)inst + 0x58, 8);
    memcpy(&_i60, (char *)inst + 0x60, 8); memcpy(&_i68, (char *)inst + 0x68, 8);
    audit_line("INFO", "call_main", "instbounds i50=0x%llx i58=0x%llx i60=0x%llx i68=0x%llx",
      (unsigned long long)_i50, (unsigned long long)_i58,
      (unsigned long long)_i60, (unsigned long long)_i68); }
  { void *_memarr = 0, *_mem0 = 0; uint64_t _m60 = 0, _m68 = 0;
    memcpy(&_memarr, (char *)inst + 8, 8); if (_memarr) memcpy(&_mem0, (char *)_memarr, 8);
    if (_mem0) { memcpy(&_m60, (char *)_mem0 + 0x60, 8); memcpy(&_m68, (char *)_mem0 + 0x68, 8); }
    audit_line("INFO", "call_main", "memchain arr=%p mem0=%p m60=0x%llx m68=0x%llx",
      _memarr, _mem0, (unsigned long long)_m60, (unsigned long long)_m68); }
  { uint64_t _r14dc = 0; memcpy(&_r14dc, (char *)inst + 0x244, 8);
    audit_line("INFO", "call_main", "r14field r14_1dc=0x%llx plus330=0x%llx",
      (unsigned long long)_r14dc, (unsigned long long)(_r14dc + 0x330)); }
  if (!ok) {
    audit_line("INFO", "call_main", "dumping wasm call stack", 0);
    wasm_runtime_dump_call_stack(env);
    fflush(stdout);
  }
  if (g_wasm_mem) { uint32_t _tbcount = 0; memcpy(&_tbcount, g_wasm_mem + 12370200, 4);
    audit_line("INFO", "call_main", "timebar_count=%u", _tbcount); }
  if (g_wasm_mem) { uint64_t _rp2 = 0; memcpy(&_rp2, g_wasm_mem + 25030024, 8);
    char _rb2[256] = {0}; if (_rp2) { strncpy(_rb2, (const char *)(g_wasm_mem + _rp2), 255); _rb2[255] = 0; }
    audit_line("INFO", "call_main", "rootdir_after_main ptr=0x%llx val=%s",
      (unsigned long long)_rp2, _rp2 ? _rb2 : "(null)");
    { int _g1 = 0; int64_t _g2 = 0; int64_t _g3 = 0; memcpy(&_g1, g_wasm_mem + 8348848, 4);
      memcpy(&_g2, g_wasm_mem + 8349736, 8); memcpy(&_g3, g_wasm_mem + 8349728, 4);
      const char *_s1 = (const char *)(g_wasm_mem + 135449); const char *_s2 = (const char *)(g_wasm_mem + 2413881);
      audit_line("INFO", "call_main", "mainglobals dev_flag=%d argv_ptr=0x%llx argc=%lld str135449=%.80s env2413881=%.80s",
        _g1, (unsigned long long)_g2, (long long)_g3, _s1, _s2); }
    if (_rp2 && _rp2 + 8 * 20 < 0xc4000000ULL) { uint64_t _e[20]; memcpy(_e, g_wasm_mem + _rp2, 8 * 20);
      audit_line("INFO", "call_main", "argvdump e0=0x%llx e1=0x%llx e2=0x%llx e18=0x%llx e19=0x%llx",
        (unsigned long long)_e[0], (unsigned long long)_e[1], (unsigned long long)_e[2], (unsigned long long)_e[18], (unsigned long long)_e[19]);
      if (_e[0] && _e[0] + 64 < 0xc4000000ULL) { char _s0[64] = {0}; memcpy(_s0, g_wasm_mem + _e[0], 63);
        audit_line("INFO", "call_main", "argvdump s0=%s", _s0); }
      if (_e[1] && _e[1] + 64 < 0xc4000000ULL) { char _s1[64] = {0}; memcpy(_s1, g_wasm_mem + _e[1], 63);
        audit_line("INFO", "call_main", "argvdump s1=%s", _s1); } }
    { uint64_t _dev = 0, _gp1 = 0, _gp2 = 0, _tid = 0, _prog = 0, _av0 = 0; uint32_t _a0 = 0, _rsz = 0;
      uint8_t _b836 = 0, _b978 = 0;
      memcpy(&_dev, g_wasm_mem + 9780688, 8); memcpy(&_gp1, g_wasm_mem + 8348856, 8);
      memcpy(&_gp2, g_wasm_mem + 8348872, 8); memcpy(&_tid, g_wasm_mem + 9780616, 8);
      memcpy(&_prog, g_wasm_mem + 6593912, 8); memcpy(&_av0, g_wasm_mem + 10590160, 8);
      memcpy(&_a0, g_wasm_mem + 0, 4); memcpy(&_rsz, g_wasm_mem + 6583408, 4);
      _b836 = g_wasm_mem[8361120]; _b978 = g_wasm_mem[9780961];
      audit_line("INFO", "call_main", "contglobals dev9780688=0x%llx gp8348856=0x%llx gp8348872=0x%llx tid=0x%llx prog6593912=0x%llx av0=0x%llx m0=%u ringsz=%u b836=%u b978=%u",
        (unsigned long long)_dev, (unsigned long long)_gp1, (unsigned long long)_gp2, (unsigned long long)_tid,
        (unsigned long long)_prog, (unsigned long long)_av0, _a0, _rsz, _b836, _b978); } }
  AUDIT_EXIT("call_main", ok ? 0 : -2);
  return ok ? 0 : -2;
}

int main(int argc, char **argv) {
  audit_open();
  AddVectoredExceptionHandler(1, veh_handler);
  audit_line("INFO", "main", "module_base=%p", (void *)GetModuleHandle(NULL));
  fprintf(stdout, "MODULE_BASE=%p\n", (void *)GetModuleHandle(NULL)); fflush(stdout);
  audit_line("CANARY", "main", "audit-alive aot-host-v2-tls-in-import");
  AUDIT_ENTER("main", 2, (uint64_t *)0);
  const char *path = argc > 1 ? argv[1] : "E:/gta/gta-sl1-opt1.aot";
  uint32_t size = 0; uint8_t *buf = read_file(path, &size);
  if (!buf) { AUDIT_EXIT("main", -1); return 1; }
  if (!wasm_runtime_init()) { audit_line("ERR","main","wasm_runtime_init failed",0); AUDIT_EXIT("main",-2); return 2; }
  wasm_runtime_set_max_thread_num(32);
  wasm_runtime_set_log_level(WASM_LOG_LEVEL_DEBUG);
  register_all();
  wasm_module_t m = load_aot(buf, size);
  if (!m) { AUDIT_EXIT("main", -3); return 3; }
  wasm_module_inst_t inst = instantiate(m);
  if (!inst) { AUDIT_EXIT("main", -4); return 4; }
  {
    wasm_memory_inst_t mi = wasm_runtime_get_default_memory(inst);
    audit_line("INFO", "main", "memory inst=%p cur_pages=%llu max_pages=%llu bytes=%llu",
      (void *)mi,
      (unsigned long long)(mi ? wasm_memory_get_cur_page_count(mi) : 0),
      (unsigned long long)(mi ? wasm_memory_get_max_page_count(mi) : 0),
      (unsigned long long)(mi ? wasm_memory_get_cur_page_count(mi) * wasm_memory_get_bytes_per_page(mi) : 0));
  }
  {
    wasm_memory_inst_t mi = wasm_runtime_get_default_memory(inst);
    uint8_t *base = mi ? (uint8_t *)wasm_memory_get_base_address(mi) : NULL;
    g_wasm_mem = base;
    if (base) {
      char s[65] = {0};
      memcpy(s, base + 3128086, 48); s[48] = 0;
      audit_line("INFO", "main", "DATA_CHECK addr=3128086 str=%s", s);
      memcpy(s, base + 3122734, 24); s[24] = 0;
      audit_line("INFO", "main", "DATA_CHECK addr=3122734 str=%s", s);
    }
    else audit_line("ERR", "main", "DATA_CHECK no memory base", 0);
  }
  if (getenv("GTA_AOT_CALL_MAIN")) call_main(inst, argc, argv);
  audit_line("INFO", "main", "LOADED inst=%p imports_called=%llu", (void *)inst, (unsigned long long)g_call_seq);
  AUDIT_EXIT("main", 0);
  wasm_runtime_deinstantiate(inst);
  wasm_runtime_unload(m);
  wasm_runtime_destroy();
  free(buf);
  if (g_audit_file) { fclose(g_audit_file); g_audit_file = NULL; }
  DeleteCriticalSection(&g_audit_lock);
  return 0;
}
