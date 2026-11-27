import re, sys

def parse(p):
    data = []
    for line in open(p, encoding='utf-8', errors='replace'):
        if '[wgpu] fps:' not in line:
            continue
        m = re.search(r'fps: ([\d.]+) \((\d+) frames, (\d+) draws/frame', line)
        t = re.search(r'TIME draw/up/bg/pipe/ensure/present/shader ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', line)
        pl = re.search(r'pipelines \+(\d+) \((\d+) ms\)', line)
        if not (m and t):
            continue
        data.append(dict(fps=float(m.group(1)), frames=int(m.group(2)), draws=int(m.group(3)),
                         draw=float(t.group(1)), up=float(t.group(2)), bg=float(t.group(3)),
                         pipe=float(t.group(4)),
                         plnew=int(pl.group(1)) if pl else 0, plms=int(pl.group(2)) if pl else 0))
    return [x for x in data if x['draws'] > 500]

for f in sys.argv[1:]:
    d = parse(f)
    tail = d[-12:]
    avg = lambda k: sum(x[k] for x in tail) / len(tail)
    us = sum(x['draw'] * 1000 / x['draws'] for x in tail) / len(tail)
    print(f'{f}: n={len(tail)} fps={avg("fps"):.2f} draws={avg("draws"):.0f} TIMEdraw={avg("draw"):.2f}ms us/draw={us:.1f} pipeMs={avg("pipe"):.2f}ms newPipelines={sum(x["plnew"] for x in tail)} pipeWall={sum(x["plms"] for x in tail)}ms')
