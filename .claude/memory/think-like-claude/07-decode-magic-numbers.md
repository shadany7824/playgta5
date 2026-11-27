# 07 — Decode magic numbers: they are usually text or addresses

## The lesson
Big unexplained numbers in compiled or decompiled code are almost always **packed text, string addresses or global variables**. Decode them before you guess what they mean.

## What happened here
`rage_fiDeviceLocal_Open` had this check before it used the web file system:
```
if ((f[0]:int ^ 1835099951) | (f[2]:ushort ^ 12133)) goto B_f;   // B_f = plain open()
```
Decoding the two numbers as little-endian bytes:
```
python -c "import struct;print(struct.pack('<I',1835099951),struct.pack('<H',12133))"
→ b'/gam' b'e/'
```
So the path must start with **`/game/`**, or the engine uses plain `open()`, which fails in this setup. This one decode explained the whole bug together with lesson 05.
In the same session, error-string addresses were decoded from the wasm data section (passive rodata segment 0, base address 1024):
`3128086` → "Unable to find critical archive '%s'", `3122485` → "E:/P1/gta5/build/dev_ng/", `3122734` → "/game/".

## How to apply
- A 32-bit compare against a large constant → try decoding it as 4 ASCII bytes (little-endian). 16-bit → 2 bytes.
- An address passed to a print/log/error function → it's a format string. Find it in the data segment.
- An address read/written as float/int in many functions → a global setting. Name it and write it down (memory files keep these, e.g. LOD `23318984`, ped density `7155636`).
- Write a tiny reusable decoder script and note how the address maps to the file (segment base).

## Common encodings
| Looks like | Usually is |
|---|---|
| 1,000,000,000+ compared with a loaded int | 4 chars of text |
| 1065353216 | float 1.0 (bit pattern) |
| 1,000,000-30,000,000 passed to printf-like calls | string address |
| A value near other addresses in the same function | struct/global field |

## One-line rule
**A magic number is a message. Decode it.**
