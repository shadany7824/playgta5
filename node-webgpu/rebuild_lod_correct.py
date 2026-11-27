from pathlib import Path

src = Path(r'E:\Malik\game\game.wat')
out = Path(r'E:\Malik\game\game-lodlive.wat')
s = src.read_text(encoding='utf-8', errors='replace')

if '$gta_lod_cutoff' not in s:
    s = s.replace('(module $game.wasm\n', '(module $game.wasm\n  (global $gta_lod_cutoff (export "gta_lod_cutoff") (mut f32) (f32.const 50))\n', 1)

old1 = '''      i64.const 7300188
      i32.load
      local.tee 5
      i32.const 0
      i32.ge_s
      if  ;; label = @2
        local.get 2
        local.get 5
        i32.store
      end
      return
'''
new1 = old1.replace('      return\n', '''      local.get 1
      global.get $gta_lod_cutoff
      f32.lt
      if
        local.get 2
        i32.const 0
        i32.store
        local.get 3
        i32.const 255
        i32.store
      end
      return
''')

old2 = '''        local.get 3
        local.get 6
        i32.store
        local.get 4
        i32.const -1
        i32.store
      end
      return
'''
new2 = old2.replace('      return\n', '''      local.get 1
      global.get $gta_lod_cutoff
      f32.lt
      if
        local.get 3
        i32.const 0
        i32.store
        local.get 4
        i32.const 255
        i32.store
      end
      return
''')

assert s.count(old1) == 1, ('func1 context count', s.count(old1))
assert s.count(old2) == 1, ('func2 context count', s.count(old2))
s = s.replace(old1, new1, 1).replace(old2, new2, 1)
out.write_text(s, encoding='utf-8', newline='')
print('rebuilt game-lodlive.wat with correct output-LOD patch')
print('gta_lod_cutoff refs:', s.count('$gta_lod_cutoff'))
