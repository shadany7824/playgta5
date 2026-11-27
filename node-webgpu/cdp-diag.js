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
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails;
    console.log('EXCEPTION', d.text, d.exception && d.exception.description ? d.exception.description.split('\n')[0] : '', d.url || '', d.lineNumber);
  }
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
    console.log('CONSOLE_ERROR', m.params.args.map((a) => a.value || a.description || '').join(' ').slice(0, 200));
  }
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  return r.result && r.result.result ? r.result.result.value : undefined;
};
await send('Runtime.enable');
await send('Page.enable');
console.log('typeof gtaPanel=', await ev("typeof gtaPanel"));
console.log('typeof worker=', await ev("typeof worker"));
console.log('panelHtml=', (await ev("document.getElementById('gtaPanel')?.outerHTML") || '').slice(0, 160));
await send('Page.reload', { ignoreCache: true });
await sleep(20000);
console.log('after reload typeof gtaPanel=', await ev("typeof gtaPanel"));
console.log('after reload panel=', await ev("document.getElementById('gtaPanel')?.style.display"));
ws.close();
