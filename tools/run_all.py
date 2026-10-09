"""Run the whole harness in order (DESIGN §10).

    python -m tools.run_all [--run <dir>] [--scenes ...] [--engines ...] [--spp-scale f] [--phase0] [--perf]
        [--skip-references] [--settle-frames N] [--dynamic-settle-frames N] [--perf-rounds N] [--perf-frames N]
        [--perf-warmup N] [--timeout S]

Creates the run directory (``runs/<utc>`` and ``runs/LATEST``; an explicit ``--run`` is created if missing and
becomes LATEST when it lives under the runs root), then runs the steps:

1. ``spec``: validate the selected scenes and list their views (``tools.spec``);
2. ``references``: render or fetch every view's reference (``tools.reference``; skipped with
   ``--skip-references``, after which ``pairs`` uses the run's copies or complete cache entries and never renders);
3. ``parity`` (only with ``--phase0``): ``python -m tools.parity --run <dir>`` (``--dynamic-settle-frames`` and
   ``--timeout`` are passed on);
4. ``pairs``: engines x modes against the reference, metrics.json, gates.json, sheets (``tools.pairs``;
   ``--settle-frames`` and ``--dynamic-settle-frames`` are passed on);
5. ``temporal``: temporal.json and plots (``tools.temporal``);
6. ``perf`` (only with ``--perf``): the cost of the measured engines, ``python -m tools.perf --run <dir>
   [--engines <engines>]`` (every mode, probe_dynamic included), then with ``--phase0`` also the Phase 0
   performance gate ``python -m tools.perf --run <dir> --phase0`` (web vs native, interleaved); both merge into
   ``perf.json``, the gate run also writes ``phase0/perf.json``. ``--perf-rounds``, ``--perf-frames``,
   ``--perf-warmup`` become their ``--rounds``, ``--frames``, ``--warmup``;
7. ``report``: ``python -m tools.report --run <dir>``.

Each step's status and wall time go into ``run.json`` (``steps`` and ``durations.run_all``). A failed step is
recorded and the later steps still run. After the last step, ``report.md`` is rebuilt once more so it includes the
report step itself, the finish time and the overall verdict. Tools are called through their ``main(argv)`` when
importable, else as ``python -m tools.<name>`` subprocesses; a tool whose module does not exist yet is recorded as
``missing``.
Exit code 0 when every step that ran succeeded, else 1.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import io
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from . import REPO_ROOT
from .layout import RunLayout, new_run_dir, write_latest
from .runjson import host_info, update_run_json, utc_now

__all__ = ["DEFAULT_RUNS_ROOT", "STEPS", "call_tool", "main", "run_all"]

DEFAULT_RUNS_ROOT = REPO_ROOT / "runs"
STEPS = ("spec", "references", "parity", "pairs", "temporal", "perf", "report")


class _Tee(io.TextIOBase):
    """Writes to the real stdout and keeps the last lines (for a failed step's tail)."""

    def __init__(self, stream, keep: int = 40):
        self.stream, self.keep, self.lines, self._buf = stream, keep, [], ""

    def write(self, s: str) -> int:
        self.stream.write(s)
        self._buf += s
        *done, self._buf = self._buf.split("\n")
        self.lines = (self.lines + done)[-self.keep:]
        return len(s)

    def flush(self) -> None:
        self.stream.flush()

    def tail(self) -> list[str]:
        return (self.lines + ([self._buf] if self._buf else []))[-self.keep:]


def call_tool(module: str, argv: Sequence[str], echo: bool = True) -> dict:
    """Run ``module.main(argv)`` in this process when importable, else ``python -m module`` as a subprocess.

    Returns {"status": "ok"|"failed"|"missing", "returncode", "reason", "via", "tail"}; never raises.
    """
    argv = [str(a) for a in argv]
    rel = Path(*module.split(".")).with_suffix(".py")
    if importlib.util.find_spec(module) is None:
        return {"status": "missing", "returncode": None, "reason": f"{rel.as_posix()} not present", "via": None,
                "tail": []}
    try:
        mod = importlib.import_module(module)
        entry = getattr(mod, "main", None)
    except Exception as e:  # noqa: BLE001 - fall back to a subprocess (its own interpreter state)
        entry, why = None, f"{type(e).__name__}: {e}"
    else:
        why = f"{module} has no main()"
    if callable(entry):
        tee = _Tee(sys.stdout)
        try:
            with contextlib.redirect_stdout(tee):
                rc = entry(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except Exception as e:  # noqa: BLE001 - a crashing step is recorded, the run goes on
            tb = traceback.format_exc().rstrip().splitlines()
            return {"status": "failed", "returncode": None, "reason": f"{type(e).__name__}: {e}", "via": "main",
                    "tail": (tee.tail() + tb)[-40:]}
        rc = 0 if rc is None else int(rc)
        return {"status": "ok" if rc == 0 else "failed", "returncode": rc,
                "reason": None if rc == 0 else f"exit code {rc}", "via": "main", "tail": [] if rc == 0 else tee.tail()}
    try:
        p = subprocess.run([sys.executable, "-m", module, *argv], cwd=str(REPO_ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        return {"status": "failed", "returncode": None, "reason": f"could not start: {e} ({why})", "via": "subprocess",
                "tail": []}
    out = (p.stdout or "") + (p.stderr or "")
    if echo and out:
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    lines = out.splitlines()[-40:]
    return {"status": "ok" if p.returncode == 0 else "failed", "returncode": p.returncode,
            "reason": None if p.returncode == 0 else f"exit code {p.returncode}", "via": "subprocess",
            "tail": [] if p.returncode == 0 else lines}


def _step_spec(scenes, scenes_root) -> dict:
    from .spec import SpecError, discover_scenes

    try:
        files = discover_scenes(scenes, scenes_root)
    except SpecError as e:
        return {"status": "failed", "returncode": None, "reason": str(e), "via": "main", "tail": []}
    if not files:
        return {"status": "failed", "returncode": None, "reason": f"no scenes match {scenes!r}", "via": "main",
                "tail": []}
    return call_tool("tools.spec", [*map(str, files), "--check"])


def _step_references(run_dir, scenes, spp_scale, scenes_root, cache_root) -> dict:
    from .reference import run_references

    try:
        res = run_references(run_dir, scenes, spp_scale, cache_root, scenes_root=scenes_root)
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "returncode": None, "reason": f"{type(e).__name__}: {e}", "via": "main",
                "tail": traceback.format_exc().rstrip().splitlines()[-40:]}
    failed = res.get("failed") or []
    return {"status": "failed" if failed or not res.get("ok") else "ok", "returncode": None,
            "reason": "; ".join(f"{f['scene']}/{f['view']}: {f['error']}" for f in failed)[:2000] or
            (None if res.get("ok") else "no views referenced"), "via": "main", "tail": [],
            "summary": {"ok": len(res.get("ok") or []), "failed": len(failed), "rendered": res.get("rendered"),
                        "cache_hits": res.get("hits")}}


def _step_perf(base: list[str], engines: str | None, phase0: bool) -> dict:
    """tools.perf for the cost of the measured engines (every mode), then with phase0 the Phase 0 gate run."""
    parts = [("cost", call_tool("tools.perf", [*base, *(["--engines", engines] if engines else [])]))]
    if phase0:
        parts.append(("phase0", call_tool("tools.perf", [*base, "--phase0"])))
    bad = [(n, r) for n, r in parts if r["status"] != "ok"]
    status = "ok" if not bad else ("missing" if all(r["status"] == "missing" for _, r in parts) else "failed")
    return {"status": status, "returncode": max((r["returncode"] or 0 for _, r in parts), default=0) if bad else 0,
            "reason": "; ".join(f"{n}: {r['reason']}" for n, r in bad) or None, "via": parts[0][1]["via"],
            "tail": [line for _, r in bad for line in r["tail"]][-40:],
            "parts": [{"name": n, "status": r["status"], "reason": r["reason"], "returncode": r["returncode"]}
                      for n, r in parts]}


def run_all(run_dir=None, scenes: str = "all", engines: str | None = None, spp_scale: float = 1.0,
            phase0: bool = False, perf: bool = False, skip_references: bool = False, runs_root=None,
            scenes_root=None, cache_root=None, timeout: float | None = None, settle_frames: int | None = None,
            dynamic_settle_frames: int | None = None, perf_rounds: int | None = None,
            perf_frames: int | None = None, perf_warmup: int | None = None,
            log: Callable[[str], None] | None = print) -> dict:
    """Run every step (see the module docstring); returns {"run": dir, "steps": [...], "ok": bool}."""
    say = log or (lambda _m: None)
    runs_root = Path(runs_root) if runs_root is not None else DEFAULT_RUNS_ROOT
    if run_dir is None:
        run = new_run_dir(runs_root)
    else:
        run = Path(run_dir)
        run.mkdir(parents=True, exist_ok=True)
        try:
            if run.resolve().parent == runs_root.resolve():
                write_latest(run, runs_root)
        except OSError:
            pass
    layout = RunLayout(run)
    started = utc_now()
    from renderers.base import git_sha

    config = {"scenes": scenes, "engines": engines, "spp_scale": spp_scale, "phase0": phase0, "perf": perf,
              "skip_references": skip_references, "scenes_root": None if scenes_root is None else str(scenes_root),
              "cache_root": None if cache_root is None else str(cache_root), "timeout": timeout,
              "settle_frames": settle_frames, "dynamic_settle_frames": dynamic_settle_frames,
              "perf_rounds": perf_rounds, "perf_frames": perf_frames, "perf_warmup": perf_warmup}
    update_run_json(run, {"started_utc": started, "git": git_sha(), "host": host_info(),
                          "config": {"run_all": config}}, lambda d: d.__setitem__("steps", []))
    say(f"run_all: {run}")
    common = ["--run", str(run)]
    extra_scenes = ["--scenes-root", str(scenes_root)] if scenes_root is not None else []
    extra_cache = ["--cache", str(cache_root)] if cache_root is not None else []
    extra_timeout = ["--timeout", repr(float(timeout))] if timeout else []

    def opt(flag: str, value) -> list[str]:
        return [] if value is None else [flag, str(int(value))]

    plan: list[tuple[str, Callable[[], dict] | None, str | None]] = [
        ("spec", lambda: _step_spec(scenes, scenes_root), None),
        ("references", (lambda: _step_references(run, scenes, spp_scale, scenes_root, cache_root)),
         "--skip-references" if skip_references else None),
        ("parity", lambda: call_tool("tools.parity", [
            *common, *extra_scenes, *extra_cache, *extra_timeout,
            *opt("--dynamic-settle-frames", dynamic_settle_frames)]), None if phase0 else "needs --phase0"),
        ("pairs", lambda: call_tool("tools.pairs", [
            *common, "--scenes", scenes, "--spp-scale", repr(float(spp_scale)), *extra_scenes,
            *(["--engines", engines] if engines else []), *extra_cache, *extra_timeout,
            *opt("--settle-frames", settle_frames), *opt("--dynamic-settle-frames", dynamic_settle_frames),
            *(["--skip-references"] if skip_references else [])]), None),
        ("temporal", lambda: call_tool("tools.temporal", [*common, "--scenes", scenes, *extra_scenes]), None),
        ("perf", lambda: _step_perf([*common, *extra_scenes, *extra_timeout, *opt("--rounds", perf_rounds),
                                      *opt("--frames", perf_frames), *opt("--warmup", perf_warmup)],
                                     engines, phase0), None if perf else "needs --perf"),
        ("report", lambda: call_tool("tools.report", common), None),
    ]
    steps = []
    for name, fn, skip in plan:
        t0 = time.perf_counter()
        if skip:
            rec = {"name": name, "status": "skipped", "reason": skip, "seconds": 0.0}
        else:
            say(f"== {name}")
            try:
                r = fn()
            except Exception as e:  # noqa: BLE001
                r = {"status": "failed", "reason": f"{type(e).__name__}: {e}",
                     "tail": traceback.format_exc().rstrip().splitlines()[-40:]}
            rec = {"name": name, **r, "seconds": round(time.perf_counter() - t0, 4)}
            say(f"== {name}: {rec['status']}" + (f" ({rec['reason']})" if rec.get("reason") else "")
                + f" in {rec['seconds']:.1f} s")
        steps.append(rec)
        update_run_json(run, {"durations": {"run_all": {name: rec["seconds"]}}},
                        lambda d, rec=rec: d.setdefault("steps", []).append(rec))
    ok = all(s["status"] in ("ok", "skipped") for s in steps)
    update_run_json(run, {"finished_utc": utc_now(), "ok": ok})
    if any(s["name"] == "report" and s["status"] == "ok" for s in steps):
        # the report step ran before run.json had its own step record, the finish time and the verdict: rebuild
        # report.md from the final run.json (cheap: it reads JSON files only)
        try:
            from .report import write_report

            write_report(run)
        except Exception as e:  # noqa: BLE001 - the report of the step itself stays
            say(f"report: rebuild with the final run.json failed: {type(e).__name__}: {e}")
    bad = [s["name"] for s in steps if s["status"] not in ("ok", "skipped")]
    say(f"run_all: {'all steps ok' if ok else 'not ok: ' + ', '.join(bad)}; {layout.run_json}")
    return {"run": str(run), "steps": steps, "ok": ok}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.run_all", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", default=None, help="run directory (default: a new runs/<utc>)")
    ap.add_argument("--scenes", default="all", help="all | group | name | comma list (default all)")
    ap.add_argument("--engines", default=None, help="engines for pairs (default: tools.pairs' default)")
    ap.add_argument("--spp-scale", type=float, default=1.0, help="reference spp multiplier (e.g. 0.25)")
    ap.add_argument("--phase0", action="store_true", help="also run the Phase 0 parity (and perf --phase0)")
    ap.add_argument("--perf", action="store_true", help="also run tools.perf")
    ap.add_argument("--skip-references", action="store_true", help="do not render references (use existing ones)")
    ap.add_argument("--runs-root", default=None, help=f"where new runs and LATEST live (default {DEFAULT_RUNS_ROOT})")
    ap.add_argument("--scenes-root", default=None, help="scene directory (default <repo>/scenes)")
    ap.add_argument("--cache", default=None, help="reference cache root (default <repo>/cache)")
    ap.add_argument("--timeout", type=float, default=None, help="seconds per runner launch (pairs, parity, perf)")
    ap.add_argument("--settle-frames", type=int, default=None,
                    help="pairs: station frames of non-dynamic modes (default: tools.pairs' default)")
    ap.add_argument("--dynamic-settle-frames", type=int, default=None,
                    help="pairs and parity: station frames of dynamic modes (default: each tool's default)")
    ap.add_argument("--perf-rounds", type=int, default=None, help="perf: interleaved rounds (default: tools.perf's)")
    ap.add_argument("--perf-frames", type=int, default=None, help="perf: timed frames per launch")
    ap.add_argument("--perf-warmup", type=int, default=None, help="perf: warm-up frames per launch")
    args = ap.parse_args(argv)
    res = run_all(args.run, scenes=args.scenes, engines=args.engines, spp_scale=args.spp_scale, phase0=args.phase0,
                  perf=args.perf, skip_references=args.skip_references, runs_root=args.runs_root,
                  scenes_root=args.scenes_root, cache_root=args.cache, timeout=args.timeout,
                  settle_frames=args.settle_frames, dynamic_settle_frames=args.dynamic_settle_frames,
                  perf_rounds=args.perf_rounds, perf_frames=args.perf_frames, perf_warmup=args.perf_warmup)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
