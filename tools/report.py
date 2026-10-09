"""Run report (DESIGN §9, §10): ``runs/<id>/report.md`` built from the run's JSON files only.

    python -m tools.report --run <dir>|LATEST [--out FILE] [--print]

Inputs, any of which may be missing (the report then says so in one line): ``run.json``, ``metrics.json``,
``gates.json``, ``temporal.json``, ``perf.json``, ``phase0/parity.json``, ``phase0/perf.json``. Images are only
linked, never read. An engine's known limits come from its ``metrics.json`` block (written by ``tools.pairs`` from
``Engine.known_limits()``); when the block lacks them, the registry engine's ``known_limits()`` is used if the method
exists.

Sections: run header (date, git sha, host, devices per engine, whether timings are representative); engines and
modes (mode table with counterparts, skip reasons, known limits); Phase 0 (parity per view and mode, performance
gate); calibration gates per subject (by-design skips listed apart as known limits); one table per scene and view
(rows engine/mode, a column per ROI; ``appearance`` scenes show only FLIP); temporal results; cost; real failures
(status failed, never by-design skips) with their reasons; warnings; durations.

Number formats: bias and energy as signed percentages, every other number to 3 significant digits. A bias, energy or
leak within ``NOISE_K`` reference standard errors of the reference is marked ``†`` (below the reference noise
floor). Metrics are never combined into one number.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .layout import RunLayout, read_latest

__all__ = ["DASH", "FLOOR_MARK", "INPUTS", "NOISE_K", "build_report", "fmt_bytes", "fmt_pct", "fmt_sig",
           "load_inputs", "main", "resolve_run", "write_report"]

NOISE_K = 2.0  # a value within NOISE_K reference standard errors is "below the reference noise floor"
FLOOR_MARK = "†"
DASH = "–"
# key -> (RunLayout attribute, file name as printed)
INPUTS = {"run": ("run_json", "run.json"), "metrics": ("metrics_json", "metrics.json"),
          "gates": ("gates_json", "gates.json"), "temporal": ("temporal_json", "temporal.json"),
          "perf": ("perf_json", "perf.json"), "parity": ("phase0_parity_json", "phase0/parity.json"),
          "phase0_perf": ("phase0_perf_json", "phase0/perf.json")}
_GROUP_ORDER = {"calibration": 0, "targeted": 1, "realworld": 2}
_AFTERGLOW_KEYS = ("0.1", "0.25", "0.5", "1.0")  # DESIGN §7: r at 0.1, 0.25, 0.5 and 1.0 s
_DEVICE_KEYS = ("adapter", "backend", "adapter_type", "browser")


# ------------------------------------------------------------------------------------------------ formatting

def _f(x) -> float | None:
    if isinstance(x, bool):
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def fmt_sig(x, digits: int = 3) -> str:
    """``x`` to ``digits`` significant digits: 0.0990, 1.00, 12.3, 1230, 1.23e-05 (DASH when undefined)."""
    v = _f(x)
    if v is None:
        return DASH
    if v == 0:
        return "0"
    a = abs(v)
    if a < 1e-3 or a >= 1e7:
        return f"{v:.{digits - 1}e}"
    if a >= 10 ** digits:  # no exponent for large values: round to the significant digits instead
        return str(int(round(v, digits - 1 - int(math.floor(math.log10(a))))))
    s = f"{v:#.{digits}g}"
    return s[:-1] if s.endswith(".") else s


def fmt_pct(x, signed: bool = True, digits: int = 3) -> str:
    """Fraction as a percentage to ``digits`` significant digits, signed by default: +10.0%, -0.123%."""
    v = _f(x)
    if v is None:
        return DASH
    if v == 0:
        return "0%"
    s = fmt_sig(v * 100.0, digits)
    return (("+" + s) if signed and v > 0 else s) + "%"


def fmt_bytes(n) -> str:
    v = _f(n)
    if v is None:
        return DASH
    for unit, size in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if abs(v) >= size:
            return f"{fmt_sig(v / size)} {unit}"
    return f"{int(v)} B"


def fmt_seconds(s) -> str:
    v = _f(s)
    if v is None:
        return DASH
    if v < 60:
        return f"{fmt_sig(v)} s"
    m, sec = divmod(int(round(v)), 60)
    if m < 60:
        return f"{m} min {sec:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


def _lsb(x) -> str:
    """8-bit differences: whole LSB counts as integers (p99.9 and max are observed values), else 3 digits."""
    v = _f(x)
    return str(int(v)) if v is not None and v.is_integer() else fmt_sig(v)


def _cell(x) -> str:
    s = DASH if x is None or x == "" else str(x)
    return s.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _table(headers: Sequence[str], rows: Iterable[Sequence], right: Iterable[int] = ()) -> list[str]:
    right = set(right)
    out = ["| " + " | ".join(_cell(h) if h else " " for h in headers) + " |",
           "|" + "|".join("---:" if i in right else "---" for i in range(len(headers))) + "|"]
    for r in rows:
        cells = list(r) + [None] * (len(headers) - len(r))
        out.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return out


def _link(path: str | None, text: str | None = None) -> str:
    if not path:
        return DASH
    p = str(path).replace("\\", "/")
    return f"[{text or p}]({p.replace(' ', '%20')})"


def _short(text, n: int = 300) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _below_floor(value, noise, ref_value=0.0) -> bool:
    v, n, r = _f(value), _f(noise), _f(ref_value)
    return v is not None and n is not None and r is not None and abs(v - r) <= NOISE_K * n


def _dicts(x) -> list[dict]:
    return [d for d in (x or []) if isinstance(d, dict)] if isinstance(x, list) else []


def _flat(d: Mapping, prefix: str = "", depth: int = 2) -> dict:
    """{'a.b': scalar} for nested dicts (lists of scalars joined), ``depth`` levels deep."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, Mapping) and depth > 1:
            out.update(_flat(v, key + ".", depth - 1))
        elif isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
            out[key] = ", ".join(_scalar(x) for x in v)
        elif not isinstance(v, (Mapping, list)):
            out[key] = v
    return out


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return fmt_sig(v) if isinstance(v, float) else str(v)
    return DASH if v is None else str(v)


def _pick(d: Mapping | None, *keys, default=None):
    """First present, non-None value among ``keys`` (dotted keys reach into nested dicts)."""
    if not isinstance(d, Mapping):
        return default
    for k in keys:
        cur: Any = d
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, Mapping) else None
            if cur is None:
                break
        if cur is not None:
            return cur
    return default


def _verdict(passed=None, status: str | None = None) -> str:
    if status == "skipped":
        return "skipped (by design)"
    if status == "not_applicable":
        return "n/a"
    return {True: "PASS", False: "FAIL"}.get(passed if isinstance(passed, bool) else None, "n/a")


def _row_passed(row: Mapping) -> bool | None:
    """A gate verdict of a row: ``gate.passed`` (tools.parity), else a flat ``passed``-like key, else a
    passed/failed status. A run status such as 'ok' is not a verdict."""
    for k in ("gate.passed", "passed", "pass", "parity_gate", "gate_passed"):
        p = _pick(row, k)
        if isinstance(p, bool):
            return p
    st = row.get("status")
    if st in ("passed", "pass"):
        return True
    if st in ("failed", "fail") and not isinstance(row.get("gate"), Mapping):
        return False
    return None


# ------------------------------------------------------------------------------------------------ inputs

def resolve_run(run: str | Path | None, runs_root: str | Path | None = None) -> Path:
    """A run directory from a path, or ``LATEST`` / None (the run named by <runs_root>/LATEST)."""
    from . import REPO_ROOT

    root = Path(runs_root) if runs_root is not None else REPO_ROOT / "runs"
    if run is None or str(run) == "LATEST":
        latest = read_latest(root)
        if latest is None:
            raise FileNotFoundError(f"{root / 'LATEST'} does not name an existing run directory")
        return latest
    return Path(run)


