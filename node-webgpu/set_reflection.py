import sys
p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8', errors='replace').read()
v = sys.argv[1]
assert "'-reflectionQuality=1'" in s or "'-reflectionQuality=0'" in s
import re
s = re.sub(r"'-reflectionQuality=\d+'", "'-reflectionQuality=%s'" % v, s, count=1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('reflectionQuality =', v)
