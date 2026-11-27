# Force is_runtime_thread=1 after wasm instantiation by calling the exported set_thread_state.
# set_thread_state(thread_ptr, is_main_thread, is_runtime_thread, supports_wait)
# We need valid thread_ptr; the engine sets it during init. Instead, patch the WAT-level global
# is easier: but we can't recompile. Alternative: check if __wasm_call_ctors ran by looking at
# whether emscripten_init_main_thread_js import was called. Let's add that import logging.

g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
# Find the JS import emscripten_init_main_thread_js definition
old = 'function __emscripten_init_main_thread_js(tb){tb=bigintToI53Checked(tb);var can_block=!ENVIRONMENT_IS_WEB;__emscripten_thread_init(tb,!ENVIRONMENT_IS_WORKER,1,can_block,1048576,false);PThread.threadInitTLS()}'
new = 'function __emscripten_init_main_thread_js(tb){globalThis.__diag&&globalThis.__diag("INIT_MAIN_THREAD called tb="+tb+" IS_WORKER="+ENVIRONMENT_IS_WORKER);tb=bigintToI53Checked(tb);var can_block=!ENVIRONMENT_IS_WEB;__emscripten_thread_init(tb,!ENVIRONMENT_IS_WORKER,1,can_block,1048576,false);PThread.threadInitTLS();globalThis.__diag&&globalThis.__diag("INIT_MAIN_THREAD done")}'
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED init_main_thread diag')