def load_inputs(run_dir) -> tuple[dict[str, Any], dict[str, str]]:
    """({key: parsed JSON or None}, {key: 'missing' | 'unreadable: ...'}) for every INPUTS file."""
    layout = RunLayout(run_dir)
    docs, problems = {}, {}
    for key, (attr, _name) in INPUTS.items():
        path = getattr(layout, attr)
        docs[key] = None
        if not path.is_file():
            problems[key] = "missing"
            continue
        try:
            docs[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            problems[key] = f"unreadable ({type(e).__name__}: {e})"
    return docs, problems


def _missing_line(problems: Mapping[str, str], key: str, what: str) -> list[str]:
    return [f"_{INPUTS[key][1]} {problems.get(key, 'missing')}: {what}._", ""]


class _Ctx:
    """Shared state of one report build: inputs, engine/mode order, collected failures and warnings."""

    def __init__(self, layout: RunLayout, docs: dict, problems: dict):
        self.layout, self.docs, self.problems = layout, docs, problems
        self.run = docs["run"] if isinstance(docs["run"], dict) else {}
        self.metrics = docs["metrics"] if isinstance(docs["metrics"], dict) else {}
        self.gates = docs["gates"] if isinstance(docs["gates"], dict) else {}
        self.temporal = docs["temporal"] if isinstance(docs["temporal"], dict) else {}
        self.perf = docs["perf"] if isinstance(docs["perf"], dict) else {}
        self.failures: list[tuple[str, str, str]] = []  # (where, what, reason)
        self.warnings: list[tuple[str, str]] = []  # (where, text)
        eng = self.metrics.get("engines") if isinstance(self.metrics.get("engines"), dict) else {}
        self.engines: dict[str, dict] = {k: (v if isinstance(v, dict) else {}) for k, v in eng.items()}
        for name in self.run.get("engines") or []:
            if isinstance(name, str):
                self.engines.setdefault(name, {})
        self.results = _dicts(self.metrics.get("results"))
        for r in self.results:
            if isinstance(r.get("engine"), str):
                self.engines.setdefault(r["engine"], {})

    def engine_index(self, name) -> int:
        names = list(self.engines)
        return names.index(name) if name in names else len(names)

    def mode_index(self, engine, mode) -> int:
        modes = list((self.engines.get(engine) or {}).get("modes") or {})
        return modes.index(mode) if mode in modes else len(modes)

    def row_key(self, r: Mapping) -> tuple:
        return (self.engine_index(r.get("engine")), str(r.get("engine")), self.mode_index(r.get("engine"),
                r.get("mode")), str(r.get("mode")))

    def fail(self, where: str, what: str, reason) -> None:
        self.failures.append((where, what, _short(reason if reason not in (None, "") else "no reason recorded", 400)))

    def warn(self, where: str, text) -> None:
        self.warnings.append((where, _short(text, 300)))


def _registry_engine(name: str):
    try:
        from renderers import get_engine

        return get_engine(name)
    except Exception:  # noqa: BLE001 - unknown or broken engines simply contribute nothing
        return None


# ------------------------------------------------------------------------------------------------ header

def _devices(ctx: _Ctx) -> dict[str, list[dict]]:
    """{engine: [device dicts]} from run.json launches, perf.json and phase0 files (deduplicated)."""
    out: dict[str, list[dict]] = defaultdict(list)

    def add(engine, dev):
        if not engine:
            return
        if isinstance(dev, str):
            dev = {"adapter": dev}
        if not isinstance(dev, Mapping):
            return
        d = {k: dev.get(k) for k in _DEVICE_KEYS if dev.get(k) not in (None, "")}
        if dev.get("software_rendering") or dev.get("software"):
            d["software_rendering"] = True
        if not d:
            return
        same = next((x for x in out[engine] if x.get("adapter") == d.get("adapter")), None)
        if same is None:
            out[engine].append(d)
        else:  # the same adapter seen by several tools: merge what each recorded
            for k, v in d.items():
                same.setdefault(k, v)

    for x in _dicts(ctx.run.get("launches")):
        add(x.get("engine"), x.get("device"))
    for key, val in (ctx.run.get("devices") or {}).items() if isinstance(ctx.run.get("devices"), dict) else ():
        add(key, val)
    for doc in (ctx.perf, ctx.docs.get("phase0_perf"), ctx.docs.get("parity")):
        if not isinstance(doc, dict):
            continue
        devs = doc.get("devices")
        if isinstance(devs, dict):
            for eng, dev in devs.items():
                add(eng, dev)
        for e in _dicts(_pick(doc, "entries", "results", "rows")):
            add(e.get("engine"), e.get("device") or e.get("adapter"))
    return out


def _device_text(d: Mapping) -> str:
    extra = [str(d[k]) for k in ("adapter_type", "backend") if d.get(k)]
    if d.get("browser"):
        extra.append(str(d["browser"]))
    if d.get("software_rendering"):
        extra.append("software rendering")
    return f"{d.get('adapter') or 'unknown adapter'}" + (f" ({', '.join(extra)})" if extra else "")


def _representative(ctx: _Ctx, devices: Mapping[str, list[dict]]) -> str:
    for key, doc in (("perf.json", ctx.perf), ("phase0/perf.json", ctx.docs.get("phase0_perf")),
                     ("phase0/parity.json", ctx.docs.get("parity"))):
        if isinstance(doc, dict) and isinstance(doc.get("representative"), bool):
            why = doc.get("reason") or doc.get("representative_reason")
            return ("yes" if doc["representative"] else "no") + (f": {why}" if why else "") + f" ({key})"
    soft = sorted({_device_text(d) for devs in devices.values() for d in devs
                   if str(d.get("adapter_type", "")).upper() == "CPU" or d.get("software_rendering")})
    if soft:
        return "no: software rasterizer (" + "; ".join(soft) + "); inferred from the recorded devices, no perf.json"
    return "unknown: no perf.json, and no device marks a software rasterizer"


def _header(ctx: _Ctx) -> list[str]:
    run = ctx.run
    rid = run.get("run") or ctx.metrics.get("run") or ctx.layout.run_id
    out = [f"# Lighting comparison report: {rid}", "",
           "Built by `tools/report.py` from the run's JSON files only. Every metric is reported on its own; "
           "nothing is folded into a single number.", ""]
    missing = [f"`{INPUTS[k][1]}` {v}" for k, v in ctx.problems.items()]
    if missing:
        out += ["Inputs not available: " + "; ".join(missing) + ".", ""]
    host = run.get("host") if isinstance(run.get("host"), dict) else {}
    host_txt = ", ".join(x for x in (host.get("os"), f"Python {host['python']}" if host.get("python") else None,
                                    host.get("cpu"), f"{host['cpus']} CPUs" if host.get("cpus") else None,
                                    f"node {host['node']}" if host.get("node") else None) if x) or DASH
    started = run.get("started_utc") or _pick(run, "durations.pairs.started_utc") or ctx.metrics.get("created_utc")
    finished = run.get("finished_utc")
    devices = _devices(ctx)
    rows = [("Run directory", f"`{ctx.layout.root.as_posix()}`"),
            ("Date (UTC)", f"{started or DASH}" + (f" to {finished}" if finished else
                                                   " (no finish time recorded: run in progress or interrupted)")),
            ("Git", f"`{run.get('git') or ctx.metrics.get('git') or 'unknown'}`"),
            ("Host", host_txt)]
    if devices:
        for eng in sorted(devices, key=ctx.engine_index):
            rows.append((f"Device: {eng}", "; ".join(_device_text(d) for d in devices[eng])))
    else:
        rows.append(("Devices", "not recorded (no device in run.json launches, perf.json or phase0 files)"))
    rows.append(("Timings representative", _representative(ctx, devices)))
    cfg = run.get("config") if isinstance(run.get("config"), dict) else {}
    ra = cfg.get("run_all") if isinstance(cfg.get("run_all"), dict) else {}
    pairs = cfg.get("pairs") if isinstance(cfg.get("pairs"), dict) else {}
    perf_cfg = next((cfg[k] for k in ("perf", "perf_phase0") if isinstance(cfg.get(k), dict)), {})
    conf = []
    for k, src in (("scenes", ra or pairs), ("engines", pairs or ra), ("spp_scale", ra or pairs), ("phase0", ra),
                   ("perf", ra), ("settle_frames", pairs), ("dynamic_settle_frames", pairs)):
        if src.get(k) not in (None, ""):
            v = src[k]
            conf.append(f"{k} {', '.join(map(str, v)) if isinstance(v, list) else _scalar(v)}")
    if perf_cfg.get("rounds") is not None:  # the last tools.perf run's settings
        conf.append(f"perf {perf_cfg['rounds']} rounds x {perf_cfg.get('frames')} frames after "
                    f"{perf_cfg.get('warmup')} warm-up")
    if conf:
        rows.append(("Config", "; ".join(conf)))
    if "ok" in run:
        rows.append(("run_all", "all steps ok" if run["ok"] else "some steps failed (see Failures)"))
    out += _table(["", ""], rows) + [""]
    out += ["Interactive viewer: `python -m tools.inspector --run " + ctx.layout.root.as_posix() + "` "
            "(Windows: `Inspect.cmd`).", ""]
    return out


# ------------------------------------------------------------------------------------------------ engines

def _engines(ctx: _Ctx) -> list[str]:
    out = ["## Engines and modes", ""]
    if not ctx.engines:
        return out + _missing_line(ctx.problems, "metrics", "no engines recorded")
    try:
        from renderers.base import ALL_CAPABILITIES
    except Exception:  # noqa: BLE001
        ALL_CAPABILITIES = frozenset()
    rows = []
    for name, b in ctx.engines.items():
        st = b.get("status") or ("ok" if any(r.get("engine") == name and r.get("status") == "ok"
                                             for r in ctx.results) else None)
        status = st or DASH
        if st == "skipped":
            status = f"skipped (by design): {b.get('reason') or DASH}"
        elif st == "failed":
            status = f"failed: {b.get('reason') or DASH}"
            ctx.fail(name, "engine availability check", b.get("reason"))
        caps = b.get("capabilities")
        lacking = sorted(set(ALL_CAPABILITIES) - set(caps)) if isinstance(caps, list) and caps else None
        rows.append((name, status, b.get("version"), ", ".join(lacking) if lacking else ("none" if caps else None)))
    out += _table(["engine", "status", "version", "capabilities lacking"], rows) + [""]
    for name, b in ctx.engines.items():
        modes = b.get("modes") if isinstance(b.get("modes"), dict) else {}
        source = ""
        eng = None
        if not modes or "known_limits" not in b:
            eng = _registry_engine(name)
        if not modes and eng is not None:
            try:
                modes = {m: {"kind": i.kind, "dynamic": i.dynamic, "counterpart": i.counterpart,
                             "description": i.description} for m, i in eng.modes().items()}
                source = " (from the engine registry; metrics.json has no mode table)" if modes else ""
            except Exception:  # noqa: BLE001
                modes = {}
        out += [f"### {name}", ""]
        if modes:
            out += [f"Modes{source}:", ""]
            out += _table(["mode", "kind", "dynamic", "counterpart (engine terms)", "description"],
                          [(m, i.get("kind"), _scalar(bool(i.get("dynamic"))), i.get("counterpart"),
                            i.get("description")) for m, i in modes.items() if isinstance(i, dict)]) + [""]
        else:
            out += ["No mode table recorded.", ""]
        skips = defaultdict(set)
        for r in ctx.results:
            if r.get("engine") == name and r.get("status") == "skipped" and r.get("by_design"):
                skips[str(r.get("reason") or "by design")].add(str(r.get("scene")))
        if b.get("status") == "skipped" and b.get("reason"):
            out += [f"Skipped on every scene (by design): {b['reason']}", ""]
        else:
            for why, scenes in sorted(skips.items()):
                out += [f"By-design skips: {', '.join(sorted(scenes))}: {why}", ""]
        limits = b.get("known_limits")
        src = ""
        if limits is None and eng is not None and hasattr(eng, "known_limits"):
            try:
                limits, src = list(eng.known_limits()), " (from the engine registry)"
            except Exception:  # noqa: BLE001
                limits = None
        if limits:
            out += [f"Known limits{src}:", ""] + [f"- {_cell(x)}" for x in limits] + [""]
        elif limits is not None:
            out += ["Known limits: none declared.", ""]
    return out


# ------------------------------------------------------------------------------------------------ phase 0

def _rows_of(doc) -> list[dict]:
    if isinstance(doc, list):
        return _dicts(doc)
    if isinstance(doc, dict):
        for k in ("entries", "results", "views", "rows", "items"):
            if isinstance(doc.get(k), list):
                return _dicts(doc[k])
    return []


def _gate_text(gate: Mapping) -> str:
    """'PASS' / 'FAIL' / 'incomplete' / 'not measurable' plus the gate's own reason and counts."""
    passed = gate.get("passed")
    status = gate.get("status")
    verdict = {True: "PASS", False: "FAIL"}.get(passed if isinstance(passed, bool) else None) or \
        (str(status).replace("_", " ") if status else "n/a")
    bits = []
    if gate.get("entries") is not None and gate.get("passed_entries") is not None:
        bits.append(f"{gate['passed_entries']}/{gate['entries']} entries passed")
    if gate.get("failed_entries"):
        bits.append("failed: " + ", ".join(map(str, gate["failed_entries"])))
    if gate.get("not_compared"):
        bits.append("not compared: " + "; ".join(map(str, gate["not_compared"])))
    if gate.get("reason"):
        bits.append(str(gate["reason"]))
    if gate.get("baseline") and gate.get("system"):
        bits.append(f"{gate['system']} vs baseline {gate['baseline']}")
    if gate.get("representative") is False:  # the reason is printed once, below the gate
        bits.append("not representative")
    if not bits:  # an unknown schema: show its scalars
        bits = [f"{k} {_scalar(v)}" for k, v in _flat(gate).items()
                if k not in ("passed", "status", "criterion", "representative", "representative_reason", "note")
                and v is not None][:12]
    return f"**{verdict}**" + (" (" + "; ".join(_short(b, 400) for b in bits) + ")" if bits else "")


def _representative_flag(*docs) -> tuple[bool | None, str | None]:
    for d in docs:
        if isinstance(d, Mapping) and isinstance(d.get("representative"), bool):
            # a gate's own "reason" explains the verdict; documents use "reason" for the representativeness
            why = d.get("representative_reason") if "representative_reason" in d else \
                (None if "status" in d and "criterion" in d else d.get("reason"))
            return d["representative"], why
    return None, None


def _parity(ctx: _Ctx, parity) -> list[str]:
    out = []
    gate = parity.get("gate") if isinstance(parity, dict) and isinstance(parity.get("gate"), dict) else None
    rep, why = _representative_flag(parity if isinstance(parity, dict) else None, gate)
    crit = (parity.get("criterion") if isinstance(parity, dict) else None) or (gate or {}).get("criterion")
    out += [f"Gate: {crit or 'per view and mode, p99.9 ≤ 1 LSB and mean ≤ 0.1 LSB over all pixels (DESIGN §5.4)'}.",
            "Valid pixels exclude silhouettes (ROI `all` of the reference), where two rasterizers' edge rules "
            "differ.", ""]
    rows = []
    for r in _rows_of(parity):
        where = f"{r.get('scene')}/{r.get('view')}/{r.get('mode')}"
        st = r.get("status")
        valid = r.get("valid") if isinstance(r.get("valid"), dict) else None
        if st in ("failed", "error"):
            result = f"failed: {_short(r.get('reason') or DASH, 160)}"
            ctx.fail(where, "Phase 0 parity (run)", r.get("reason"))
        elif st == "skipped":
            result = f"skipped{' (by design)' if r.get('by_design') else ''}: {_short(r.get('reason') or DASH, 160)}"
            if not r.get("by_design"):
                ctx.warn(f"{where} parity", f"skipped: {r.get('reason')}")
        else:
            passed = _row_passed(r)
            result = _verdict(passed)
            if passed is False:
                p, m = _pick(r, "gate.p99_9", "all.p99_9", "p99_9"), _pick(r, "gate.mean", "all.mean", "mean")
                if rep is False:
                    result += " (not representative)"
                else:
                    ctx.fail(where, "Phase 0 parity gate", f"p99.9 {fmt_sig(p)} LSB, mean {fmt_sig(m)} LSB")
        rows.append((r.get("scene"), r.get("view"), r.get("mode"),
                     _lsb(_pick(r, "all.p99_9", "gate.p99_9", "p99_9", "lsb_p99_9", "p999")),
                     _lsb(_pick(r, "all.mean", "gate.mean", "mean", "lsb_mean")),
                     _lsb(_pick(r, "all.max", "max", "lsb_max")),
                     _scalar(_pick(r, "all.pixels_gt1", "pixels_gt1", "lsb_gt1_px")),
                     f"{_lsb(valid.get('p99_9'))} / {_lsb(valid.get('mean'))}" if valid else DASH,
                     fmt_sig(_pick(r, "linear.all.rel_l1", "linear_rel_l1", "rel_l1")),
                     result, _link(_pick(r, "files.sheet", "sheet"), "sheet")))
    if rows:
        out += _table(["scene", "view", "mode", "p99.9 (LSB)", "mean (LSB)", "max (LSB)", "px > 1 LSB",
                       "valid px: p99.9 / mean", "linear rel_l1", "result", "sheet"], rows,
                      right=(3, 4, 5, 6, 7, 8)) + [""]
    else:
        out += ["No parity entries recorded.", ""]
    if gate is None and isinstance(parity, dict) and isinstance(parity.get("passed"), bool):
        gate = {"passed": parity["passed"]}
    if gate is not None:
        out += [f"Parity gate: {_gate_text(gate)}", ""]
    if rep is False:
        out += [f"Not representative{': ' + why if why else ''}. The result is recorded, not judged; the gate runs "
                "on a real GPU.", ""]
    return out


def _gate_pairs_table(pairs: list[dict], baseline: str, system: str) -> list[str]:
    rows = []
    for p in pairs:
        b = p.get("baseline") if isinstance(p.get("baseline"), dict) else {}
        s = p.get("system") if isinstance(p.get("system"), dict) else {}
        rows.append((p.get("scene"), p.get("mode"), p.get("view"),
                     f"{fmt_sig(_pick(b, 'gpu_ms.p50'))} / {fmt_sig(_pick(b, 'gpu_ms.p95'))}",
                     f"{fmt_sig(_pick(s, 'gpu_ms.p50'))} / {fmt_sig(_pick(s, 'gpu_ms.p95'))}",
                     f"{fmt_sig(p.get('gpu_p50_ratio'))} / {fmt_sig(p.get('gpu_p95_ratio'))}",
                     f"{fmt_sig(_pick(b, 'cpu_ms.p50'))} / {fmt_sig(_pick(s, 'cpu_ms.p50'))}",
                     _verdict(p.get("passed")) if isinstance(p.get("passed"), bool) else
                     str(p.get("status") or "n/a").replace("_", " "), _short(p.get("reason") or "", 200)))
    return _table(["scene", "mode", "view", f"{baseline} GPU ms p50 / p95", f"{system} GPU ms p50 / p95",
                   "GPU ratio p50 / p95", f"CPU ms p50 {baseline} / {system}", "result", "reason"], rows,
                  right=(3, 4, 5, 6))


def _phase0(ctx: _Ctx) -> list[str]:
    out = ["## Phase 0 (three.js original vs native port)", ""]
    parity, p0perf = ctx.docs.get("parity"), ctx.docs.get("phase0_perf")
    if parity is None and p0perf is None and not isinstance(ctx.perf.get("phase0_gate"), dict):
        return out + [f"_phase0/parity.json and phase0/perf.json {ctx.problems.get('parity', 'missing')}: "
                      "Phase 0 was not run for this run (`python -m tools.parity`, `python -m tools.perf --phase0`)._",
                      ""]
    out += ["### Parity (8-bit, `--parity`, |web − native| per channel)", ""]
    out += _parity(ctx, parity) if parity is not None else _missing_line(ctx.problems, "parity", "no parity results")
    out += ["### Performance gate (GPU ms totals, interleaved rounds)", ""]
    gate = None
    if isinstance(p0perf, dict):
        gate = p0perf.get("phase0_gate") if isinstance(p0perf.get("phase0_gate"), dict) else \
            (p0perf.get("gate") if isinstance(p0perf.get("gate"), dict) else None)
    else:
        out += _missing_line(ctx.problems, "phase0_perf", "no Phase 0 timings")
    if gate is None and isinstance(ctx.perf.get("phase0_gate"), dict):
        gate = ctx.perf["phase0_gate"]
    if gate is None:
        if isinstance(p0perf, dict) and _rows_of(p0perf):
            out += _perf_table(ctx, _rows_of(p0perf)) + [""]
        return out + ["No performance gate recorded.", ""]
    rep, why = _representative_flag(gate, p0perf if isinstance(p0perf, dict) else None, ctx.perf)
    out += [f"Gate: {gate.get('criterion') or 'native GPU p50 ≤ web GPU p50 and native GPU p95 ≤ web GPU p95'}.", ""]
    pairs = _dicts(gate.get("pairs"))
    if pairs:
        out += _gate_pairs_table(pairs, str(gate.get("baseline") or "baseline"),
                                 str(gate.get("system") or "system")) + [""]
    elif isinstance(p0perf, dict) and _rows_of(p0perf):
        out += _perf_table(ctx, _rows_of(p0perf)) + [""]
    out += [f"Performance gate: {_gate_text(gate)}", ""]
    if rep is False:
        out += [f"Not representative{': ' + why if why else ''}. The result is recorded, not judged.", ""]
    elif gate.get("passed") is False:
        ctx.fail("Phase 0", "performance gate", gate.get("reason") or "native slower than web")
    return out


# ------------------------------------------------------------------------------------------------ gates

def _tol_text(t) -> str:
    if isinstance(t, Mapping):
        parts = []
        for k, v in t.items():
            if k == "bias":
                parts.append(f"|bias| ≤ {fmt_pct(v, False)}")
            elif k in ("rel_l1", "radiance_rel"):
                parts.append(f"{'radiance error' if k == 'radiance_rel' else k} ≤ {fmt_pct(v, False)}")
            elif k == "px":
                parts.append(f"≤ {fmt_sig(v)} px")
            else:
                parts.append(f"{k} ≤ {_scalar(v)}")
        return ", ".join(parts)
    if _f(t) is not None:
        return f"≤ {fmt_pct(t, False)}"
    return DASH


def _gate_values(g: Mapping) -> str:
    v = g.get("values") if isinstance(g.get("values"), dict) else {}
    name = g.get("name")
    if name in ("oracle", "survey_equivalence", "furnace_isolated"):
        bits = []
        if "mode" in v:
            bits.append(f"mode {v['mode']}")
        if v.get("bias") is not None or v.get("rel_l1") is not None:  # % like the tolerance column
            bits.append(f"bias {fmt_pct(v.get('bias'))}, rel_l1 {fmt_pct(v.get('rel_l1'), False)}")
        if v.get("energy") is not None:
            bits.append(f"energy {fmt_pct(v['energy'])}")
        if v.get("pixels") is not None:
            bits.append(f"{v['pixels']} px")
        return ", ".join(bits) or DASH
    if name == "handedness":
        quads = v.get("quads") or v.get("emitters") or {}
        if isinstance(quads, dict) and quads:
            d = [_f(q.get("distance_px")) for q in quads.values() if isinstance(q, dict)]
            e = [_f(q.get("radiance_rel_err")) for q in quads.values() if isinstance(q, dict)]
            d, e = [x for x in d if x is not None], [x for x in e if x is not None]
            return (f"{len(quads)} quads, max offset {fmt_sig(max(d)) if d else DASH} px, "
                    f"max radiance error {fmt_pct(max(e), False) if e else DASH}")
        return DASH
    if name == "ref_noise":
        return f"rel. s.e. {fmt_pct(v.get('rel_se'), False)}"
    flat = _flat(v)
    return ", ".join(f"{k} {_scalar(x)}" for k, x in list(flat.items())[:6]) or DASH


def _gates(ctx: _Ctx) -> list[str]:
    out = ["## Calibration and reference gates", ""]
    if not ctx.gates:
        return out + _missing_line(ctx.problems, "gates", "no gates")
    gates = _dicts(ctx.gates.get("gates"))
    tol = ctx.gates.get("tolerances") if isinstance(ctx.gates.get("tolerances"), dict) else {}
    if tol:
        out += ["Tolerances: reference vs oracle " + _tol_text(tol.get("reference_oracle")) +
                "; engines' direct mode vs oracle " + _tol_text(tol.get("engine_oracle")) +
                "; reference noise in targeted ROIs: relative standard error "
                + _tol_text(tol.get("reference_noise_rel_se")) + ".", ""]
    summary = ctx.gates.get("summary") if isinstance(ctx.gates.get("summary"), dict) else {}
    subjects = list(summary) + sorted({str(g.get("subject")) for g in gates} - set(summary))
    skipped = [g for g in gates if g.get("status") == "skipped" or (g.get("by_design") and g.get("passed") is None)]
    for subj in subjects:
        s = summary.get(subj) or {}
        sg = [g for g in gates if str(g.get("subject")) == subj]
        counts = {k: s.get(k, sum(1 for g in sg if g.get("status") == k))
                  for k in ("passed", "failed", "not_applicable", "skipped")}
        out += [f"### {subj}: {counts['passed']} passed, {counts['failed']} failed, {counts['not_applicable']} "
                f"not applicable, {counts['skipped']} skipped by design", ""]
        main = [g for g in sg if g not in skipped and g.get("name") not in ("ref_noise", "furnace_isolated")]
        if main:
            rows = []
            for g in main:
                rows.append((g.get("name"), f"{g.get('scene')} / {g.get('view')}", g.get("component"), g.get("roi"),
                             _gate_values(g), _tol_text(g.get("tolerance")), _verdict(g.get("passed"),
                                                                                      g.get("status")),
                             _short(g.get("detail") or "", 200) if g.get("passed") is not True else ""))
            out += _table(["gate", "scene / view", "component", "ROI", "values", "tolerance", "result", "detail"],
                          rows) + [""]
        noise = [g for g in sg if g not in skipped and g.get("name") == "ref_noise"]
        if noise:
            out += _noise_table(noise) + [""]
        meas = [g for g in sg if g not in skipped and g.get("name") == "furnace_isolated"]
        if meas:
            out += ["Measurements, not gates (indirect modes on the furnace, DESIGN §8):", ""]
            out += _table(["scene / view", "ROI", "values", "detail"],
                          [(f"{g.get('scene')} / {g.get('view')}", g.get("roi"), _gate_values(g),
                            _short(g.get("detail") or "", 160)) for g in meas]) + [""]
        for g in sg:
            if g.get("status") == "failed" or (g.get("passed") is False and g not in skipped):
                where = f"{g.get('scene')}/{g.get('view')}" + (f" [{g['roi']}]" if g.get("roi") else "")
                ctx.fail(where, f"gate {g.get('name')} ({subj}, {g.get('component')})",
                         g.get("detail") or _gate_values(g))
    out += ["### Known limits: by-design skips (not failures)", ""]
    if skipped:
        groups: dict[tuple, list] = defaultdict(list)
        for g in skipped:
            groups[(str(g.get("subject")), str(g.get("reason") or g.get("detail") or "by design"))].append(g)
        rows = []
        for (subj, why), gs in groups.items():
            where = sorted({f"{g.get('scene')}/{g.get('view')}" for g in gs})
            names = sorted({str(g.get("name")) for g in gs})
            rows.append((subj, ", ".join(where), ", ".join(names), len(gs), why))
        out += _table(["subject", "scene / view", "gates", "count", "reason"], rows, right=(3,)) + [""]
    else:
        out += ["None.", ""]
    for w in ctx.gates.get("warnings") or []:
        ctx.warn("gates.json", w)
    return out


def _noise_table(noise: list[dict]) -> list[str]:
    groups: dict[tuple, list] = defaultdict(list)
    for g in noise:
        groups[(str(g.get("scene")), str(g.get("view")), str(g.get("component")))].append(g)
    rows = []
    for (scene, view, comp), gs in groups.items():
        rated = [(g, _f((g.get("values") or {}).get("rel_se"))) for g in gs]
        worst = max((x for x in rated if x[1] is not None), key=lambda x: x[1], default=None)
        npass = sum(1 for g in gs if g.get("passed") is True)
        nfail = [g for g in gs if g.get("passed") is False]
        rows.append((f"{scene} / {view}", comp, f"{npass}/{len(gs)}",
                     f"{fmt_pct(worst[1], False)} ({worst[0].get('roi')})" if worst else DASH,
                     ", ".join(f"{g.get('roi')} {fmt_pct((g.get('values') or {}).get('rel_se'), False)}"
                               for g in nfail) or "none"))
    return (["Reference noise (relative standard error of the reference ROI mean; dark ROIs relative to the scene's "
             "leak normaliser):", ""]
            + _table(["scene / view", "component", "ROIs passed", "worst ROI", "failed ROIs"], rows))


# ------------------------------------------------------------------------------------------------ scenes

def _roi_order(rows: list[dict]) -> list[tuple[str, str, Any]]:
    """[(roi, role, pixels)] over the rows, 'all' first, then in first-seen order."""
    seen: dict[str, tuple[str, Any]] = {}
    for r in rows:
        for name, s in (r.get("rois") or {}).items():
            if isinstance(s, dict) and name not in seen:
                seen[name] = (str(s.get("role") or "any"), s.get("pixels"))
    names = sorted(seen, key=lambda n: (n != "all", list(seen).index(n)))
    return [(n, *seen[n]) for n in names]


def _roi_header(name: str, role: str, pixels) -> str:
    px = f", {pixels} px" if pixels is not None else ""
    if role == "dark":
        return f"{name} (dark{px}): leak_abs / leak_rel (reference)"
    if role == "bleed":
        return f"{name} (bleed{px}): bias / rel_l1 / rel_mse / bleed Δc"
    return f"{name} ({role}{px}): bias / rel_l1 / rel_mse"


def _roi_cell(r: dict, roi: str, role: str) -> str:
    s = (r.get("rois") or {}).get(roi)
    if not isinstance(s, dict):
        return DASH
    if role == "dark":
        mark = FLOOR_MARK if _below_floor(s.get("leak_abs"), s.get("ref_noise_abs"), s.get("ref_leak_abs")) else ""
        return (f"{fmt_sig(s.get('leak_abs'))} / {fmt_pct(s.get('leak_rel'), False)}{mark} "
                f"(ref {fmt_pct(s.get('ref_leak_rel'), False)})")
    b = s.get("bias")
    if b is None and s.get("bias_abs") is not None:
        ref0 = _f(s.get("ref_mean")) == 0
        txt = f"ΔY {fmt_sig(s['bias_abs'])}" + (" (reference 0)" if ref0 else
                                                " (reference ≈ 0 within noise)" if s.get("ref_within_noise") else "")
    else:
        mark = FLOOR_MARK if _below_floor(b, s.get("ref_noise_rel")) else ""
        txt = f"{fmt_pct(b)}{mark} / {fmt_sig(s.get('rel_l1'))} / {fmt_sig(s.get('rel_mse'))}"
    if role == "bleed":
        bl = (r.get("bleed") or {}).get(roi)
        txt += f" / {fmt_sig(bl.get('dist')) if isinstance(bl, dict) else DASH}"
    return txt


def _noise_cell(r: dict, roi: str, role: str) -> str:
    s = (r.get("rois") or {}).get(roi)
    if not isinstance(s, dict):
        return DASH
    if role == "dark":
        return f"leak_rel σ {fmt_pct(s.get('leak_noise_rel'), False)}"
    return f"σ {fmt_pct(s.get('ref_noise_rel'), False)}"


def _row_label(r: Mapping) -> str:
    return f"{r.get('engine')} / {r.get('mode') or 'all modes'}"


def _row_notes(r: Mapping) -> str:
    st = r.get("status")
    if st and st != "ok":
        return f"{st}{' (by design)' if r.get('by_design') else ''}: {_short(r.get('reason') or DASH, 200)}"
    notes = list(r.get("warnings") or [])
    if isinstance(r.get("flip"), dict) and r["flip"].get("error"):
        notes.append(f"FLIP: {r['flip']['error']}")
    return "; ".join(_short(n, 160) for n in notes)


def _view_table(ctx: _Ctx, scene: str, view: str, rows: list[dict], comparison: str) -> list[str]:
    out = [f"#### {scene} / {view}", ""]
    sheet = next((_pick(r, "files.sheet") for r in rows if _pick(r, "files.sheet")), None)
    if sheet:
        out += [f"Contact sheet: {_link(sheet)}", ""]
    rows = sorted(rows, key=ctx.row_key)
    ok = [r for r in rows if r.get("status") == "ok"]
    if comparison == "appearance":
        rois = []
        for r in ok:
            for k in ((r.get("flip") or {}).get("rois") or {}):
                if k not in rois:
                    rois.append(k)
        rois.sort(key=lambda n: n != "all")
        body = [(_row_label(r), fmt_sig((r.get("flip") or {}).get("mean")),
                 *[fmt_sig(((r.get("flip") or {}).get("rois") or {}).get(k)) for k in rois], _row_notes(r))
                for r in rows]
        return out + _table(["engine / mode", "FLIP mean", *[f"FLIP {k}" for k in rois], "notes"], body,
                            right=range(1, 2 + len(rois))) + [""]
    rois = _roi_order(ok)
    headers = ["engine / mode", "component", *[_roi_header(*x) for x in rois], "energy", "FLIP mean", "notes"]
    body = []
    for comp in ("direct", "isolated"):
        src = next((r for r in ok if r.get("component") == comp), None)
        if src is not None:
            all_noise = ((src.get("rois") or {}).get("all") or {}).get("ref_noise_rel")
            body.append((f"reference noise ({comp})", comp, *[_noise_cell(src, n, role) for n, role, _ in rois],
                         f"σ {fmt_pct(all_noise, False)}", DASH, "relative s.e. of the reference ROI mean"))
    for r in rows:
        if r.get("status") != "ok":
            body.append((_row_label(r), r.get("component"), *[DASH] * len(rois), DASH, DASH, _row_notes(r)))
            continue
        all_noise = ((r.get("rois") or {}).get("all") or {}).get("ref_noise_rel")
        e = r.get("energy")
        emark = FLOOR_MARK if _below_floor(e, all_noise) else ""
        body.append((_row_label(r), r.get("component"), *[_roi_cell(r, n, role) for n, role, _ in rois],
                     f"{fmt_pct(e)}{emark}" if e is not None else DASH,
                     fmt_sig((r.get("flip") or {}).get("mean")), _row_notes(r)))
    return out + _table(headers, body) + [""]


def _scenes(ctx: _Ctx) -> list[str]:
    out = ["## Results per scene and view", ""]
    if not ctx.results and not ctx.metrics:
        return out + _missing_line(ctx.problems, "metrics", "no per-scene results")
    out += [f"Rows are engine / mode; `direct` rows measure the direct component against reference `direct`, "
            f"indirect rows the isolated component `final(mode) − final(direct)` against `full − direct` "
            f"(DESIGN §7). Cells: bias (signed, relative) / rel_l1 / rel_mse; dark ROIs: leak_abs / leak_rel "
            f"(the reference's own leak_rel); bleed ROIs add the chromaticity error ‖Δc‖. energy = Σ Y(engine) / "
            f"Σ Y(reference) − 1 over `all`. {FLOOR_MARK} = within {NOISE_K:g} reference standard errors of the "
            f"reference (below the reference noise floor). rel_l1 and rel_mse also contain the reference's per-pixel "
            f"noise. Where the reference is 0, or zero up to its noise (ROI mean within 2 standard errors of 0), "
            f"the cell shows the absolute ΔY = mean Y(engine) − mean Y(reference) instead of ratios. FLIP: HDR-FLIP "
            f"of the final image against reference `full` (lower is better). `appearance` scenes report only FLIP.",
            ""]
    scenes = ctx.metrics.get("scenes") if isinstance(ctx.metrics.get("scenes"), dict) else {}
    by_scene: dict[str, list[dict]] = defaultdict(list)
    for r in ctx.results:
        by_scene[str(r.get("scene"))].append(r)
    names = list(dict.fromkeys(list(scenes) + list(by_scene)))
    names.sort(key=lambda n: (_GROUP_ORDER.get((scenes.get(n) or {}).get("group"), 9), n))
    for name in names:
        info = scenes.get(name) if isinstance(scenes.get(name), dict) else {}
        rs = by_scene.get(name, [])
        comparison = info.get("comparison") or "exact"
        meta = [x for x in (info.get("group"), f"comparison {comparison}") if x]
        out += [f"### {name} ({', '.join(meta)})", ""]
        if info.get("failure_mode"):
            out += [f"Failure mode: {_cell(info['failure_mode'])}", ""]
        ln = info.get("leak_norm")
        if isinstance(ln, dict) and any(v is not None for v in ln.values()):
            out += ["Leak normaliser (brightest view's mean Y over `all`): "
                    + ", ".join(f"{k} {fmt_sig(v)}" for k, v in ln.items()), ""]
        if info.get("error"):
            ctx.fail(name, "scene", info["error"])
            out += [f"Scene failed: {_cell(info['error'])}", ""]
        ref = info.get("reference") if isinstance(info.get("reference"), dict) else {}
        if ref.get("status") == "failed":
            ctx.fail(name, "reference", ref.get("error"))
            out += [f"Reference failed: {_cell(ref.get('error'))}", ""]
        for w in ref.get("warnings") or []:
            ctx.warn(f"{name} reference", w)
        for w in info.get("warnings") or []:
            ctx.warn(name, w)
        views = [str(v.get("id")) for v in _dicts(info.get("views"))]
        views += [str(v) for v in dict.fromkeys(r.get("view") for r in rs) if v is not None and str(v) not in views]
        scene_level = [r for r in rs if r.get("view") is None]
        if not views:
            if scene_level:
                out += _table(["engine / mode", "notes"], [(_row_label(r), _row_notes(r)) for r in scene_level])
                out += [""]
            else:
                out += ["No views recorded.", ""]
        for view in views:
            vrows = [r for r in rs if str(r.get("view")) == view] + scene_level
            out += _view_table(ctx, name, view, vrows, comparison)
        # failures and warnings, grouped over views
        groups: dict[tuple, list] = defaultdict(list)
        for r in rs:
            if r.get("status") == "failed" or (r.get("status") not in ("ok", "skipped", None)):
                groups[(r.get("engine"), r.get("mode"), str(r.get("reason")))].append(r.get("view"))
            for w in r.get("warnings") or []:
                ctx.warn(f"{name}/{r.get('view')} {r.get('engine')}/{r.get('mode')}", w)
        for (eng, mode, reason), vs in groups.items():
            where = f"{name} [{', '.join(str(v) for v in vs if v is not None) or 'all views'}]"
            ctx.fail(where, f"{eng}/{mode or 'all modes'}", reason)
    for w in ctx.metrics.get("warnings") or []:
        ctx.warn("metrics.json", w)
    return out


# ------------------------------------------------------------------------------------------------ temporal

def _temporal(ctx: _Ctx) -> list[str]:
    out = ["## Temporal (dynamic modes on timeline scenes)", ""]
    if not ctx.temporal:
        return out + _missing_line(ctx.problems, "temporal", "no temporal results")
    results = _dicts(ctx.temporal.get("results"))
    out += ["Per step: t90 = time until the isolated ROI mean stays within 10 % of the change; afterglow r(t) = "
            "(y − ref_post) / (ref_pre − ref_post) at 0.1 / 0.25 / 0.5 / 1 s after a falling step (0 = settled on the "
            "reference); settled residual = (post − ref_post) / (ref_pre − ref_post). Flicker over the last frames of "
            "each state: temporal_cv (per-pixel temporal std / mean) / f2f (mean frame-to-frame change / mean).", ""]
    by_scene: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_scene[str(r.get("scene"))].append(r)
    if not results:
        out += ["No temporal results (no dynamic mode ran on a timeline scene).", ""]
    for scene, rs in sorted(by_scene.items()):
        rs = sorted(rs, key=lambda r: (*ctx.row_key(r), r.get("roi") != "all", str(r.get("roi"))))
        out += [f"### {scene}", ""]
        plots = list(dict.fromkeys((f"{r.get('engine')} / {r.get('mode')}", r.get("plot")) for r in rs
                                   if r.get("plot")))
        if plots:
            out += ["Plots: " + ", ".join(_link(p, label) for label, p in plots), ""]
        rows = []
        for r in rs:
            for s in _dicts(r.get("steps")):
                ag = s.get("afterglow") if isinstance(s.get("afterglow"), dict) else None
                if ag and ag.get("residual") is None and not any(v is not None for v in (ag.get("r") or {}).values()):
                    ag = None  # no finite frame after the step: nothing was measured
                if s.get("pre") is None or s.get("post") is None:
                    t90 = "no data"
                elif not s.get("timed", s.get("t90_frames") is not None):
                    t90 = "no change"
                elif s.get("t90_frames") is None:
                    t90 = "not settled"
                else:
                    t90 = f"{fmt_sig(s.get('t90_s'))} s ({s['t90_frames']} frames)"
                rr = (ag or {}).get("r") or {}
                rows.append((f"{r.get('engine')} / {r.get('mode')}", r.get("roi"), s.get("frame"),
                             f"{fmt_sig(s.get('pre'))} → {fmt_sig(s.get('post'))}", t90,
                             *[fmt_sig(rr.get(k)) if ag else DASH for k in _AFTERGLOW_KEYS],
                             (f"{fmt_sig(ag.get('t05_s'))} s" if ag.get("t05_frames") is not None else "never")
                             if ag else DASH,
                             fmt_sig(ag.get("residual")) if ag else DASH))
        if rows:
            out += _table(["engine / mode", "ROI", "step frame", "settled pre → post", "t90", "r(0.1 s)",
                           "r(0.25 s)", "r(0.5 s)", "r(1 s)", "r ≤ 0.05 after", "settled residual"], rows,
                          right=(2, 5, 6, 7, 8, 9, 10)) + [""]
            out += ["Afterglow columns are empty for rising steps (afterglow is defined on falling steps only).", ""]
        states = list(dict.fromkeys(str(f.get("view") or f"state{f.get('state')}")
                                    for r in rs for f in _dicts(r.get("flicker"))))
        if states:
            frows = []
            for r in rs:
                fl = {str(f.get("view") or f"state{f.get('state')}"): f for f in _dicts(r.get("flicker"))}
                frows.append((f"{r.get('engine')} / {r.get('mode')}", r.get("roi"),
                              *[f"{fmt_sig(fl[s].get('temporal_cv'))} / {fmt_sig(fl[s].get('f2f'))}" if s in fl
                                else DASH for s in states]))
            out += _table(["engine / mode", "ROI", *[f"{s}: temporal_cv / f2f" for s in states]], frows) + [""]
        for r in rs:
            if r.get("frames_missing"):
                ctx.warn(f"{scene} {r.get('engine')}/{r.get('mode')} [{r.get('roi')}]",
                         f"{r['frames_missing']} timeline frames missing")
    skipped = _dicts(ctx.temporal.get("skipped"))
    by_design = [s for s in skipped if s.get("by_design") or s.get("status") == "skipped" and
                 s.get("by_design") is not False]
    if by_design:
        groups: dict[str, set] = defaultdict(set)
        for s in by_design:
            groups[str(s.get("reason") or "by design")].add(f"{s.get('engine')}/{s.get('mode') or 'all modes'}")
        out += ["Not measured (by design): " + "; ".join(f"{', '.join(sorted(v))}: {k}" for k, v in
                                                         sorted(groups.items())), ""]
    for s in skipped:
        if s not in by_design:
            if s.get("status") == "failed":
                ctx.fail(f"{s.get('scene')} temporal", f"{s.get('engine')}/{s.get('mode') or 'all modes'}",
                         s.get("reason"))
            else:
                ctx.warn(f"{s.get('scene')} temporal", f"{s.get('engine')}/{s.get('mode') or 'all modes'} not "
                                                       f"measured: {s.get('reason')}")
    for w in ctx.temporal.get("warnings") or []:
        ctx.warn("temporal.json", w)
    return out


# ------------------------------------------------------------------------------------------------ cost

def _perf_table(ctx: _Ctx, entries: list[dict]) -> list[str]:
    rows = []
    for e in sorted(entries, key=lambda e: (str(e.get("scene")), *ctx.row_key(e))):
        mem = e.get("memory") if isinstance(e.get("memory"), dict) else {}
        pre = e.get("precompute") if isinstance(e.get("precompute"), dict) else {}
        gpu_mem = None
        if mem.get("gpu_texture_bytes") is not None or mem.get("gpu_buffer_bytes") is not None:
            gpu_mem = (f"{fmt_bytes(mem.get('gpu_texture_bytes'))} textures + "
                       f"{fmt_bytes(mem.get('gpu_buffer_bytes'))} buffers")
        pre_txt = f"{fmt_seconds(pre.get('seconds'))}, {fmt_bytes(pre.get('bytes'))}" if pre else None
        adapter = e.get("adapter") or _pick(e, "device.adapter")
        if isinstance(adapter, dict):
            adapter = adapter.get("adapter") or adapter.get("name")
        rounds = _scalar(e.get("rounds"))
        if e.get("rounds_requested") is not None:
            rounds = f"{rounds}/{e['rounds_requested']}"
        passes = e.get("passes") if isinstance(e.get("passes"), dict) else {}
        ptxt = ", ".join(f"{k} {fmt_sig(v.get('p50') if isinstance(v, dict) else v)}" for k, v in passes.items())
        notes = []
        if e.get("status") not in (None, "ok"):
            notes.append(f"{e['status']}{' (by design)' if e.get('by_design') else ''}: {e.get('reason')}")
        if e.get("gpu_timestamps") is False:
            notes.append(f"no GPU timestamps ({e.get('gpu_reason') or 'gpu_ms missing'})")
        where = e.get("scene") if not e.get("view") else f"{e.get('scene')} / {e.get('view')}"
        rows.append((e.get("engine"), e.get("mode"), where, adapter, rounds,
                     fmt_sig(_pick(e, "gpu_ms.p50")), fmt_sig(_pick(e, "gpu_ms.p95")),
                     fmt_sig(_pick(e, "cpu_ms.p50")), fmt_sig(_pick(e, "cpu_ms.p95")), ptxt or None, gpu_mem,
                     fmt_bytes(mem.get("peak_rss_bytes")), pre_txt, "; ".join(_short(n, 160) for n in notes)))
    return _table(["engine", "mode", "scene", "adapter", "rounds", "GPU ms p50", "GPU ms p95", "CPU ms p50",
                   "CPU ms p95", "GPU passes p50 (information)", "GPU memory", "peak RSS", "precompute", "notes"], rows,
                  right=(4, 5, 6, 7, 8, 11))


def _cost(ctx: _Ctx) -> list[str]:
    out = ["## Cost", ""]
    if not ctx.perf:
        return out + _missing_line(ctx.problems, "perf", "no cost measurements (`python -m tools.perf --run <dir>`)")
    rep = ctx.perf.get("representative")
    if isinstance(rep, bool):
        out += [f"Representative machine: {'yes' if rep else 'no'}"
                + (f" ({ctx.perf.get('reason')})" if ctx.perf.get("reason") else "")
                + ("" if rep else ". Timings from software rasterizers do not predict GPU cost; compare them "
                   "only with each other."), ""]
    entries = _rows_of(ctx.perf)
    for e in entries:
        if e.get("status") == "failed":
            ctx.fail(f"{e.get('scene')} perf", f"{e.get('engine')}/{e.get('mode')}", e.get("reason"))
    for s in ctx.perf.get("scene_errors") or []:
        if isinstance(s, dict):
            ctx.fail(f"{s.get('scene')} perf", "scene", s.get("error") or s.get("reason"))
        else:
            ctx.fail("perf", "scene", s)
    if not entries:
        return out + ["No cost entries recorded.", ""]
    out += ["Per-frame times after warm-up, pooled over interleaved rounds (DESIGN §7 Cost). GPU ms are per-frame "
            "totals; memory is what the runner allocated plus peak RSS; precompute covers shader and pipeline "
            "builds and tables.", ""]
    skips: dict[tuple, list[dict]] = defaultdict(list)  # by-design skips: one line per engine and reason
    for e in entries:
        if e.get("status") == "skipped" and e.get("by_design"):
            skips[(str(e.get("engine")), str(e.get("reason") or "by design"))].append(e)
    shown = [e for e in entries if not (e.get("status") == "skipped" and e.get("by_design"))]
    if shown:
        out += _perf_table(ctx, shown) + [""]
    for (eng, why), es in sorted(skips.items(), key=lambda kv: ctx.engine_index(kv[0][0])):
        modes = ", ".join(dict.fromkeys(str(e.get("mode")) for e in es))
        scenes = ", ".join(dict.fromkeys(str(e.get("scene")) for e in es))
        out += [f"Not measured (by design): {eng} ({modes}; {scenes}): {why}", ""]
    passes: dict[str, set] = defaultdict(set)
    for e in entries:
        if isinstance(e.get("passes"), dict):
            passes[str(e.get("engine"))] |= set(e["passes"])
    if len(passes) > 1 or any(len(v) for v in passes.values()):
        out += ["Pass categories differ between engines (" + "; ".join(
            f"{k}: {', '.join(sorted(v))}" for k, v in sorted(passes.items(), key=lambda kv: ctx.engine_index(kv[0])))
                + "; threejs-web renders shadows inside its passes), so compare GPU totals, not passes.", ""]
    return out


# ------------------------------------------------------------------------------------------------ failures etc.

def _run_failures(ctx: _Ctx) -> None:
    for s in _dicts(ctx.run.get("steps")):
        if s.get("status") not in ("ok", "skipped"):
            ctx.fail("run_all", f"step {s.get('name')} ({s.get('status')})", s.get("reason"))


def _failures(ctx: _Ctx) -> list[str]:
    out = ["## Failures", "", "Real failures only (status failed); by-design skips are listed under the engines, the "
           "known limits and the temporal section.", ""]
    if not ctx.failures:
        return out + ["None.", ""]
    rows = list(dict.fromkeys(ctx.failures))
    return out + _table(["where", "what", "reason"], rows) + [""]


def _warnings(ctx: _Ctx) -> list[str]:
    if not ctx.warnings:
        return []
    groups: dict[str, list[str]] = defaultdict(list)
    for where, text in ctx.warnings:
        if where not in groups[text]:
            groups[text].append(where)
    rows = [(", ".join(ws[:8]) + (f" (+{len(ws) - 8} more)" if len(ws) > 8 else ""), text)
            for text, ws in groups.items()]
    return ["## Warnings", ""] + _table(["where", "warning"], rows) + [""]


def _durations(ctx: _Ctx) -> list[str]:
    out = ["## Durations", ""]
    run = ctx.run
    dur = run.get("durations") if isinstance(run.get("durations"), dict) else {}
    rows = []
    steps = _dicts(run.get("steps"))
    for s in steps:
        rows.append((f"run_all: {s.get('name')}", s.get("status"), fmt_seconds(s.get("seconds"))))
    if not steps and isinstance(dur.get("run_all"), dict):
        for k, v in dur["run_all"].items():
            rows.append((f"run_all: {k}", None, fmt_seconds(v)))
    for tool, d in dur.items():
        if tool == "run_all" or not isinstance(d, dict):
            continue
        for k, v in d.items():
            if k.endswith("_s"):
                rows.append((f"{tool}: {k[:-2]}", None, fmt_seconds(v)))
    if not dur and isinstance(ctx.metrics.get("durations"), dict):
        for k, v in ctx.metrics["durations"].items():
            if k.endswith("_s"):
                rows.append((f"pairs: {k[:-2]}", None, fmt_seconds(v)))
    if isinstance(ctx.temporal.get("durations"), dict) and "temporal" not in dur:
        rows.append(("temporal: total", None, fmt_seconds(ctx.temporal["durations"].get("total_s"))))
    if not rows and not run:
        return out + _missing_line(ctx.problems, "run", "no durations")
    if rows:
        out += _table(["step", "status", "wall time"], rows, right=(2,)) + [""]
    launches = _dicts(run.get("launches"))
    if launches:
        per: dict[str, list[float]] = defaultdict(list)
        for x in launches:
            v = _f(x.get("seconds"))
            if v is not None:
                per[str(x.get("engine"))].append(v + (_f(x.get("bundle_seconds")) or 0.0))
        out += ["Runner launches (bundle + runner wall time): " + "; ".join(
            f"{k}: {len(v)} launches, {fmt_seconds(sum(v))}" for k, v in sorted(per.items(), key=lambda kv:
                                                                                ctx.engine_index(kv[0]))), ""]
        slow = sorted(launches, key=lambda x: -(_f(x.get("seconds")) or 0.0))[:5]
        out += _table(["slowest launches", "kind", "status", "seconds"],
                      [(f"{x.get('engine')} / {x.get('scene')} / {x.get('mode')}", x.get("kind"), x.get("status"),
                        fmt_seconds(x.get("seconds"))) for x in slow], right=(3,)) + [""]
    return out


# ------------------------------------------------------------------------------------------------ driver

def _safe(section: Callable[[_Ctx], list[str]], ctx: _Ctx, title: str) -> list[str]:
    try:
        return section(ctx)
    except Exception as e:  # noqa: BLE001 - one malformed input must not lose the whole report
        ctx.fail("report", f"section '{title}'", f"{type(e).__name__}: {e}")
        return [f"## {title}", "", f"_This section could not be built: {type(e).__name__}: {_cell(e)}._", ""]


def build_report(run_dir) -> str:
    """The report.md text for a run directory (see the module docstring)."""
    layout = RunLayout(run_dir)
    if not layout.root.is_dir():
        raise FileNotFoundError(f"run directory {layout.root} does not exist")
    docs, problems = load_inputs(layout.root)
    ctx = _Ctx(layout, docs, problems)
    parts = [_safe(_header, ctx, "Run")]
    parts.append(_safe(_engines, ctx, "Engines and modes"))
    parts.append(_safe(_phase0, ctx, "Phase 0"))
    parts.append(_safe(_gates, ctx, "Calibration and reference gates"))
    parts.append(_safe(_scenes, ctx, "Results per scene and view"))
    parts.append(_safe(_temporal, ctx, "Temporal"))
    parts.append(_safe(_cost, ctx, "Cost"))
    _run_failures(ctx)
    parts.append(_failures(ctx))
    parts.append(_warnings(ctx))
    parts.append(_safe(_durations, ctx, "Durations"))
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts.append([f"_Generated {stamp} by `python -m tools.report`._", ""])
    text = "\n".join(line for part in parts for line in part)
    return text.rstrip("\n") + "\n"


def write_report(run_dir, out=None) -> Path:
    """Build the report and write it (default ``<run>/report.md``); returns the path."""
    text = build_report(run_dir)
    path = Path(out) if out is not None else RunLayout(run_dir).report_md
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.report", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", default="LATEST", help="run directory, or LATEST (default: the run named by runs/LATEST)")
    ap.add_argument("--runs-root", default=None, help="where LATEST lives (default <repo>/runs)")
    ap.add_argument("--out", default=None, help="output file (default <run>/report.md)")
    ap.add_argument("--print", action="store_true", help="also print the report")
    args = ap.parse_args(argv)
    try:
        run = resolve_run(args.run, args.runs_root)
        path = write_report(run, args.out)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    if args.print:
        text = path.read_text(encoding="utf-8")
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:  # a console code page without these characters (Windows without UTF-8 mode)
            sys.stdout.flush()
            sys.stdout.buffer.write(text.encode("utf-8"))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
