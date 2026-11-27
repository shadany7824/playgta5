p = r'E:\gta\playgta5\LOD-Settings.cmd'
s = open(p, encoding='utf-8', errors='replace').read()
s = s.replace('echo   1) FAST   - LOD 0.3 (original, ~7.6 FPS)',
              'echo   1) FAST   - LOD 0.3 start (~7.6 FPS)')
s = s.replace('echo   2) SHARP  - 50m near full detail (patched, ~5.6-6.7 FPS)',
              'echo   2) SHARP  - 50m near full detail (~5.6-6.7 FPS)')
s = s.replace('echo   3) Exit', 'echo   3) Exit\n echo.\n echo   IN GAME: press Ctrl+S for live settings panel')
open(p, 'w', encoding='utf-8', newline='').write(s)
print('menu updated')
