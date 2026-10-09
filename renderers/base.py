"""Engine adapter interface, runner launch and capability derivation (DESIGN §4)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent

__all__ = ["NotWired", "Unsupported", "ModeInfo", "Engine", "LaunchResult", "launch", "needs_capabilities",
           "ALL_CAPABILITIES", "write_bundle", "load_bundle", "git_sha", "REPO_ROOT", "LOG_TAIL_LINES"]

ALL_CAPABILITIES = frozenset({"light:point", "light:directional", "light:rect", "light:environment", "shape:mesh",
                              "timeline", "op:set_light", "op:set_transform", "op:set_material"})
LOG_TAIL_LINES = 40


class NotWired(Exception):
    """The engine cannot run here (missing module, runtime, adapter...). ``.reason`` is the skip reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Unsupported(Exception):
    """The scene needs a capability the engine lacks (by-design skip). ``.reason`` names it."""

    def __init__(self, reason: str, missing: Sequence[str] = ()):
        super().__init__(reason)
        self.reason = reason
        self.missing = sorted(missing)


@dataclass(frozen=True)
class ModeInfo:
    name: str
    kind: str  # "direct" | "indirect"
    dynamic: bool
    counterpart: str  # what the mode is in the engine's own terms
    description: str


def needs_capabilities(scene) -> set[str]:
    """Capabilities (DESIGN §4.4) a scene needs: light types, mesh shapes, timeline and the ops it uses."""
    need = {f"light:{lt.type}" for lt in scene.lights}
    if any(o.shape.get("type") == "mesh" for o in scene.objects):
        need.add("shape:mesh")
    if scene.timeline is not None:
        need.add("timeline")
        need |= {f"op:{a['op']}" for _, acts in scene.timeline.steps for a in acts}
    return need


class Engine(ABC):
    """One engine = one adapter (bundle builder, this interpreter) + one runner (subprocess)."""

    name: str = ""

    @abstractmethod
    def modes(self) -> dict[str, ModeInfo]:
        """Modes by name; exactly one has kind 'direct'."""

    @abstractmethod
    def capabilities(self) -> set[str]:
        ...

    @abstractmethod
    def check_available(self) -> None:
        """Raise NotWired(reason) when the engine cannot run on this machine."""

    @abstractmethod
    def build_bundle(self, scene, mode: str, views: list, capture: dict, out_dir: Path) -> Path:
        """Write <out_dir>/bundle.json + arrays/*.bin; return the bundle.json path."""

    @abstractmethod
    def runner_argv(self, bundle_json: Path, out_dir: Path, extra: list[str]) -> list[str]:
        ...

    @abstractmethod
    def version(self) -> str:
        ...

    def runner_env(self) -> dict[str, str]:
        """Extra environment variables for the runner subprocess."""
        return {}

    def known_limits(self) -> list[str]:
        """Known, by-design limits of the engine's lighting (one sentence each), for the report. Default: none."""
        return []

    def direct_mode(self) -> str:
        direct = [m for m, info in self.modes().items() if info.kind == "direct"]
        if len(direct) != 1:
            raise ValueError(f"engine {self.name!r} must have exactly one direct mode, has {direct}")
        return direct[0]

    def missing_capabilities(self, scene) -> set[str]:
        return needs_capabilities(scene) - set(self.capabilities())

    def check_supports(self, scene) -> None:
        """Raise Unsupported naming every capability the scene needs and the engine lacks."""
        missing = self.missing_capabilities(scene)
        if missing:
            raise Unsupported(f"{self.name} lacks {', '.join(sorted(missing))}", missing)


# ------------------------------------------------------------------------------------------------ bundles

