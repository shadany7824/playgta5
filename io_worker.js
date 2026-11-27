// HTTP read worker + persistent block cache: serves every file read of the engine threads (platform/file/httpfs_wasm.cpp).
//
// Engine threads used to read with their own synchronous XMLHttpRequest, behind a service worker that cached the blocks. Each response is a fresh ArrayBuffer (plus the
// request's own copy of the body) that the browser frees only when that worker's GC runs, and an engine thread that is mostly inside wasm or blocked in Atomics.wait
// almost never does: the bytes read piled up as ~1.5 GB of renderer memory (reproduced with 30 blank workers reading 1.8 GB: 3.6 GB working set, whatever is done to
// the buffers afterwards), and the service worker added another ~0.9 GB of its own.
// This worker has an event loop and streams every response chunk by chunk straight into a persistent store in the Origin Private File System; reads are then served
// from the store into the shared wasm heap. No JavaScript buffers are involved, so nothing has to be garbage collected.
//
// Store: `store.bin` is append-only. A range fetch reserves room at the end (whole 256 KB blocks of the file), streams the body into it, and records where every block
// went in `journal.bin` (16-byte entries: file id, block, offset low, offset high) after the data has been flushed. The journal header carries the manifest version;
// another version (or a foreign magic) starts an empty store. Without OPFS (or when another tab has the store open: sync access handles are exclusive) blocks are
// only kept in a 48 MB memory cache.
//
// Protocol with the engine threads (all in the shared wasm heap, `table` = address of an Int32 table, see httpfs_wasm.cpp):
//   header: [0] doorbell (incremented by every request or hint), [1] slot counter (each engine thread takes one slot on its first read),
//           [2] word offset of the hint ring, [3] its entries, [4] hints claimed by the engine, [5] hints consumed here
//   slot i (16 words at 16 + 16*i): [0] state 0 idle / 1 requested / 3 taken by this worker / 2 done, [1] file id, [2..3] offset, [4..5] destination address, [6] length, [7] result (bytes or -1)
//   hint ring (4 words per entry): file id, offset low, offset high, length (written last; 0 = free): a read the engine has queued and will perform later, one at a time (the
//   streamer's single reader thread); fetching it now, HINT_PAR at a time, turns ~3 reads/s (one round trip each) into as many as the link carries. See drainHints.
'use strict';
let mem, HEAP32, HEAPU8, table;
let files = [], base = '', bc = null, pendingBytes = 0, lastPost = 0, noHints = false, dataQuery = '';		// noHints: ?nohints=1 (diagnostics), see drainHints; dataQuery: ?v=<manifest version> on every data URL
// Store block size 4 KB. The engine mounts ~1,200 archives at boot and reads only each one's table of contents (16 bytes, the entries, the names: median 3 KB, 4.9 MB for all
// of them, measured with ?trace=1); fetching 256 KB (first version) or 16 KB blocks plus a growing read-ahead (second) made the boot download 25x larger for those files.
// Read-ahead now only follows *large* sequential reads (streamed resources), see serve().
const BS = 4096, MAX_RUN = 256, MAX_AHEAD = 512 * 1024, FIRST_AHEAD = 64 * 1024, AHEAD_MIN_READ = 65536;
const MBS = 262144;		// block size of the memory-only fallback (no store)
let remoteLog = false;		// ?log=1 on the page (loader.js passes it in the init message): this worker's diagnostics go to the dev server
function log(text) { if (remoteLog) fetch('/log', { method: 'POST', body: text }).catch(() => {}); }

