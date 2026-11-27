# 02 — Corrected diagnosis and ranked hypotheses

## What the problem file got right
- The fault site: `main+0x4fc` = `cmp rax,[rcx+0x60]; ja <exception>` before `dec dword [rdx+rax]`. Decompile: `c = GOT_data_internal_rage_g_DisableInitNan; c[0]:int = c[0]:int - 1;`. Good disassembly work; this is the right instruction.
- Dead ends (getenv, rootdir global, ud2 patch, AOT rebuild for mismatch) are correctly closed.

## What needs correcting
- "**Root cause: the GOT data relocation value**… WAMR AOT memory64 data-relocation issue" → **wrong frame.** The name `GOT.data.internal.*` is a wasm-ld *symbol name for a wasm global*, not a WAMR AOT GOT/relocation entry. `mov rax,[rdi+0x230]` is the AOT code **reading a wasm global** from the instance's global storage. Its value comes from the game's own `wasm_init_tls()`, not from WAMR relocation code.
- So **"Next step 1: find WAMR AOT GOT/data-relocation init"** would study code that isn't involved. Don't start there.
- (Lesson 08: match the term to your exact system. "GOT" in wasm-ld naming ≠ "GOT" in a native/AOT loader.)

## The real question
**What value does that TLS-pointer global hold at main+0x4fc, and who wrote it?** It must be `tls_base + 720`, where tls_base is the main thread's TLS block (in bounds). OOB means `wasm_init_tls` was called with a bad `tls_base`, or never with a good one for this instance, or the global storage `rdi` points at isn't this instance's.

## Ranked hypotheses
| # | Hypothesis | Why plausible | Test |
|---|---|---|---|
| H1 | **Init order differs from JS.** Host runs thread_init + tls_init before ctors; JS runs them inside ctors via `_emscripten_init_main_thread_js`. Before ctors, `thread_ptr[23]` (pthread+184) and allocator state aren't what the game expects, so tls_init takes a different branch (`internal_memalign` before the C runtime and RAGE regions are set up), or a later step re-inits TLS with a bad block | Proven difference vs the working setup (lesson 04/12); the crash is the first TLS use in main | File 03 dumps + file 04 fix |
| H2 | **`tls_base` chosen from a garbage `thread_ptr[23]`** (pthread struct not yet initialized by C when the host calls tls_init early) | `emscripten_tls_init` trusts `c[23]` if non-zero | Dump `thread_ptr`, `mem[thread_ptr+184]`, and the tls_init return value at checkpoint 1 |
| H3 | **Another exec env / instance**: main runs in an exec env whose instance globals were never TLS-initialized (e.g. singleton env vs the env used for init) | Host uses `wasm_runtime_get_exec_env_singleton(inst)`; any other env would have fresh globals (tls_base = 0 → GOT = 0+off, in bounds, so a huge value would need more) | Log the env/instance pointer used for init and for main; dump globals through the same instance |
| H4 | **Something writes the global later** (a `global.set` in ctors/Load path through a host import misbehaving) | The forced `Load()` (lesson 03) runs engine code outside the normal flow before main | Checkpoints 3→4 in file 03 show which step changed the value |
| H5 | WAMR AOT memory64 bug in global load/store width for this global | Possible but rare | Only if the dump shows the stored value is correct yet AOT code reads something else |

## Decision
Do file 03 (measure). It decides between H1-H5 in **one run**. Then file 04 (the fix for H1/H2, the most likely).
