"""Engine registry with lazy imports (DESIGN §4.1). A missing engine module yields an engine whose
check_available() raises NotWired('module not present') instead of crashing the import."""

from __future__ import annotations

import importlib
from pathlib import Path

from .base import Engine, ModeInfo, NotWired, Unsupported

__all__ = ["get_engine", "list_engines", "ENGINES", "Engine", "ModeInfo", "NotWired", "Unsupported"]

# name -> (module, class)
ENGINES: dict[str, tuple[str, str]] = {
    "threejs-native": ("renderers.threejs", "ThreeJsNative"),  # the measured system (DESIGN §0)
    "threejs-web": ("renderers.threejs", "ThreeJsWeb"),  # the original WebGL build (Phase 0 parity / perf baseline)
    "future": ("renderers.future", "FutureEngine"),  # the slot: NotWired until wired (docs/FUTURE_ADAPTER.md)
    "fake": ("renderers.future", "FakeRenderer"),  # test engine: perturbed reference (renderers/fake_runner.py)
}


class _UnavailableEngine(Engine):
    """Stand-in for an engine whose module or class cannot be imported."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason

    def modes(self) -> dict[str, ModeInfo]:
        return {}

    def capabilities(self) -> set[str]:
        return set()

    def check_available(self) -> None:
        raise NotWired(self.reason)

    def build_bundle(self, scene, mode, views, capture, out_dir: Path) -> Path:
        raise NotWired(self.reason)

    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]:
        raise NotWired(self.reason)

    def version(self) -> str:
        return "not available"


def list_engines() -> list[str]:
    return list(ENGINES)


def get_engine(name: str) -> Engine:
    """Instantiate a registered engine. Unknown names raise ValueError; import problems give an engine whose
    check_available() raises NotWired ('module not present' when the module file does not exist)."""
    if name not in ENGINES:
        raise ValueError(f"unknown engine {name!r}; known: {', '.join(ENGINES)}")
    mod_name, cls_name = ENGINES[name]
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        if e.name == mod_name:
            return _UnavailableEngine(name, "module not present")
        return _UnavailableEngine(name, f"import of {mod_name} failed: {e}")
    except Exception as e:  # noqa: BLE001 - reported as the skip reason
        return _UnavailableEngine(name, f"import of {mod_name} failed: {type(e).__name__}: {e}")
    cls = getattr(mod, cls_name, None)
    if cls is None:
        return _UnavailableEngine(name, f"{mod_name} has no {cls_name}")
    eng = cls()
    if not getattr(eng, "name", None):
        eng.name = name
    return eng
