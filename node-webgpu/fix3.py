p = r'E:\gta\playgta5\node-webgpu\harness.js'
s = open(p, encoding='utf-8').read()
# Replace maybeStart logic: wgpu worker never sends 'loaded' in Node; start when io loaded
old = "let readyCount = 0;\nconst maybeStart = () => {\n  readyCount++;\n  if (readyCount < 2) return;\n  console.log('[harness] both workers loaded; starting game.js');\n  try { require(GAME_JS); } catch (e) { console.error('[harness] game.js load error:', e.stack || e); }\n};"
new = "let gameStarted = false;\nconst maybeStart = (who) => {\n  console.log('[harness] worker signal:', who);\n  if (gameStarted) return;\n  gameStarted = true;\n  console.log('[harness] starting game.js');\n  try { require(GAME_JS); } catch (e) { console.error('[harness] game.js load error:', e.stack || e); }\n};"
assert old in s, 'maybeStart not found'
s = s.replace(old, new, 1)
# wgpu message handler: ready signal + display messages; do not gate start on it
s = s.replace("wgpu.on('message', (m) => {\n  if (m && m.loaded) maybeStart();\n  else if (m && m.ready) console.log('[harness] wgpu worker ready');\n});",
              "wgpu.on('message', (m) => {\n  console.log('[harness] wgpu msg:', JSON.stringify(m).slice(0,150));\n});")
# io loaded triggers start
s = s.replace("io.on('message', (m) => { if (m && m.loaded) maybeStart(); });",
              "io.on('message', (m) => { if (m && m.loaded) maybeStart('io loaded'); });")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('HARNESS FIXED: start on io loaded; wgpu in Node sends ready not loaded')
