"""Runner of the fake test engine (DESIGN §4.3; engine in renderers/future.py).

    python renderers/fake_runner.py --bundle <dir>/bundle.json --out <capture dir> [--adapter S] [--power P]
        [--parity] [--backend B]

Reads the reference EXRs and AOVs named in the bundle and writes the perturbed images as a real engine would:
``<out>/<station>/final.exr`` (FLOAT32) or ``<out>/frames/<frame:05d>.exr`` (HALF) for every listed frame, plus
``receipt.json`` and ``timing.json``. Exit 0 ok, 2 by-design skip (one JSON line ``{"skip": reason}``), 1 failure.
The adapter/power/backend options are accepted and recorded; there is no GPU.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import platform
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parent.parent
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path[0] = str(_REPO)  # run as a script: import the package, never sibling modules by bare name
elif str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np  # noqa: E402

RUNNER_REL = "renderers/fake_runner.py"


class Skip(Exception):
    """By-design skip: exit code 2 with {"skip": reason}."""


def _utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _rgb(path: str) -> np.ndarray:
    from tools.exr import read_exr

    return read_exr(path)[..., :3].astype(np.float64)


def _dark_mask(view: dict, rois: list[dict], shape) -> np.ndarray:
    """Union of the view's dark ROIs (box/normal on the reference AOVs, valid pixels, not eroded)."""
    from tools.masks import load_aux, roi_mask, valid_mask

    out = np.zeros(shape[:2], dtype=bool)
    dark = [r for r in rois if r["role"] == "dark" and (r.get("views") is None or view["id"] in r["views"])]
    if not dark:
        return out
    aux = load_aux(Path(view["reference"]["depth"]).parent)
    valid = valid_mask(aux)
    for r in dark:
        roi = SimpleNamespace(box_min=np.asarray(r["min"], float), box_max=np.asarray(r["max"], float),
                              normal=None if r.get("normal") is None else np.asarray(r["normal"], float),
                              min_cos=r.get("min_cos"))
        out |= roi_mask(roi, aux, valid)
    return out


class _View:
    """Reference images of one view and the fake's targets for it."""

    def __init__(self, view: dict, rois: list[dict], pert: dict, indirect: bool):
        full, direct = _rgb(view["reference"]["full"]), _rgb(view["reference"]["direct"])
        self.direct = (1.0 + float(pert["direct_bias"])) * direct
        if indirect:
            self.dark = _dark_mask(view, rois, full.shape)
            self.indirect = (1.0 + float(pert["bias"])) * (full - direct)
            self.indirect[self.dark] += float(pert["leak"])
        else:
            self.dark = None
            self.indirect = np.zeros_like(direct)


