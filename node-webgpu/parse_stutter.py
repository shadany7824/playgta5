import re, sys

# Parses [wgpu] stutter lines: worst-frame ms + the pipeline ms share of the worst frames.
pat = re.compile(r'stutter: (\d+) frames > 25 ms, (\d+) > (\d+) ms, worst (\d+) ms; worst frames \(ms: [^)]*\): (.+)')
frame = re.compile(r'(\d+): (\d+)/(\d+)/(\d+)/([\d.]+) ([\d.]+)MB/(\d+)/(\d+)')

for p in sys.argv[1:]:
    worsts, pipe_worst, idle_worst, n = [], [], [], 0
    for line in open(p, encoding='utf-8', errors='replace'):
        if 'stutter:' not in line:
            continue
        m = pat.search(line)
        if not m:
            continue
        n += 1
        worsts.append(int(m.group(4)))
        # first listed frame is the worst of that interval: idle/pipeline/modules/uploads MB/gpu wait/submit
        f = frame.search(m.group(5))
        if f:
            idle_worst.append(int(f.group(2)))
            pipe_worst.append(int(f.group(3)))
    if not worsts:
        print(f'{p}: no stutter lines')
        continue
    avg = lambda a: sum(a) / len(a)
    print(f'{p}: intervals={n} worstAvg={avg(worsts):.0f}ms worstMax={max(worsts)}ms | '
          f'worst-frame pipelineAvg={avg(pipe_worst):.0f}ms max={max(pipe_worst)}ms | idleAvg={avg(idle_worst):.0f}ms')
