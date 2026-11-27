# Write clean WAT without BOM; memory64 syntax for WABT 1.0.41
open(r'E:\gta\playgta5\node-webgpu\mem64.wat', 'w', encoding='utf-8', newline='').write('(module (memory (export "m") i64 1 10))\n')
print('WAT written')
