"""Phase 0 parity gate (DESIGN §5.4): the original three.js r186 WebGL build (``threejs-web``) against the native
port (``threejs-native``), both runners in ``--parity`` (one sample, ACES + sRGB, 8-bit canvas output; §5.1).

    python -m tools.parity --run <dir> [--views scenes/phase0_parity.json] [--timeout S] [--adapter S]
        [--power high-performance|low-power] [--settle-frames N] [--dynamic-settle-frames N] [--scenes-root DIR]
        [--cache DIR] [--echo] [--strict]

For each (scene, mode) of the views file (``{"parity_version": 1, "views": [{"scene", "view", "modes"}]}``), both
three.js bundles are built for the listed views only (``RunLayout.parity_bundle_dir``) and both runners are launched
with ``--parity`` into ``RunLayout.parity_capture_dir`` (``phase0/captures/<engine>/<scene>/<mode>/``), so parity
never overwrites the measurement bundles or captures. Station views settle ``--settle-frames`` frames (2; dynamic
modes ``--dynamic-settle-frames``, 64); a timeline state view runs the timeline up to its capture frame. Then, per
view and mode, the two 8-bit ``final.png`` are compared per channel, ``d = |web - native|`` in LSB:

- ``max``, ``mean`` and ``p99_9`` of d over every (pixel, channel) value, the same per channel (``R``, ``G``,
  ``B``), and the count and fraction of pixels with any channel more than 1 LSB apart (``pixels_gt1``,
  ``fraction_gt1``);
- the same restricted to the valid pixels (``valid``): ROI ``all`` of ``tools.masks`` (``|normal| > 0.99``,
  ``depth > 0``, eroded by 1 pixel) from the view's reference AOVs, taken from the run's ``reference/<scene>/<view>/``
  when present, else from a complete entry of the reference cache with the same view hash (any spp: the AOVs depend
  only on the view). Without either, ``valid`` is null and ``valid_mask.reason`` says why;
- informational (``linear``): the relative difference of the linear ``final.exr`` the same parity launches write (the
  same single sample, NoToneMapping): ``rel_l1 = sum|native - web| / sum|web|`` and ``bias = sum(native - web) /
  sum(web)`` over pixels and channels (null when the web image is black), plus ``max_abs``, on all and on valid
  pixels.

``p99_9`` is the smallest value v with at least 99.9 % of the values <= v (numpy ``method="inverted_cdf"``), so it is
always an observed LSB difference. **Gate**, per view and mode on all pixels: ``p99_9 <= 1`` and ``mean <= 0.1``.
The overall gate passes when every listed view and mode was compared and passed, fails when any compared one failed,
and is ``incomplete`` (``passed: null``) otherwise.

Writes ``phase0/parity.json`` (per view/mode entries, the overall gate, the device of each side from the receipts, and
``representative: false`` with the reason when either side is a software rasterizer: SwiftShader, llvmpipe,
lavapipe, softpipe, WARP / Microsoft Basic Render, or ``adapter_type`` CPU) and contact sheets
``phase0/sheets/<scene>__<view>__<mode>.png`` (web | native | per-channel |diff| x 32, labelled). ``run.json`` gets
the parity config and durations. Exit code 0 when every launch and comparison ran, whatever the gate (``--strict``:
also 1 when the gate did not pass); 1 when something failed; 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import REPO_ROOT
from .layout import RunLayout
from .pairs import _read_json, _rel, _write_json, resolve_engines
from .runjson import host_info, update_run_json, utc_now

__all__ = ["CHANNELS", "DEFAULT_CACHE_ROOT", "DEFAULT_ENGINES", "DEFAULT_TIMEOUT", "DEFAULT_VIEWS_FILE", "DIFF_GAIN",
           "GATE_MEAN_LSB", "GATE_P99_9_LSB", "PARITY_VERSION", "SETTLE_DYNAMIC", "SETTLE_STATIC", "compare_view",
           "device_summary", "diff_stats", "find_aux_dir", "gate_check", "linear_diff", "load_views_file", "main",
           "overall_gate", "parity_capture_request", "parity_sheet", "percentile_lsb", "representativeness",
           "run_parity", "software_reason", "valid_pixel_mask"]

PARITY_VERSION = 1
DEFAULT_VIEWS_FILE = REPO_ROOT / "scenes" / "phase0_parity.json"
DEFAULT_CACHE_ROOT = REPO_ROOT / "cache"
DEFAULT_ENGINES = ("threejs-web", "threejs-native")  # (web side, native side)
DEFAULT_TIMEOUT = 1800.0
SETTLE_STATIC = 2
SETTLE_DYNAMIC = 64
GATE_P99_9_LSB = 1.0
GATE_MEAN_LSB = 0.1
GT_LSB = 1  # pixels with any channel more than this many LSB apart are counted
DIFF_GAIN = 32
CHANNELS = ("R", "G", "B")
CRITERION = (f"per view and mode, |web - native| per channel on 8-bit values over all pixels: "
             f"p99.9 <= {GATE_P99_9_LSB:g} LSB and mean <= {GATE_MEAN_LSB:g} LSB")
PERCENTILE_METHOD = ("inverted_cdf: the smallest value v with at least 99.9 % of the (pixel, channel) values <= v")
# Software rasterizers named in adapter / driver / WebGL renderer strings (lower case; regexes).
SOFTWARE_ADAPTERS = (("swiftshader", "SwiftShader"), ("llvmpipe", "llvmpipe"), ("lavapipe", "lavapipe"),
                     ("softpipe", "softpipe"), (r"microsoft basic render", "Microsoft Basic Render Driver (WARP)"),
                     (r"\bwarp\b", "WARP"))


# ------------------------------------------------------------------------------------------------ views file

def load_views_file(path=None) -> dict:
    """The validated views file: {"path", "description", "views": [{"scene", "view", "modes"}]}. Raises ValueError
    with the file and entry named."""
    p = Path(path) if path is not None else DEFAULT_VIEWS_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"{p}: cannot read the views file ({e})") from None
    except json.JSONDecodeError as e:
        raise ValueError(f"{p}: not JSON ({e})") from None
    if not isinstance(doc, dict) or doc.get("parity_version") != 1:
        raise ValueError(f"{p}: parity_version must be 1")
    views = doc.get("views")
    if not isinstance(views, list) or not views:
        raise ValueError(f"{p}: views must be a non-empty list")
    out, seen = [], set()
    for i, v in enumerate(views):
        where = f"{p}: views[{i}]"
        if not isinstance(v, dict):
            raise ValueError(f"{where}: must be an object")
        unknown = set(v) - {"scene", "view", "modes"}
        if unknown:
            raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
        for k in ("scene", "view"):
            if not isinstance(v.get(k), str) or not v[k]:
                raise ValueError(f"{where}.{k}: must be a non-empty string")
        modes = v.get("modes")
        if not isinstance(modes, list) or not modes or not all(isinstance(m, str) and m for m in modes):
            raise ValueError(f"{where}.modes: must be a non-empty list of mode names")
        for m in modes:
            key = (v["scene"], v["view"], m)
            if key in seen:
                raise ValueError(f"{where}: {v['scene']}/{v['view']}/{m} listed twice")
            seen.add(key)
        out.append({"scene": v["scene"], "view": v["view"], "modes": list(modes)})
    return {"path": str(p), "description": str(doc.get("description", "")), "views": out}


# ------------------------------------------------------------------------------------------------ devices

def software_reason(device: Mapping | None) -> str | None:
    """Why a receipt's device block is a software rasterizer, or None (hardware, or no device given)."""
    if not device:
        return None
    hay = " ".join(str(device.get(k) or "") for k in ("adapter", "driver", "vendor", "webgl_renderer",
                                                       "description")).lower()
    found = [label for pat, label in SOFTWARE_ADAPTERS if re.search(pat, hay)]
    found = list(dict.fromkeys(found))
    if str(device.get("adapter_type") or "").lower() == "cpu":
        found.append("adapter_type CPU")
    elif device.get("software_rendering") and not found:
        found.append("software rendering")
    return ", ".join(found) or None


