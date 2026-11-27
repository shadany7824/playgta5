p = r'E:\Malik\game\game.wat'
with open(p, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
for center in [10357256, 10745589]:
    print('=== call at', center, '===')
    for j in range(center - 18, center + 2):
        print(j, lines[j - 1].rstrip()[:170])
