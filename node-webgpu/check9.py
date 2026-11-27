s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
i = s.find('function updateMemoryViews')
print('=== updateMemoryViews ===')
print(s[i:i+900])
print()
# check where Number() or Math on BigInt might happen near initMemory
j = s.find('function initMemory')
print('=== initMemory full ===')
print(s[j:j+500])
