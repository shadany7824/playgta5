src = r'E:\Malik\game\game.wat'
dst = r'E:\Malik\game\game-lod50.wat'
insert = '''
        local.get 1
        f32.const 50
        f32.lt
        if
          f32.const 0x1p+0 (;=1;)
          local.set 9
        end
'''
targets = ('LODDrawable::CalcLODLevelAndCrossfade_', 'LODDrawable::CalcLODLevelAndCrossfadeForProxyLod_')
inside = False
patched = 0
with open(src, encoding='utf-8', errors='replace') as fin, open(dst, 'w', encoding='utf-8', newline='\n') as fout:
    for line in fin:
        fout.write(line)
        if line.lstrip().startswith('(func $'):
            inside = any(t in line for t in targets)
        if inside and line.strip() == 'local.set 9':
            fout.write(insert)
            patched += 1
            inside = False
print('patched functions:', patched)
assert patched == 2, 'expected 2 LOD functions patched'
