import re, os
p = r'E:\gta\playgta5\game-log.txt'
mark = 321868490
size = os.path.getsize(p)
print('size now:', size, 'appended MB:', round((size-mark)/1024/1024, 1))
with open(p, 'rb') as f:
    f.seek(mark)
    data = f.read().decode('utf-8', errors='replace')
lines = data.splitlines()
print('new lines:', len(lines))
for i, l in enumerate(lines[:5]):
    print('HEAD', i, l[:180])
envs = [l for l in lines if '[page env]' in l]
print('page env:', envs[-1][:400] if envs else 'none')
fps = []
for line in lines:
    m = re.search(r'\[wgpu\] fps: ([\d.]+) \((\d+) frames, (\d+) draws/frame', line)
    if m:
        fps.append((float(m.group(1)), int(m.group(2)), int(m.group(3))))
world = [x for x in fps if x[2] > 300]
print('fps samples:', len(fps), 'world:', len(world))
for label, d in [('WORLD all', world), ('WORLD last12', world[-12:]), ('WORLD last8', world[-8:])]:
    if d:
        f = [x[0] for x in d]
        dr = [x[2] for x in d]
        print(f'{label}: n={len(d)} fps avg={sum(f)/len(f):.2f} min={min(f):.2f} max={max(f):.2f} | draws avg={sum(dr)/len(dr):.0f} min={min(dr)} max={max(dr)}')
print('markers:', 'scripts', sum('Script Name' in l for l in lines), 'promoted', sum('promoting to CACHE' in l for l in lines), 'init session', sum('Init Session' in l for l in lines))
print('--- last 8 ---')
for x in world[-8:]:
    print(f'  fps={x[0]:6.2f} frames={x[1]:4d} draws={x[2]:5d}')
for line in [l for l in lines if 'stutter:' in l][-2:]:
    print('STUTTER', line.strip()[:240])
