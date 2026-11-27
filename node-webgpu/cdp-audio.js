// CDP audio diagnostic: read AudioContext state + the worklet ring counters from the page.
const http = require('http');

function get(path) {
	return new Promise((res, rej) => {
		http.get({ host: '127.0.0.1', port: 9222, path }, r => {
			let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d)));
		}).on('error', rej);
	});
}

(async () => {
	const targets = await get('/json/list');
	const page = targets.find(t => t.type === 'page' && t.url.includes('localhost:8000'));
	if (!page) { console.log('NO_GAME_PAGE'); console.log(targets.map(t => t.type + ' ' + t.url).join('\n')); return; }
	const ws = new WebSocket(page.webSocketDebuggerUrl);
	let id = 0; const pending = new Map();
	const send = (method, params = {}) => new Promise((res, rej) => {
		const i = ++id; pending.set(i, { res, rej });
		try { ws.send(JSON.stringify({ id: i, method, params })); } catch (e) { rej(e); }
	});
	ws.addEventListener('message', ev => {
		const m = JSON.parse(ev.data);
		if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id); }
	});
	await new Promise(r => ws.addEventListener('open', r));

	const expr = `(() => {
		const o = { url: location.href };
		// find any AudioContext the page created
		try {
			// page keeps audio state in globals
			o.audioStarted = typeof globalThis.audioStarted !== 'undefined' ? globalThis.audioStarted : 'n/a';
			o.audioPending = !!globalThis.audioPending;
		} catch (e) { o.globalsErr = String(e); }
		// scan for AudioContext instances reachable from window
		try {
			const keys = Object.getOwnPropertyNames(window).filter(k => /audio|Audio/i.test(k));
			o.windowAudioKeys = keys.slice(0, 20);
		} catch (e) {}
		return JSON.stringify(o);
	})()`;
	const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
	console.log(r.result && r.result.value);

	// also pull recent console log lines mentioning audio
	const r2 = await send('Runtime.evaluate', {
		expression: `JSON.stringify((window.__logLines||[]).filter(l=>/audio/i.test(l)).slice(-25))`,
		returnByValue: true
	});
	console.log('LOG:', r2.result && r2.result.value);

	ws.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
