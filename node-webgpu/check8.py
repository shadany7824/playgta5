s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
for key in ['Module["wasmMemory"]', 'wasmMemory=new', 'wasmMemory=Module', 'if(Module["wasmMemory"])']:
    print('%-28s %d' % (key, s.count(key)))
i = s.find('wasmMemory=')
print('=== first wasmMemory= context ===')
print(s[i-250:i+250])
