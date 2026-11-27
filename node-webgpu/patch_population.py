p = r'E:\gta\playgta5\node-webgpu\wgpu_worker_node.js'
s = open(p, encoding='utf-8', errors='replace').read()
anchor = "let canvas = null, canvasCtx = null, canvasFormat = null, blit = null, blitSampler = null, canvasConfigured = false;"
fn = """// population density override (Node-only, env-configurable): ambient peds + scenario peds
const PED_DENSITY = (isNode && process.env.WGPU_PED_DENSITY !== undefined) ? +process.env.WGPU_PED_DENSITY : 0;
function patchPopulation() {
	if (!PED_DENSITY) return;
	try {
		const dv = new DataView(mem.buffer);
		dv.setFloat32(7155636, PED_DENSITY, true);
		if (!patchPopulation.logged) {
			patchPopulation.logged = true;
			logLine('population: ambient peds ' + PED_DENSITY + ' written to 7155636');
		}
	} catch (e) { if (!patchPopulation.err) { patchPopulation.err = true; logLine('population error ' + e.message); } }
}
"""
assert anchor in s
s = s.replace(anchor, fn + anchor, 1)
old = "async function present(id) {\n\tpatchLod();"
new = "async function present(id) {\n\tpatchLod();\n\tpatchPopulation();"
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('population patch installed')
