import re

DCMP_IDX = r'E:\gta\playgta5\.claude\memory\engine-code-map\engine-function-index.tsv'
VER = r'E:\gta\playgta5\.claude\memory\engine-code-map\verified-30000-lines.txt'

idx = open(DCMP_IDX, encoding='utf-8').read().split('\n')
funcs = []
for l in idx:
    p = l.split('\t')
    if len(p) >= 2 and p[1].isdigit():
        funcs.append((int(p[1]), p[0]))
funcs.sort()

K1 = ('rage_grc','rage_dl','rage_fw','CLod','CLodScale','streaming','CSettings','CTimeCycle',
      'RageDirect3D','wasm_null','grc','Draw','Render','Cull','Visibility','CReplay','graphics',
      'CVehicle','CPed','CEntity','Entity','rage_at','rage_rmc')
K2 = ('network','net','CNet','CPacket','CPed','ped_','CVehicle','vehicle_','task_commands',
      'hud_commands','audio','CAudio','CAI','AI_','CReplay','money','stats','player','camera',
      'weapon','object','entity','misc_commands','socialclub','CScript','rage_at','rage_par',
      'rage_sr','rage_ptxu','rage_ph','rage_rmc')

b1 = set(n for ln, n in funcs if any(k in n for k in K1))
b1 = set(list(b1)[:10000]) if len(b1) > 10000 else b1
b2 = set(n for ln, n in funcs if any(k in n for k in K2))
b2 = set(list(b2)[:10000]) if len(b2) > 10000 else b2

# verified region 30k: read headers from the verified file
ver = open(VER, encoding='utf-8').read()
v = set(re.findall(r'^===== (\S+) \|', ver, re.M))

print('index functions total      :', len(funcs))
print('batch1 matched (prefix)    :', len(set(n for ln,n in funcs if any(k in n for k in K1))), '-> capped', len(b1))
print('batch2 matched (prefix)    :', len(set(n for ln,n in funcs if any(k in n for k in K2))), '-> capped', len(b2))
print('batch1 AND batch2 overlap    :', len(b1 & b2))
print('verified-30k functions     :', len(v))
print('verified AND batch1          :', len(v & b1))
print('verified AND batch2          :', len(v & b2))
union = b1 | b2 | v
print('DISTINCT functions with ANY analysis:', len(union))
print('remaining of 91008              :', 91008 - len(union))
print('total dcmp LINES (not functions)    :', sum(1 for _ in open(r'E:\Malik\game\game.dcmp', encoding='utf-8', errors='replace')))
