# 07 — If it still fails after file 04

Go by the file 03 dump. Don't guess (lesson 26: after two fails, research).

## Case 1: `tls_init` inside the import fails (re-entrancy)
- Read the exact exception text. Check how this WAMR version handles nested `wasm_runtime_call_wasm` from a raw native (exec env state, `wasm_runtime_set_exception` leftovers, stack-limit checks).
- Alternative with the same semantics: make the import **record `tb` only**, and have the host call thread_init + tls_init **at the same moment** by splitting ctors. That isn't possible from outside, so prefer making re-entrancy work. Research WAMR docs/issues for "call wasm from native function" with **your WAMR commit** (lesson 08).

## Case 2: `tls_base` from tls_init is wrong even inside the import
- Dump `thread_ptr` and `mem[thread_ptr + 184]` (the `c[23]` field) right before the call. In JS the same field decides between "use the pthread's TLS block" and "allocate one".
- Compare the main pthread struct bytes (tb .. tb+256) in host vs JS at the moment of the import (JS: read `HEAPU8.slice(tb, tb+256)` in the import wrapper). A difference names the field the host didn't set up.

## Case 3: values correct, exception still fires
- Prove that `rdi+0x230` reads global 15: compute `offsetof(global_data)` in `AOTModuleInstance` + global 15's `data_offset`. If it's not 0x230, the AOT code reads a different global. Find which one (match by offset) and dump that one instead.
- Check `[rcx+0x60]`: which bound field (`mem_bound_check_4bytes`?) at that offset in `AOTMemoryInstance` for this WAMR version, and its value. A bound computed for i32 memory on a memory64 instance would also produce false OOB.

## Case 4: the crash moves to a new place
That's progress. New Stage, same method: stack/fault site → decompile of that function → which global/import → JS reference value.

## When to stop and ask the owner
- After R1 + one Case run without new information.
- If a fix needs WAMR changes beyond debug logging (e.g. changing nested-call or bound-check code), write the evidence and the proposed change first.
- Be honest about ETA. The problem file's estimate (2-5 days, maybe 1-2 weeks) still stands until boot passes this point.
