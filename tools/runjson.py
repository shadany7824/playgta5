"""runs/<id>/run.json (DESIGN §3): read-modify-write helpers shared by tools.pairs, tools.temporal and tools.run_all.

run.json holds the run's config, git sha, host, engines, scenes, start/end and per-tool durations. Each tool owns
its own keys (``config.<tool>``, ``durations.<tool>``, ``launches``, ``steps``) and merges them in with
``update_run_json``, which writes atomically and never drops keys written by another tool.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
from pathlib import Path
from typing import Any, Callable

from .layout import RunLayout

__all__ = ["RUN_JSON_VERSION", "host_info", "read_run_json", "update_run_json", "utc_now"]

RUN_JSON_VERSION = 1


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def host_info() -> dict:
    return {"os": f"{platform.system()} {platform.release()}", "platform": platform.platform(),
            "python": platform.python_version(), "cpu": platform.processor() or platform.machine(),
            "cpus": os.cpu_count(), "node": platform.node()}


def read_run_json(run_dir) -> dict:
    """run.json as a dict ({} when missing or unreadable)."""
    try:
        d = json.loads(RunLayout(run_dir).run_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return d if isinstance(d, dict) else {}


def _merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def update_run_json(run_dir, updates: dict | None = None, mutate: Callable[[dict], Any] | None = None) -> dict:
    """Deep-merge ``updates`` into run.json (dicts merge, everything else replaces), then call ``mutate(doc)``
    for list edits; writes atomically and returns the document."""
    layout = RunLayout(run_dir)
    layout.ensure(layout.root)
    doc = read_run_json(run_dir)
    doc.setdefault("run_json_version", RUN_JSON_VERSION)
    doc.setdefault("run", layout.run_id)
    if updates:
        _merge(doc, updates)
    if mutate is not None:
        mutate(doc)
    path = layout.run_json
    tmp = path.with_name(f"run.json.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, allow_nan=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return doc
