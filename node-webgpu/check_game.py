s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
print('game.js len', len(s))
for key in ['ENVIRONMENT_IS_NODE', 'require("fs")', 'worker_threads', 'process.versions', 'ENVIRONMENT_IS_WEB', 'ENVIRONMENT_IS_WORKER']:
    print(repr(key), s.count(key))
print('--- first 700 chars ---')
print(s[:700])