const pathIndex = new Map();
const fileBytes = new Map();		// diagnostics: network bytes per file path, top of the list goes to the server log every 25 MB
let statTotal = 0, statNext = 25 * 1048576, statT0 = performance.now();
function tally(f, n) {
	fileBytes.set(f.path, (fileBytes.get(f.path) || 0) + n);
	statTotal += n;
	if (statTotal >= statNext) {
		statNext += 25 * 1048576;
		const top = [...fileBytes].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([p, b]) => p.split('/').slice(-2).join('/') + ' ' + (b / 1048576 | 0) + 'MB').join(' | ');
		const ext = new Map(), sizes = [0, 0, 0, 0];		// bytes by extension; bytes by fetched amount per file: <1 MB, <8 MB, <32 MB, more
		for (const [pth, b] of fileBytes) {
			const e = (pth.match(/\.(\w+)$/) || [, '?'])[1]; ext.set(e, (ext.get(e) || 0) + b);
			sizes[b < 1048576 ? 0 : b < 8388608 ? 1 : b < 33554432 ? 2 : 3] += b;
		}
		log('[io] by extension: ' + [...ext].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([e, b]) => e + ' ' + (b / 1048576 | 0) + 'MB').join(' ') + ' | by per-file bytes: <1MB ' + (sizes[0] / 1048576 | 0) + ' <8MB ' + (sizes[1] / 1048576 | 0) + ' <32MB ' + (sizes[2] / 1048576 | 0) + ' MB');
		const r = reqStats, mb = (b) => (b / 1048576).toFixed(0);
		let wholeN = 0, wholeB = 0, partN = 0, partB = 0; const wholeBig = [];
		for (const [pth, b] of fileBytes) {
			const f = files[pathIndex.get(pth)];
			if (f.size > 262144 && b >= 0.9 * f.size) { wholeN++; wholeB += b; wholeBig.push([pth, b]); } else { partN++; partB += b; }
		}
		wholeBig.sort((a, b) => b[1] - a[1]);
		log('[io] files read (almost) completely: ' + wholeN + ' = ' + (wholeB / 1048576 | 0) + ' MB; everything else: ' + partN + ' files = ' + (partB / 1048576 | 0) + ' MB; biggest whole reads: ' + wholeBig.slice(0, 12).map(([pth, b]) => pth.split('/').slice(-2).join('/') + ' ' + (b / 1048576 | 0)).join(' | '));
		log('[io] engine requests: ' + r.n + ' (' + mb(r.bytes) + ' MB asked) <=64K: ' + r.small[0] + ' (' + mb(r.small[1]) + ' MB), <=1M: ' + r.mid[0] + ' (' + mb(r.mid[1]) + ' MB), >1M: ' + r.big[0] + ' (' + mb(r.big[1]) + ' MB); starting in the first 1 MB of a file: ' + r.head[0] + ' (' + mb(r.head[1]) + ' MB)');
		log('[io] ' + ((performance.now() - statT0) / 1000 | 0) + 's ' + (statTotal / 1048576 | 0) + ' MB fetched, ' + fileBytes.size + ' files; top: ' + top);
	}
}
const reqStats = { n: 0, bytes: 0, small: [0, 0], mid: [0, 0], big: [0, 0], head: [0, 0] };		// diagnostics: requests by size class; `head` = starting in the first 1 MB of a file
// ?log=1: every 5 s, how the network is used (how many fetches are in flight is the speed: a fetch costs a round trip) and how often and how long the engine waited for it
const netStat = { started: 0, active: 0, maxActive: 0, demand: 0, demandMiss: 0, demandWaitMs: 0, cold: 0, slowLogged: 0 };		// cold: reads that had to start their own fetch (nobody hinted them); the other misses joined a fetch in flight (hinted, but not finished yet)
function startNetStats() {
	let last = { started: 0, demand: 0, demandMiss: 0, demandWaitMs: 0, bytes: 0, cold: 0 }, t = performance.now();
	setInterval(() => {
		const now = performance.now(), s = (now - t) / 1000, mb = (statTotal - last.bytes) / 1048576;
		const started = netStat.started - last.started, demand = netStat.demand - last.demand, miss = netStat.demandMiss - last.demandMiss, wait = netStat.demandWaitMs - last.demandWaitMs, cold = netStat.cold - last.cold;
		t = now; last = { started: netStat.started, demand: netStat.demand, demandMiss: netStat.demandMiss, demandWaitMs: netStat.demandWaitMs, bytes: statTotal, cold: netStat.cold };
		if (!started && !demand) return;
		log('[io] net ' + s.toFixed(0) + ' s: ' + mb.toFixed(1) + ' MB (' + (mb / s).toFixed(2) + ' MB/s), fetches started ' + started + ', in flight now ' + netStat.active + ' (most ' + netStat.maxActive + '), engine reads ' + demand + ', of which ' + miss + ' waited for the network (' + cold + ' not hinted; ' + (miss ? (wait / miss).toFixed(0) : 0) + ' ms each), hint queue ' + hintQueue.length + ', hints seen ' + hintsSeen + ' fetched ' + hintsFetched);
		netStat.maxActive = netStat.active;
	}, 5000);
}
let traceOn = false, traceBuf = [], traceN = 0;
function noteTrace(id, off, len) {		// ?trace=1: every engine request (file index, offset, length), posted in batches: tools analyse them offline
	if (traceN++ > 60000) return;
	traceBuf.push(id + ',' + off + ',' + len);
	if (traceBuf.length >= 2000) { log('[trace] ' + traceBuf.join(';')); traceBuf = []; }
}
function noteRequest(off, len) {
	const r = reqStats; r.n++; r.bytes += len;
	const c = len <= 65536 ? r.small : len <= 1048576 ? r.mid : r.big; c[0]++; c[1] += len;
	if (off < 1048576) { r.head[0]++; r.head[1] += len; }
}
function report(n) {
	pendingBytes += n;
	const now = performance.now();
	if (now - lastPost > 400) { lastPost = now; bc.postMessage({ dl: pendingBytes }); pendingBytes = 0; }
}

// ---- persistent store --------------------------------------------------------------------------------------------------------------------------------------
let sh = null, jh = null, storeEnd = 0, journalEnd = 16;
const index = new Map();		// id * 1048576 + block -> offset in store.bin
const pendingJournal = [];
const inflight = new Map();		// same key -> Promise of the run fetching the block
const memCache = new Map();		// fallback without a store: key -> Uint8Array (LRU)
let memBytes = 0;
const blockLen = (f, block) => Math.min(BS, f.size - block * BS);
// The server's copy of a file is shorter than the manifest says (it changed after the manifest was made: serve.py warns at start): from now on the file is that long, so
// reads past its end come back short (end of file) instead of failing over and over (the engine retries a failed read forever: CFileMgr::ReadLine on loadingtime.dat).
function shrink(f, size) {
	if (size >= f.size) return;
	log('[io] ' + f.path + ' is ' + size + ' bytes on the server, not ' + f.size + ' as the manifest says: reading it as ' + size + ' bytes (regenerate the manifest)');
	f.size = size;
}
// Indexes the blocks a..b of a run of file f stored at `offset`, of which `got` of `fullBytes` bytes arrived (fewer: the file ends inside the run).
function indexRun(id, f, a, b, offset, got, fullBytes) {
	const keep = (k) => { index.set(id * 1048576 + k, offset + (k - a) * BS); pendingJournal.push([id, k, offset + (k - a) * BS]); };
	if (got >= fullBytes) { for (let k = a; k <= b; k++) keep(k); return; }
	shrink(f, a * BS + got);
	const whole = Math.floor(got / BS);
	for (let k = a; k < a + whole; k++) keep(k);
	// The file's new last block, partly filled: this session only. The journal would bring it back next time under the manifest's longer size, and reads would run past its
	// bytes into whatever follows in the store.
	if (got % BS) index.set(id * 1048576 + a + whole, offset + whole * BS);
}

