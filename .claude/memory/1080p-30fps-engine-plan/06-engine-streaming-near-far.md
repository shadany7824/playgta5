# 06 — Streaming: load the near area fully, the far area reduced and slower

## Idea (owner's)
Today the engine streams a big area around the player. Load the **near area completely and first**, load the **far area with less detail and lower priority**, and drop far detail it doesn't need. Less world in memory/scene → fewer entities to scan and draw, less IO and CPU on 2 cores.

## Be precise about what streaming changes
- Streaming decides **what is loaded**. Drawing decides **what is visible this frame**. Loaded-but-far objects are usually drawn as LOD/SLOD (file 05). So streaming alone mostly saves **IO, memory and scan CPU**. Draws drop only if far HD objects stop being loaded, or LODs are skipped.
- Measure both: draws/frame **and** engine CPU (file 02 2B), plus hitch count (streaming spikes on 2 cores).

## Engine functions (from `engine-code-map\engine-function-index.tsv`, read bodies in `game.dcmp`)
| Function | funcidx | line | Role |
|---|---|---|---|
| `rage_fwBoxStreamer_RequestAboutPos` | 5458 | 554001 | Requests map/data boxes around a position. **Find the radius / box test**: a near/far split can happen here |
| `rage_fwMapDataStore_RequestGroup` | 5386 | 552082 | Map data group requests |
| `CStreaming_Update` | 64912 | 4287328 | Per-frame streaming update |
| `CStreaming_RequestObject` | 64933 | 4295293 | Single request (has priority flags) |
| `CStreaming_LoadAllRequestedObjects` | 64832 | 4279301 | Blocking load-all (used at load screens) |
| `CStreamVolumeMgr_RegisterSphere` / `RegisterFrustum` | 47037 / 47036 | - | Script "stream volumes": force-load a sphere/frustum. That's how scripts say "load near here fully" |
| `rage_strStreamingEngine_*` | 6124-6219 | ~592788+ | Low-level streaming engine (async placement, packfiles) |
| `CLodMgr_WithinVisibleRange` | 47333 | - | Decides if an LOD entity is in visible range |

## Steps
1. **Read `rage_fwBoxStreamer_RequestAboutPos`** fully: find the distance/radius it uses (a float constant or a global). Write: where the radius comes from (constant in code / global address / argument from the caller) and who calls it (`grep -n "rage_fwBoxStreamer_RequestAboutPos(" game.dcmp`).
2. **Find the streaming distances**: look in the callers for multipliers like `lodScale`, `fFarDist`, and timecycle values. Also check `CLodMgr_WithinVisibleRange` for the far-range cutoff.
3. **Plan the change** (write it down before patching):
   - Near radius unchanged (full HD).
   - Far radius reduced (e.g. 0.6-0.7×) or the far HD request skipped, so only LOD/SLOD is kept far away.
   - Optional: lower the priority of far requests so near ones always win (look for a priority/flags argument in `CStreaming_RequestObject`).
4. **Apply** with the proven methods: a global → JS write each frame (like file 05); a constant inside a function → WAT patch of that one function on a **copy** of game.wasm, with `harness.js` pointed at the copy (backup, `wasm-validate --enable-all`).
5. Don't touch the blocking `LoadAllRequestedObjects` path (load screens), or loading may hang.

## Measure
Draws/frame, FPS, engine wait %, hitch count > 100 ms, IO fetch count per minute (`IO FETCH` lines), RAM. Screenshots near + far, before/after. Drive/move if input is available: streaming problems show when moving (holes, missing roads).

## Pass
Fewer hitches and/or draws, with **no holes or missing ground near the player** and no endless loading. If the world gets holes, revert immediately.

## Risk
Medium-high: streaming bugs can make the game fall through the world or hang on load. Always keep the unpatched wasm one config switch away.
