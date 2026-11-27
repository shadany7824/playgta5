s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
i = s.find('function initMemory')
print(s[i:i+700])
print()
# check INITIAL_MEMORY definition
import re
m = re.search(r'INITIAL_MEMORY[=:][^,;]{0,80}', s)
print('INITIAL_MEMORY:', m.group(0)[:120] if m else 'not found')