def device_summary(receipt: Mapping | None) -> dict | None:
    """{adapter, adapter_type, backend, vendor, driver, browser?, software, software_reason} from a receipt."""
    dev = (receipt or {}).get("device")
    if not isinstance(dev, Mapping):
        return None
    out = {k: dev.get(k) for k in ("adapter", "adapter_type", "backend", "vendor", "driver", "browser")
           if dev.get(k) not in (None, "")}
    why = software_reason(dev)
    out["software"] = why is not None
    out["software_reason"] = why
    return out


def representativeness(devices: Mapping[str, Mapping | None]) -> tuple[bool, str | None]:
    """(representative, reason): False when any side has no recorded device or runs on a software rasterizer."""
    if not devices:
        return False, "no device recorded"
    reasons = []
    for name, d in devices.items():
        if not d:
            reasons.append(f"{name}: no device recorded (no successful launch)")
        elif d.get("software"):
            reasons.append(f"{name} runs on a software rasterizer: {d.get('adapter')} ({d.get('software_reason')})")
    return (not reasons), ("; ".join(reasons) or None)


# ------------------------------------------------------------------------------------------------ comparison

def _u8(img) -> np.ndarray:
    a = np.asarray(img)
    if a.dtype != np.uint8:
        raise ValueError(f"parity images must be uint8, got {a.dtype}")
    if a.ndim != 3 or a.shape[2] < 3:
        raise ValueError(f"parity images must be (H, W, 3|4), got {a.shape}")
    return a[:, :, :3]


