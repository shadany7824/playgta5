p = r'E:\gta\playgta5\mirror\playgta5.com\index.html'
s = open(p, encoding='utf-8', errors='replace').read()
start = s.index('// ---- live settings panel (Ctrl+S) ----')
end = s.index('</script>', start)
new_js = '''// ---- live settings bar (always visible) ----
const gtaPanel = document.getElementById('gtaPanel');
const gtaStatus = document.getElementById('gtaPanelStatus');
const panelToggle = document.getElementById('gtaPanelToggle');
gtaPanel.style.display = 'block';
panelToggle.addEventListener('click', () => {
  gtaPanel.style.display = gtaPanel.style.display === 'none' ? 'block' : 'none';
});
for (const b of document.querySelectorAll('[data-lod]')) b.addEventListener('click', () => {
  const v = +b.dataset.lod;
  worker.postMessage({ lodCutoff: v });
  gtaStatus.textContent = 'LOD: ' + (v ? 'sharp under 50m' : 'fast (0.3 everywhere)');
});
for (const b of document.querySelectorAll('[data-ped]')) b.addEventListener('click', () => {
  const v = +b.dataset.ped;
  worker.postMessage({ pedDensity: v });
  gtaStatus.textContent = 'Ped density: ' + v;
});
document.getElementById('gtaPanelClose').addEventListener('click', () => { gtaPanel.style.display = 'none'; });
for (const b of document.querySelectorAll('[data-ram]')) b.addEventListener('click', () => {
  const v = b.dataset.ram;
  const u = new URL(location.href);
  u.searchParams.set('ram', v);
  location.href = u.toString();
});
addEventListener('keydown', (e) => {
  if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault(); e.stopImmediatePropagation();
    gtaPanel.style.display = gtaPanel.style.display === 'none' ? 'block' : 'none';
  }
}, { capture: true });
'''
s = s[:start] + new_js + s[end:]
s = s.replace('id="gtaPanel" style="display:none', 'id="gtaPanel" style="display:block')
if 'id="gtaPanelToggle"' not in s:
    s = s.replace('<button id="gtaPanelClose">x</button>', '<button id="gtaPanelToggle" type="button">Settings</button><button id="gtaPanelClose">x</button>')
open(p, 'w', encoding='utf-8', newline='').write(s)
print('visible live settings bar installed')