async function openStore(version) {
	try {
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('gamedata', { create: true });
		// A reload while the previous page's io worker is still shutting down finds the files locked (sync access handles are exclusive): wait for it to let go.
		const openHandle = async (name) => {
			for (let attempt = 0; ; attempt++) {
				try { return await (await dir.getFileHandle(name, { create: true })).createSyncAccessHandle(); }
				catch (e) { if (attempt >= 40 || e.name !== 'NoModificationAllowedError') throw e; await new Promise((r) => setTimeout(r, 250)); }		// up to 10 s
			}
		};
		const s = await openHandle('store.bin');
		let j;
		try { j = await openHandle('journal.bin'); } catch (e) { s.close(); throw e; }
		const head = new DataView(new ArrayBuffer(16));
		let ok = false;
		if (j.getSize() >= 16) {
			j.read(new Uint8Array(head.buffer), { at: 0 });
			ok = head.getUint32(0, true) === 0x4a415449 && head.getFloat64(8, true) === version;
		}
		if (!ok) {
			s.truncate(0); j.truncate(0);
			head.setUint32(0, 0x4a415449, true); head.setFloat64(8, version, true);
			j.write(new Uint8Array(head.buffer), { at: 0 });
			j.flush();
		}
		storeEnd = s.getSize();
		const size = j.getSize();
		const n = Math.floor((size - 16) / 16);
		const buf = new Uint8Array(n * 16);
		if (n) j.read(buf, { at: 16 });
		const dv = new DataView(buf.buffer);
		let good = 0;
		for (let i = 0; i < n; i++) {
			const id = dv.getUint32(i * 16, true), block = dv.getUint32(i * 16 + 4, true), off = dv.getUint32(i * 16 + 8, true) + dv.getUint32(i * 16 + 12, true) * 4294967296;
			const f = files[id];
			if (f && off + blockLen(f, block) <= storeEnd) { index.set(id * 1048576 + block, off); good++; }
		}
		journalEnd = 16 + n * 16;
		sh = s; jh = j;
		log('[io] persistent store: ' + good + ' blocks (' + (good * BS / 1048576 | 0) + ' MB), store.bin ' + (storeEnd / 1048576 | 0) + ' MB');
	} catch (e) {
		sh = jh = null;
		log('[io] no persistent store (' + e.message + '): blocks are cached in memory only');
	}
}

// ---- boot read set: recorded with ?record=1, replayed at page load ----------------------------------------------------------------------------------------
// The engine reads (almost) the same ~600 MB of archive headers and start-up data on every boot. A run with ?record=1 logs the block ranges per file in order of first
// touch (POST /log, record_bootset.py extracts them); every later page load fetches that set right away, with several requests in flight, in parallel with the download
// and start-up of the engine instead of one blocking request at a time from its threads.
let recording = false;
const touched = new Map();		// path -> [[first, last], ...]
function recordTouch(id, a, b) {		// byte range actually asked for by the engine (no read-ahead, independent of the block size)
	const p = files[id].path;
	let r = touched.get(p);
	if (!r) { r = []; touched.set(p, r); if (touched.size === 1) setTimeout(dumpRecording, 75000); }
	r.push([a, b]);
}
function dumpRecording() {
	const out = [];
	for (const [p, r] of touched) {
		r.sort((x, y) => x[0] - y[0]);
		const m = [];
		for (const [a, b] of r) { const l = m[m.length - 1]; if (l && a <= l[1] + 4096) l[1] = Math.max(l[1], b); else m.push([a, b]); }
		out.push([p, m]);
	}
	log('[bootset] ' + JSON.stringify(out));
}

