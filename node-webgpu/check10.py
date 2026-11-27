s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
i = s.find('function getMemoryBuffer')
print('=== getMemoryBuffer ===')
print(s[i:i+500])
