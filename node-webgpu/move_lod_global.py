from pathlib import Path
p = Path(r'E:\Malik\game\game-lodlive.wat')
s = p.read_text(encoding='utf-8', errors='replace')
line = '  (global $gta_lod_cutoff (export "gta_lod_cutoff") (mut f32) (f32.const 50))\n'
s = s.replace(line, '', 1)
lines = s.splitlines(keepends=True)
last = max(i for i, l in enumerate(lines) if l.startswith('  (import '))
lines.insert(last + 1, line)
p.write_text(''.join(lines), encoding='utf-8', newline='')
print('global moved after import at line', last + 1)