// An overloaded host answers 503/500/429 (seen 2026-10-06: 10,000 visitors in a day, thousands of error responses, and the engine quits when a data file cannot be read): such an
// answer, or none, is retried up to 8 times with growing, jittered waits (~20 s in all). Only the start of a response is retried (nothing of its body has been used yet).
async function fetchRetry(url, init) {
	for (let attempt = 0; ; attempt++) {
		let res = null, err = null;
		try { res = await fetch(url, init); } catch (e) { err = e; }
		if (res && res.status < 500 && res.status !== 429) return res;
		if (attempt >= 7) { if (res) return res; throw err; }
		netStat.retries = (netStat.retries || 0) + 1;
		await new Promise((r) => setTimeout(r, Math.min(5000, 300 * 2 ** attempt) * (0.5 + Math.random())));
	}
}
async function sha1Hex(s) { return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1', new TextEncoder().encode(s))), (b) => b.toString(16).padStart(2, '0')).join(''); }
let dataVersion = '';		// the manifest's version (set when it is loaded): part of a cached batch's name
// One POST /data/batch answers a list of block runs with one streamed body: thousands of small archive pieces cost one round trip per batch instead of one each.
// The boot set's batches are the same for every visitor (`wanted` marks the files this visitor still needs; the rest of the batch is read and dropped), so the host keeps each one as a
// static file named after a hash of its request (host/index.php save_batch): it is asked for with a plain GET first, which Cloudflare caches, and only if that fails (not built yet,
// an old host, no DecompressionStream) does the POST build it.
function batchFetch(runsIn, compressed, wanted) {
	const runs = runsIn.map((r) => {
		const f = files[r.id], bytes = (r.b - r.a) * BS + blockLen(f, r.b), skip = !!wanted && !wanted.has(r.id), offset = skip ? 0 : storeEnd;
		if (!skip) storeEnd += bytes;
		return { id: r.id, a: r.a, b: r.b, f, bytes, offset, skip };
	});
	netStat.started++; if (++netStat.active > netStat.maxActive) netStat.maxActive = netStat.active;
	const p = (async () => {
		const body = JSON.stringify(runs.map((r) => [r.f.path, r.a * BS, r.a * BS + r.bytes - 1]));
		let lens = runs.map((r) => r.bytes);
		const consume = async (reader) => {
			let ri = 0, inRun = 0;
			while (ri < runs.length && lens[ri] === 0) ri++;
			for (;;) {
				const { done, value } = await reader.read();
				if (done) break;
				report(value.length);
				for (let pos = 0; pos < value.length && ri < runs.length;) {
					const r = runs[ri], n = Math.min(value.length - pos, lens[ri] - inRun);
					if (!r.skip) { sh.write(value.subarray(pos, pos + n), { at: r.offset + inRun }); tally(r.f, n); }
					inRun += n; pos += n;
					if (inRun === lens[ri]) { ri++; inRun = 0; while (ri < runs.length && lens[ri] === 0) ri++; }
				}
			}
			if (ri !== runs.length) throw new Error('short batch answer: ' + ri + ' of ' + runs.length + ' runs');
		};
		let cached = false;
		if (compressed && dataVersion && self.crypto && crypto.subtle && typeof DecompressionStream !== 'undefined') {
			try {
				const res = await fetch(base + 'batchc/' + await sha1Hex(dataVersion + ':' + body) + '.bin' + dataQuery, { priority: 'low' });
				if (res.ok && res.body) { await consume(res.body.pipeThrough(new DecompressionStream('gzip')).getReader()); cached = true; netStat.batchCached = (netStat.batchCached || 0) + 1; }
			} catch (e) { /* not built yet or unusable: the POST below builds and sends it (blocks written so far are written again at the same places) */ }
		}
		if (!cached) {
			const res = await fetchRetry(base + (compressed ? 'batch?gz=1' + (dataVersion ? '&c=1&v=' + encodeURIComponent(dataVersion) : '') : 'batch'), { method: 'POST', priority: 'low', body });
			if (!res.ok) throw new Error('HTTP ' + res.status + ' for a batch');
			// the length of each range as sent (a range is clamped at the end of the server's copy of the file); without the header, the lengths asked for
			const sent = (res.headers.get('X-Run-Lengths') || '').split(',').map(Number);
			lens = sent.length === runs.length && sent.every((n, i) => n >= 0 && n <= runs[i].bytes) ? sent : runs.map((r) => r.bytes);
			await consume(res.body.getReader());
		}
		runs.forEach((r, i) => { if (!r.skip) indexRun(r.id, r.f, r.a, r.b, r.offset, lens[i], r.bytes); });
		scheduleFlush();
	})();
	const done = () => { netStat.active--; for (const r of runs) if (!r.skip) for (let k = r.a; k <= r.b; k++) inflight.delete(r.id * 1048576 + k); };
	for (const r of runs) if (!r.skip) for (let k = r.a; k <= r.b; k++) inflight.set(r.id * 1048576 + k, p);
	p.then(done, done);
	return p;
}

// Lanes: the host answers a Range request (Apache) at a few hundred KB/s per stream whatever the link is, and the speed grows with the number of streams (measured from here:
// 6 in flight 3.4 MB/s, 32 3.6, 64 7.1, 128 14.1 MB/s): the boot set (~580 MB) is fetched as ranges, RUN_LANES at a time. Compressible small files still go through the host's
// PHP (compressed batches), few at a time: PHP answers about 16 requests at once.
const RUN_LANES = 16, BATCH_LANES = 4, RUN_GAP = 64;		// local SSD serve: 16 lanes is plenty and leaves CPU cycles for the game (remote host needed 32+)
async function prefetch(name) {
	let set;
	try { const r = await fetchRetry(base + name, { cache: 'no-store' }); if (!r.ok) return; set = await r.json(); } catch (e) { return; }
	// in boot order: compressible small files whole, in compressed batches; everything else as runs of at most MAX_RUN blocks (1 MB)
	const runs = [], batches = [];
	let cbatch = [], cbytes = 0;
	const addRuns = (id, a, b) => { for (let k = a; k <= b; k += MAX_RUN) runs.push({ id, a: k, b: Math.min(b, k + MAX_RUN - 1) }); };
	for (const [path, ranges] of set) {
		const id = pathIndex.get(path);
		if (id === undefined) continue;
		const f = files[id], lastBlock = Math.ceil(f.size / BS) - 1;
		if (COMPRESSIBLE.test(f.path) && f.size <= WHOLE_MAX) {		// small compressible files: whole files, several per request, compressed by the server
			cbatch.push({ id, a: 0, b: lastBlock }); cbytes += f.size;
			if (cbytes >= 4194304 || cbatch.length >= 300) { batches.push(cbatch); cbatch = []; cbytes = 0; }
			continue;
		}
		let cur = null;
		for (const [x, y] of ranges) {
			const a = Math.floor(x / BS), b = Math.min(Math.floor(y / BS), lastBlock);
			if (cur && a <= cur.b + RUN_GAP) cur.b = Math.max(cur.b, b);
			else { if (cur) addRuns(id, cur.a, cur.b); cur = { a, b }; }
		}
		if (cur) addRuns(id, cur.a, cur.b);
	}
	if (cbatch.length) batches.push(cbatch);
	const t0 = performance.now();
	log('[io] prefetching the boot set: ' + set.length + ' files, ' + runs.length + ' ranges, ' + batches.length + ' compressed batches');
	let nextRun = 0, nextBatch = 0;
	const runLane = async () => {
		while (nextRun < runs.length) {
			const r = runs[nextRun++];
			try { await ensureBlocks(r.id, r.a, r.b, true); } catch (e) { log('[io] prefetch failed: ' + e.message); }		// blocks already stored or on their way cost nothing
		}
	};
	const batchLane = async () => {
		while (nextBatch < batches.length) {
			const full = batches[nextBatch++], wanted = new Set(full.filter((it) => untouched(it.id, files[it.id])).map((it) => it.id));		// files the engine already fetched meanwhile are dropped from the answer, not from the request: the request is the same for everybody
			try { if (wanted.size) await batchFetch(full, true, wanted); } catch (e) { log('[io] prefetch failed: ' + e.message); }
		}
	};
	await Promise.all([...Array.from({ length: RUN_LANES }, runLane), ...Array.from({ length: BATCH_LANES }, batchLane)]);
	log('[io] boot set prefetched in ' + ((performance.now() - t0) / 1000 | 0) + ' s, ' + (statTotal / 1048576 | 0) + ' MB fetched so far; ' + (netStat.batchCached || 0) + ' of ' + batches.length + ' batches from the host\'s static copies, ' + (netStat.retries || 0) + ' retried requests');
}

let flushTimer = 0;
function writeJournal() {
	if (!pendingJournal.length || !jh || !sh) return;
	const n = pendingJournal.length;
	const buf = new DataView(new ArrayBuffer(n * 16));
	pendingJournal.forEach((e, i) => { buf.setUint32(i * 16, e[0], true); buf.setUint32(i * 16 + 4, e[1], true); buf.setUint32(i * 16 + 8, e[2] % 4294967296, true); buf.setUint32(i * 16 + 12, Math.floor(e[2] / 4294967296), true); });
	pendingJournal.length = 0;
	try {
		sh.flush();		// the data first, then the entries that point at it
		jh.write(new Uint8Array(buf.buffer), { at: journalEnd });
		journalEnd += n * 16;
		jh.flush();
	} catch (e) { log('[io] journal write failed: ' + e.message); }
}
function scheduleFlush() {
	if (flushTimer || !jh) return;
	flushTimer = setTimeout(() => { flushTimer = 0; writeJournal(); }, 2000);
}

// ---- fetching --------------------------------------------------------------------------------------------------------------------------------------------------
// Streams bytes [start, end] of file f; onChunk(u8, positionInRange) receives the body as it arrives. `low`: speculative (boot set, read-ahead): the browser serves it after everything
// else on the connection (fetch priority), so that a read the engine is blocked on is not queued behind megabytes of it (measured: engine reads waited up to 6.6 s behind 32 prefetch streams).
async function fetchRange(f, start, end, onChunk, whole, low) {
	netStat.started++; if (++netStat.active > netStat.maxActive) netStat.maxActive = netStat.active;
	try { return await fetchRangeRaw(f, start, end, onChunk, whole, low); } finally { netStat.active--; }
}
async function fetchRangeRaw(f, start, end, onChunk, whole, low) {
	const url = base + f.path.split('/').map(encodeURIComponent).join('/') + dataQuery;		// ?v=<manifest version>: the same URL always has the same bytes, so the host (and Cloudflare, with a rule for /data/) may cache it for ever
	// no-store: the host's own static serving of a range (Apache, host/data/.htaccess) sends no Cache-Control, and Chrome would keep every 206 in its HTTP cache next to this store
	const init = { cache: 'no-store', priority: low ? 'low' : 'high' };
	if (!whole) init.headers = { Range: 'bytes=' + start + '-' + end };		// whole: the server sends a compressed copy, the browser decodes it
	const res = await fetchRetry(url, init);
	if (res.status !== 206 && res.status !== 200) throw new Error('HTTP ' + res.status + ' for ' + f.path);
	let skip = res.status === 200 ? start : 0;		// a server that ignores Range sends the whole file
	const total = end - start + 1;
	const reader = res.body.getReader();
	let pos = 0;
	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		report(value.length); tally(f, value.length);
		let chunk = value;
		if (skip) {
			const drop = Math.min(skip, chunk.length);
			skip -= drop; chunk = chunk.subarray(drop);
		}
		if (chunk.length > total - pos) chunk = chunk.subarray(0, total - pos);
		if (chunk.length) { onChunk(chunk, pos); pos += chunk.length; }
		if (pos >= total) { reader.cancel().catch(() => {}); break; }
	}
	return pos;
}

