from pathlib import Path
p = Path(r'E:\Malik\game\game-lodlive.wat')
s = p.read_text(encoding='utf-8', errors='replace')
if '$gta_lod_hits' not in s:
    s = s.replace('  (global $gta_lod_cutoff (export "gta_lod_cutoff") (mut f32) (f32.const 50))\n',
                  '  (global $gta_lod_cutoff (export "gta_lod_cutoff") (mut f32) (f32.const 50))\n  (global $gta_lod_hits (export "gta_lod_hits") (mut i32) (i32.const 0))\n', 1)
snippet = '''      if
        local.get {ptr}
        i32.const 0
        i32.store
'''
for ptr in (2, 3, 4):
    old = snippet.format(ptr=ptr)
    if old in s:
        s = s.replace(old, old + '        global.get $gta_lod_hits\n        i32.const 1\n        i32.add\n        global.set $gta_lod_hits\n')
p.write_text(s, encoding='utf-8', newline='')
print('counter inserted; refs', s.count('$gta_lod_hits'))
