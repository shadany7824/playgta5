import json, glob, os, collections
files = sorted(glob.glob(r'E:\gta\playgta5\node-webgpu\prof\*.cpuprofile'), key=os.path.getmtime)
p = files[-1]
print('profile:', p)
d = json.load(open(p, encoding='utf-8'))
nodes = {n['id']: n for n in d['nodes']}
samples = d.get('samples', [])
deltas = d.get('timeDeltas', [])
print('samples:', len(samples), 'duration s:', round(sum(deltas) / 1e6, 1))
counts = collections.Counter(samples)
total = sum(counts.values())
rows = []
for nid, cnt in counts.items():
    n = nodes.get(nid)
    if not n:
        continue
    cf = n['callFrame']
    name = cf.get('functionName') or '(anonymous)'
    url = cf.get('url', '')
    line = cf.get('lineNumber', 0)
    short = url.split('/')[-1] if url else '(native)'
    rows.append((cnt, cnt * 100.0 / total, name, short, line + 1))
rows.sort(reverse=True)
print('--- top 20 self time ---')
for cnt, pct, name, short, line in rows[:20]:
    print(f'{pct:6.2f}%  {cnt:6d}  {name[:44]:44s} {short}:{line}')
