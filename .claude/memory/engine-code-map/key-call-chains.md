# Key call chains — RAGE engine (verified 2026-11-23 from game.dcmp)

All line numbers are in `E:\Malik\game\game.dcmp` (WABT pseudo-C). Addresses like `19446852L` are absolute addresses in wasm linear memory.

## 1. LOD scale / draw-distance chain (the FPS lever)

```
CSettingsManager_ApplySettings()            line 4339931  func65672
  └─ reads sysParams into global settings block ~19446816..19447092
     └─ 19446852L = LodScale float (sysParam at string 25035944, "lodScale")
        set by -lodScale=N engine arg; clamped 0.0..1.0 (line 2272785)
  └─ CSettingsManager_GetSettings(19446816L)  line 4271858 func64737
       returns a + 8L  →  [7]:float == address 19446852L
```

`CTimeCycle_ApplyLodScaleModifiers(rage::tcKeyframeUncompressed&)` — line 5128333, func 77611:
```
if (settings[7]:float < 1.0) {                 // 19446852L
   b = rage_tcManager_FindModifier(25492320L, "lodscale-ish" hash)
   rage_tcModifier_Apply(b, 1.0f - settings[7]:float);   // LOD modifier
}
if (settings[39]:float > 0.0) { ... Apply(settings[39]) } // 19446912L
```
- `-lodScale=0` → modifier 1.0 (full detail, more draws). `-lodScale=1` → modifier 0 (max reduction).
- **Verified win:** `-lodScale=1` gives ~25% FPS (6.97→8.74 avg). Other reads of 19446852L: lines 4339974 (`<= 0.2f` → flag), 4340122 (`CVisualSettings` blend), 2272785 (set from sysParam).

Other LOD targets from memory (`1080p-optimization/03`):
`CLodScale_SetGlobalScaleFromScript`, `CLodMgr_OverrideLodDist`, `rage_fwBaseEntityContainer_SetLodDistCached` (line 1128509), `rage_fwScanNodes::ProcessEntityContainer` (line 1159661).

## 2. Draw generation → vtable call_indirect

Draw calls are C++ virtual calls lowered to `call_indirect` with a vtable slot (e.g. `(b[0]:long)[12]`). `RageDirect3DDeviceContext11_DrawIndexed(...)` (memory note 15) does exactly that. The function pointer comes from a vtable in wasm linear memory, NOT a fixed `__indirect_function_table` slot — that's why the table hook is hard.

Exports (from `wasm-objdump -x`): `__indirect_function_table` (89,367 entries), `func[6406]` = `rage::tcModifier::Apply_rage::tcKeyframeUncompressed&__float__const`. Elem[1] segment count 89,367.

## 3. Settings globals block (from ApplySettings, line 4339931+)
Addresses read in that function (all `[0]:float` unless noted):
| Address | Use |
|---|---|
| 19446852 | LodScale (from -lodScale) |
| 19446848 | int, -lodQuality-ish, clamped 0..3 |
| 19446856/60 | floats clamped 0..1 (shadow/reflection-ish) |
| 19446864 | int (0..3) |
| 19446852/912 | LodScale / MaxLodScale flags |
| 19446852,19446912,19446920/928/936/944 | timecycle / visual settings |
| 19447088/092 | near/far float |
| 19446960/968 | fog/distance floats |

SysParam strings found in wasm: `lodScale` @ 50368472, `lodscale` @ 49491974, `LODScale` @ 50369082, `DrawDistance` @ 48816747.

## 4. Where the engine waits (from live game-log frame profile, 2026-11-23)
- Render thread: 56–71% `DL_BEGIN_DRAW > Wait on queued frames [sleep]`
- Main thread: 46% `Wait for render [semaphore]`
- The engine blocks waiting for `wgpu_worker.js` to drain the command ring — the driver is the bottleneck.

## Wire profile (per frame at ~2,900 draws)
setPipeline 1306 · setBindGroup 3970 · setVertexBuffer 2748 · setIndexBuffer 2655 · draw 3037 · uploadBuffer 3696 · viewport 61 · stencil 281 · blend 50 · scissor 0. ~10,000 wire state calls/frame = the design gap.
