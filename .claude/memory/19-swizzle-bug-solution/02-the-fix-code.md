# 02 — The fix: `flattenSwizzles()` in `wgpu_worker_node.js`

## Where
- File: `E:\gta\playgta5\node-webgpu\wgpu_worker_node.js` (the Node-only worker copy; **don't** edit the mirror `wgpu_worker.js`, the Chrome launchers use it).
- Backup first: `copy wgpu_worker_node.js wgpu_worker_node.js.bak-swizzle-20261125`
- Put the function near the other shader helpers (file 19 says ~line 101). Call it in `shaderProgram()` **on the WGSL source string, before `packUniforms(source)`** and before `device.createShaderModule(...)`.
- Make sure **every** path that creates a shader module goes through it (`grep -n "createShaderModule" wgpu_worker_node.js`), including pipeline-seed / pre-compile paths and any compute or blit shaders built from game WGSL. Hand-written internal shaders (blit/upscale) don't need it but won't be harmed.

## Code
```js
// Tint bug crbug 553777974 (Dawn rev 1e975e28 < fix CL 338555): an outer single-component
// swizzle on a swizzle (v.yyyy.w) fails IR lowering. Compose chains: base.A.B -> base.A[idx(B)].
// Safe: swizzles only exist on vectors in WGSL; scan 2026-11-25 = 20,984 chains, 0 scalar bases,
// 0 rgba, 0 assignment targets. WGPU_FLATTEN_SWIZZLE=0 off, =all composes every chain, default = trigger only.
const SWZ_IDX = { x: 0, y: 1, z: 2, w: 3 };
const SWZ_MODE = (typeof process !== 'undefined' && process.env.WGPU_FLATTEN_SWIZZLE) || 'single';
let swzRewrites = 0;
function flattenSwizzles(src) {
	if (SWZ_MODE === '0') return src;
	// single mode MUST match only a 1-letter outer swizzle. A {1,4} outer would consume `.xyzw.xy`
	// in `v.xyzw.xy.x` and skip the overlapping `.xy.x` (bug caught by unit test 2026-11-25).
	const re = SWZ_MODE === 'all'
		? /\.([xyzw]{1,4})\.([xyzw]{1,4})(?![A-Za-z0-9_])/g
		: /\.([xyzw]{1,4})\.([xyzw])(?![A-Za-z0-9_])/g;
	let prev;
	do {
		prev = src;
		src = src.replace(re, (m, a, b, off, str) => {
			if (!/[A-Za-z0-9_)\]]/.test(str[off - 1] || '')) return m;  // must follow an expression
			let out = '';
			for (const ch of b) { const i = SWZ_IDX[ch]; if (i >= a.length) return m; out += a[i]; }
			swzRewrites++;
			return '.' + out;
		});
	} while (src !== prev);   // each rewrite shortens the text -> terminates
	return src;
}
```
Notes:
- Tested 2026-11-25 (`E:\gta\_tmp_claude\swz-test.js`): all 10 cases of file 03 T1 pass in both modes. The first version (single mode with a `{1,4}` outer + length check) FAILED on `v.xyzw.xy.x`, which is why single mode has its own regex.
- `v.xyzw.xy.x` in single mode: pass 1 rewrites `.xy.x` → `.x` (`v.xyzw.x`), pass 2 rewrites `.xyzw.x` → `.x` (`v.x`). The `do/while` repeats until nothing changes.
- In `single` mode, a chain like `v.xy.yx` (outer length 2) stays unchanged. The bug only needs the outer single case.
- The lookbehind check skips odd text (comments starting with `.`). The lookahead stops at `.xyz_foo`-style names.
- Log once per shader module when rewrites happened (for proof), e.g. in `shaderProgram`: `if (swzRewrites > before) log('[wgpu] swizzle flatten: ' + name + ' +' + (swzRewrites - before))`. Add a total to the 10 s fps line, or log it once at 60 s.

## Hash / cache caution
If the worker keys a shader or pipeline cache by **source text or its hash**, apply the flatten **before** the key is computed in one place only. Otherwise the same shader could be compiled twice. Check how `shaderProgram` caches modules (`grep -n "shaderCache\|modules.get\|hash" wgpu_worker_node.js`).

## After the edit
1. `E:\gta\playgta5\node24\node_modules\node\bin\node.exe --check wgpu_worker_node.js`
2. Do the unit tests from file 03 **before** a game run.