def percentile_lsb(values, q: float = 99.9) -> float | None:
    """The q-th percentile by the inverted CDF (an observed value); None for no values."""
    v = np.asarray(values).ravel()
    if not v.size:
        return None
    return float(np.percentile(v, q, method="inverted_cdf"))


def _stats(d: np.ndarray) -> dict:
    """d: (N, 3) integer |diff| per pixel and channel."""
    n = int(d.shape[0])
    if n == 0:
        return {"pixels": 0, "max": None, "mean": None, "p99_9": None, "pixels_gt1": 0, "fraction_gt1": None,
                "channels": {c: {"max": None, "mean": None, "p99_9": None} for c in CHANNELS}}
    gt = (d > GT_LSB).any(axis=1)
    return {"pixels": n, "max": int(d.max()), "mean": float(d.mean()), "p99_9": percentile_lsb(d),
            "pixels_gt1": int(gt.sum()), "fraction_gt1": float(gt.mean()),
            "channels": {c: {"max": int(d[:, i].max()), "mean": float(d[:, i].mean()),
                             "p99_9": percentile_lsb(d[:, i])} for i, c in enumerate(CHANNELS)}}


def _mask(mask, shape) -> np.ndarray:
    m = np.asarray(mask, dtype=bool)
    if m.shape != tuple(shape[:2]):
        raise ValueError(f"mask shape {m.shape} != image shape {tuple(shape[:2])}")
    return m


def diff_stats(web, native, mask=None) -> dict:
    """|web - native| statistics in 8-bit LSB (see the module docstring), optionally over ``mask`` pixels only."""
    a, b = _u8(web), _u8(native)
    if a.shape != b.shape:
        raise ValueError(f"image shapes differ: web {a.shape}, native {b.shape}")
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    if mask is not None:
        d = d[_mask(mask, a.shape)]
    return _stats(d.reshape(-1, 3))


def gate_check(stats: Mapping | None) -> dict:
    """Gate of one view/mode from its all-pixel stats: p99.9 <= 1 LSB and mean <= 0.1 LSB."""
    p = None if not stats else stats.get("p99_9")
    m = None if not stats else stats.get("mean")
    passed = None if p is None or m is None else bool(p <= GATE_P99_9_LSB and m <= GATE_MEAN_LSB)
    return {"passed": passed, "p99_9": p, "mean": m, "max_p99_9": GATE_P99_9_LSB, "max_mean": GATE_MEAN_LSB}


def linear_diff(web, native, mask=None) -> dict:
    """Relative difference of the linear images (informational): rel_l1, bias, max_abs over pixels and channels."""
    a = np.asarray(web, dtype=np.float64)[..., :3]
    b = np.asarray(native, dtype=np.float64)[..., :3]
    if a.shape != b.shape:
        raise ValueError(f"image shapes differ: web {a.shape}, native {b.shape}")
    if mask is not None:
        m = _mask(mask, a.shape)
        a, b = a[m], b[m]
    a, b = a.reshape(-1, 3), b.reshape(-1, 3)
    ok = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    bad = int((~ok).sum())
    a, b = a[ok], b[ok]
    out = {"pixels": int(a.shape[0]), "nonfinite_pixels": bad, "rel_l1": None, "bias": None, "max_abs": None,
           "web_mean": None, "native_mean": None, "note": None}
    if not a.size:
        out["note"] = "no pixels"
        return out
    diff = b - a
    den, tot = float(np.abs(a).sum()), float(a.sum())
    out.update(max_abs=float(np.abs(diff).max()), web_mean=float(a.mean()), native_mean=float(b.mean()))
    if den > 0:
        out["rel_l1"] = float(np.abs(diff).sum() / den)
    if tot > 0:
        out["bias"] = float(diff.sum() / tot)
    if den == 0:
        out["note"] = "web image is black: relative difference undefined"
    return out


