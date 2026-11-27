import re, os
p = r'E:\gta\playgta5\game-log.txt'
size = os.path.getsize(p)
print('log size:', size)
with open(p, 'rb') as f:
    f.seek(max(0, size - 120 * 1024 * 1024))
    data = f.read().decode('utf-8', errors='replace')
lines = data.splitlines()
print('tail lines:', len(lines))
# find last session launch marker containing 1920x1080
start = 0
for i, line in enumerate(lines):
    if '1920x1080' in line and ('page env' in line.lower() or 'location' in line.lower() or 'http' in line.lower()):
        start = i
print('session marker line idx:', start)
if start < len(lines):
    print('marker:', lines[start][:220])
sess = lines[start:]
fps = []
for line in sess:
    m = re.search(r'\[wgpu\] fps: ([\d.]+) \((\d+) frames, (\d+) draws/frame', line)
    if m:
        fps.append((float(m.group(1)), int(m.group(2)), int(m.group(3))))
print('fps samples in session:', len(fps))
world = [x for x in fps if x[2] > 300]
print('world samples (draws>300):', len(world))
for label, d in [('WORLD all', world), ('WORLD last12', world[-12:]), ('WORLD last8', world[-8:])]:
    if d:
        f = [x[0] for x in d]
        dr = [x[2] for x in d]
        print(f'{label}: n={len(d)} fps avg={sum(f)/len(f):.2f} min={min(f):.2f} max={max(f):.2f} | draws avg={sum(dr)/len(dr):.0f} min={min(dr)} max={max(dr)}')
print('--- last 10 raw ---')
for x in world[-10:]:
    print(f'  fps={x[0]:6.2f} frames={x[1]:4d} draws={x[2]:5d}')
print('--- gpu wait (last 3 stutter lines) ---')
for line in [l for l in sess if 'stutter:' in l][-3:]:
    print('  ' + line.strip()[:240])