// Makes sure blocks first..last of file id are in the store; returns when they are.
// Compressible small files (shader effects, metadata) are fetched whole, compressed by the server: the engine reads them completely anyway.
const COMPRESSIBLE = /\.(fxc|meta|xml|dat|ymt|txt|csv|gfx|json|sps|cfg)$/i, WHOLE_MAX = 8 * 1048576;
function untouched(id, f) {
	if (!COMPRESSIBLE.test(f.path) || f.size > WHOLE_MAX) return false;
	for (let b = 0, n = Math.ceil(f.size / BS); b < n; b++) if (index.has(id * 1048576 + b) || inflight.has(id * 1048576 + b)) return false;
	return true;
}
const SLICE_BLOCKS = 32;		// 128 KB: see startRun
async function ensureBlocks(id, first, last, low) {
	const f = files[id], waits = [];
	last = Math.min(last, Math.ceil(f.size / BS) - 1);		// the file may have turned out shorter than the manifest says (shrink)
	if (first > last) return;
	let runStart = -1;
	if (untouched(id, f)) { first = 0; last = Math.ceil(f.size / BS) - 1; }
	const whole = first === 0 && last === Math.ceil(f.size / BS) - 1 && untouched(id, f);
	const startRun = (a, b, wholeFile) => {
		const offset = storeEnd, bytes = (b - a) * BS + blockLen(f, b);		// a run is whole blocks of the file: only the last can be short
		storeEnd += bytes;
		const p = (async () => {
			// A read the engine may be blocked on (not low) is cut into slices fetched side by side: one stream through the host moves ~0.15 MB/s after its round trip of ~0.6 s (a 512 KB
			// read took 2-5 s, measured), so eight of them in parallel finish in about a second. Speculative runs (low) stay whole: their speed is the number in flight, not their latency.
			const slice = wholeFile || low ? b - a + 1 : SLICE_BLOCKS, jobs = [];
			for (let s = a; s <= b; s += slice) {
				const e = Math.min(b, s + slice - 1), pos = (s - a) * BS, n = (e - s) * BS + blockLen(f, e);
				jobs.push(fetchRange(f, s * BS, s * BS + n - 1, (chunk, at) => sh.write(chunk, { at: offset + pos + at }), wholeFile, low).then((g) => [g, n]));
			}
			let got = 0;
			for (const [g, n] of await Promise.all(jobs)) { got += g; if (g < n) break; }		// a short slice: the file ends there
			indexRun(id, f, a, b, offset, got, bytes);
			scheduleFlush();
		})();
		for (let k = a; k <= b; k++) inflight.set(id * 1048576 + k, p);
		p.then(() => { for (let k = a; k <= b; k++) inflight.delete(id * 1048576 + k); }, () => { for (let k = a; k <= b; k++) inflight.delete(id * 1048576 + k); });
		waits.push(p);
	};
	if (whole) { startRun(0, last, true); await Promise.all(waits); return; }
	for (let b = first; b <= last + 1; b++) {
		const need = b <= last && !index.has(id * 1048576 + b) && !inflight.has(id * 1048576 + b);
		if (need && runStart < 0) runStart = b;
		if (runStart >= 0 && (!need || b - runStart + 1 > MAX_RUN)) {
			startRun(runStart, b - 1);
			runStart = need ? b : -1;
		}
		if (b <= last && inflight.has(id * 1048576 + b)) waits.push(inflight.get(id * 1048576 + b));
	}
	await Promise.all(waits);
}

