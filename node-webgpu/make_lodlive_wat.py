src = r'E:\Malik\game\game.wat'
dst = r'E:\Malik\game\game-lodlive.wat'
targets = ('LODDrawable::CalcLODLevelAndCrossfade_', 'LODDrawable::CalcLODLevelAndCrossfadeForProxyLod_')
insert = '''
        local.get 1
        global.get $gta_lod_cutoff
        f32.lt
        if
          f32.const 0x1p+0 (;=1;)
          local.set 9
        end
'''
with open(src, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
last_import = max(i for i, l in enumerate(lines) if l.lstrip().startswith('(import '))
inside = False
patched = 0
with open(dst, 'w', encoding='utf-8', newline='\n') as fout:
    for i, line in enumerate(lines):
        fout.write(line)
        if i == last_import:
            fout.write('  (global $gta_lod_cutoff (export "gta_lod_cutoff") (mut f32) (f32.const 50))\n')
        if line.lstrip().startswith('(func $'):
            inside = any(t in line for t in targets)
        if inside and line.strip() == 'local.set 9':
            fout.write(insert)
            patched += 1
            inside = False
print('last import line', last_import + 1, 'functions patched', patched)
assert patched == 2
