"""Stub engine + runner for tests/test_parity.py and tests/test_perf.py (no GPU, no browser).

``StubEngine`` writes a minimal bundle (capture + measure blocks only); its runner is this file:

    python tests/phase0_stub.py --bundle <dir>/bundle.json --out <capture dir> [--parity] [--adapter S] [--power P]

It writes, per station (or listed timeline frame), a deterministic 8-bit pattern as ``final.png`` (with ``--parity``)
and its linear version as ``final.exr``, plus receipt.json and timing.json whose frame times are known: warm-up frames
take 1000 ms (so any leak of warm-up frames into the statistics shows), timed frame i takes ``gpu_ms + 0.5 * (i % 4)``
GPU ms and half of that CPU ms. Behaviour comes from environment variables that ``StubEngine.runner_env`` sets:
STUB_OFFSET (LSB added to the pattern), STUB_OFFSET_COLS (only in the first N columns), STUB_ADAPTER,
STUB_ADAPTER_TYPE, STUB_GPU_MS ('none' = no GPU timestamps), STUB_SKIP (exit 2 with that reason), STUB_LOG (append
"<engine> <out dir>" per launch).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

STUB_RUNNER = Path(__file__).resolve()


def pattern(h: int, w: int) -> np.ndarray:
    """Deterministic uint8 (h, w, 3) image with values in [0, 253] (so +2 LSB never clips)."""
    y, x = np.mgrid[0:h, 0:w]
    return np.stack([(x * 7 + y * 3 + c * 50) % 254 for c in range(3)], axis=-1).astype(np.uint8)


# ------------------------------------------------------------------------------------------------ engine (tests)

def make_engine(name: str, **params):
    """A StubEngine named ``name`` (e.g. 'threejs-web') with the runner parameters above."""
    from renderers.base import ALL_CAPABILITIES, Engine, ModeInfo, NotWired, write_bundle
    from tools.spec import capture_kind

    class StubEngine(Engine):
        def __init__(self):
            self.name = name
            self.params = params

        def modes(self):
            return {"direct": ModeInfo("direct", "direct", False, "stub", "stub direct"),
                    "probe": ModeInfo("probe", "indirect", False, "stub", "stub probe")}

        def capabilities(self):
            return set(ALL_CAPABILITIES)

        def check_available(self):
            if params.get("unavailable"):
                raise NotWired(str(params["unavailable"]))

        def build_bundle(self, scene, mode, views, capture, out_dir):
            cap = {k: v for k, v in capture.items() if k in ("stations", "timeline")}
            measure = {"timing": True, "warmup_frames": 0, "parity": False, **capture.get("measure", {})}
            bundle = {"bundle_version": 1, "engine": "stub", "mode": mode, "scene": scene.name,
                      "kind": capture_kind(scene), "image": {"width": scene.width, "height": scene.height},
                      "capture": cap, "measure": measure, "engine_data": {}}
            return write_bundle(Path(out_dir), bundle, {})

        def runner_argv(self, bundle_json, out_dir, extra):
            return [sys.executable, str(STUB_RUNNER), "--bundle", str(bundle_json), "--out", str(out_dir),
                    *[str(e) for e in extra]]

        def runner_env(self):
            env = {"STUB_ENGINE": name}
            for k in ("offset", "offset_cols", "adapter", "adapter_type", "gpu_ms", "skip", "log"):
                if params.get(k) is not None:
                    env[f"STUB_{k.upper()}"] = str(params[k])
            return env

        def version(self):
            return "stub 1"

    return StubEngine()


# ------------------------------------------------------------------------------------------------ runner

def _run(argv) -> int:
    import argparse

    from tools.exr import write_exr
    from tools.png import save_png

    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--adapter")
    ap.add_argument("--power")
    args = ap.parse_args(argv)
    env = os.environ
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if env.get("STUB_LOG"):
        with open(env["STUB_LOG"], "a", encoding="utf-8") as f:
            f.write(f"{env.get('STUB_ENGINE')} {out.as_posix()}\n")
    if env.get("STUB_SKIP"):
        print(json.dumps({"skip": env["STUB_SKIP"]}))
        return 2
    b = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    w, h = b["image"]["width"], b["image"]["height"]
    parity = bool(args.parity or b["measure"].get("parity"))
    img = pattern(h, w).astype(np.int16)
    cols = int(env.get("STUB_OFFSET_COLS", w))
    img[:, :cols] += int(env.get("STUB_OFFSET", 0))
    img = np.clip(img, 0, 255).astype(np.uint8)
    names = []
    if "stations" in b["capture"]:
        names = [f"{s['name']}/final" for s in b["capture"]["stations"]]
        n = max(int(s.get("settle_frames", 1)) for s in b["capture"]["stations"])
    else:
        names = [f"frames/{k:05d}" for k in b["capture"]["timeline"]["frames"]]
        n = int(b["capture"]["timeline"]["end_frame"]) + 1
    outputs = []
    for stem in names:
        write_exr(out / f"{stem}.exr", img.astype(np.float32) / 255.0)
        outputs.append(f"{stem}.exr")
        if parity:
            save_png(out / f"{stem}.png", img)
            outputs.append(f"{stem}.png")
    warm = int(b["measure"].get("warmup_frames", 0))
    gpu = env.get("STUB_GPU_MS", "5.0")
    frames = []
    for i in range(n):
        g = None if gpu == "none" else (1000.0 if i < warm else float(gpu) + 0.5 * (i % 4))
        frames.append({"frame": i, "station": "s", "warmup": i < warm, "gpu_ms": g,
                       "cpu_ms": 1000.0 if i < warm else (float(gpu) if gpu != "none" else 4.0) / 2 + 0.25 * (i % 4),
                       "passes": None if g is None else {"main": g}})
    timing = {"timing_version": 1, "units": "ms", "gpu_timestamps": gpu != "none", "warmup_frames": warm,
              "frames": frames, "memory": {"gpu_texture_bytes": 1000, "gpu_buffer_bytes": 10,
                                           "peak_rss_bytes": 12345},
              "precompute": {"seconds": 0.5, "bytes": 7, "items": {}}}
    adapter = env.get("STUB_ADAPTER", "Stub GPU")
    receipt = {"receipt_version": 1, "engine": env.get("STUB_ENGINE"), "engine_version": "stub 1",
               "scene": b["scene"], "mode": b["mode"], "kind": b["kind"], "parity": parity,
               "settings": {"ssaa": 1}, "outputs": outputs,
               "device": {"adapter": adapter, "backend": "Stub", "adapter_type": env.get("STUB_ADAPTER_TYPE",
                                                                                            "DiscreteGPU"),
                          "vendor": "stub", "driver": "stub 1"}}
    (out / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    (out / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(_run(sys.argv[1:]))