const seq = new Map();		// file id -> { end: offset after the last read, ahead: current read-ahead bytes }
let sharedReadFails = false;
// Copies [off, off + len) of file id from the store into the heap at dst.
function readFromStore(id, off, len, dst) {
	let done = 0;
	while (done < len) {
		const pos = off + done, block = Math.floor(pos / BS);
		let storeOff = index.get(id * 1048576 + block) + (pos - block * BS), n = Math.min(len - done, (block + 1) * BS - pos);
		// merge the following blocks while they are contiguous in the store
		for (let b = block + 1; done + n < len; b++) {
			const nextOff = index.get(id * 1048576 + b);
			if (nextOff === undefined || nextOff !== storeOff + n) break;
			n += Math.min(len - done - n, BS);
		}
		let got;
		if (!sharedReadFails) {
			try { got = sh.read(HEAPU8.subarray(dst + done, dst + done + n), { at: storeOff }); }
			catch (e) { sharedReadFails = true; log('[io] store read into the shared heap failed (' + e.message + '): going through a temporary buffer'); }
		}
		if (sharedReadFails) {
			const tmp = new Uint8Array(n);
			got = sh.read(tmp, { at: storeOff });
			HEAPU8.set(tmp, dst + done);
		}
		if (got !== n) throw new Error('store read returned ' + got + ' of ' + n);
		done += n;
	}
}

// ---- without a store ---------------------------------------------------------------------------------------------------------------------------------------
async function getMemBlock(id, block) {
	const key = id * 1048576 + block;
	const hit = memCache.get(key);
	if (hit) { memCache.delete(key); memCache.set(key, hit); return hit; }
	let p = inflight.get(key);
	if (!p) {
		const f = files[id];
		p = (async () => {
			let data = new Uint8Array(Math.min(MBS, f.size - block * MBS));
			let got = await fetchRange(f, block * MBS, block * MBS + data.length - 1, (chunk, at) => data.set(chunk, at));
			if (got < data.length) { shrink(f, block * MBS + got); data = data.subarray(0, got); }
			memCache.set(key, data); memBytes += data.length;
			while (memBytes > 48 * 1048576) { const old = memCache.keys().next().value; memBytes -= memCache.get(old).length; memCache.delete(old); }
			return data;
		})();
		inflight.set(key, p);
		p.then(() => inflight.delete(key), () => inflight.delete(key));
	}
	return p;
}

async function readWithoutStore(id, off, len, dst) {
	let done = 0;
	while (done < len) {
		const pos = off + done, block = Math.floor(pos / MBS);
		const data = await getMemBlock(id, block);
		const inBlock = pos - block * MBS, n = Math.min(len - done, data.length - inBlock);
		if (n <= 0) break;
		HEAPU8.set(data.subarray(inBlock, inBlock + n), dst + done);
		done += n;
	}
	return done;
}

// ---- requests ---------------------------------------------------------------------------------------------------------------------------------------------------
function views() {
	if (HEAPU8.length !== mem.buffer.byteLength) { HEAP32 = new Int32Array(mem.buffer); HEAPU8 = new Uint8Array(mem.buffer); }
}

