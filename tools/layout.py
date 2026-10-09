"""Run directory layout (DESIGN §3): the only place run paths are spelled out."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any

__all__ = ["RunLayout", "new_run_dir", "write_latest", "read_latest", "reference_cache_dir", "CAPTURE_KINDS",
           "REFERENCE_FILES"]

CAPTURE_KINDS = ("stations", "timeline")
_KIND_ALIASES = {"stations": "stations", "station": "stations", "timeline": "timeline", "state": "timeline"}
REFERENCE_FILES = ("full.exr", "direct.exr", "full_stderr.exr", "direct_stderr.exr", "depth.exr", "normal.exr",
                   "position.exr", "receipt.json")


def _kind(kind: str) -> str:
    try:
        return _KIND_ALIASES[kind]
    except KeyError:
        raise ValueError(f"capture kind must be one of {CAPTURE_KINDS} (or view kind station/state), "
                         f"got {kind!r}") from None


def _get(view: Any, key: str):
    return view[key] if isinstance(view, dict) else getattr(view, key)


class RunLayout:
    """Paths inside runs/<run_id>/. Nothing is created until a caller writes; use ``ensure`` for dirs."""

    def __init__(self, run_dir):
        self.root = Path(run_dir)

    def __repr__(self) -> str:
        return f"RunLayout({str(self.root)!r})"

    @property
    def run_id(self) -> str:
        return self.root.name

    @staticmethod
    def ensure(path: Path) -> Path:
        """mkdir -p ``path`` (a directory) and return it."""
        Path(path).mkdir(parents=True, exist_ok=True)
        return Path(path)

    # -- run-level files
    @property
    def run_json(self) -> Path:
        return self.root / "run.json"

    def views_json(self, scene: str) -> Path:
        return self.root / "views" / f"{scene}.json"

    # -- reference
    def reference_dir(self, scene: str, view: str) -> Path:
        return self.root / "reference" / scene / view

    def reference_file(self, scene: str, view: str, name: str) -> Path:
        """name: one of REFERENCE_FILES (e.g. 'full.exr')."""
        return self.reference_dir(scene, view) / name

    # -- engines
    def engine_root(self, engine: str) -> Path:
        return self.root / engine

    def bundle_dir(self, engine: str, scene: str, mode: str) -> Path:
        return self.engine_root(engine) / scene / "bundles" / mode

    def bundle_json(self, engine: str, scene: str, mode: str) -> Path:
        return self.bundle_dir(engine, scene, mode) / "bundle.json"

    def capture_dir(self, engine: str, scene: str, kind: str, mode: str) -> Path:
        """kind: 'stations' | 'timeline' (view kinds 'station' | 'state' are accepted too)."""
        return self.engine_root(engine) / scene / _kind(kind) / mode

    def station_capture(self, engine: str, scene: str, mode: str, station: str) -> Path:
        return self.capture_dir(engine, scene, "stations", mode) / station / "final.exr"

    def timeline_frame(self, engine: str, scene: str, mode: str, frame: int) -> Path:
        return self.capture_dir(engine, scene, "timeline", mode) / "frames" / f"{int(frame):05d}.exr"

    def view_capture(self, engine: str, scene: str, mode: str, view) -> Path:
        """Capture file for a View (or a dict with id/kind/capture_frame): station final or state capture frame."""
        kind = _get(view, "kind")
        if kind == "station":
            return self.station_capture(engine, scene, mode, _get(view, "id"))
        if kind == "state":
            return self.timeline_frame(engine, scene, mode, _get(view, "capture_frame"))
        raise ValueError(f"view kind must be 'station' or 'state', got {kind!r}")

    def receipt_json(self, engine: str, scene: str, kind: str, mode: str) -> Path:
        return self.capture_dir(engine, scene, kind, mode) / "receipt.json"

    def timing_json(self, engine: str, scene: str, kind: str, mode: str) -> Path:
        return self.capture_dir(engine, scene, kind, mode) / "timing.json"

    def runner_log(self, engine: str, scene: str, kind: str, mode: str) -> Path:
        return self.capture_dir(engine, scene, kind, mode) / "runner.log"

    # -- results
    @property
    def metrics_json(self) -> Path:
        return self.root / "metrics.json"

    @property
    def gates_json(self) -> Path:
        return self.root / "gates.json"

    @property
    def temporal_json(self) -> Path:
        return self.root / "temporal.json"

    @property
    def perf_json(self) -> Path:
        return self.root / "perf.json"

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def sheets_dir(self) -> Path:
        return self.root / "sheets"

    def sheet_png(self, scene: str, view: str) -> Path:
        return self.sheets_dir / scene / f"{view}.png"

    @property
    def temporal_dir(self) -> Path:
        return self.root / "temporal"

    def temporal_png(self, scene: str, engine: str, mode: str) -> Path:
        return self.temporal_dir / f"{scene}__{engine}__{mode}.png"

    @property
    def phase0_dir(self) -> Path:
        return self.root / "phase0"

    @property
    def phase0_parity_json(self) -> Path:
        return self.phase0_dir / "parity.json"

    @property
    def phase0_perf_json(self) -> Path:
        return self.phase0_dir / "perf.json"

    @property
    def phase0_sheets_dir(self) -> Path:
        return self.phase0_dir / "sheets"

    # -- Phase 0 parity and perf launches (DESIGN §5.4, §7 cost): their own trees, so they never overwrite the
    #    measurement bundles and captures under <engine>/<scene>/
    def parity_bundle_dir(self, engine: str, scene: str, mode: str) -> Path:
        return self.phase0_dir / "bundles" / engine / scene / mode

    def parity_capture_dir(self, engine: str, scene: str, mode: str) -> Path:
        """<run>/phase0/captures/<engine>/<scene>/<mode>/ (the runner's --out in --parity)."""
        return self.phase0_dir / "captures" / engine / scene / mode

    def parity_capture(self, engine: str, scene: str, mode: str, view, ext: str = "png") -> Path:
        """A view's parity output: <dir>/<station>/final.<ext> or <dir>/frames/<frame:05d>.<ext> (ext png|exr)."""
        d = self.parity_capture_dir(engine, scene, mode)
        kind = _get(view, "kind")
        if kind == "station":
            return d / _get(view, "id") / f"final.{ext}"
        if kind == "state":
            return d / "frames" / f"{int(_get(view, 'capture_frame')):05d}.{ext}"
        raise ValueError(f"view kind must be 'station' or 'state', got {kind!r}")

    def phase0_sheet_png(self, scene: str, view: str, mode: str) -> Path:
        return self.phase0_sheets_dir / f"{scene}__{view}__{mode}.png"

    def perf_dir(self, phase0: bool = False) -> Path:
        """<run>/perf/ (tools.perf) or <run>/phase0/perf/ (tools.perf --phase0)."""
        return (self.phase0_dir if phase0 else self.root) / "perf"

    def perf_bundle_dir(self, engine: str, scene: str, mode: str, phase0: bool = False) -> Path:
        return self.perf_dir(phase0) / "bundles" / engine / scene / mode

    def perf_capture_dir(self, engine: str, scene: str, mode: str, round_no: int, phase0: bool = False) -> Path:
        """One timed launch: <perf dir>/captures/<engine>/<scene>/<mode>/round<k>/ (k counts from 1)."""
        return self.perf_dir(phase0) / "captures" / engine / scene / mode / f"round{int(round_no)}"

    @property
    def inspect_dir(self) -> Path:
        return self.root / "inspect"


def reference_cache_dir(key: str, cache_root="cache") -> Path:
    """cache/reference/<key>/ (sibling of runs/, shared across runs)."""
    return Path(cache_root) / "reference" / key


def _utc_id() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_latest(run_dir, root="runs") -> Path:
    """Point <root>/LATEST at run_dir (stores the dir name when it lives under root, else the absolute path)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(run_dir)
    try:
        text = run_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        text = str(run_dir.resolve())
    latest = root / "LATEST"
    tmp = root / f"LATEST.tmp{os.getpid()}"
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, latest)
    return latest


def read_latest(root="runs") -> Path | None:
    """The run dir named by <root>/LATEST, or None when missing or pointing at nothing."""
    latest = Path(root) / "LATEST"
    try:
        text = latest.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    p = Path(text)
    p = p if p.is_absolute() else Path(root) / p
    return p if p.is_dir() else None


def new_run_dir(root="runs", run_id: str | None = None, set_latest: bool = True) -> Path:
    """Create runs/<run_id> (default: UTC timestamp, suffixed -2, -3... if taken) and update LATEST."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    base = run_id or _utc_id()
    cand, n = root / base, 1
    while True:
        try:
            cand.mkdir(parents=False, exist_ok=bool(run_id) and n == 1)
            break
        except FileExistsError:
            n += 1
            cand = root / f"{base}-{n}"
    if set_latest:
        write_latest(cand, root)
    return cand
