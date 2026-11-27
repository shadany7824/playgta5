p = r'E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js'
s = open(p, encoding='utf-8').read()

old_start = s.find('const LOD_PATCH = 0;')
old_end = s.find('\n}', s.find('function patchLod()')) + 2
print('found range:', old_start, old_end)
print('OLD:', s[old_start:old_start+200])

new = '''const LOD_PATCH = 0.3;  // LOW global LOD scale -> shorter cull distance -> fewer draws (target FPS)
const LOD_ADDRS = [23318984];  // global LOD scale used by CGameScan_KickVisibilityJobs
const LOD_FLAG = 23319072;      // bit 1 must be set (CLodScale_SetGlobalScaleFromScript does this)
function patchLod() {
	if (!LOD_PATCH) return;
	try {
		const buf = mem.buffer;
		const scratch = new ArrayBuffer(4);
		new DataView(scratch).setFloat32(0, LOD_PATCH, true);
		const bits = new Int32Array(scratch)[0];
		const iv = new Int32Array(buf);
		for (const addr of LOD_ADDRS) Atomics.store(iv, addr >> 2, bits);
		// set enable flag bit 1 (byte at LOD_FLAG) so KickVisibilityJobs uses the scale
		const bv = new Uint8Array(buf);
		bv[LOD_FLAG] = bv[LOD_FLAG] | 1;
		if (!patchLod.logged) {
			patchLod.logged = true;
			logLine('lodpatch: wrote ' + LOD_PATCH + ' to ' + LOD_ADDRS.join(',') + ' + flag bit1 at ' + LOD_FLAG + ' (bits ' + bits + ')');
		}
	} catch (e) {
		if (!patchLod.err) { patchLod.err = true; logLine('lodpatch: error ' + (e && e.message || e)); }
	}
}'''
s = s[:old_start] + new + s[old_end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('REWROTE lodpatch with low value + flag bit')
