"""Shared fixtures: tiny scenes from tests/data and a temporary run layout."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:  # pytest.ini sets pythonpath=.; keep direct invocations working too
    sys.path.insert(0, str(REPO))

from tools.layout import RunLayout, new_run_dir  # noqa: E402
from tools.spec import load_scene  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
TINY_SCENES = ("mini_point_plane", "mini_room", "mini_timeline", "mini_survey")


@pytest.fixture
def data_dir() -> Path:
    return DATA


@pytest.fixture
def tiny_scene():
    """Loader: tiny_scene('mini_room') -> Scene from tests/data/mini_room.json."""

    def _load(name: str):
        return load_scene(DATA / f"{name}.json")

    return _load


@pytest.fixture
def tmp_layout(tmp_path) -> RunLayout:
    """RunLayout over a fresh runs/<id> directory under tmp_path (LATEST updated there)."""
    return RunLayout(new_run_dir(tmp_path / "runs", run_id="test"))


@pytest.fixture
def run_layout(tmp_layout) -> RunLayout:
    return tmp_layout
