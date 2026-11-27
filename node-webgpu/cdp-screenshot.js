import fs from 'node:fs';
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
await send('Page.enable');
await sleep(1000);
const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
if (!r.result || !r.result.data) { console.log('NO_IMAGE', JSON.stringify(r).slice(0, 300)); process.exit(1); }
const out = 'E:/gta/playgta5/shots/current-area.png';
fs.mkdirSync('E:/gta/playgta5/shots', { recursive: true });
fs.writeFileSync(out, Buffer.from(r.result.data, 'base64'));
console.log('saved', out, fs.statSync(out).size);
ws.close();