def _poison(img: np.ndarray) -> np.ndarray:
    img = np.array(img, dtype=np.float64)
    img[img.shape[0] // 2, img.shape[1] // 2, :] = np.nan
    return img


def run(args) -> int:
    from renderers.base import load_bundle
    from tools.exr import write_exr

    started = _utc()
    t0 = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bundle, _arrays = load_bundle(args.bundle)
    if int(bundle.get("bundle_version", 0)) != 1:
        raise Skip(f"unsupported bundle_version {bundle.get('bundle_version')}")
    ed = bundle["engine_data"]
    pert, faults = ed["perturbation"], ed["faults"]
    scene, mode = bundle["scene"], bundle["mode"]
    indirect = ed["mode_kind"] == "indirect"
    print(f"fake: {scene} / {mode} ({ed['mode_kind']}), perturbation {json.dumps(pert, sort_keys=True)}", flush=True)
    if faults.get("skip"):
        raise Skip(f"injected skip (fake engine 'skip' flag) for {scene}/{mode}")
    if faults.get("crash"):
        print("fake: about to crash on purpose", flush=True)
        raise RuntimeError(f"injected crash (fake engine 'crash' flag) for {scene}/{mode}")
    write = not faults.get("missing")
    nan = bool(faults.get("nan"))
    views = {v["id"]: v for v in ed["views"]}
    rois = ed["rois"]
    frames_log: list[dict] = []
    outputs: list[str] = []
    convergence: dict = {}
    rendered = 0

    def record(frame: int, station: str, t_start: float) -> None:
        frames_log.append({"frame": frame, "station": station, "warmup": False,
                           "cpu_ms": round((time.perf_counter() - t_start) * 1e3, 4), "gpu_ms": None,
                           "passes": None})

    if bundle["kind"] == "stations":
        for st in bundle["capture"]["stations"]:
            ts = time.perf_counter()
            v = _View(views[st["name"]], rois, pert, indirect)
            img = v.direct + v.indirect
            if nan:
                img = _poison(img)
            n = int(st.get("settle_frames", 1))
            rendered += n
            record(n - 1, st["name"], ts)
            convergence[st["name"]] = {"settle_frames": n, "last_rel_change": float(pert["last_rel_change"])}
            if write:
                write_exr(out / st["name"] / "final.exr", img.astype(np.float32), channels="R,G,B",
                          pixel_type="float", compression="zip")
                outputs.append(f"{st['name']}/final.exr")
            print(f"  {st['name']}: written={write}", flush=True)
    else:
        tl = bundle["capture"]["timeline"]
        end = int(tl["end_frame"])
        wanted = set(int(f) for f in tl.get("frames", range(end + 1)))
        state_views = sorted((v for v in ed["views"] if v["kind"] == "state"), key=lambda v: v["frames"][0])
        cache: dict[str, _View] = {}
        tau = float(pert["tau"])
        a = math.exp(-1.0 / tau) if tau > 0 else 0.0
        noise, seed = float(pert["noise"]), int(pert["seed"])
        y = None
        prev = last = None
        for k in range(end + 1):
            ts = time.perf_counter()
            sv = next(v for v in state_views if v["frames"][0] <= k <= v["frames"][1])
            if sv["id"] not in cache:
                cache[sv["id"]] = _View(sv, rois, pert, indirect)
            v = cache[sv["id"]]
            y = (1.0 - a) * v.indirect if y is None else a * y + (1.0 - a) * v.indirect
            ind = y
            if noise > 0 and indirect:
                rng = np.random.default_rng([seed, k])
                ind = y * (1.0 + noise * rng.standard_normal(y.shape[:2]))[..., None]
            img = v.direct + ind
            rendered += 1
            if k >= end - 1:
                prev, last = last, img
            if k in wanted:
                if nan:
                    img = _poison(img)
                if write:
                    write_exr(out / "frames" / f"{k:05d}.exr", img.astype(np.float32), channels="R,G,B",
                              pixel_type="half", compression="zip")
                    outputs.append(f"frames/{k:05d}.exr")
            record(k, tl["camera"], ts)
        rel = 0.0
        if prev is not None and last is not None:
            den = float(np.mean(np.abs(last)))
            rel = float(np.mean(np.abs(last - prev)) / den) if den > 0 else 0.0
        convergence[tl["camera"]] = {"frames": end + 1, "last_rel_change": rel}
        print(f"  timeline: {end + 1} frames, {len(wanted)} listed, written={write}", flush=True)

    receipt = {
        "receipt_version": 1, "engine": ed.get("engine_name", "fake"),
        "engine_version": "fake engine (perturbed Mitsuba reference)", "runner": RUNNER_REL,
        "scene": scene, "mode": mode, "kind": bundle["kind"], "parity": bool(args.parity),
        "settings": {"perturbation": pert, "faults": faults, "mode_kind": ed["mode_kind"],
                     "dynamic": ed["dynamic"], "response": "y(k) = a y(k-1) + (1-a) target, a = exp(-1/tau)",
                     "formats": {"stations": "FLOAT32 ZIP", "timeline": "HALF ZIP"}, "tonemap": None},
        "device": {"adapter": "none (numpy)", "backend": args.backend or "none", "adapter_type": "CPU",
                   "vendor": "none", "driver": "none", "requested_adapter": args.adapter, "power": args.power},
        "frames": {"fps": bundle.get("fps", 60), "rendered": rendered, "timestep": "fixed"},
        "seed": bundle.get("seed", 1), "convergence": convergence, "outputs": outputs,
        "started_utc": started, "finished_utc": _utc(), "wall_seconds": round(time.perf_counter() - t0, 4),
        "host": {"os": platform.platform(), "python": platform.python_version(),
                 "cpu": platform.processor() or platform.machine()},
    }
    timing = {"timing_version": 1, "units": "ms", "gpu_timestamps": False, "warmup_frames": 0,
              "frames": frames_log, "memory": {"gpu_texture_bytes": 0, "gpu_buffer_bytes": 0, "peak_rss_bytes": 0},
              "precompute": {"seconds": 0.0, "bytes": 0, "items": {}}}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    (out / "timing.json").write_text(json.dumps(timing, indent=1) + "\n", encoding="utf-8")
    print(f"fake: wrote {len(outputs)} outputs in {receipt['wall_seconds']:.2f} s", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--power", default=None, choices=["high-performance", "low-power"])
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--backend", default=None)
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
