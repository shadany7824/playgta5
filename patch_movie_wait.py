"""Patch game.wasm so missions no longer freeze when a TV movie stops (e.g. Michael's TV in Complications).

This build has no Bink: the AsyncBink thread never starts, so a bwMovie never reports loaded (byte 171).
Seven functions contain an inlined CMovieMgr::CMovie::WaitTillLoaded that sleeps until it does, so the main
thread hangs for good in "Movie Manager" (hang report: 100% Update>Render Update>Movie Manager [sleep]).
Each copy is guarded by `if (!(flags97 & 1))`; turning the 'and' into an 'or' makes every copy skip its wait.
One byte per site, so the file size does not change.

Works on the untouched game.wasm and on one patched by other scripts: functions are found by index.
The first run keeps the input as game.wasm.pre-movie-patch. Running it again is safe.
Restore: cp game.wasm.pre-movie-patch game.wasm
"""
import shutil, sys
from pathlib import Path

WASM = Path(__file__).resolve().parent / 'mirror' / 'playgta5.com' / 'b' / '8b0b5899ed' / 'game.wasm'
BACKUP = WASM.with_name('game.wasm.pre-movie-patch')

# CMovieMgr: UpdateFrame, Delete, CMovie::Play, Stop, GetTime; CPauseMenu: Open, SetupCodeForUnPause
MOVIE_WAITS = (80969, 80987, 81493, 81494, 81507, 36164, 36283)
# i32.load8_u 97; i32.const 1; i32.and; i32.eqz; if; i64.const 79877 (WaitTillLoaded's hang-detect crash func)
WAIT_TEST = bytes.fromhex('2d0061' '4101' '71' '45' '0440' '4285f004')
SKIPPED = WAIT_TEST[:5] + b'\x72' + WAIT_TEST[6:]  # i32.or


def leb(data, i):
    result = shift = 0
    while True:
        byte = data[i]; i += 1
        result |= (byte & 0x7f) << shift; shift += 7
        if byte < 0x80:
            return result, i


def imported_functions(data):
    """Function indices start after the imported functions."""
    i = 8
    while i < len(data):
        section, j = data[i], i + 1
        size, j = leb(data, j)
        if section == 2:
            count, p = leb(data, j)
            funcs = 0
            for _ in range(count):
                for _ in range(2):  # module and field names
                    n, p = leb(data, p); p += n
                kind = data[p]; p += 1
                if kind == 0: _, p = leb(data, p); funcs += 1                      # func: type index
                elif kind == 1: p += 1; flags, p = leb(data, p); _, p = leb(data, p); p = leb(data, p)[1] if flags & 1 else p  # table
                elif kind == 2: flags, p = leb(data, p); _, p = leb(data, p); p = leb(data, p)[1] if flags & 1 else p         # memory
                elif kind == 3: p += 2                                              # global: type, mutability
                elif kind == 4: p += 1; _, p = leb(data, p)                         # tag
                else: sys.exit(f'unknown import kind {kind}; nothing written')
            return funcs
        i = j + size
    return 0


def function_bodies(data):
    """{function index: (start, end)} of each code body."""
    imported = imported_functions(data)
    i = 8
    while data[i] != 10:
        size, j = leb(data, i + 1)
        i = j + size
    _, j = leb(data, i + 1)
    count, p = leb(data, j)
    bodies = {}
    for n in range(count):
        size, q = leb(data, p)
        bodies[imported + n] = (q, q + size)
        p = q + size
    return bodies


def main():
    data = bytearray(WASM.read_bytes())
    if data[:8] != b'\0asm\1\0\0\0':
        sys.exit(f'{WASM} is not a wasm module; nothing written')
    bodies = function_bodies(data)
    todo, done = [], 0
    for fn in MOVIE_WAITS:
        if fn not in bodies:
            sys.exit(f'func[{fn}] not found: not the expected game.wasm build; nothing written')
        start, end = bodies[fn]
        body = bytes(data[start:end])
        if body.count(SKIPPED) == 1 and WAIT_TEST not in body:
            done += 1
        elif body.count(WAIT_TEST) == 1:
            todo.append(start + body.find(WAIT_TEST) + 5)
        else:
            sys.exit(f'func[{fn}] has no WaitTillLoaded test: not the expected game.wasm build; nothing written')
    if not todo:
        print(f'game.wasm already patched ({done} of {len(MOVIE_WAITS)} movie waits skipped)')
        return
    if not BACKUP.exists():
        shutil.copy2(WASM, BACKUP)
    for at in todo:
        data[at] = 0x72
    WASM.write_bytes(data)
    print(f'game.wasm patched: {len(todo)} movie waits now skipped ({done} already were); backup: {BACKUP.name}')


if __name__ == '__main__':
    main()
