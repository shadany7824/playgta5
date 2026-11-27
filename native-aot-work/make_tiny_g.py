import struct

def uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)

def section(sid, payload):
    return bytes([sid]) + uleb(len(payload)) + payload

def vec(items):
    return uleb(len(items)) + b''.join(items)

# type: () -> ()
types = vec([b'\x60' + vec([]) + vec([])])
# one function of type 0
funcs = vec([uleb(0)])
# memory64: flags=0x05 (max present + memory64), min=1, max=1 (u64 LEB)
mems = vec([b'\x05' + uleb(1) + uleb(1)])
# globals: [0] f32 mut = 50.0 ; [1] i64 mut = 1000
g0 = b'\x7d\x01' + b'\x43' + struct.pack('<f', 50.0)
g1 = b'\x7e\x01' + b'\x42' + uleb(1000)
globs = vec([g0, g1])
# exports: func f=0, global g=1
ex = vec([uleb(1) + b'f' + b'\x00' + uleb(0),
          uleb(1) + b'g' + b'\x03' + uleb(1)])
# code: i64.const 1234 ; global.set 1 ; end
body = uleb(0) + b'\x42' + uleb(1234) + b'\x24' + uleb(1) + b'\x0b'
code = vec([uleb(len(body)) + body])

wasm = b'\x00asm\x01\x00\x00\x00' + section(1, types) + section(3, funcs) + \
       section(5, mems) + section(6, globs) + section(7, ex) + section(10, code)
p = r'E:\gta\_tmp_claude\tiny-g.wasm'
open(p, 'wb').write(wasm)
print('wrote', p, len(wasm), 'bytes')
