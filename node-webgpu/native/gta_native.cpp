#include <node_api.h>
#include <cstdint>
#include <vector>

struct Cmd { int32_t op, pos, n, tail; };

static bool arg_i32(napi_env env, napi_value v, int32_t *out) {
  return napi_get_value_int32(env, v, out) == napi_ok;
}

static napi_value make_i32_array(napi_env env, const std::vector<Cmd> &cmds, int field) {
  size_t n = cmds.size();
  napi_value buf, arr;
  if (napi_create_arraybuffer(env, n ? n * sizeof(int32_t) : sizeof(int32_t), nullptr, &buf) != napi_ok) return nullptr;
  int32_t *p = nullptr;
  if (napi_get_arraybuffer_info(env, buf, reinterpret_cast<void **>(&p), nullptr) != napi_ok) return nullptr;
  if (p) for (size_t i = 0; i < n; ++i) p[i] = field == 0 ? cmds[i].op : field == 1 ? cmds[i].pos : field == 2 ? cmds[i].n : cmds[i].tail;
  if (napi_create_typedarray(env, napi_int32_array, n, buf, 0, &arr) != napi_ok) return nullptr;
  return arr;
}

static napi_value Decode(napi_env env, napi_callback_info info) {
  size_t argc = 5;
  napi_value args[5];
  if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) != napi_ok) return nullptr;
  void *data = nullptr;
  if (napi_get_arraybuffer_info(env, args[0], &data, nullptr) != napi_ok || !data) return nullptr;
  const uint32_t *w = static_cast<const uint32_t *>(data);
  int32_t ringW = 0, tail = 0, head = 0, ringData = 0;
  if (!arg_i32(env, args[1], &ringW) || !arg_i32(env, args[2], &tail) || !arg_i32(env, args[3], &head) || !arg_i32(env, args[4], &ringData)) return nullptr;

  std::vector<Cmd> cmds;
  int32_t pos = tail;
  for (;;) {
    if (pos == head) break;
    const uint32_t *base = w + (ringW + (pos >> 2));
    int32_t op = static_cast<int32_t>(base[0]);
    int32_t n = static_cast<int32_t>(base[1]);
    if (n < 0 || n > 1000000) break;
    if (op == 1) { cmds.push_back({op, ringW + (pos >> 2), n, ringData}); pos = ringData; continue; }
    cmds.push_back({op, ringW + (pos >> 2), n, pos + n * 4 + 8});
    pos += n * 4 + 8;
  }

  napi_value out, ops, positions, counts, tails;
  if (napi_create_object(env, &out) != napi_ok) return nullptr;
  ops = make_i32_array(env, cmds, 0);
  positions = make_i32_array(env, cmds, 1);
  counts = make_i32_array(env, cmds, 2);
  tails = make_i32_array(env, cmds, 3);
  if (!ops || !positions || !counts || !tails) return nullptr;
  napi_set_named_property(env, out, "ops", ops);
  napi_set_named_property(env, out, "pos", positions);
  napi_set_named_property(env, out, "n", counts);
  napi_set_named_property(env, out, "tails", tails);
  return out;
}

static napi_value Init(napi_env env, napi_value exports) {
  napi_value fn;
  napi_create_function(env, nullptr, 0, Decode, nullptr, &fn);
  napi_set_named_property(env, exports, "decode", fn);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
