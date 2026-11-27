import sys, re
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
w, h = sys.argv[1], sys.argv[2]
s2 = re.sub(r"'-width=\d+', '-height=\d+'", "'-width=%s', '-height=%s'" % (w, h), s, count=1)
assert s2 != s, 'width args not found'
open(p, 'w', encoding='utf-8', newline='').write(s2)
print('harness internal res =', w, 'x', h)
