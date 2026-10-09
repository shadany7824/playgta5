"""The future-engine slot and the fake test engine (DESIGN §0, §4).

``FutureEngine`` ('future') is the slot a later engine fills. It is not wired: ``check_available`` raises
``NotWired('future engine not wired: see docs/FUTURE_ADAPTER.md')`` and ``tools/pairs.py`` reports that as a by-design
skip. docs/FUTURE_ADAPTER.md is the contract an engine must meet to take its place.

``FakeRenderer`` ('fake') is a real engine (bundle + subprocess runner, ``renderers/fake_runner.py``) whose images are
the Mitsuba reference perturbed by known amounts, so the tests can check that every metric recovers them:

- mode ``direct`` (kind direct): ``(1 + direct_bias) * reference direct``;
- mode ``gi`` (kind indirect, dynamic): ``direct + (1 + bias) * reference isolated + leak`` (``leak`` added to R, G
  and B, so ``Y`` rises by ``leak``, on the pixels of every ``dark`` ROI of the view, unrestricted by erosion);
- timeline frames: the indirect part answers each step with a first-order response,
  ``y(k) = a * y(k - 1) + (1 - a) * target(state(k))``, ``a = exp(-1 / tau)`` (``tau`` in frames; ``y(-1) = 0``;
  ``tau = 0`` is instantaneous), so ``|y(f + n) - post| = |delta| * a**(n + 1)`` and t90 is
  ``ceil(tau * ln 10) - 1`` frames; optional seeded noise multiplies every pixel of the indirect part by
  ``1 + noise * N(0, 1)`` (one draw per frame and pixel, from ``seed`` and the frame number);
- fault injection, each a selector (``True`` = everything, ``"scene"``, ``"scene/mode"``, ``"*/mode"`` or a list):
  ``crash`` (runner raises: exit 1 with a traceback), ``nan`` (one NaN pixel at the image centre in every capture),
  ``skip`` (runner exits 2 with ``{"skip": ...}``), ``missing`` (captures not written);
- ``last_rel_change``: the value the receipt reports as station convergence (to exercise the pairs warning).

The bundle carries these parameters, the absolute paths of each view's reference EXRs and AOVs (the run's
``reference/<scene>/<view>/``, derived from the bundle directory or given as ``capture["reference_dirs"]``) and the
ROI boxes. Parameters come from the constructor, else from ``$HARNESS_FAKE`` (a JSON object), so the CLI can
configure it: ``HARNESS_FAKE='{"bias": 0.1}' python -m tools.pairs --run R --engines fake``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tools.layout import RunLayout
from tools.spec import Scene, capture_kind

from .base import ALL_CAPABILITIES, REPO_ROOT, Engine, ModeInfo, NotWired, git_sha, write_bundle

__all__ = ["FUTURE_REASON", "FUTURE_MODES", "FAKE_MODES", "FAKE_DEFAULTS", "FutureEngine", "FakeRenderer",
           "selector_matches"]

FUTURE_REASON = "future engine not wired: see docs/FUTURE_ADAPTER.md"

# The slot's mode table (docs/FUTURE_ADAPTER.md §1): one direct mode plus the engine's indirect modes, each with its
# counterpart in the system (three.js r186: direct, probe, probe_dynamic). The engine-side columns are filled when
# an engine is wired; until then the names are placeholders.
FUTURE_MODES: dict[str, ModeInfo] = {
    "direct": ModeInfo("direct", "direct", False, "(to fill) the engine's direct-only lighting; system: direct",
                       "Direct lighting only."),
    "indirect": ModeInfo("indirect", "indirect", False, "(to fill) the engine's static GI; system: probe",
                         "Static indirect lighting, rebuilt after each timeline step."),
    "indirect_dynamic": ModeInfo("indirect_dynamic", "indirect", True,
                                 "(to fill) the engine's dynamic GI; system: probe_dynamic",
                                 "Dynamic indirect lighting, updated every frame."),
}

FAKE_MODES: dict[str, ModeInfo] = {
    "direct": ModeInfo("direct", "direct", False, "(1 + direct_bias) * Mitsuba reference direct",
                       "Reference direct image (test engine)."),
    "gi": ModeInfo("gi", "indirect", True,
                   "direct + (1 + bias) * reference isolated + leak on dark ROIs; first-order response tau after "
                   "each timeline step; optional seeded noise",
                   "Reference GI with injected bias, leak, lag and noise (test engine)."),
}

FAKE_DEFAULTS = {"bias": 0.0, "direct_bias": 0.0, "leak": 0.0, "tau": 0.0, "noise": 0.0, "seed": 1,
                 "crash": False, "nan": False, "skip": False, "missing": False, "last_rel_change": 0.0}
_SELECTORS = ("crash", "nan", "skip", "missing")


def selector_matches(sel, scene: str, mode: str) -> bool:
    """Fault selector: True/False, 'scene', 'scene/mode', '*/mode', '*', or a list of those."""
    if isinstance(sel, bool) or sel is None:
        return bool(sel)
    if isinstance(sel, (list, tuple)):
        return any(selector_matches(s, scene, mode) for s in sel)
    s = str(sel)
    if s in ("*", "all"):
        return True
    if "/" in s:
        sc, md = s.split("/", 1)
        return sc in ("*", scene) and md in ("*", mode)
    return s == scene


class FutureEngine(Engine):
    """The future engine's slot (not wired; contract in docs/FUTURE_ADAPTER.md)."""

    name = "future"

    def modes(self) -> dict[str, ModeInfo]:
        return dict(FUTURE_MODES)

    def capabilities(self) -> set[str]:
        return set()  # declared by the engine once it is wired (DESIGN §4.4)

    def check_available(self) -> None:
        raise NotWired(FUTURE_REASON)

    def build_bundle(self, scene, mode, views, capture, out_dir: Path) -> Path:
        raise NotWired(FUTURE_REASON)

    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]:
        raise NotWired(FUTURE_REASON)

    def version(self) -> str:
        return "not wired"

    def known_limits(self) -> list[str]:
        return []  # filled in docs/FUTURE_ADAPTER.md §7 once an engine is wired