def write_bundle(out_dir: Path, bundle: dict, arrays: dict[str, np.ndarray]) -> Path:
    """Write arrays as little-endian C-order .bin under out_dir/arrays/, fill bundle['arrays'], write bundle.json."""
    out_dir = Path(out_dir)
    adir = out_dir / "arrays"
    adir.mkdir(parents=True, exist_ok=True)
    for stale in adir.glob("*.bin"):
        if stale.stem not in arrays:
            stale.unlink()
    table = {}
    for name, arr in arrays.items():
        a = np.ascontiguousarray(arr)
        a = a.astype(a.dtype.newbyteorder("<"), copy=False)
        rel = f"arrays/{name}.bin"
        (out_dir / rel).write_bytes(a.tobytes())
        table[name] = {"file": rel, "dtype": a.dtype.name, "shape": list(a.shape)}
    bundle = dict(bundle)
    bundle["arrays"] = table
    path = out_dir / "bundle.json"
    tmp = out_dir / f"bundle.json.tmp{os.getpid()}"
    tmp.write_text(json.dumps(bundle, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_bundle(bundle_json) -> tuple[dict, dict[str, np.ndarray]]:
    """Read bundle.json and every array it lists (numpy arrays in native byte order)."""
    bundle_json = Path(bundle_json)
    bundle = json.loads(bundle_json.read_text(encoding="utf-8"))
    arrays = {}
    for name, spec in bundle.get("arrays", {}).items():
        dt = np.dtype(spec["dtype"]).newbyteorder("<")
        raw = (bundle_json.parent / spec["file"]).read_bytes()
        arrays[name] = np.frombuffer(raw, dtype=dt).reshape(spec["shape"]).astype(dt.newbyteorder("="))
    return bundle, arrays


# ------------------------------------------------------------------------------------------------ launch

@dataclass
class LaunchResult:
    status: str  # "ok" | "skipped" | "failed"
    reason: str
    seconds: float
    log_tail: list[str] = field(default_factory=list)  # last LOG_TAIL_LINES lines of runner.log
    returncode: int | None = None
    argv: list[str] = field(default_factory=list)
    log: Path | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def by_design(self) -> bool:
        return self.status == "skipped"


def _parse_skip(lines: Sequence[str]) -> str | None:
    for line in reversed(lines):
        s = line.strip()
        if s.startswith("{") and '"skip"' in s:
            try:
                d = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and "skip" in d:
                return str(d["skip"])
    return None


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)  # runner started in its own session
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def launch(engine: Engine, bundle_json, out_dir, timeout_s: float, extra: Sequence[str] = (),
           echo: bool = False) -> LaunchResult:
    """Run the engine's runner on a bundle. stdout+stderr go to <out_dir>/runner.log (and to this process's
    stdout when echo=True). Exit 0 -> ok, 2 -> skipped (reason from the runner's {"skip": ...} line),
    anything else / timeout / launch error -> failed. Never raises on runner failure."""
    t0 = time.perf_counter()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "runner.log"
    try:
        argv = [str(a) for a in engine.runner_argv(Path(bundle_json), out_dir, list(extra))]
    except NotWired as e:
        return LaunchResult("skipped", e.reason, time.perf_counter() - t0, [], None, [], None)
    except Exception as e:  # noqa: BLE001 - reported, never raised
        return LaunchResult("failed", f"runner_argv: {type(e).__name__}: {e}", time.perf_counter() - t0)
    env = dict(os.environ)
    env.update(engine.runner_env())
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    tail: deque[str] = deque(maxlen=max(LOG_TAIL_LINES, 200))
    with open(log_path, "w", encoding="utf-8", errors="replace", newline="\n") as log:
        log.write("$ " + " ".join(argv) + "\n")
        log.flush()
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    cwd=str(REPO_ROOT), env=env, **kw)
        except OSError as e:
            msg = f"could not start runner: {e}"
            log.write(msg + "\n")
            return LaunchResult("failed", msg, time.perf_counter() - t0, [msg], None, argv, log_path)

        def pump():
            try:
                for raw in iter(proc.stdout.readline, b""):
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    tail.append(line)
                    log.write(line + "\n")
                    log.flush()
                    if echo:
                        print(line, flush=True)
            except (ValueError, OSError):  # log closed after a timeout while a grandchild held the pipe
                pass

        th = threading.Thread(target=pump, daemon=True)
        th.start()
        timed_out = False
        try:
            rc = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                rc = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                rc = None
        th.join(timeout=10)
        seconds = time.perf_counter() - t0
        if timed_out:
            status, reason = "failed", f"timeout after {timeout_s:g} s"
        elif rc == 0:
            status, reason = "ok", ""
        elif rc == 2:
            status, reason = "skipped", _parse_skip(list(tail)) or "runner exited 2 without a skip reason"
        else:
            last = next((ln for ln in reversed(tail) if ln.strip()), "")
            status, reason = "failed", f"exit code {rc}" + (f": {last.strip()[:300]}" if last else "")
        log.write(f"# {status}: exit code {rc} after {seconds:.2f} s{' (timeout)' if timed_out else ''}\n")
    return LaunchResult(status, reason, seconds, list(tail)[-LOG_TAIL_LINES:], rc, argv, log_path)


def git_sha(short: bool = True) -> str:
    """Current git commit of the repo (with '+dirty' when the work tree has changes), or 'unknown'."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short" if short else "--verify", "HEAD"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if not sha:
            return "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=str(REPO_ROOT),
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"
