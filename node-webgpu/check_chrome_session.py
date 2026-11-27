import os
p = r'E:\gta\playgta5\game-log.txt'
size = os.path.getsize(p)
with open(p, 'rb') as f:
    f.seek(max(0, size - 40 * 1024 * 1024))
    data = f.read().decode('utf-8', errors='replace')
lines = data.splitlines()
envs = [(i, l) for i, l in enumerate(lines) if '[page env]' in l]
print('page env markers in last 40MB:', len(envs))
for i, l in envs[-3:]:
    print('idx', i, l[:600])
urls = [(i, l) for i, l in enumerate(lines) if '1920x1080' in l and 'http' in l]
print('url-ish lines:', len(urls))
for i, l in urls[-2:]:
    print('idx', i, l[:600])
