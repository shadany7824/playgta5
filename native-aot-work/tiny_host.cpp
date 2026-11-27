#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "wasm_export.h"

extern "C" void aot_debug_dump_globals(wasm_module_inst_t inst, const char *tag);

static char *read_file(const char *path, uint32_t *size) {
  FILE *f = fopen(path, "rb");
  if (!f) return NULL;
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  char *b = (char *)malloc(n); fread(b, 1, n, f); fclose(f);
  *size = (uint32_t)n; return b;
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "E:/gta/_tmp_claude/tiny-g.aot";
  uint32_t sz = 0; char *buf = read_file(path, &sz);
  if (!buf) { printf("no file\n"); return 1; }
  if (!wasm_runtime_init()) { printf("init failed\n"); return 2; }
  char err[256] = {0};
  wasm_module_t mod = wasm_runtime_load((uint8_t *)buf, sz, err, sizeof(err));
  if (!mod) { printf("load failed: %s\n", err); return 3; }
  wasm_module_inst_t inst = wasm_runtime_instantiate(mod, 65536, 65536, err, sizeof(err));
  if (!inst) { printf("inst failed: %s\n", err); return 4; }
  aot_debug_dump_globals(inst, "TINY-before");
  wasm_function_inst_t f = wasm_runtime_lookup_function(inst, "f");
  printf("func f=%p\n", (void *)f);
  if (f) {
    wasm_exec_env_t env = wasm_runtime_get_exec_env_singleton(inst);
    uint32_t a[2] = {0, 0};
    bool ok = wasm_runtime_call_wasm(env, f, 0, a);
    printf("call ok=%d exc=%s\n", ok, wasm_runtime_get_exception(inst));
    aot_debug_dump_globals(inst, "TINY-after");
    void *gd = 0; memcpy(&gd, (char *)inst + 0x18, 8);
    unsigned char *p = (unsigned char *)gd;
    printf("global_data=%p bytes=", gd);
    for (int i = 0; i < 32; i++) printf("%02x", p[i]);
    printf("\n");
  }
  wasm_runtime_deinstantiate(inst);
  wasm_runtime_unload(mod);
  wasm_runtime_destroy();
  return 0;
}
