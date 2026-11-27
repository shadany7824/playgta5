p = r'E:\gta\playgta5\mirror\playgta5.com\index.html'
s = open(p, encoding='utf-8', errors='replace').read()
marker = '// ---- live settings panel (Ctrl+S) ----'
start = s.index(marker)
end = s.index('</script>', start)
js = s[start:end]
s = s[:start] + s[end:]
s = s.replace('<script src="/touch-controls.js">\n</script>', '<script src="/touch-controls.js"></script>', 1)
idx = s.index('</script>')
s = s[:idx] + js + s[idx:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('panel JS moved into the game module script')