def compare_view(web_png, native_png, web_exr=None, native_exr=None, mask=None) -> dict:
    """All comparisons of one view/mode: {"all", "valid", "gate", "linear": {"all", "valid"}}. ``valid`` (and
    ``linear.valid``) are None without a mask; ``linear`` is None without both EXRs."""
    res = {"all": diff_stats(web_png, native_png), "valid": None}
    if mask is not None:
        res["valid"] = diff_stats(web_png, native_png, mask)
    res["gate"] = gate_check(res["all"])
    res["linear"] = None
    if web_exr is not None and native_exr is not None:
        res["linear"] = {"all": linear_diff(web_exr, native_exr),
                         "valid": None if mask is None else linear_diff(web_exr, native_exr, mask)}
    return res


def _short(s, n: int = 44) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 3] + "..."


def _fmt(x, spec: str = ".3g") -> str:
    return "n/a" if x is None else format(x, spec)


def parity_sheet(web, native, out_png, title: str = "", web_label: str = "threejs-web",
                 native_label: str = "threejs-native", stats: Mapping | None = None) -> Path:
    """Labelled contact sheet ``web | native | |diff| x DIFF_GAIN`` (per channel, clipped to 255)."""
    from . import png
    from .sheets import MIN_TILE_WIDTH

    a, b = _u8(web), _u8(native)
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    diff = np.clip(d * DIFF_GAIN, 0, 255).astype(np.uint8)
    st = stats or {}
    dl = f"|diff| x{DIFF_GAIN} per channel\nmax {_fmt(st.get('max'))}, p99.9 {_fmt(st.get('p99_9'))}, " \
         f"mean {_fmt(st.get('mean'), '.3f')} LSB"
    scale = max(1, math.ceil(MIN_TILE_WIDTH / max(1, a.shape[1])))
    img = png.sheet([[(a, web_label), (b, native_label), (diff, dl)]], title=title, scale=scale)
    return png.save_png(out_png, img)


# ------------------------------------------------------------------------------------------------ masks

_cache_index: dict[str, dict[str, list[tuple[int, Path]]]] = {}


def _aux_complete(d: Path) -> bool:
    from .masks import AUX_FILES

    return all((d / f).is_file() for f in AUX_FILES.values())


def find_aux_dir(layout: RunLayout, view, cache_root=None) -> tuple[Path | None, str]:
    """(directory holding depth/normal/position.exr for the view, source) or (None, reason): the run's reference
    copy, else the cache entry with the same view hash and the highest aov_spp."""
    rdir = layout.reference_dir(view.scene, view.id)
    if _aux_complete(rdir):
        return rdir, "run reference"
    root = (Path(cache_root) if cache_root is not None else DEFAULT_CACHE_ROOT) / "reference"
    key = str(root.resolve())
    if key not in _cache_index:
        idx: dict[str, list[tuple[int, Path]]] = {}
        for rec_path in sorted(root.glob("*/receipt.json")) if root.is_dir() else []:
            rec = _read_json(rec_path) or {}
            inp = rec.get("inputs") or {}
            if inp.get("view_hash"):
                idx.setdefault(inp["view_hash"], []).append((int(inp.get("aov_spp") or 0), rec_path.parent))
        _cache_index[key] = idx
    for _aov, d in sorted(_cache_index[key].get(view.hash, []), key=lambda t: -t[0]):
        if _aux_complete(d):
            return d, f"reference cache {d.name[:12]}"
    return None, (f"no reference AOVs for {view.scene}/{view.id} in the run ({_rel(layout, rdir)}) or the cache "
                  f"({root})")


