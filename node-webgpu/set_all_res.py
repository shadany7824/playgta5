import sys, re
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
w, h = sys.argv[1], sys.argv[2]
s = re.sub(r"res=\d+x\d+", "res=%sx%s" % (w, h), s, count=1)
s = re.sub(r"'-width=\d+', '-height=\d+'", "'-width=%s', '-height=%s'" % (w, h), s, count=1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('harness internal', w, 'x', h)
