#include <node_api.h>
static napi_value Bench(napi_env env, napi_callback_info info) {
  size_t argc = 1;
  napi_value args[1];
  napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
  void *data; size_t len;
  napi_get_arraybuffer_info(env, args[0], &data, &len);
  volatile uint64_t sum = 0;
  const uint32_t *p = static_cast<const uint32_t *>(data);
  for (size_t i = 0; i < len / 4; ++i) sum += p[i];
  napi_value out;
  napi_create_uint32(env, (uint32_t)(sum & 0xffffffff), &out);
  return out;
}
static napi_value Init(napi_env env, napi_value exports) {
  napi_value fn;
  napi_create_function(env, nullptr, 0, Bench, nullptr, &fn);
  napi_set_named_property(env, exports, "bench", fn);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
