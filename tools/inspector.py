"""Interactive viewer for a run (DESIGN §3 ``inspect/``, §10): build ``<run>/inspect/`` and serve it locally.

    python -m tools.inspector [scene] [--run <dir>|LATEST] [--scene name] [--no-open] [--port N] [--no-serve]
        [--scenes-root DIR] [--runs-root DIR]

(Named ``inspector`` because ``tools.inspect`` would shadow the standard-library ``inspect`` module.)

Build: ``<run>/inspect/`` gets

- ``index.html``, ``viewer.js``, ``style.css``: the viewer, copied from ``tools/inspector_web/``. No external
  resources (no CDN, no web fonts), so it works offline;
- ``manifest.json``: run id, engines, the scenes and views built, the path of each view manifest;
- ``data/<scene>/<view>/``: ``manifest.json`` (image size, display exposures, error epsilons, columns, files, ROIs,
  the metrics.json rows of the view, links) and the raw data:

  - ``*.f16``: float16 little-endian, row-major, row 0 = top of the image, ``channels`` values per pixel (3 = linear
    RGB, 1 = the standard error of Y), ``height * width * channels * 2`` bytes. Reference ``full``, ``direct`` and
    ``isolated`` (``full - direct``) plus the per-pixel standard error of Y of the direct and isolated components;
    per engine mode its ``final`` and its measured component (``direct`` mode: the final itself; other modes:
    ``final(mode) - final(direct)`` of the same engine, computed in float64 before the float16 cast);
  - ``roi__<name>.u8``: one byte per pixel, 1 inside the ROI (masks from ``tools.masks.view_masks``: the same
    eroded masks the metrics use; ROI ``all`` = valid pixels);
- ``links/``: copies of the contact sheets, temporal plots and report.md, so the server root holds everything.

Serve: ``ThreadingHTTPServer`` on 127.0.0.1 (``--port``, default 8765, or the next free port), opens the browser
unless ``--no-open``; Ctrl+C stops it. ``--no-serve`` only builds.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import shutil
import sys
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np

from . import REPO_ROOT
from .layout import RunLayout, read_latest

__all__ = ["ASSET_DIR", "ASSETS", "DEFAULT_PORT", "INSPECT_VERSION", "build_inspector", "main", "make_server",
           "resolve_run", "serve", "to_f16"]

INSPECT_VERSION = 1
ASSET_DIR = Path(__file__).resolve().parent / "inspector_web"
ASSETS = ("index.html", "viewer.js", "style.css")
DEFAULT_PORT = 8765
F16_MAX = 65504.0
_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _say_default(msg: str) -> None:
    print(msg, flush=True)


def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _write_json(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(_clean(doc), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return _f(x)
    if isinstance(x, Path):
        return x.as_posix()
    return x


def _safe(name: str) -> str:
    return _SAFE.sub("_", str(name)).strip("_") or "x"


def to_f16(img) -> np.ndarray:
    """float16 little-endian copy: finite values clipped to the float16 range, NaN/inf kept (the viewer marks them)."""
    a = np.asarray(img, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        a = np.where(np.isfinite(a), np.clip(a, -F16_MAX, F16_MAX), a)
    return np.ascontiguousarray(a.astype("<f2"))


def resolve_run(run: str | Path | None, runs_root: str | Path | None = None) -> Path:
    """A run directory from a path, or ``LATEST`` / None (the run named by <runs_root>/LATEST)."""
    root = Path(runs_root) if runs_root is not None else REPO_ROOT / "runs"
    if run is None or str(run) == "LATEST":
        latest = read_latest(root)
        if latest is None:
            raise FileNotFoundError(f"{root / 'LATEST'} does not name an existing run directory "
                                    f"(run the harness first, or pass --run <dir>)")
        return latest
    p = Path(run)
    if not p.is_dir():
        raise FileNotFoundError(f"run directory {p} does not exist")
    return p


# ------------------------------------------------------------------------------------------------ inputs

def _scenes_root(run_doc: Mapping, override) -> Path | None:
    if override is not None:
        return Path(override)
    cfg = run_doc.get("config") if isinstance(run_doc.get("config"), dict) else {}
    for tool in ("pairs", "run_all"):
        root = (cfg.get(tool) or {}).get("scenes_root") if isinstance(cfg.get(tool), dict) else None
        if root and Path(root).is_dir():
            return Path(root)
    return None


def _scene_infos(layout: RunLayout, metrics: Mapping) -> dict[str, dict]:
    """{scene: {"group", "comparison", "failure_mode", "kind", "views": [{"id", "kind", "station",
    "capture_frame"}], "scene_hash"}} from views/<scene>.json, completed by metrics.json."""
    out: dict[str, dict] = {}
    vdir = layout.root / "views"
    for p in sorted(vdir.glob("*.json")) if vdir.is_dir() else []:
        d = _read_json(p)
        if isinstance(d, dict) and isinstance(d.get("views"), list):
            out[p.stem] = {"group": d.get("group"), "comparison": d.get("comparison") or "exact",
                           "failure_mode": d.get("failure_mode"), "kind": d.get("kind"),
                           "scene_hash": d.get("scene_hash"),
                           "views": [v for v in d["views"] if isinstance(v, dict) and v.get("id")]}
    for name, info in (metrics.get("scenes") or {}).items() if isinstance(metrics.get("scenes"), dict) else ():
        if not isinstance(info, dict):
            continue
        cur = out.setdefault(name, {"views": []})
        for k in ("group", "comparison", "failure_mode", "kind"):
            if cur.get(k) in (None, "") and info.get(k) not in (None, ""):
                cur[k] = info[k]
        if not cur["views"] and isinstance(info.get("views"), list):
            cur["views"] = [v for v in info["views"] if isinstance(v, dict) and v.get("id")]
        cur.setdefault("comparison", "exact")
    rroot = layout.root / "reference"
    for d in sorted(rroot.iterdir()) if rroot.is_dir() else []:  # references without views/ or metrics entries
        if d.is_dir() and d.name not in out:
            out[d.name] = {"comparison": "exact", "views": [{"id": v.name, "kind": "station"}
                                                            for v in sorted(d.iterdir()) if v.is_dir()]}
    return out


def _engine_modes(layout: RunLayout, metrics: Mapping) -> dict[str, dict]:
    """{engine: {"status", "reason", "version", "modes": {mode: {"kind", "dynamic", ...}}}} in run order."""
    out: dict[str, dict] = {}
    for name, b in (metrics.get("engines") or {}).items() if isinstance(metrics.get("engines"), dict) else ():
        if isinstance(b, dict):
            out[name] = {"status": b.get("status"), "reason": b.get("reason"), "version": b.get("version"),
                         "modes": dict(b.get("modes") or {})}
    for r in metrics.get("results") or []:
        if isinstance(r, dict) and r.get("engine"):
            e = out.setdefault(r["engine"], {"status": None, "reason": None, "version": None, "modes": {}})
            if r.get("mode") and r["mode"] not in e["modes"]:
                e["modes"][r["mode"]] = {"kind": r.get("kind") or ("direct" if r["mode"] == "direct" else
                                                                      "indirect")}
    if not out:  # no metrics.json: engine directories and their capture modes, kinds from the registry
        from .gates import run_engines

        for eng in run_engines(layout):
            reg = None
            try:
                from renderers import get_engine

                reg = get_engine(eng).modes()
            except Exception:  # noqa: BLE001
                reg = None
            modes = {}
            for kdir in sorted(layout.engine_root(eng).glob("*/*")):
                if kdir.name in ("stations", "timeline"):
                    for m in sorted(p.name for p in kdir.iterdir() if p.is_dir()):
                        info = reg.get(m) if reg else None
                        modes.setdefault(m, {"kind": info.kind if info else ("direct" if m == "direct" else
                                                                             "indirect"),
                                             "dynamic": bool(info.dynamic) if info else None})
            out[eng] = {"status": None, "reason": None, "version": None, "modes": modes}
    return out


def _direct_mode(modes: Mapping[str, dict]) -> str | None:
    d = [m for m, i in modes.items() if isinstance(i, dict) and i.get("kind") == "direct"]
    return d[0] if len(d) == 1 else ("direct" if "direct" in modes else None)


def _spec_view(name: str, view_id: str, scenes_root, cache: dict, warnings: list):
    """The spec View (for its ROIs), or None when the scene spec cannot be loaded."""
    if name not in cache:
        try:
            from .spec import discover_scenes, expand_views, load_scene

            scene = load_scene(discover_scenes(name, scenes_root)[0])
            cache[name] = (scene, {v.id: v for v in expand_views(scene)})
        except Exception as e:  # noqa: BLE001 - masks fall back to ROI 'all'
            cache[name] = None
            warnings.append(f"{name}: scene spec not loadable ({type(e).__name__}: {e}); only ROI 'all' is shown")
    entry = cache[name]
    return None if entry is None else (entry[0], entry[1].get(view_id))


# ------------------------------------------------------------------------------------------------ build

def _rgb(path: Path) -> np.ndarray:
    from .exr import read_exr

    return read_exr(path)[..., :3].astype(np.float64)


class _ViewWriter:
    def __init__(self, out_dir: Path, h: int, w: int):
        self.dir, self.h, self.w = out_dir, h, w
        out_dir.mkdir(parents=True, exist_ok=True)

    def f16(self, name: str, img) -> dict:
        a = np.asarray(img, dtype=np.float64)
        if a.ndim == 2:
            a = a[..., None]
        if a.shape[:2] != (self.h, self.w):
            raise ValueError(f"{name}: image {a.shape[:2]} != view size {(self.h, self.w)}")
        (self.dir / name).write_bytes(to_f16(a).tobytes())
        return {"file": name, "dtype": "float16", "channels": int(a.shape[2])}

    def u8(self, name: str, mask) -> dict:
        m = np.ascontiguousarray(np.asarray(mask, dtype=bool).astype(np.uint8))
        (self.dir / name).write_bytes(m.tobytes())
        return {"file": name, "dtype": "uint8", "channels": 1}


def _copy_link(src: Path, root: Path, rel: str) -> str | None:
    """Copy ``src`` to ``root/links/rel`` when it exists (skipped when unchanged); returns the link path."""
    if not src.is_file():
        return None
    dst = root / "links" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        st, dt = src.stat(), dst.stat() if dst.exists() else None
        if dt is None or dt.st_size != st.st_size or dt.st_mtime < st.st_mtime:
            shutil.copy2(src, dst)
    except OSError:
        return None
    return f"links/{rel}"


def _build_view(layout: RunLayout, scene: str, info: dict, view: dict, engines: dict, results: list,
                spec, inspect_root: Path, warnings: list) -> dict:
    from .masks import ALL_ROI, view_masks
    from .metrics import load_reference_images, luminance, pixel_stderr_y, isolated_stderr

    vid = str(view["id"])
    rdir = layout.reference_dir(scene, vid)
    ref = load_reference_images(rdir)
    if "full" not in ref or "direct" not in ref:
        raise FileNotFoundError(f"reference {rdir.relative_to(layout.root).as_posix()} lacks full.exr/direct.exr")
    full, direct = ref["full"].astype(np.float64), ref["direct"].astype(np.float64)
    iso = full - direct
    h, w = full.shape[:2]
    vw = _ViewWriter(inspect_root / "data" / _safe(scene) / _safe(vid), h, w)
    vwarn: list[str] = []

    # masks: the metrics' masks (spec ROIs need the spec view), else ROI 'all' only
    spec_scene, spec_view = spec if spec else (None, None)
    try:
        if spec_view is not None:
            masks = view_masks(spec_view, rdir)
        else:
            masks = view_masks(vid, rdir, rois=[])
    except Exception as e:  # noqa: BLE001 - AOVs missing: no masks, the viewer still shows the images
        masks = {ALL_ROI: np.ones((h, w), bool)}
        vwarn.append(f"masks unavailable ({type(e).__name__}: {e}); ROI 'all' = every pixel")
    roles = {ALL_ROI: "any"}
    if spec_scene is not None:
        roles.update({r.name: r.role for r in spec_scene.rois})
    rows = [r for r in results if isinstance(r, dict) and r.get("scene") == scene and
            (r.get("view") == vid or r.get("view") is None)]
    for r in rows:
        for k, s in (r.get("rois") or {}).items():
            if isinstance(s, dict) and s.get("role") and k not in roles:
                roles[k] = s["role"]
    all_mask = masks.get(ALL_ROI)
    rois = []
    for name, m in masks.items():
        if np.asarray(m).shape != (h, w):
            continue
        rois.append({"name": name, "role": roles.get(name, "any"), "pixels": int(np.asarray(m).sum()),
                     **vw.u8(f"roi__{_safe(name)}.u8", m)})

    def eps_of(img) -> float:
        Y = luminance(img)
        sel = np.isfinite(Y) & (all_mask if all_mask is not None and all_mask.any() else True)
        mu = abs(float(Y[sel].mean())) if np.any(sel) else 0.0
        return 0.01 * mu if mu > 0 else 1e-12

    se_direct = ref.get("direct_stderr")
    se_iso = isolated_stderr(ref)
    ref_col = {"id": "reference", "label": "reference", "kind": "reference", "status": "ok", "reason": None,
               "files": {"final": vw.f16("ref_full.f16", full), "direct": vw.f16("ref_direct.f16", direct),
                         "isolated": vw.f16("ref_isolated.f16", iso)},
               "noise": {}}
    if se_direct is not None:
        ref_col["noise"]["direct"] = vw.f16("ref_se_direct.f16", pixel_stderr_y(se_direct))
    if se_iso is not None:
        ref_col["noise"]["isolated"] = vw.f16("ref_se_isolated.f16", pixel_stderr_y(se_iso))
    columns = [ref_col]

    vkind = view.get("kind") or "station"
    vdict = {"id": vid, "kind": vkind, "capture_frame": view.get("capture_frame")}
    by_mode = {(r.get("engine"), r.get("mode")): r for r in rows if r.get("view") == vid}
    scene_skip = {r.get("engine"): r for r in rows if r.get("view") is None}
    finals: dict[tuple, tuple[np.ndarray | None, str | None]] = {}

    def capture(eng: str, mode: str) -> tuple[np.ndarray | None, str | None]:
        key = (eng, mode)
        if key not in finals:
            r = by_mode.get(key) or {}
            rel = (r.get("files") or {}).get("capture")
            try:
                path = layout.root / rel if rel else layout.view_capture(eng, scene, mode, vdict)
            except ValueError:
                path = None
            img, why = None, None
            if path is not None and path.is_file():
                try:
                    img = _rgb(path)
                    if img.shape[:2] != (h, w):
                        img, why = None, f"capture is {img.shape[:2]}, reference {(h, w)}"
                except Exception as e:  # noqa: BLE001
                    why = f"capture unreadable: {type(e).__name__}: {e}"
            else:
                why = "no capture"
            finals[key] = (img, why)
        return finals[key]

    for eng, block in engines.items():
        modes = block.get("modes") or {}
        dmode = _direct_mode(modes)
        listed = [m for m in modes if (eng, m) in by_mode]
        if not listed and eng in scene_skip:
            r = scene_skip[eng]
            columns.append({"id": f"{eng}", "label": f"{eng}", "engine": eng, "mode": None, "kind": None,
                            "status": r.get("status"), "reason": r.get("reason"), "by_design": r.get("by_design"),
                            "files": {}})
            continue
        if not listed and not by_mode:  # no metrics rows at all: show whatever was captured
            listed = [m for m in modes if capture(eng, m)[0] is not None]
        for mode in listed:
            minfo = modes.get(mode) or {}
            kind = minfo.get("kind") or ("direct" if mode == dmode else "indirect")
            comp = "direct" if kind == "direct" else "isolated"
            r = by_mode.get((eng, mode)) or {}
            col = {"id": f"{eng}/{mode}", "label": f"{eng} / {mode}", "engine": eng, "mode": mode, "kind": kind,
                   "component": comp, "dynamic": minfo.get("dynamic"), "status": r.get("status") or "ok",
                   "reason": r.get("reason"), "by_design": r.get("by_design"), "files": {}}
            img, why = capture(eng, mode)
            if img is None:
                col["missing"] = why
                columns.append(col)
                continue
            base = f"{_safe(eng)}__{_safe(mode)}"
            col["files"]["final"] = vw.f16(f"{base}__final.f16", img)
            if comp == "direct":
                col["files"]["component"] = col["files"]["final"]
            else:
                dimg, dwhy = capture(eng, dmode) if dmode else (None, "engine has no direct mode")
                if dimg is not None:
                    col["files"]["component"] = vw.f16(f"{base}__isolated.f16", img - dimg)
                else:
                    col["component_missing"] = f"direct mode {dmode}: {dwhy}"
            columns.append(col)

    links: dict[str, Any] = {"sheet": None, "temporal": []}
    sheet_rel = next(((r.get("files") or {}).get("sheet") for r in rows if (r.get("files") or {}).get("sheet")),
                     None)
    sheet = layout.root / sheet_rel if sheet_rel else layout.sheet_png(scene, vid)
    links["sheet"] = _copy_link(sheet, inspect_root, f"sheets/{_safe(scene)}/{_safe(vid)}.png")
    if layout.temporal_dir.is_dir():
        for p in sorted(layout.temporal_dir.glob(f"{scene}__*.png")):
            parts = p.stem.split("__")
            label = " / ".join(parts[1:]) if len(parts) >= 3 else p.stem
            link = _copy_link(p, inspect_root, f"temporal/{p.name}")
            if link:
                links["temporal"].append({"label": label, "href": link})
    if spec_scene is not None and info.get("scene_hash") and info["scene_hash"] != spec_scene.hash:
        vwarn.append("the scene spec changed since the run: ROI masks may differ from the ones the metrics used")
    doc = {"inspect_version": INSPECT_VERSION, "scene": scene, "view": vid, "kind": vkind,
           "station": view.get("station"), "capture_frame": view.get("capture_frame"),
           "frames": view.get("frames"), "width": w, "height": h, "group": info.get("group"),
           "comparison": info.get("comparison") or "exact", "failure_mode": info.get("failure_mode"),
           "exposure": _exposures(full, direct, iso),
           "eps": {"direct": eps_of(direct), "isolated": eps_of(iso)},
           "format": {"f16": "float16 little-endian, row-major, row 0 = top, `channels` values per pixel",
                      "u8": "uint8 per pixel, 1 = inside the ROI"},
           "columns": columns, "rois": rois, "metrics": rows, "links": links, "warnings": vwarn}
    _write_json(vw.dir / "manifest.json", doc)
    warnings += [f"{scene}/{vid}: {x}" for x in vwarn]
    return doc


def build_inspector(run_dir, scene: str | None = None, scenes_root=None,
                    log: Callable[[str], None] | None = _say_default) -> Path:
    """Build ``<run>/inspect/`` (see the module docstring); returns the directory.

    ``scene`` restricts the build to one scene (the viewer opens on it). Raises FileNotFoundError when the run has
    no references, ValueError for an unknown scene.
    """
    say = log or (lambda _m: None)
    layout = RunLayout(run_dir)
    if not layout.root.is_dir():
        raise FileNotFoundError(f"run directory {layout.root} does not exist")
    root = layout.inspect_dir
    metrics = _read_json(layout.metrics_json)
    metrics = metrics if isinstance(metrics, dict) else {}
    run_doc = _read_json(layout.run_json)
    run_doc = run_doc if isinstance(run_doc, dict) else {}
    infos = _scene_infos(layout, metrics)
    if scene is not None:
        if scene not in infos:
            raise ValueError(f"scene {scene!r} is not in run {layout.run_id} (scenes: {', '.join(infos) or 'none'})")
        infos = {scene: infos[scene]}
    if not infos:
        raise FileNotFoundError(f"run {layout.root} has no views (no views/*.json, metrics.json scenes or "
                                f"reference/ directories)")
    engines = _engine_modes(layout, metrics)
    results = [r for r in metrics.get("results") or [] if isinstance(r, dict)]
    sroot = _scenes_root(run_doc, scenes_root)
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("data",):
        if (root / sub).exists():
            shutil.rmtree(root / sub)
    for name in ASSETS:
        shutil.copyfile(ASSET_DIR / name, root / name)
    warnings: list[str] = []
    spec_cache: dict = {}
    scenes_out = []
    order = {"calibration": 0, "targeted": 1, "realworld": 2}
    for name in sorted(infos, key=lambda n: (order.get(infos[n].get("group"), 9), n)):
        info = infos[name]
        views_out = []
        for v in info.get("views") or []:
            vid = str(v["id"])
            entry = {"id": vid, "kind": v.get("kind"), "manifest": None, "error": None}
            if not layout.reference_dir(name, vid).is_dir():
                entry["error"] = "no reference in the run"
                views_out.append(entry)
                continue
            try:
                _build_view(layout, name, info, v, engines, results, _spec_view(name, vid, sroot, spec_cache,
                                                                                warnings), root, warnings)
                entry["manifest"] = f"data/{_safe(name)}/{_safe(vid)}/manifest.json"
            except Exception as e:  # noqa: BLE001 - one broken view must not lose the others
                entry["error"] = f"{type(e).__name__}: {e}"
                warnings.append(f"{name}/{vid}: {entry['error']}")
            views_out.append(entry)
        scenes_out.append({"name": name, "group": info.get("group"), "comparison": info.get("comparison"),
                           "failure_mode": info.get("failure_mode"), "kind": info.get("kind"), "views": views_out})
        built = sum(1 for x in views_out if x["manifest"])
        say(f"  {name}: {built}/{len(views_out)} views")
    report = _copy_link(layout.report_md, root, "report.md")
    doc = {"inspect_version": INSPECT_VERSION, "run": layout.run_id, "run_dir": layout.root.resolve().as_posix(),
           "created_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "git": run_doc.get("git") or metrics.get("git"), "default_scene": scene,
           "engines": engines, "scenes": scenes_out, "links": {"report": report}, "warnings": warnings}
    _write_json(root / "manifest.json", doc)
    for w in warnings:
        say(f"  warning: {w}")
    return root


# ------------------------------------------------------------------------------------------------ serve

class _Handler(SimpleHTTPRequestHandler):
    """Static files from the inspect directory with explicit MIME types (Windows can map .js to text/plain)."""

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, "": "application/octet-stream",
                      ".js": "text/javascript", ".css": "text/css", ".html": "text/html",
                      ".json": "application/json", ".f16": "application/octet-stream",
                      ".u8": "application/octet-stream", ".png": "image/png", ".md": "text/plain; charset=utf-8"}
    verbose = False

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args) -> None:  # noqa: A002 - signature of the base class
        if self.verbose:
            sys.stdout.write("[http] " + (format % args) + "\n")


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # http.server sets SO_REUSEADDR; on Windows that lets a second server bind a port another one listens on, so a
    # taken port would not be noticed. Elsewhere it only allows rebinding a port in TIME_WAIT.
    allow_reuse_address = os.name != "nt"


def make_server(directory, port: int = DEFAULT_PORT, verbose: bool = False) -> ThreadingHTTPServer:
    """ThreadingHTTPServer on 127.0.0.1 serving ``directory``; ``port`` 0 = any free port. When ``port`` is taken,
    the next 20 ports are tried, then any free port."""
    handler = partial(type("InspectHandler", (_Handler,), {"verbose": verbose}), directory=str(directory))
    candidates = [port] if port == 0 else [port + i for i in range(21)] + [0]
    last = None
    for p in candidates:
        try:
            return _Server(("127.0.0.1", p), handler)
        except OSError as e:
            last = e
    raise OSError(f"no free port to serve on (last error: {last})")


def serve(directory, port: int = DEFAULT_PORT, open_browser: bool = True, fragment: str = "",
          say: Callable[[str], None] = _say_default) -> int:
    server = make_server(directory, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/index.html" + (f"#{fragment}" if fragment else "")
    say(f"serving {directory} at {url}")
    say("press Ctrl+C to stop")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        say("stopped")
    finally:
        server.server_close()
    return 0


def _exposures(full, direct, iso) -> dict:
    """Initial display exposures, as the contact sheets pick them (tools.sheets): a component that is ~0 next to the
    final (exposure above COMPONENT_EXPOSURE_MAX times the final's) is shown on the final's scale."""
    from .sheets import COMPONENT_EXPOSURE_MAX, exposure_for

    out = {"final": exposure_for(full), "direct": exposure_for(direct), "isolated": exposure_for(iso)}
    for k in ("direct", "isolated"):
        if out[k] > COMPONENT_EXPOSURE_MAX * out["final"]:
            out[k] = out["final"]
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.inspector", description=__doc__.split("\n\n")[0])
    ap.add_argument("scene_pos", nargs="?", default=None, metavar="scene", help="scene to open (same as --scene)")
    ap.add_argument("--run", default="LATEST", help="run directory, or LATEST (default: runs/LATEST)")
    ap.add_argument("--scene", default=None, help="build only this scene and open it")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--no-serve", action="store_true", help="build inspect/ and exit")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port on 127.0.0.1 (default {DEFAULT_PORT}; "
                                                                   "0 = any free port)")
    ap.add_argument("--scenes-root", default=None, help="scene specs (default: the run's, else <repo>/scenes)")
    ap.add_argument("--runs-root", default=None, help="where LATEST lives (default <repo>/runs)")
    args = ap.parse_args(argv)
    scene = args.scene or args.scene_pos
    try:
        run = resolve_run(args.run, args.runs_root)
        print(f"building {RunLayout(run).inspect_dir}" + (f" (scene {scene})" if scene else ""), flush=True)
        root = build_inspector(run, scene=scene, scenes_root=args.scenes_root)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}", flush=True)
        return 1
    if args.no_serve:
        print(f"built {root}")
        return 0
    try:
        return serve(root, args.port, open_browser=not args.no_open, fragment=scene or "")
    except OSError as e:
        print(f"FAIL {e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
