p = r'E:\gta\playgta5\node-webgpu\wgpu_worker_node.js'
s = open(p, encoding='utf-8', errors='replace').read()
old = "\tpatchLod();\n\tpatchPopulation();"
new = "\tpatchLod();\n\tpatchPopulation();\n\tif (isNode) {\n\t\tconst now = performance.now();\n\t\tif (!present.__occLast || now - present.__occLast > 10000) {\n\t\t\tpresent.__occLast = now;\n\t\t\ttry { logLine('OCCFLAG 6621392=' + new Uint8Array(mem.buffer)[6621392] + ' softRasterizer=' + (new Uint8Array(mem.buffer)[6621392] & 1 ? 'enabled' : 'DISABLED')); } catch(e) {}\n\t\t}\n\t}"
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('occlusion flag diagnostic added')
