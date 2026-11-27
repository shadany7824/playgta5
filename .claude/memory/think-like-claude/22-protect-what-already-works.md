# 22 — Protect what already works while you experiment

## The lesson
Experiments must not break the thing the owner uses every day. Work on **copies** and separate paths, so the working setup stays one click away.

## What happened here
- The Chrome launchers (`Play-Final.cmd`, `Play-Shader.cmd`, ...) load the **mirror** `wgpu_worker.js`. The Node harness loads the **same file** through `wgpu_wrapper2.js`. An optimization edited into the mirror file for Node would also change (or break) the owner's playable Chrome setup.
- So the plan says: copy it to `node-webgpu\wgpu_worker_node.js`, point the Node wrapper at the copy, prove the copy behaves the same, and only then edit the copy. The agent did this, and file 19 refers to `wgpu_worker_node.js`.
- Same with the engine: wasm patches go into a **copy** (`game-patched.wasm`), never the served `game.wasm`.
- The working JS Dawn (`node24\wgpu\node_modules\webgpu`) stays untouched while the experimental `native-dawn` C++ path is developed. It's the fallback (`WGPU_NATIVE_DRIVER=0`).

## How to apply
- Before editing, ask: **what else uses this file?** (`grep` for its name in launchers, loaders, wrappers.) Owner rule U10: grep every caller before changing something shared.
- Split shared files into an experiment copy when an experiment needs to change them.
- Keep a switch (env var, config path) to go back to the stable path without editing.
- After an experiment, re-run one quick check of the stable path (does Chrome still start?).

## One-line rule
**Experiment on a copy. The owner's working game is not a test bench.**
