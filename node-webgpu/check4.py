s = open(r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\game.js', encoding='utf-8', errors='replace').read()
print('=== last 1200 chars of game.js ===')
print(s[-1200:])
print()
print('=== Module assignment / run call patterns ===')
import re
for key in ['Module=typeof', 'ready(', 'run(', 'callMain', '_main', 'Module["onRuntimeInitialized"]', 'process.exit']:
    print('%-30s %d' % (key, s.count(key)))
