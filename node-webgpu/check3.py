s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
import re
for key in ['self.location', 'require(']:
    print('====', key)
    for m in list(re.finditer(re.escape(key), s))[:8]:
        print('...', s[max(0,m.start()-100):m.start()+160].replace('\n',' ')[:260])