def valid_pixel_mask(aux_dir) -> np.ndarray:
    """ROI 'all' of DESIGN §7 from a reference directory's AOVs: valid pixels eroded by 1 pixel."""
    from .masks import erode, load_aux, valid_mask

    return erode(valid_mask(load_aux(aux_dir)), 1)


# ------------------------------------------------------------------------------------------------ launches

def parity_capture_request(scene, views: list, info, settle_frames: int = SETTLE_STATIC,
                           dynamic_settle_frames: int = SETTLE_DYNAMIC) -> dict:
    """capture dict for Engine.build_bundle: the listed views only, measure.parity on."""
    measure = {"parity": True}
    if scene.timeline is None:
        n = max(1, int(dynamic_settle_frames if info.dynamic else settle_frames))
        return {"settle_frames": n, "measure": measure,
                "stations": [{"name": v.id, "camera": v.station.name, "settle_frames": n} for v in views]}
    frames = sorted({int(v.capture_frame) for v in views})
    return {"measure": measure,
            "timeline": {"camera": scene.timeline.station, "end_frame": frames[-1], "frames": frames}}


def _launch(layout: RunLayout, eng, scene, views: list, mode: str, avail: dict, cfg: dict, extra: list[str]) -> dict:
    """Build the parity bundle and run one runner in --parity. Never raises."""
    from renderers.base import NotWired, Unsupported, launch

    cdir = layout.parity_capture_dir(eng.name, scene.name, mode)
    rec = {"engine": eng.name, "scene": scene.name, "mode": mode, "views": [v.id for v in views], "status": "failed",
           "reason": None, "by_design": False, "seconds": 0.0, "bundle_seconds": 0.0, "returncode": None,
           "log_tail": [], "capture_dir": _rel(layout, cdir), "receipt": None}
    if avail["status"] != "ok":
        rec.update(status=avail["status"], reason=avail["reason"], by_design=avail["status"] == "skipped")
        return rec
    modes = eng.modes()
    if mode not in modes:
        rec.update(status="skipped", by_design=True, reason=f"{eng.name} has no mode {mode!r} (modes: "
                                                           f"{', '.join(modes)})")
        return rec
    t0 = time.perf_counter()
    try:
        capture = parity_capture_request(scene, views, modes[mode], cfg["settle_frames"],
                                         cfg["dynamic_settle_frames"])
        bundle_json = eng.build_bundle(scene, mode, views, capture,
                                       layout.parity_bundle_dir(eng.name, scene.name, mode))
    except (NotWired, Unsupported) as e:
        rec.update(status="skipped", reason=e.reason, by_design=True, bundle_seconds=time.perf_counter() - t0)
        return rec
    except Exception as e:  # noqa: BLE001 - recorded as the failure reason
        rec.update(reason=f"bundle: {type(e).__name__}: {e}", bundle_seconds=time.perf_counter() - t0,
                   log_tail=traceback.format_exc().rstrip().splitlines()[-40:])
        return rec
    rec["bundle_seconds"] = time.perf_counter() - t0
    if cdir.exists():
        shutil.rmtree(cdir, ignore_errors=True)  # stale captures must not hide a failure
    res = launch(eng, bundle_json, cdir, cfg["timeout"], extra=extra, echo=cfg["echo"])
    rec.update(status=res.status, reason=res.reason or None, by_design=res.by_design, seconds=res.seconds,
               returncode=res.returncode, log_tail=list(res.log_tail) if res.status != "ok" else [])
    if res.ok:
        rec["receipt"] = _read_json(cdir / "receipt.json")
    return rec


def _read_png(path: Path) -> np.ndarray:
    from .png import load_png

    return load_png(path)[:, :, :3]


def _read_rgb(path: Path) -> np.ndarray | None:
    from .exr import read_exr

    return read_exr(path)[..., :3].astype(np.float64) if path.is_file() else None


