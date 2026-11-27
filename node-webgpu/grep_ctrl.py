import re
f = open(r'E:\Malik\game\game.dcmp', encoding='utf-8', errors='replace')
hits = []
for n, line in enumerate(f, 1):
    low = line.lower()
    if 'using controller' in low or 'packfile' in low and 'promoting' in low:
        hits.append((n, line.strip()[:160]))
f.close()
print('hits', len(hits))
for h in hits[:20]:
    print(h[0], h[1])