class FakeRenderer(Engine):
    """Test engine: the reference perturbed by known amounts (see the module docstring)."""

    name = "fake"
    runner_rel = "renderers/fake_runner.py"

    def __init__(self, name: str | None = None, **params):
        if name:
            self.name = name
        if not params:
            env = os.environ.get("HARNESS_FAKE")
            if env:
                params = json.loads(env)
                if not isinstance(params, dict):
                    raise ValueError("$HARNESS_FAKE must be a JSON object")
        unknown = set(params) - set(FAKE_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown fake engine parameters {sorted(unknown)}; known: {sorted(FAKE_DEFAULTS)}")
        self.params = {**FAKE_DEFAULTS, **params}
        if float(self.params["tau"]) < 0 or float(self.params["noise"]) < 0:
            raise ValueError("tau and noise must be >= 0")

    def modes(self) -> dict[str, ModeInfo]:
        return dict(FAKE_MODES)

    def capabilities(self) -> set[str]:
        return set(ALL_CAPABILITIES)

    def check_available(self) -> None:
        if not (REPO_ROOT / self.runner_rel).is_file():
            raise NotWired(f"{self.runner_rel} not present")

    def version(self) -> str:
        return f"fake engine (perturbed Mitsuba reference) @ {git_sha()}"

    def known_limits(self) -> list[str]:
        return ["Test engine: its images are the Mitsuba reference perturbed by known amounts, not a renderer."]

    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]:
        return [sys.executable, str(REPO_ROOT / self.runner_rel), "--bundle", str(bundle_json), "--out",
                str(out_dir), *[str(e) for e in extra]]

    # -- bundle
    def _reference_dirs(self, scene: Scene, views: list, capture: dict, out_dir: Path) -> dict[str, Path]:
        given = capture.get("reference_dirs") or {}
        if given:
            return {v.id: Path(given[v.id]) for v in views}
        run = Path(out_dir).resolve().parents[3]  # <run>/<engine>/<scene>/bundles/<mode>
        layout = RunLayout(run)
        return {v.id: layout.reference_dir(scene.name, v.id) for v in views}

    def build_bundle(self, scene: Scene, mode: str, views: list, capture: dict, out_dir: Path) -> Path:
        if mode not in FAKE_MODES:
            raise ValueError(f"unknown fake mode {mode!r}; modes: {list(FAKE_MODES)}")
        self.check_supports(scene)
        capture = dict(capture or {})
        kind = capture_kind(scene)
        refs = self._reference_dirs(scene, views, capture, out_dir)
        files = ("full.exr", "direct.exr", "depth.exr", "normal.exr", "position.exr")
        vlist = []
        for v in views:
            d = refs[v.id].resolve()
            missing = [f for f in files if not (d / f).is_file()]
            if missing:
                raise FileNotFoundError(f"fake engine needs the reference of {scene.name}/{v.id}: "
                                        f"{', '.join(missing)} missing in {d}")
            vlist.append({"id": v.id, "kind": v.kind, "station": v.station.name,
                          "frames": list(v.frame_range) if v.frame_range else None,
                          "capture_frame": v.capture_frame,
                          "reference": {f[:-4]: str(d / f) for f in files}})
        if kind == "stations":
            settle = int(capture.get("settle_frames", 1))
            stations = capture.get("stations") or [{"name": v.id, "camera": v.station.name} for v in views]
            cap = {"stations": [{"name": s["name"], "camera": s.get("camera", s["name"]),
                                 "settle_frames": int(s.get("settle_frames", settle))} for s in stations]}
        else:
            tl = scene.timeline
            block = dict(capture.get("timeline", {}))
            frames = block.get("frames", capture.get("frames"))
            frames = sorted({int(f) for f in (range(tl.end_frame + 1) if frames is None else frames)})
            cap = {"timeline": {"camera": block.get("camera", tl.station), "end_frame": int(tl.end_frame),
                                "frames": frames}}
        rois = [{"name": r.name, "role": r.role, "min": r.box_min.tolist(), "max": r.box_max.tolist(),
                 "normal": None if r.normal is None else r.normal.tolist(), "min_cos": r.min_cos,
                 "views": r.views} for r in scene.rois]
        info = FAKE_MODES[mode]
        fps = scene.timeline.fps if scene.timeline is not None else 60
        bundle = {
            "bundle_version": 1, "engine": "fake", "mode": mode, "scene": scene.name, "kind": kind,
            "image": {"width": int(scene.width), "height": int(scene.height)},
            "fps": int(fps) if float(fps).is_integer() else float(fps), "seed": int(self.params["seed"]),
            "capture": cap,
            "measure": {"timing": True, "warmup_frames": 0, "parity": False},
            "arrays": {},
            "engine_data": {
                "engine_name": self.name, "mode_kind": info.kind, "dynamic": info.dynamic,
                "perturbation": {k: v for k, v in self.params.items() if k not in _SELECTORS},
                "faults": {k: selector_matches(self.params[k], scene.name, mode) for k in _SELECTORS},
                "views": vlist, "rois": rois,
                "timeline": None if scene.timeline is None else {
                    "fps": scene.timeline.fps, "end_frame": int(scene.timeline.end_frame),
                    "steps": [int(f) for f, _ in scene.timeline.steps]},
            },
        }
        return write_bundle(Path(out_dir), bundle, {})