def _compare_entry(layout: RunLayout, scene, view, mode: str, web, nat, launches: Mapping[str, dict],
                   cfg: dict) -> dict:
    """One parity.json entry (never raises)."""
    sheet = layout.phase0_sheet_png(scene.name, view.id, mode)
    paths = {"web_png": layout.parity_capture(web.name, scene.name, mode, view, "png"),
             "native_png": layout.parity_capture(nat.name, scene.name, mode, view, "png"),
             "web_exr": layout.parity_capture(web.name, scene.name, mode, view, "exr"),
             "native_exr": layout.parity_capture(nat.name, scene.name, mode, view, "exr")}
    e = {"scene": scene.name, "view": view.id, "mode": mode, "kind": view.kind, "status": "failed", "reason": None,
         "by_design": False, "gate": gate_check(None), "all": None, "valid": None, "valid_mask": None,
         "linear": None, "adapters": {}, "files": {**{k: _rel(layout, p) for k, p in paths.items()},
                                                   "sheet": None}, "warnings": []}
    for side in (web, nat):
        e["adapters"][side.name] = (device_summary(launches[side.name].get("receipt")) or {}).get("adapter")
    bad = [launches[s.name] for s in (web, nat) if launches[s.name]["status"] != "ok"]
    if bad:
        failed = any(L["status"] == "failed" for L in bad)
        e.update(status="failed" if failed else "skipped", by_design=not failed and all(L["by_design"] for L in bad),
                 reason="; ".join(f"{L['engine']} {L['status']}: {L['reason']}" for L in bad))
        return e
    try:
        missing = [k for k in ("web_png", "native_png") if not paths[k].is_file()]
        if missing:
            raise FileNotFoundError("capture missing: " + ", ".join(e["files"][k] for k in missing))
        a, b = _read_png(paths["web_png"]), _read_png(paths["native_png"])
        if a.shape != b.shape:
            raise ValueError(f"image shapes differ: web {a.shape}, native {b.shape}")
        mask, minfo = None, {"source": None, "dir": None, "pixels": None, "fraction": None, "reason": None}
        aux_dir, source = find_aux_dir(layout, view, cfg.get("cache_root"))
        if aux_dir is None:
            minfo["reason"] = source
        else:
            try:
                mask = _mask(valid_pixel_mask(aux_dir), a.shape)
                minfo.update(source=source, dir=_rel(layout, aux_dir), pixels=int(mask.sum()),
                             fraction=float(mask.mean()))
            except Exception as ex:  # noqa: BLE001 - the valid-pixel block is optional
                mask = None
                minfo["reason"] = f"reference AOVs unusable ({source}): {type(ex).__name__}: {ex}"
        exr_w, exr_n = _read_rgb(paths["web_exr"]), _read_rgb(paths["native_exr"])
        if exr_w is None or exr_n is None:
            e["warnings"].append("linear final.exr missing on a side: no linear comparison")
        res = compare_view(a, b, exr_w, exr_n, mask)
    except Exception as ex:  # noqa: BLE001 - recorded, the run goes on
        e["reason"] = f"compare: {type(ex).__name__}: {ex}"
        return e
    e.update(status="ok", all=res["all"], valid=res["valid"], gate=res["gate"], linear=res["linear"],
             valid_mask=minfo)
    try:
        g = res["gate"]
        verdict = {True: "PASS", False: "FAIL", None: "n/a"}[g["passed"]]

        def vs(value, limit, spec):  # the comparison as it came out (not the criterion): "80 > 1", "0.02 <= 0.1"
            op = "?" if value is None else ("<=" if value <= limit else ">")
            return f"{_fmt(value, spec)} {op} {limit:g}"

        title = (f"{scene.name} / {view.id} / {mode}: parity {verdict} (p99.9 {vs(g['p99_9'], GATE_P99_9_LSB, '.3g')}"
                 f", mean {vs(g['mean'], GATE_MEAN_LSB, '.3f')} LSB)")
        parity_sheet(a, b, sheet, title, f"{web.name}\n{_short(e['adapters'].get(web.name))}",
                     f"{nat.name}\n{_short(e['adapters'].get(nat.name))}", res["all"])
        e["files"]["sheet"] = _rel(layout, sheet)
    except Exception as ex:  # noqa: BLE001 - a sheet must not fail the comparison
        e["warnings"].append(f"sheet: {type(ex).__name__}: {ex}")
    return e


