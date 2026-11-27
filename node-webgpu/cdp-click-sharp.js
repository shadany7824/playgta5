const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const list = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = list.find((p) => p.type === 'page' && p.url.includes('localhost:8000'));
if (!page) { console.log('NO_PAGE'); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  return r.result && r.result.result ? r.result.result.value : undefined;
};
console.log('panel=', await ev("document.getElementById('gtaPanel')?.style.display"));
console.log('lodButtons=', await ev("[...document.querySelectorAll('[data-lod]')].map(b=>b.dataset.lod).join(',')"));
console.log('before=', await ev("document.getElementById('gtaPanelStatus')?.textContent"));
await ev("[...document.querySelectorAll('[data-lod]')].find(b=>b.dataset.lod==='50').click()");
await sleep(2000);
console.log('after=', await ev("document.getElementById('gtaPanelStatus')?.textContent"));
ws.close();
