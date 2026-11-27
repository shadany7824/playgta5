p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "const LOD_PATCH = 0.3;  // LOW global LOD scale -> shorter cull distance -> fewer draws (target FPS)"
new = "const LOD_PATCH = (isNode && process.env.WGPU_LOD_PATCH !== undefined) ? +process.env.WGPU_LOD_PATCH : 0.3;  // Node: WGPU_LOD_PATCH overrides (0=off); browser default 0.3"
assert old in s, 'pattern not found'
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('lod env patch applied')