def overall_gate(entries: Sequence[Mapping]) -> dict:
    """passed when every entry was compared and passed; failed when any compared entry failed; else incomplete."""
    compared = [e for e in entries if e.get("status") == "ok"]
    name = lambda e: f"{e['scene']}/{e['view']}/{e['mode']}"  # noqa: E731
    failed = [name(e) for e in compared if (e.get("gate") or {}).get("passed") is False]
    passed_n = sum(1 for e in compared if (e.get("gate") or {}).get("passed") is True)
    not_compared = [f"{name(e)}: {e.get('status')}: {e.get('reason')}" for e in entries if e.get("status") != "ok"]
    if failed:
        status, passed = "failed", False
    elif not_compared or not entries or passed_n != len(compared):
        status, passed = "incomplete", None
    else:
        status, passed = "passed", True
    return {"passed": passed, "status": status, "criterion": CRITERION, "entries": len(entries),
            "compared": len(compared), "passed_entries": passed_n, "failed_entries": failed,
            "not_compared": not_compared}


# ------------------------------------------------------------------------------------------------ driver

def run_parity(run_dir, views_file=None, engines: Sequence = DEFAULT_ENGINES, timeout: float = DEFAULT_TIMEOUT,
               adapter: str | None = None, power: str | None = None, settle_frames: int = SETTLE_STATIC,
               dynamic_settle_frames: int = SETTLE_DYNAMIC, scenes_root=None, cache_root=None, echo: bool = False,
               log: Callable[[str], None] | None = print) -> dict:
    """Run the parity comparison (module docstring); returns the parity.json document (plus "path")."""
    from renderers.base import NotWired, git_sha
    from .spec import discover_scenes, expand_views, load_scene

    say = log or (lambda _m: None)
    started, t_all = utc_now(), time.perf_counter()
    layout = RunLayout(run_dir)
    layout.ensure(layout.root)
    vf = load_views_file(views_file)
    engs = resolve_engines(list(engines))
    if len(engs) != 2:
        raise ValueError(f"parity compares exactly two engines (web side, native side), got {len(engs)}")
    web, nat = engs
    cfg = {"views_file": vf["path"], "engines": [e.name for e in engs], "timeout": float(timeout),
           "adapter": adapter, "power": power, "settle_frames": int(settle_frames),
           "dynamic_settle_frames": int(dynamic_settle_frames),
           "scenes_root": None if scenes_root is None else str(scenes_root),
           "cache_root": None if cache_root is None else str(cache_root), "echo": bool(echo)}
    extra = ["--parity"] + (["--adapter", adapter] if adapter else []) + (["--power", power] if power else [])

    avail: dict[str, dict] = {}
    for eng in engs:
        try:
            eng.check_available()
            avail[eng.name] = {"status": "ok", "reason": None}
        except NotWired as e:
            avail[eng.name] = {"status": "skipped", "reason": e.reason}
            say(f"{eng.name}: not available: {e.reason}")
        except Exception as e:  # noqa: BLE001
            avail[eng.name] = {"status": "failed", "reason": f"check_available: {type(e).__name__}: {e}"}
            say(f"{eng.name}: FAIL {avail[eng.name]['reason']}")

    groups: dict[tuple[str, str], list[str]] = {}
    for v in vf["views"]:
        for m in v["modes"]:
            ids = groups.setdefault((v["scene"], m), [])
            if v["view"] not in ids:
                ids.append(v["view"])

    entries: list[dict] = []
    launches: list[dict] = []
    receipts: dict[str, list[dict]] = {e.name: [] for e in engs}
    scenes: dict[str, Any] = {}
    for (scene_name, mode), view_ids in groups.items():
        try:
            if scene_name not in scenes:
                scenes[scene_name] = load_scene(discover_scenes(scene_name, scenes_root)[0])
            scene = scenes[scene_name]
            by_id = {v.id: v for v in expand_views(scene)}
            unknown = [v for v in view_ids if v not in by_id]
            if unknown:
                raise ValueError(f"no view {', '.join(unknown)} (views: {', '.join(by_id)})")
            views = [by_id[v] for v in view_ids]
        except Exception as e:  # noqa: BLE001 - a bad entry must not end the run
            say(f"{scene_name}/{mode}: FAIL {type(e).__name__}: {e}")
            for vid in view_ids:
                entries.append({"scene": scene_name, "view": vid, "mode": mode, "kind": None, "status": "failed",
                                "reason": f"scene: {type(e).__name__}: {e}", "by_design": False,
                                "gate": gate_check(None), "all": None, "valid": None, "valid_mask": None,
                                "linear": None, "adapters": {}, "files": {}, "warnings": []})
            continue
        say(f"{scene_name} / {mode}: {', '.join(view_ids)}")
        res = {}
        for eng in engs:
            r = _launch(layout, eng, scene, views, mode, avail[eng.name], cfg, extra)
            res[eng.name] = r
            say(f"  {eng.name}: {r['status']}{' (' + str(r['reason']) + ')' if r['reason'] else ''} "
                f"in {r['bundle_seconds'] + r['seconds']:.1f} s")
            if r["receipt"]:
                receipts[eng.name].append(r["receipt"])
            launches.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
                             if k != "receipt"})
        for v in views:
            e = _compare_entry(layout, scene, v, mode, web, nat, res, cfg)
            entries.append(e)
            if e["status"] == "ok":
                g, va = e["gate"], e["valid"]
                say(f"  {v.id}: {'PASS' if g['passed'] else 'FAIL'} p99.9 {_fmt(g['p99_9'])} mean "
                    f"{_fmt(g['mean'], '.4f')} max {e['all']['max']} LSB, {e['all']['pixels_gt1']} px > 1 LSB"
                    + (f"; valid px: p99.9 {_fmt(va['p99_9'])} mean {_fmt(va['mean'], '.4f')}" if va else ""))
            else:
                say(f"  {v.id}: {e['status']}: {e['reason']}")

    devices, adapters = {}, {}
    for eng in engs:
        sums = [device_summary(r) for r in receipts[eng.name]]
        sums = [s for s in sums if s]
        devices[eng.name] = sums[0] if sums else None
        adapters[eng.name] = sorted({str(s.get("adapter")) for s in sums})
    representative, why = representativeness(devices)
    gate = overall_gate(entries)
    gate["representative"] = representative
    if not representative:
        gate["note"] = "recorded, not representative: " + (why or "")
    doc = {"parity_version": PARITY_VERSION, "run": layout.run_id, "created_utc": started, "git": git_sha(),
           "host": host_info(), "views_file": vf["path"], "criterion": CRITERION, "percentile": PERCENTILE_METHOD,
           "diff_gain": DIFF_GAIN, "gate": gate, "representative": representative, "reason": why,
           "devices": devices, "adapters": adapters, "config": cfg, "entries": entries, "launches": launches,
           "durations": {"total_s": round(time.perf_counter() - t_all, 4)}}
    path = _write_json(layout.phase0_parity_json, doc)
    update_run_json(layout.root, {"config": {"parity": cfg}, "durations": {"parity": {
        "started_utc": started, "finished_utc": utc_now(), **doc["durations"]}}})
    say(f"parity gate: {gate['status']} ({gate['passed_entries']}/{gate['entries']} passed"
        + (f"; failed: {', '.join(gate['failed_entries'])}" if gate["failed_entries"] else "") + ")"
        + ("" if representative else f"; NOT representative: {why}"))
    say(f"wrote {path}")
    doc["path"] = str(path)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.parity", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="run directory (runs/<id>); created if missing")
    ap.add_argument("--views", default=None, help=f"views file (default {DEFAULT_VIEWS_FILE.relative_to(REPO_ROOT)})")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per runner launch")
    ap.add_argument("--adapter", default=None, help="adapter substring passed to both runners")
    ap.add_argument("--power", default=None, choices=["high-performance", "low-power"], help="passed to both runners")
    ap.add_argument("--settle-frames", type=int, default=SETTLE_STATIC, help="station frames, non-dynamic modes")
    ap.add_argument("--dynamic-settle-frames", type=int, default=SETTLE_DYNAMIC, help="station frames, dynamic modes")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--cache", default=None, help="reference cache root for the valid-pixel masks "
                                                  "(default <repo>/cache)")
    ap.add_argument("--echo", action="store_true", help="echo runner output")
    ap.add_argument("--strict", action="store_true", help="also exit 1 when the gate did not pass")
    args = ap.parse_args(argv)
    try:
        doc = run_parity(args.run, views_file=args.views, timeout=args.timeout, adapter=args.adapter,
                         power=args.power, settle_frames=args.settle_frames,
                         dynamic_settle_frames=args.dynamic_settle_frames, scenes_root=args.scenes_root,
                         cache_root=args.cache, echo=args.echo)
    except ValueError as e:
        print(f"FAIL {e}")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    if any(e["status"] == "failed" for e in doc["entries"]):
        return 1
    return 1 if args.strict and doc["gate"]["passed"] is not True else 0


if __name__ == "__main__":
    sys.exit(main())
