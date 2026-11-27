# gameResourceMB: default 8192 (measured +11% FPS); 1024 = old default
p = r'E:\gta\playgta5\mirror\playgta5.com\index.html'
s = open(p, encoding='utf-8', errors='replace').read()
old = "\t\twasmFile: q.get('wasm') === 'lod50' ? 'lod50' : '',\t\t// ?wasm=lod50: 50m near-full-detail LOD build (diagnostic A/B)"
new = old + "\n\t\tgameResourceMB: +(q.get('ram') || 8192),\t\t// ?ram=MB: streaming/resource budget (8192 measured ~11% faster than 1024)"
assert old in s
s = s.replace(old, new, 1)
# add RAM buttons to panel
old2 = "  <div id=\"gtaPanelStatus\" style=\"opacity:.7;margin-top:10px\">Mode: loading...</div>"
new2 = ("  <div style=\"opacity:.8;margin:10px 0 6px\">RAM budget (restart to apply)</div>\n"
        "  <button data-ram=\"8192\" style=\"margin:2px;padding:6px 10px\">RAM 8GB (recommended)</button>\n"
        "  <button data-ram=\"1024\" style=\"margin:2px;padding:6px 10px\">RAM 1GB (old)</button>\n"
        + old2)
assert old2 in s
s = s.replace(old2, new2, 1)
# handler: store choice in URL and reload
js = '''
for (const b of document.querySelectorAll('[data-ram]')) b.addEventListener('click', () => {
  const v = b.dataset.ram;
  const u = new URL(location.href);
  u.searchParams.set('ram', v);
  u.searchParams.set('wasm', 'lod50');
  location.href = u.toString();
});
'''
idx = s.rfind('</script>')
s = s[:idx] + js + s[idx:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('index.html: RAM buttons + param added')

p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\loader.js'
s = open(p, encoding='utf-8', errors='replace').read()
old3 = "\t\t\tcanvas: m.canvas,"
new3 = "\t\t\tcanvas: m.canvas,\n\t\t\tgameResourceMB: m.gameResourceMB || 8192,"
assert old3 in s
s = s.replace(old3, new3, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('loader.js: gameResourceMB applied to Module')

p = r'E:\gta\playgta5\Launch-Chrome-Mode.cmd'
s = open(p, encoding='utf-8', errors='replace').read()
s = s.replace('&slots=5%WASM_PARAM%&args=', '&slots=5&ram=8192%WASM_PARAM%&args=', 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('Chrome launcher: ram=8192 default')
