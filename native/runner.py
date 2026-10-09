"""threejs-native runner (DESIGN §4.3): draws a three.js bundle with the r186 port on wgpu (Vulkan by default).

    python native/runner.py --bundle <dir>/bundle.json --out <capture dir>
        [--adapter <substring>] [--power high-performance|low-power] [--parity] [--backend vulkan]

Writes <out>/<station>/final.exr (FLOAT32 linear; --parity also final.png) or <out>/frames/<frame:05d>.exr (HALF),
plus receipt.json and timing.json. Exit 0 = success, 2 = by-design skip (one JSON line {"skip": reason} on stdout),
anything else = failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import platform
import sys
import time
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path[0] = str(_REPO)  # run as a script: import the package, never sibling modules by bare name
elif str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np  # noqa: E402

RUNNER_REL = "native/runner.py"


class Skip(Exception):
    """By-design skip: exit code 2 with {"skip": reason}."""


def _utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _rel_change(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return 0.0
    x, y = a[..., :3].astype(np.float64), b[..., :3].astype(np.float64)
    den = float(np.mean(np.abs(y)))
    return float(np.mean(np.abs(x - y)) / den) if den > 0 else 0.0


def _frame_record(idx: int, frame: int, station: str, warmup_frames: int, res, timing_on: bool) -> dict:
    passes = {k: float(res.gpu_passes.get(k, 0.0)) for k in ("shadow", "probe", "main", "resolve")}
    return {"frame": frame, "station": station, "warmup": idx < warmup_frames, "cpu_ms": round(res.cpu_ms, 4),
            "wall_ms": round(res.wall_ms, 4),
            "gpu_ms": round(sum(passes.values()), 6) if (timing_on and res.gpu_passes) else None,
            "passes": {k: round(v, 6) for k, v in passes.items()} if (timing_on and res.gpu_passes) else None,
            "probe_captured": bool(res.probe_captured)}


def run(args) -> int:
    from renderers.base import git_sha, load_bundle
    from tools.exr import write_exr
    from tools.png import save_png

    from native import PORT_NAME
    from native.device import GpuTimer, NoAdapter, open_device, peak_rss_bytes
    from native.render import MEASURE_FORMAT, PARITY_FORMAT, Renderer
    from native.scene import SceneState
    from native.shadows import DEPTH_FORMAT

    started = _utc()
    t0 = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bundle, arrays = load_bundle(args.bundle)
    if int(bundle.get("bundle_version", 0)) != 1:
        raise Skip(f"unsupported bundle_version {bundle.get('bundle_version')}")
    ed = bundle["engine_data"]
    measure = dict(bundle.get("measure", {}))
    parity = bool(args.parity or measure.get("parity", False))
    timing_on = bool(measure.get("timing", True))
    warmup = int(measure.get("warmup_frames", 0))
    W, H = int(bundle["image"]["width"]), int(bundle["image"]["height"])
    try:
        ctx = open_device(args.backend, args.adapter, args.power)
    except NoAdapter as e:
        raise Skip(str(e)) from e
    try:
        scene = SceneState(bundle, arrays)
    except ValueError as e:
        raise Skip(f"bundle not supported by the r186 port: {e}") from e
    timer = GpuTimer(ctx)
    if not timing_on:
        timer.enabled = False
    rcfg = ed.get("renderer", {})
    offsets = rcfg.get("ssaa_offsets") or [[0.0, 0.0]]
    exposure = float(rcfg.get("parity", {}).get("exposure", 1.0))
    t_pre = time.perf_counter()
    renderer = Renderer(ctx, scene, W, H, timer=timer, exposure=exposure)
    renderer.precompute["setup_s"] = time.perf_counter() - t_pre  # geometry, LTC tables, targets, shadow maps
    probe = scene.probe_cfg
    probe_on, dynamic = bool(probe.get("enabled")), bool(probe.get("dynamic"))

    frames_log: list[dict] = []
    outputs: list[str] = []
    convergence: dict = {}
    rendered = 0
    cap = bundle["capture"]
    print(f"threejs-native: {bundle['scene']} / {bundle['mode']} on {ctx.info.get('device')} "
          f"({ctx.info.get('backend_type')}), {W}x{H}, ssaa {1 if parity else len(offsets)}, parity {parity}",
          flush=True)

    def draw(cam_cfg, *, capture_probe: bool, readback: bool):
        """One frame as the frame loop draws it: SSAA measurement, or (parity) the single-sample canvas render."""
        return renderer.render_frame(cam_cfg, offsets=offsets, capture_probe=capture_probe, probe_feedback=dynamic,
                                     with_probe=probe_on, readback=readback, parity=parity)

    def linear_single_sample(cam_cfg):
        """Parity runs: the same single sample, no view offset, linear (rgba32float, NoToneMapping) for the EXR."""
        return renderer.render_frame(cam_cfg, offsets=None, capture_probe=False, probe_feedback=False,
                                     with_probe=probe_on, readback=True).image

    def as_float(img):
        return None if img is None else img.astype(np.float64)

    if bundle["kind"] == "stations":
        for st in cap["stations"]:
            name, cam_cfg = st["name"], ed["cameras"][st["camera"]]
            n = max(1, int(st.get("settle_frames", 1)))
            scene.probe_sh = None  # each station bakes its own probe at its camera position
            prev = last = None
            for f in range(n):
                res = draw(cam_cfg, capture_probe=probe_on and (dynamic or f == 0), readback=f >= n - 2)
                rendered += 1
                frames_log.append(_frame_record(len(frames_log), f, name, warmup, res, timing_on))
                if res.image is not None:
                    prev, last = last, res.image
            convergence[name] = {"settle_frames": n, "last_rel_change": _rel_change(as_float(last), as_float(prev))}
            (out / name).mkdir(parents=True, exist_ok=True)
            if parity:
                save_png(out / name / "final.png", last[:, :, :3])
                linear = linear_single_sample(cam_cfg)
                rendered += 1
            else:
                linear = last
            write_exr(out / name / "final.exr", linear[:, :, :3], pixel_type="float", compression="zip")
            outputs.append(f"{name}/final.exr")
            if parity:
                outputs.append(f"{name}/final.png")
            print(f"  {name}: {n} frames, last_rel_change {convergence[name]['last_rel_change']:.3g}", flush=True)
    else:
        tl = cap["timeline"]
        cam_name = tl["camera"]
        cam_cfg = ed["cameras"][cam_name]
        end = int(tl["end_frame"])
        wanted = set(int(f) for f in tl.get("frames", range(end + 1)))
        (out / "frames").mkdir(parents=True, exist_ok=True)
        prev = last = None
        for k in range(end + 1):
            changed = scene.apply_events(k)
            res = draw(cam_cfg, capture_probe=probe_on and (dynamic or k == 0 or changed),
                       readback=(k in wanted) or k >= end - 1)
            rendered += 1
            frames_log.append(_frame_record(len(frames_log), k, cam_name, warmup, res, timing_on))
            if res.image is not None:
                prev, last = last, res.image
            if k in wanted:
                linear = res.image
                if parity:
                    save_png(out / "frames" / f"{k:05d}.png", res.image[:, :, :3])
                    outputs.append(f"frames/{k:05d}.png")
                    linear = linear_single_sample(cam_cfg)
                    rendered += 1
                write_exr(out / "frames" / f"{k:05d}.exr", linear[:, :, :3], pixel_type="half", compression="zip")
                outputs.append(f"frames/{k:05d}.exr")
        convergence[cam_name] = {"frames": end + 1, "last_rel_change": _rel_change(as_float(last), as_float(prev))}
        print(f"  timeline: {end + 1} frames, {len(wanted)} written", flush=True)

    pre = renderer.precompute
    settings = {
        "ssaa": 1 if parity else len(offsets), "ssaa_offsets": None if parity else offsets,
        "ssaa_method": None if parity else
        "PerspectiveCamera.setViewOffset per sample, averaged in a fixed order (1/N weights)",
        "shadow_map_type": rcfg.get("shadowMapType", "PCFShadowMap"),
        "shadow_maps": [{"light": lt.name, "type": lt.type, "mapSize": lt.shadow.get("mapSize"),
                         "bias": lt.shadow.get("bias"), "normalBias": lt.shadow.get("normalBias"),
                         "radius": lt.shadow.get("radius"),
                         "camera": lt.shadow.get("camera") or {"near": lt.shadow.get("near"),
                                                               "far": lt.shadow.get("far")}}
                        for lt in scene.shadow_lights()],
        "shadow_depth_format": DEPTH_FORMAT, "shadow_updates": "once per output frame (shared by probe and SSAA)",
        "probe": {**probe, "format": renderer.probe_format if probe_on else None,
                  "captured": "every frame (previous probe active)" if dynamic else
                  ("frame 0 and after every timeline event, probe disabled" if probe_on else None)},
        "formats": {"measurement": MEASURE_FORMAT, "parity": PARITY_FORMAT, "depth": DEPTH_FORMAT,
                    "ltc": renderer.ltc_format},
        "measurement": None if parity else {"toneMapping": "NoToneMapping", "outputColorSpace": "srgb-linear",
                                            "type": "FloatType"},
        "parity": ({"samples": 1, "view_offset": None, "target": "rgba8unorm (the canvas drawing buffer)",
                    "toneMapping": "ACESFilmicToneMapping", "toneMappingExposure": exposure,
                    "outputColorSpace": "srgb", "frames": "every frame is the canvas render",
                    "linear_exr": "same single sample, no offset, rgba32float, NoToneMapping"} if parity else None),
        "clip_space": "WebGL clip space; vertex stage negates y and remaps z: (z + w) / 2",
        "front_face": "cw (GL ccw mirrored by the y negation)",
        "precision": "highp (32-bit float)",
        "object3d_default_up": list(scene.default_up), "frame_up": list(scene.frame_up),
        "max_texture_size": renderer.max_texture_size,
    }
    receipt = {
        "receipt_version": 1, "engine": "threejs-native", "engine_version": f"{PORT_NAME} @ {git_sha()}",
        "runner": RUNNER_REL, "scene": bundle["scene"], "mode": bundle["mode"], "kind": bundle["kind"],
        "parity": parity, "settings": settings, "device": ctx.device_block(),
        "frames": {"fps": bundle.get("fps", 60), "rendered": rendered, "timestep": "fixed"},
        "seed": bundle.get("seed", 1), "convergence": convergence, "outputs": outputs,
        "started_utc": started, "finished_utc": _utc(), "wall_seconds": round(time.perf_counter() - t0, 4),
        "host": {"os": platform.platform(), "python": platform.python_version(),
                 "cpu": platform.processor() or platform.machine()},
    }
    timing = {
        "timing_version": 1, "units": "ms", "gpu_timestamps": bool(timer.enabled), "warmup_frames": warmup,
        "gpu_passes_untimed": timer.dropped,
        "frames": frames_log,
        "memory": {"gpu_texture_bytes": ctx.alloc.texture_bytes, "gpu_buffer_bytes": ctx.alloc.buffer_bytes,
                   "peak_rss_bytes": peak_rss_bytes()},
        "precompute": {"seconds": round(pre["shader_build_s"] + pre["pipeline_s"] + pre["setup_s"], 6),
                       "bytes": int(renderer.precompute_bytes),
                       "items": {"ltc_tables_bytes": int(renderer.precompute_bytes),
                                 "shader_build_s": round(pre["shader_build_s"], 6),
                                 "pipeline_s": round(pre["pipeline_s"], 6),
                                 "setup_s": round(pre["setup_s"], 6),
                                 "programs": len(renderer._programs)}},
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    (out / "timing.json").write_text(json.dumps(timing, indent=1) + "\n", encoding="utf-8")
    print(f"threejs-native: wrote {len(outputs)} outputs in {receipt['wall_seconds']:.2f} s", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bundle", required=True, help="bundle.json")
    ap.add_argument("--out", required=True, help="capture directory (RunLayout.capture_dir)")
    ap.add_argument("--adapter", default=None, help="substring of the adapter name/vendor/description")
    ap.add_argument("--power", default=None, choices=["high-performance", "low-power"])
    ap.add_argument("--parity", action="store_true", help="also write the 8-bit tonemapped final.png")
    ap.add_argument("--backend", default=None, help="wgpu backend (default: $WGPU_BACKEND_TYPE or vulkan)")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except Skip as e:
        print(json.dumps({"skip": str(e)}), flush=True)
        return 2
    except Exception:  # noqa: BLE001 - reported through runner.log
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