async function serve(slot) {
	views();
	const w = Math.floor(table / 4) + 16 + 16 * slot;		// word index of the slot (no bit shift: the memory can grow past 4 GB)
	const id = HEAP32[w + 1], off = (HEAP32[w + 2] >>> 0) + (HEAP32[w + 3] >>> 0) * 4294967296;
	const dst = (HEAP32[w + 4] >>> 0) + (HEAP32[w + 5] >>> 0) * 4294967296;
	let len = HEAP32[w + 6];
	let result = -1;
	try {
		const f = files[id];
		noteRequest(off, len); netStat.demand++;
		if (traceOn) noteTrace(id, off, len);
		if (off >= f.size) result = 0;
		else {
			if (off + len > f.size) len = f.size - off;
			if (sh) {
				// read-ahead: a read that continues the previous one of this file (a sequential scan) also fetches the next bytes, doubling up to MAX_AHEAD; anything else fetches only what it needs
				const st = seq.get(id) || { end: -1, ahead: 0 };
				// radio and talk-radio streams (audio/sfx/RADIO_*.rpf) are read as ~33 KB blocks, one after another and each a network round trip, with nothing queued behind for the
				// hints to use: a read that starts at or soon after the end of the previous one (blocks of one track) counts as sequential whatever its size
				const radio = /\/RADIO_/i.test(f.path);
				const sequential = radio ? (st.end >= 0 && off >= st.end && off - st.end <= 65536) : (off === st.end && len >= AHEAD_MIN_READ);
				st.ahead = sequential ? Math.min(MAX_AHEAD, st.ahead ? st.ahead * 2 : FIRST_AHEAD) : 0;
				st.end = off + len;
				seq.set(id, st);
				const lastByte = Math.min(f.size, off + len + st.ahead) - 1;
				if (recording) recordTouch(id, off, off + len - 1);
				// Only the requested blocks are waited for: the read-ahead is started but the engine's read completes as soon as its own bytes are in (it waited for the read-ahead
				// download too). A request whose blocks are all stored is served synchronously, without the async block bookkeeping.
				const first = Math.floor(off / BS), needLast = Math.floor((off + len - 1) / BS), aheadLast = Math.floor(lastByte / BS);
				let need = null, cold = false; const waitStart = performance.now();
				for (let b = first; b <= needLast; b++) if (!index.has(id * 1048576 + b)) { cold = cold || !inflight.has(id * 1048576 + b); need = need || true; }
				if (need) need = ensureBlocks(id, first, needLast);
				if (aheadLast > needLast) ensureBlocks(id, needLast + 1, aheadLast, true).catch((e) => log('[io] read-ahead failed: ' + e.message));
				if (need) {
					await need; views();
					const waited = performance.now() - waitStart;
					netStat.demandMiss++; netStat.demandWaitMs += waited; if (cold) netStat.cold++;
					if (waited > 1500 && netStat.slowLogged++ < 60) log('[io] slow read ' + (waited | 0) + ' ms (' + (cold ? 'not hinted' : 'hinted, not finished') + '): ' + f.path + ' at ' + off + ' for ' + len + ' bytes, in flight ' + netStat.active);
				}
				if (off + len > f.size) len = Math.max(0, f.size - off);		// the file turned out shorter than the manifest says (shrink)
				readFromStore(id, off, len, dst);
				result = len;
			} else result = await readWithoutStore(id, off, len, dst);
		}
	} catch (e) {
		log('[io] read failed: ' + e.message);
	}
	views();
	Atomics.store(HEAP32, w + 7, result);
	Atomics.store(HEAP32, w, 2);
	Atomics.notify(HEAP32, w, 1);
}

// Hints (read announcements from the engine, see the protocol above): queued here and fetched into the store; a demand read that arrives meanwhile joins the fetch in flight
// (ensureBlocks), one that arrives after finds its blocks stored. Hints for blocks already stored or on their way cost nothing. Two kinds: reads the engine has queued (normal) and
// look-ahead at objects it has requested but not queued yet (bit 30 of the length: strStreamingInfoManager::WasmAnnounceUpcoming); the first are fetched first, the second only while
// fewer than LOW_PAR are in flight and at low fetch priority, so that the reads the engine blocks on (the audio engine's included) are not queued behind them.
const HINT_PAR = 24, LOW_PAR = 8, HINT_QUEUE_MAX = 2000;		// local SSD serve: 24 in flight keeps the ~6 sockets fed with far less CPU/queue churn (remote tuning was 96/48 for ~1.5 s reads over the internet)
const hintQueue = [], lowQueue = [];
let hintActive = 0, lowActive = 0, hintsSeen = 0, hintsFetched = 0;
function pumpHints() {
	for (;;) {
		const low = !hintQueue.length;
		if (hintActive + lowActive >= HINT_PAR || (low && (!lowQueue.length || lowActive >= LOW_PAR))) return;
		const [id, off, len] = (low ? lowQueue : hintQueue).shift();
		const f = files[id];
		if (!f || off >= f.size) continue;
		const a = Math.floor(off / BS), b = Math.floor((Math.min(f.size, off + len) - 1) / BS);
		let need = false;
		for (let k = a; k <= b && !need; k++) need = !index.has(id * 1048576 + k) && !inflight.has(id * 1048576 + k);
		if (!need) continue;
		if (low) lowActive++; else hintActive++;
		hintsFetched++;
		ensureBlocks(id, a, b, low).catch(() => {}).finally(() => { if (low) lowActive--; else hintActive--; pumpHints(); });
	}
}
function drainHints(bell) {
	const ring = Atomics.load(HEAP32, bell + 2), cap = Atomics.load(HEAP32, bell + 3);
	if (!ring || !cap || !sh || noHints) return;		// an engine without hints, no store to fetch into, or ?nohints=1
	const head = Atomics.load(HEAP32, bell + 4) >>> 0;
	let tail = Atomics.load(HEAP32, bell + 5) >>> 0;
	if (((head - tail) >>> 0) > cap) tail = (head - cap) >>> 0;		// the engine lapped us: the oldest hints were overwritten
	while (tail !== head) {
		const e = bell + ring + 4 * (tail % cap);
		const raw = Atomics.load(HEAP32, e + 3);
		if (!raw) break;		// claimed but not written yet: its writer rings the doorbell again when it is
		(raw & 0x40000000 ? lowQueue : hintQueue).push([HEAP32[e], (HEAP32[e + 1] >>> 0) + (HEAP32[e + 2] >>> 0) * 4294967296, raw & 0x3fffffff]);
		hintsSeen++;
		Atomics.store(HEAP32, e + 3, 0);
		tail = (tail + 1) >>> 0;
	}
	Atomics.store(HEAP32, bell + 5, tail);
	if (hintQueue.length > HINT_QUEUE_MAX) hintQueue.splice(0, hintQueue.length - HINT_QUEUE_MAX);
	if (lowQueue.length > HINT_QUEUE_MAX) lowQueue.splice(0, lowQueue.length - HINT_QUEUE_MAX);
	pumpHints();
}

