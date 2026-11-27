import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else r'E:\gta\playgta5\node-webgpu\diag-step3-1080.txt'
lines = open(p, encoding='utf-8', errors='replace').readlines()
fps = []
for line in lines:
    m = re.search(r'\[wgpu\] fps: ([\d.]+) \((\d+) frames, (\d+) draws/frame', line)
    if m:
        fps.append((float(m.group(1)), int(m.group(2)), int(m.group(3))))
print('total fps samples:', len(fps))
world = [x for x in fps if x[2] > 300]
print('world samples (draws>300):', len(world))
for label, data in [('ALL', fps), ('WORLD', world), ('WORLD last12', world[-12:]), ('WORLD last8', world[-8:])]:
    if not data:
        continue
    f = [x[0] for x in data]
    d = [x[2] for x in data]
    print(f'{label}: n={len(data)} fps avg={sum(f)/len(f):.2f} min={min(f):.2f} max={max(f):.2f} | draws avg={sum(d)/len(d):.0f} min={min(d)} max={max(d)}')
print('--- last 14 raw world samples ---')
for x in world[-14:]:
    print(f'  fps={x[0]:6.2f} frames={x[1]:4d} draws={x[2]:5d}')
print('--- gpu wait / stutter lines (last 3) ---')
for line in [l for l in lines if 'stutter:' in l][-3:]:
    print('  ' + line.strip()[:260])
