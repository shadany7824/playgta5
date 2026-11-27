p = r'E:\gta\playgta5\node-webgpu\wgpu_worker_node.js'
s = open(p, encoding='utf-8', errors='replace').read()
repls = [
 ("const vsProg = (()=>{const _t=performance.now();const r=shaderProgram(vsObj);TP.shaders+=performance.now()-_t;return r;})();",
  "const vsProg = shaderProgram(vsObj);"),
 ("const psProg = psObj ? (()=>{const _t=performance.now();const r=shaderProgram(psObj);TP.shaders+=performance.now()-_t;return r;})() : null;",
  "const psProg = psObj ? shaderProgram(psObj) : null;"),
 ("{ const _t=performance.now(); const _ok=ensurePass(); TP.ensure+=performance.now()-_t; if (!_ok) { skipDraw('if (!ensurePass()) { skippedDraws++; return; }'); return; } }",
  "if (!ensurePass()) { skipDraw('if (!ensurePass()) { skippedDraws++; return; }'); return; }"),
 ("{ const _t=performance.now(); pl = getPipeline(vsObj, psObj, vsProg, psProg, layout, passInfo.rtInfo, passInfo.dsFormat); TP.pipeline += performance.now()-_t; }",
  "pl = getPipeline(vsObj, psObj, vsProg, psProg, layout, passInfo.rtInfo, passInfo.dsFormat);"),
 ("const g0 = vsProg.groupBindings[0] ? (() => { const _t=performance.now(); const r=stageBG(0,vsProg,0); TP.stagebg+=performance.now()-_t; return r; })() : null;",
  "const g0 = vsProg.groupBindings[0] ? stageBG(0,vsProg,0) : null;"),
 ("const g1 = psProg && psProg.groupBindings[1] ? (() => { const _t=performance.now(); const r=stageBG(1,psProg,1); TP.stagebg+=performance.now()-_t; return r; })() : null;",
  "const g1 = psProg && psProg.groupBindings[1] ? stageBG(1,psProg,1) : null;"),
]
for old, new in repls:
    assert old in s, 'not found: ' + old[:60]
    s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('6 per-draw timing closures removed')