async function loop() {
	const bell = Math.floor(table / 4);
	for (;;) {
		views();
		const seen = Atomics.load(HEAP32, bell);		// read before the scan: a request posted during the scan changes the doorbell and the wait below returns at once
		const n = Atomics.load(HEAP32, bell + 1);
		for (let slot = 0; slot < n; slot++)
			if (Atomics.compareExchange(HEAP32, bell + 16 + 16 * slot, 1, 3) === 1)
				serve(slot);
		drainHints(bell);
		const r = Atomics.waitAsync(HEAP32, bell, seen);
		if (r.async) await r.value;
	}
}

let ready = null;
async function init(m) {
	base = m.base; bc = new BroadcastChannel('game-progress'); remoteLog = !!m.log; noHints = !!m.noHints;
	const j = await (await fetchRetry(base + 'manifest.json', { cache: 'no-store' })).json();
	files = j.files.map((f) => ({ path: f[0], size: f[1] }));
	dataQuery = j.version ? '?v=' + encodeURIComponent(j.version) : ''; dataVersion = j.version ? String(j.version) : '';
	files.forEach((f, i) => pathIndex.set(f.path, i));
	recording = !!m.record; traceOn = !!m.trace;
	if (remoteLog) startNetStats();
	if (!m.noStore) await openStore(Number(String(j.version).replace(/\D/g, '')) || 0);
	if (sh && m.bootset && !m.record) prefetch(m.bootset);
}

// The page tells us when it is going away (pagehide): close the handles at once so the next load can take them.
new BroadcastChannel('game-io').onmessage = (ev) => {
	if (ev.data !== 'close') return;
	if (flushTimer) { clearTimeout(flushTimer); flushTimer = 0; }
	writeJournal();
	try { if (sh) sh.close(); if (jh) jh.close(); } catch (e) {}
	sh = jh = null;
};

// ---- the engine's per-user files (savegames, settings): platform/file/userdata_wasm.cpp posts {userdata: {path, data, mtime}} when a file under /userdata/Documents has settled and
// {userdataDelete: path} when one is gone; they are kept in IndexedDB "gta5-userdata" / store "files" (key: path, value: {data, mtime}) and put back into the engine's
// in-memory /userdata by loader.js before it starts. IndexedDB, not the OPFS store above: that one is exclusive to a single tab and is keyed to the game data's version.
let userdataDb = null;
const openUserdata = () => userdataDb || (userdataDb = new Promise((resolve, reject) => {
	const r = indexedDB.open('gta5-userdata', 1);
	r.onupgradeneeded = () => r.result.createObjectStore('files');
	r.onsuccess = () => resolve(r.result);
	r.onerror = () => { userdataDb = null; reject(r.error); };
}));
async function userdataWrite(path, record) {
	try {
		const db = await openUserdata();
		await new Promise((resolve, reject) => {
			const t = db.transaction('files', 'readwrite');
			if (record) t.objectStore('files').put(record, path); else t.objectStore('files').delete(path);
			t.oncomplete = resolve;
			t.onerror = t.onabort = () => reject(t.error);
		});
		log('[io] userdata ' + (record ? 'stored ' + path + ' (' + record.data.length + ' bytes)' : 'deleted ' + path));
	} catch (e) {
		fetch('/log', { method: 'POST', body: '[io] userdata ' + path + ' NOT stored (the save will be lost when the tab closes): ' + e }).catch(() => {});		// whatever ?log=1 says: a lost save is worth a line
	}
}

self.onmessage = async (ev) => {
	const m = ev.data;
	if (m.userdata) { userdataWrite(m.userdata.path, { data: m.userdata.data, mtime: m.userdata.mtime }); return; }
	if (m.userdataDelete) { userdataWrite(m.userdataDelete, null); return; }
	if (m.init) { ready = init(m); return; }		// sent by loader.js as soon as the page starts
	if (!m.memory) return;
	mem = m.memory; HEAP32 = new Int32Array(mem.buffer); HEAPU8 = new Uint8Array(mem.buffer);
	table = m.table;
	await ready;		// the store is open and the manifest is loaded
	loop();
};
self.postMessage({ loaded: true });
