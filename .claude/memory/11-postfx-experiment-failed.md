# 11 — Post-FX arg experiment FAILED (2026-11-20)

Tested on top of the best preset (960x540, texture 2, shadow 0, reflection 1, particles/grass/city/LOD 0, fx=hd, slots=5) in sandbox with `log=1`:
`-postFX=0,-fxaa=0,-tessellation=0,-multiSampleQuality=0,-anisotropicQualityLevel=0,-shadowSoftness=0,-SSAO=0`

Result: **12.7-13.2 FPS**, 2669-2679 draws/frame, worker 100% busy — WORSE than the 16.5-16.8 FPS baseline (1150-1250 draws). The scene/location differed, but there is no evidence of a gain; reverted immediately. Game did not crash; only benign network-allocator asserts (`net_leaderboard_mgr`) from `-nonetwork`.

## Verdict
No further software lever found. Best verified high-quality preset remains shadow=0 / reflection=1 at 960x540 = **16.5-16.8 FPS**. True 1080p = 5.6-8 FPS. Plain low profile = 30 FPS but low quality. 25-30 FPS with high textures + shadows is not achievable on i3-7100U / HD 620.
