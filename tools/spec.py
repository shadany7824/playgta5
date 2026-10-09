"""Scene spec: load, validate (path-qualified errors), apply timeline actions, expand views (DESIGN §2).

CLI: python -m tools.spec <files|dirs> [--check] [--json]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from . import REPO_ROOT
from .geometry import (GeometryError, Mesh, box_mesh, load_obj, quad_mesh, room_mesh, transform_matrix,
                       transformed_mesh, world_matrix)

__all__ = ["SpecError", "Mesh", "Material", "Object", "Light", "Station", "ROI", "Timeline", "Scene", "View",
           "load_scene", "parse_scene", "apply_actions", "state_at_frame", "expand_views", "discover_scenes",
           "world_matrix", "transformed_mesh", "timeline_states", "capture_kind", "views_summary",
           "canonical_json", "sha256_json", "GROUPS", "ROLES", "LIGHT_TYPES", "OPS", "RADIOMETRIC_FIELD",
           "SCENES_ROOT", "SPEC_VERSION"]

SPEC_VERSION = 1
GROUPS = ("calibration", "targeted", "realworld")
ROLES = ("dark", "lit", "bleed", "oracle", "any")
LIGHT_TYPES = ("point", "directional", "rect", "environment")
OPS = ("set_light", "set_transform", "set_material")
# The field a set_light action may change, per light type (named as in the light).
RADIOMETRIC_FIELD = {"point": "intensity", "directional": "irradiance", "rect": "radiance", "environment": "radiance"}
REFERENCE_KEYS = ("spp", "batches", "max_depth", "rr_depth", "aov_spp", "seed")
SCENES_ROOT = REPO_ROOT / "scenes"
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


class SpecError(ValueError):
    """Invalid scene spec. ``.path`` is the JSON path (e.g. ``objects[3].shape.size``), ``.file`` the spec file."""

    def __init__(self, path: str, msg: str, file: Path | str | None = None):
        self.path, self.msg, self.file = path, msg, (str(file) if file else None)
        text = f"{path}: {msg}" if path else msg
        super().__init__(f"{self.file}: {text}" if self.file else text)


# ------------------------------------------------------------------------------------------------ dataclasses

@dataclass(eq=False)
class Material:
    name: str
    albedo: np.ndarray  # (3,) float64


@dataclass(eq=False)
class Object:
    name: str
    material: str
    mesh: Mesh  # object space
    transform: np.ndarray  # (4,4) float64, object space -> local frame
    shape: dict  # normalized spec shape


@dataclass(eq=False)
class Light:
    name: str
    type: str  # point | directional | rect | environment
    params: dict  # spec fields as float64 arrays (rect: origin,u,v,radiance,albedo)


@dataclass(eq=False)
class Station:
    name: str
    position: np.ndarray
    look_at: np.ndarray
    up: np.ndarray
    vfov_deg: float


@dataclass(eq=False)
class ROI:
    name: str
    role: str
    box_min: np.ndarray
    box_max: np.ndarray
    normal: np.ndarray | None = None
    min_cos: float | None = None
    views: list[str] | None = None


@dataclass(eq=False)
class Timeline:
    station: str
    fps: float
    end_frame: int
    steps: list  # [(frame, [action, ...]), ...], frames strictly increasing, >= 1


@dataclass(eq=False)
class Scene:
    name: str
    group: str
    description: str
    failure_mode: str
    comparison: str
    origin: np.ndarray  # (3,) float64 survey origin
    width: int
    height: int
    display: dict
    materials: dict  # name -> Material
    objects: list  # [Object]
    lights: list  # [Light]
    stations: dict  # name -> Station
    rois: list  # [ROI]
    timeline: Timeline | None
    reference: dict  # overrides only (validated keys)
    oracle: dict | None
    source: Path | None
    hash: str = ""

    def material(self, name: str) -> Material:
        return self.materials[name]

    def object(self, name: str) -> Object:
        return next(o for o in self.objects if o.name == name)

    def light(self, name: str) -> Light:
        return next(lt for lt in self.lights if lt.name == name)


@dataclass(eq=False)
class View:
    id: str
    scene: str
    kind: str  # "station" | "state"
    station: Station
    state_index: int | None
    capture_frame: int | None
    state: Scene
    hash: str
    frame_range: tuple[int, int] | None = None  # state views: first and last frame (inclusive)


# ------------------------------------------------------------------------------------------------ canonical JSON

def _canon(x: Any) -> Any:
    if isinstance(x, np.ndarray):
        return [_canon(v) for v in x.tolist()]
    if isinstance(x, (np.floating, float)):
        f = float(x)
        if not math.isfinite(f):
            raise ValueError("non-finite number in canonical JSON")
        return f + 0.0  # -0.0 -> 0.0
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, Path):
        return x.as_posix()
    raise TypeError(f"cannot canonicalize {type(x).__name__}")


def canonical_json(obj: Any) -> str:
    """Sorted-key, compact, finite-only JSON with numpy values converted (stable hash input)."""
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("ascii")).hexdigest()


# ------------------------------------------------------------------------------------------------ validators

def _keys(d: Any, path: str, required: Sequence[str] = (), optional: Sequence[str] = ()) -> dict:
    if not isinstance(d, dict):
        raise SpecError(path, f"expected an object, got {type(d).__name__}")
    allowed = set(required) | set(optional)
    for k in d:  # unknown keys first: a typo is reported at the misspelt key, not as a missing one
        if k not in allowed and not str(k).startswith("_"):
            raise SpecError(_join(path, k), f"unknown key (allowed: {', '.join(sorted(allowed))})")
    for k in required:
        if k not in d:
            raise SpecError(_join(path, k), "required")
    return d


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _num(x: Any, path: str, lo: float | None = None, hi: float | None = None, lo_open: bool = False,
         integer: bool = False) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise SpecError(path, f"expected a number, got {json.dumps(x) if _jsonable(x) else type(x).__name__}")
    if integer and not (isinstance(x, int) or float(x).is_integer()):
        raise SpecError(path, f"expected an integer, got {x}")
    v = int(x) if integer else float(x)
    if not math.isfinite(v):
        raise SpecError(path, "must be finite")
    if lo is not None and (v <= lo if lo_open else v < lo):
        raise SpecError(path, f"must be {'>' if lo_open else '>='} {lo:g}, got {v:g}")
    if hi is not None and v > hi:
        raise SpecError(path, f"must be <= {hi:g}, got {v:g}")
    return v


def _jsonable(x: Any) -> bool:
    try:
        json.dumps(x)
        return True
    except (TypeError, ValueError):
        return False


def _vec3(x: Any, path: str, lo: float | None = None, hi: float | None = None, nonzero: bool = False) -> np.ndarray:
    if isinstance(x, np.ndarray):
        x = x.tolist()
    if not isinstance(x, (list, tuple)) or len(x) != 3:
        raise SpecError(path, "expected a list of 3 numbers")
    v = np.array([_num(c, f"{path}[{i}]", lo=lo, hi=hi) for i, c in enumerate(x)], dtype=np.float64)
    if nonzero and not np.any(v != 0):
        raise SpecError(path, "must be non-zero")
    return v


def _str(x: Any, path: str, choices: Sequence[str] | None = None, name: bool = False) -> str:
    if not isinstance(x, str):
        raise SpecError(path, "expected a string")
    if choices is not None and x not in choices:
        raise SpecError(path, f"must be one of {list(choices)}, got {x!r}")
    if name and not NAME_RE.match(x):
        raise SpecError(path, f"{x!r} is not a valid name (letters, digits, '_' and '-' only)")
    return x


def _list(x: Any, path: str) -> list:
    if not isinstance(x, list):
        raise SpecError(path, "expected a list")
    return x


def _geom(fn, path: str, *args, **kw):
    try:
        return fn(*args, **kw)
    except GeometryError as e:
        raise SpecError(_join(path, e.path) if e.path else path, e.msg) from None


def _transform(t: Any, path: str) -> dict:
    _keys(t, path, optional=("translate", "rotate_z_deg", "pivot"))
    return {"translate": _vec3(t.get("translate", [0, 0, 0]), _join(path, "translate")).tolist(),
            "rotate_z_deg": _num(t.get("rotate_z_deg", 0.0), _join(path, "rotate_z_deg")),
            "pivot": _vec3(t.get("pivot", [0, 0, 0]), _join(path, "pivot")).tolist()}


def _resolve_file(rel: str, source: Path | None, path: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        cands = [p]
    else:
        base = source.parent if source else Path.cwd()
        cands = [base / p, base.parent / p, base.parent.parent / p]
    for c in cands:
        if c.is_file():
            return c
    raise SpecError(path, f"file {rel!r} not found (looked in {', '.join(str(c.parent) for c in cands)})")


def _shape(s: Any, path: str, origin: np.ndarray, source: Path | None) -> tuple[Mesh, dict]:
    if not isinstance(s, dict):
        raise SpecError(path, "expected an object")
    typ = _str(s.get("type"), _join(path, "type"), ("box", "quad", "room", "mesh"))
    if typ == "box":
        if "center" in s or "size" in s:
            _keys(s, path, ("type", "center", "size"))
            c = _vec3(s["center"], _join(path, "center"))
            sz = _vec3(s["size"], _join(path, "size"))
            if np.any(sz <= 0):
                raise SpecError(_join(path, "size"), f"every component must be > 0, got {sz.tolist()}")
            lo, hi = c - sz / 2, c + sz / 2
        else:
            _keys(s, path, ("type", "min", "max"))
            lo, hi = _vec3(s["min"], _join(path, "min")), _vec3(s["max"], _join(path, "max"))
            if np.any(hi <= lo):
                raise SpecError(_join(path, "max"), f"must exceed min on every axis ({lo.tolist()} .. {hi.tolist()})")
        return _geom(box_mesh, path, lo, hi), {"type": "box", "min": lo.tolist(), "max": hi.tolist()}
    if typ == "quad":
        _keys(s, path, ("type", "origin", "u", "v"))
        o, u, v = (_vec3(s[k], _join(path, k)) for k in ("origin", "u", "v"))
        return _geom(quad_mesh, path, o, u, v), {"type": "quad", "origin": o.tolist(), "u": u.tolist(), "v": v.tolist()}
    if typ == "room":
        _keys(s, path, ("type", "min", "max", "thickness"), ("omit", "openings"))
        lo, hi = _vec3(s["min"], _join(path, "min")), _vec3(s["max"], _join(path, "max"))
        th = _num(s["thickness"], _join(path, "thickness"), lo=0, lo_open=True)
        omit = [_str(w, f"{path}.omit[{i}]") for i, w in enumerate(_list(s.get("omit", []), _join(path, "omit")))]
        openings = _list(s.get("openings", []), _join(path, "openings"))
        for i, op in enumerate(openings):
            _keys(op, f"{path}.openings[{i}]", ("wall", "u", "v"))
        mesh = _geom(room_mesh, path, lo, hi, th, omit, openings)
        norm_open = [{"wall": op["wall"], "u": [float(op["u"][0]), float(op["u"][1])],
                      "v": [float(op["v"][0]), float(op["v"][1])]} for op in openings]
        return mesh, {"type": "room", "min": lo.tolist(), "max": hi.tolist(), "thickness": th, "omit": omit,
                      "openings": norm_open}
    _keys(s, path, ("type", "file"), ("coords",))
    rel = _str(s["file"], _join(path, "file"))
    coords = _str(s.get("coords", "local"), _join(path, "coords"), ("local", "world"))
    f = _resolve_file(rel, source, _join(path, "file"))
    try:
        mesh = load_obj(f, origin=origin, coords=coords)
    except GeometryError as e:
        raise SpecError(_join(path, "file"), f"{f.name}: {e.msg}") from None
    return mesh, {"type": "mesh", "file": rel, "coords": coords}


def _light(d: Any, path: str) -> Light:
    if not isinstance(d, dict):
        raise SpecError(path, "expected an object")
    typ = _str(d.get("type"), _join(path, "type"), LIGHT_TYPES)
    name = _str(d.get("name"), _join(path, "name"), name=True)
    J = lambda k: _join(path, k)  # noqa: E731
    if typ == "point":
        _keys(d, path, ("name", "type", "position", "intensity"))
        params = {"position": _vec3(d["position"], J("position")), "intensity": _vec3(d["intensity"], J("intensity"), lo=0)}
    elif typ == "directional":
        _keys(d, path, ("name", "type", "direction", "irradiance"))
        params = {"direction": _vec3(d["direction"], J("direction"), nonzero=True),
                  "irradiance": _vec3(d["irradiance"], J("irradiance"), lo=0)}
    elif typ == "rect":
        _keys(d, path, ("name", "type", "origin", "u", "v", "radiance"), ("albedo",))
        o, u, v = _vec3(d["origin"], J("origin")), _vec3(d["u"], J("u"), nonzero=True), _vec3(d["v"], J("v"), nonzero=True)
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if np.linalg.norm(np.cross(u, v)) <= 1e-9 * nu * nv:
            raise SpecError(J("v"), "u and v must not be parallel")
        if abs(float(np.dot(u, v))) > 1e-6 * nu * nv:
            raise SpecError(J("v"), "u and v must be perpendicular (rect lights are rectangles)")
        params = {"origin": o, "u": u, "v": v, "radiance": _vec3(d["radiance"], J("radiance"), lo=0),
                  "albedo": _vec3(d.get("albedo", [0, 0, 0]), J("albedo"), lo=0, hi=1)}
    else:
        _keys(d, path, ("name", "type", "radiance"))
        params = {"radiance": _vec3(d["radiance"], J("radiance"), lo=0)}
    return Light(name, typ, params)


def _station(d: Any, path: str) -> Station:
    _keys(d, path, ("name", "position", "look_at"), ("up", "vfov_deg"))
    name = _str(d["name"], _join(path, "name"), name=True)
    pos = _vec3(d["position"], _join(path, "position"))
    at = _vec3(d["look_at"], _join(path, "look_at"))
    up = _vec3(d.get("up", [0, 0, 1]), _join(path, "up"), nonzero=True)
    fov = _num(d.get("vfov_deg", 60.0), _join(path, "vfov_deg"), lo=0, lo_open=True, hi=179.0)
    fwd = at - pos
    if np.linalg.norm(fwd) <= 1e-9:
        raise SpecError(_join(path, "look_at"), "must differ from position")
    if np.linalg.norm(np.cross(fwd / np.linalg.norm(fwd), up / np.linalg.norm(up))) < 1e-6:
        raise SpecError(_join(path, "up"), "must not be parallel to the view direction")
    return Station(name, pos, at, up, fov)


def _roi(d: Any, path: str) -> ROI:
    _keys(d, path, ("name", "role", "box"), ("normal", "min_cos", "views"))
    name = _str(d["name"], _join(path, "name"), name=True)
    if name == "all":
        raise SpecError(_join(path, "name"), "'all' is reserved (every view has ROI 'all')")
    role = _str(d["role"], _join(path, "role"), ROLES)
    box = _keys(d["box"], _join(path, "box"), ("min", "max"))
    lo, hi = _vec3(box["min"], _join(path, "box.min")), _vec3(box["max"], _join(path, "box.max"))
    if np.any(hi < lo):
        raise SpecError(_join(path, "box.max"), f"must be >= min on every axis ({lo.tolist()} .. {hi.tolist()})")
    normal = min_cos = None
    if "normal" in d:
        n = _vec3(d["normal"], _join(path, "normal"), nonzero=True)
        normal = n / np.linalg.norm(n)
        min_cos = _num(d.get("min_cos", 0.9), _join(path, "min_cos"), lo=-1, hi=1)
    elif "min_cos" in d:
        raise SpecError(_join(path, "min_cos"), "requires 'normal'")
    views = None
    if "views" in d:
        views = [_str(v, f"{path}.views[{i}]") for i, v in enumerate(_list(d["views"], _join(path, "views")))]
    return ROI(name, role, lo, hi, normal, min_cos, views)


def _action(a: Any, path: str, scene: Scene) -> dict:
    """Validate one timeline action against ``scene``; return it normalized (vectors as float64 arrays)."""
    if not isinstance(a, dict):
        raise SpecError(path, "expected an object")
    op = _str(a.get("op"), _join(path, "op"), OPS)
    if op == "set_light":
        lname = _str(a.get("light"), _join(path, "light"))
        lt = next((x for x in scene.lights if x.name == lname), None)
        if lt is None:
            raise SpecError(_join(path, "light"), f"no light named {lname!r}")
        fld = RADIOMETRIC_FIELD[lt.type]
        _keys(a, path, ("op", "light", fld))
        return {"op": op, "light": lname, fld: _vec3(a[fld], _join(path, fld), lo=0)}
    if op == "set_transform":
        _keys(a, path, ("op", "object", "transform"))
        oname = _str(a["object"], _join(path, "object"))
        if not any(o.name == oname for o in scene.objects):
            raise SpecError(_join(path, "object"), f"no object named {oname!r}")
        return {"op": op, "object": oname, "transform": _transform(a["transform"], _join(path, "transform"))}
    _keys(a, path, ("op", "material", "albedo"))
    mname = _str(a["material"], _join(path, "material"))
    if mname not in scene.materials:
        raise SpecError(_join(path, "material"), f"no material named {mname!r}")
    return {"op": op, "material": mname, "albedo": _vec3(a["albedo"], _join(path, "albedo"), lo=0, hi=1)}


# ------------------------------------------------------------------------------------------------ parsing

_TOP_REQUIRED = ("spec_version", "name", "group", "image", "materials", "objects", "stations")
_TOP_OPTIONAL = ("description", "failure_mode", "comparison", "origin", "display", "lights", "rois", "timeline",
                 "reference", "oracle")


def parse_scene(d: Any, source: Path | str | None = None) -> Scene:
    """Validate a spec dict and resolve it into a Scene (raises SpecError with a JSON path)."""
    source = Path(source).resolve() if source else None
    try:
        return _parse(d, source)
    except SpecError as e:
        if source and not e.file:
            raise SpecError(e.path, e.msg, source) from None
        raise


def _parse(d: Any, source: Path | None) -> Scene:
    _keys(d, "", _TOP_REQUIRED, _TOP_OPTIONAL)
    if isinstance(d["spec_version"], bool) or d["spec_version"] != SPEC_VERSION:
        raise SpecError("spec_version", f"must be {SPEC_VERSION}, got {d['spec_version']!r}")
    name = _str(d["name"], "name", name=True)
    if source is not None and source.stem != name:
        raise SpecError("name", f"{name!r} must equal the file stem {source.stem!r}")
    group = _str(d["group"], "group", GROUPS)
    if source is not None and source.parent.name in GROUPS and source.parent.name != group:
        raise SpecError("group", f"{group!r} does not match the directory {source.parent.name!r}")
    description = _str(d.get("description", ""), "description")
    failure_mode = _str(d.get("failure_mode", ""), "failure_mode")
    if group == "targeted" and not failure_mode.strip():
        raise SpecError("failure_mode", "targeted scenes must name their single failure mode")
    comparison = _str(d.get("comparison", "exact"), "comparison", ("exact", "appearance"))
    origin = _vec3(d.get("origin", [0.0, 0.0, 0.0]), "origin")
    img = _keys(d["image"], "image", ("width", "height"))
    width = _num(img["width"], "image.width", lo=1, integer=True)
    height = _num(img["height"], "image.height", lo=1, integer=True)
    disp = _keys(d.get("display", {}), "display", optional=("exposure",))
    display = {"exposure": _num(disp.get("exposure", 1.0), "display.exposure", lo=0, lo_open=True)}

    mats = d["materials"]
    if not isinstance(mats, dict) or not mats:
        raise SpecError("materials", "expected a non-empty object of name -> material")
    materials = {}
    for mname, m in mats.items():
        p = f"materials.{mname}"
        _str(mname, p, name=True)
        _keys(m, p, ("type", "albedo"))
        _str(m["type"], _join(p, "type"), ("diffuse",))
        materials[mname] = Material(mname, _vec3(m["albedo"], _join(p, "albedo"), lo=0, hi=1))

    names: dict[str, str] = {}

    def claim(n: str, p: str):
        if n in names:
            raise SpecError(p, f"name {n!r} already used by {names[n]} (object and light names share one namespace)")
        names[n] = p

    objects = []
    for i, o in enumerate(_list(d["objects"], "objects")):
        p = f"objects[{i}]"
        _keys(o, p, ("name", "material", "shape"), ("transform",))
        oname = _str(o["name"], _join(p, "name"), name=True)
        claim(oname, _join(p, "name"))
        mat = _str(o["material"], _join(p, "material"))
        if mat not in materials:
            raise SpecError(_join(p, "material"), f"no material named {mat!r}")
        mesh, shape = _shape(o["shape"], _join(p, "shape"), origin, source)
        tf = _transform(o.get("transform", {}), _join(p, "transform"))
        objects.append(Object(oname, mat, mesh, transform_matrix(tf), shape))
    if not objects:
        raise SpecError("objects", "at least one object is required")

    lights = []
    for i, lt in enumerate(_list(d.get("lights", []), "lights")):
        light = _light(lt, f"lights[{i}]")
        claim(light.name, f"lights[{i}].name")
        lights.append(light)
    envs = [i for i, lt in enumerate(lights) if lt.type == "environment"]
    if len(envs) > 1:
        raise SpecError(f"lights[{envs[1]}]", "at most one environment light")

    stations = {}
    for i, s in enumerate(_list(d["stations"], "stations")):
        st = _station(s, f"stations[{i}]")
        if st.name in stations:
            raise SpecError(f"stations[{i}].name", f"duplicate station {st.name!r}")
        stations[st.name] = st
    if not stations:
        raise SpecError("stations", "at least one station is required")

    rois = []
    for i, r in enumerate(_list(d.get("rois", []), "rois")):
        roi = _roi(r, f"rois[{i}]")
        if any(x.name == roi.name for x in rois):
            raise SpecError(f"rois[{i}].name", f"duplicate ROI {roi.name!r}")
        rois.append(roi)

    ref = _keys(d.get("reference", {}), "reference", optional=REFERENCE_KEYS)
    reference = {k: _num(v, f"reference.{k}", lo=0 if k == "seed" else 1, integer=True) for k, v in ref.items()}
    if "spp" in reference and "batches" in reference and reference["spp"] < reference["batches"]:
        raise SpecError("reference.spp", "must be >= batches")

    oracle = None
    if "oracle" in d:
        o = d["oracle"]
        if not isinstance(o, dict):
            raise SpecError("oracle", "expected an object")
        if "type" not in o:
            raise SpecError("oracle.type", "required")
        _str(o["type"], "oracle.type")
        if not _jsonable(o):
            raise SpecError("oracle", "must be plain JSON")
        if group != "calibration":
            raise SpecError("oracle", "only calibration scenes carry an oracle")
        oracle = copy.deepcopy(o)
    elif group == "calibration":
        raise SpecError("oracle", "calibration scenes must carry an oracle")

    scene = Scene(name=name, group=group, description=description, failure_mode=failure_mode,
                  comparison=comparison, origin=origin, width=width, height=height, display=display,
                  materials=materials, objects=objects, lights=lights, stations=stations, rois=rois,
                  timeline=None, reference=reference, oracle=oracle, source=source)

    if "timeline" in d:
        t = _keys(d["timeline"], "timeline", ("station", "end_frame", "steps"), ("fps",))
        st = _str(t["station"], "timeline.station")
        if st not in stations:
            raise SpecError("timeline.station", f"no station named {st!r}")
        fps = _num(t.get("fps", 60), "timeline.fps", lo=0, lo_open=True)
        end = _num(t["end_frame"], "timeline.end_frame", lo=0, integer=True)
        steps = []
        prev = 0
        for i, s in enumerate(_list(t["steps"], "timeline.steps")):
            p = f"timeline.steps[{i}]"
            _keys(s, p, ("frame", "actions"))
            fr = _num(s["frame"], _join(p, "frame"), lo=1, integer=True)
            if fr <= prev:
                raise SpecError(_join(p, "frame"), f"frames must be strictly increasing and >= 1 (got {fr} after {prev})")
            if fr > end:
                raise SpecError(_join(p, "frame"), f"{fr} is after end_frame {end}")
            acts = [_action(a, f"{p}.actions[{j}]", scene) for j, a in enumerate(_list(s["actions"], _join(p, "actions")))]
            steps.append((fr, acts))
            prev = fr
        scene.timeline = Timeline(st, fps, end, steps)

    view_ids = _view_ids(scene)
    for i, roi in enumerate(rois):
        for j, v in enumerate(roi.views or []):
            if v not in view_ids:
                raise SpecError(f"rois[{i}].views[{j}]", f"no view {v!r} (views: {view_ids})")
    scene.hash = _scene_hash(scene)
    return scene


def load_scene(path) -> Scene:
    """Load, validate and resolve a scene spec file."""
    path = Path(path)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpecError("", "file not found", path) from None
    except json.JSONDecodeError as e:
        raise SpecError("", f"invalid JSON: {e}", path) from None
    return parse_scene(d, path)


# ------------------------------------------------------------------------------------------------ hashes

def _render_state(scene: Scene) -> dict:
    """Everything that affects a rendered pixel (geometry by array hash)."""
    return {
        "materials": {n: m.albedo for n, m in scene.materials.items()},
        "objects": [{"name": o.name, "material": o.material, "matrix": o.transform.reshape(-1),
                     "geometry": o.mesh.hashes()} for o in scene.objects],
        "lights": [{"name": lt.name, "type": lt.type, "params": lt.params} for lt in scene.lights],
    }


def _station_dict(st: Station) -> dict:
    return {"name": st.name, "position": st.position, "look_at": st.look_at, "up": st.up, "vfov_deg": st.vfov_deg}


def _actions_json(actions: list) -> list:
    return [dict(a) for a in actions]


def _scene_hash(scene: Scene) -> str:
    tl = scene.timeline
    return sha256_json({
        "spec_version": SPEC_VERSION, "name": scene.name, "group": scene.group, "description": scene.description,
        "failure_mode": scene.failure_mode, "comparison": scene.comparison, "origin": scene.origin,
        "image": [scene.width, scene.height], "display": scene.display, "state": _render_state(scene),
        "shapes": [o.shape for o in scene.objects],
        "stations": [_station_dict(s) for s in scene.stations.values()],
        "rois": [{"name": r.name, "role": r.role, "min": r.box_min, "max": r.box_max, "normal": r.normal,
                  "min_cos": r.min_cos, "views": r.views} for r in scene.rois],
        "timeline": None if tl is None else {"station": tl.station, "fps": tl.fps, "end_frame": tl.end_frame,
                                             "steps": [[f, _actions_json(a)] for f, a in tl.steps]},
        "reference": scene.reference, "oracle": scene.oracle,
    })


def _view_hash(state: Scene, station: Station) -> str:
    return sha256_json({"state": _render_state(state), "camera": _station_dict(station),
                        "image": [state.width, state.height]})


# ------------------------------------------------------------------------------------------------ actions / views

def _copy_scene(scene: Scene) -> Scene:
    return replace(
        scene,
        materials={n: Material(m.name, m.albedo.copy()) for n, m in scene.materials.items()},
        objects=[Object(o.name, o.material, o.mesh, o.transform.copy(), o.shape) for o in scene.objects],
        lights=[Light(lt.name, lt.type, {k: np.array(v, dtype=np.float64) for k, v in lt.params.items()})
                for lt in scene.lights],
        display=dict(scene.display), reference=dict(scene.reference),
    )


def apply_actions(scene: Scene, actions: Iterable[dict]) -> Scene:
    """Return a new Scene with the timeline actions applied in order (the input is not modified)."""
    out = _copy_scene(scene)
    for i, a in enumerate(actions):
        a = _action(a, f"actions[{i}]", out)
        if a["op"] == "set_light":
            lt = out.light(a["light"])
            fld = RADIOMETRIC_FIELD[lt.type]
            lt.params[fld] = np.array(a[fld], dtype=np.float64)
        elif a["op"] == "set_transform":
            out.object(a["object"]).transform = transform_matrix(a["transform"])
        else:
            out.materials[a["material"]].albedo = np.array(a["albedo"], dtype=np.float64)
    out.hash = _scene_hash(out)
    return out


def timeline_states(scene: Scene) -> list[tuple[int, int]]:
    """[(first_frame, last_frame)] per state, inclusive (DESIGN §2 Views); [] without a timeline."""
    tl = scene.timeline
    if tl is None:
        return []
    starts = [0] + [f for f, _ in tl.steps]
    ends = [f - 1 for f, _ in tl.steps] + [tl.end_frame]
    return list(zip(starts, ends))


def state_at_frame(scene: Scene, k: int) -> Scene:
    """The scene as drawn at frame k: every action scheduled at frames <= k applied."""
    if scene.timeline is None:
        return scene
    acts = [a for f, step in scene.timeline.steps if f <= k for a in step]
    return apply_actions(scene, acts) if acts else scene


def capture_kind(scene: Scene) -> str:
    """'timeline' for timeline scenes, else 'stations' (bundle/capture kind, DESIGN §4.2)."""
    return "timeline" if scene.timeline is not None else "stations"


def _view_ids(scene: Scene) -> list[str]:
    if scene.timeline is None:
        return list(scene.stations)
    return [f"state{i}" for i in range(len(scene.timeline.steps) + 1)]


def expand_views(scene: Scene) -> list[View]:
    """One view per station, or one per timeline state (capture_frame = last frame of the state)."""
    if scene.timeline is None:
        return [View(id=st.name, scene=scene.name, kind="station", station=st, state_index=None,
                     capture_frame=None, state=scene, hash=_view_hash(scene, st)) for st in scene.stations.values()]
    tl = scene.timeline
    st = scene.stations[tl.station]
    views = []
    state = scene
    for i, (first, last) in enumerate(timeline_states(scene)):
        if i > 0:
            state = apply_actions(state, tl.steps[i - 1][1])
        views.append(View(id=f"state{i}", scene=scene.name, kind="state", station=st, state_index=i,
                          capture_frame=last, state=state, hash=_view_hash(state, st), frame_range=(first, last)))
    return views


def views_summary(scene: Scene, views: list[View] | None = None) -> dict:
    """JSON-ready description of a scene's views (written to runs/<id>/views/<scene>.json)."""
    views = expand_views(scene) if views is None else views
    return {
        "views_version": 1, "scene": scene.name, "group": scene.group, "kind": capture_kind(scene),
        "comparison": scene.comparison, "failure_mode": scene.failure_mode,
        "image": {"width": scene.width, "height": scene.height}, "scene_hash": scene.hash,
        "fps": scene.timeline.fps if scene.timeline else None,
        "end_frame": scene.timeline.end_frame if scene.timeline else None,
        "steps": [f for f, _ in scene.timeline.steps] if scene.timeline else [],
        "views": [{"id": v.id, "kind": v.kind, "station": v.station.name, "state_index": v.state_index,
                   "capture_frame": v.capture_frame, "frames": list(v.frame_range) if v.frame_range else None,
                   "hash": v.hash} for v in views],
    }


# ------------------------------------------------------------------------------------------------ discovery / CLI

def discover_scenes(selector: str | Sequence[str] = "all", root: Path | str | None = None) -> list[Path]:
    """Scene files under ``root``/<group>/*.json matching the selector.

    selector: 'all', a group name, a scene name (file stem), or a path to a .json file; a comma-separated
    string or a list combines several. Raises SpecError when a token matches nothing.
    """
    root = Path(root) if root is not None else SCENES_ROOT
    tokens = [t.strip() for t in selector.split(",")] if isinstance(selector, str) else [str(t) for t in selector]
    tokens = [t for t in tokens if t]
    files = []
    for g in GROUPS:
        gd = root / g
        if gd.is_dir():
            files += sorted(gd.glob("*.json"))
    out: list[Path] = []
    for tok in tokens or ["all"]:
        if tok == "all":
            hit = files
        elif tok in GROUPS:
            hit = [f for f in files if f.parent.name == tok]
        elif tok.endswith(".json") and Path(tok).is_file():
            hit = [Path(tok)]
        else:
            hit = [f for f in files if f.stem == tok]
        if not hit and tok not in ("all",) + GROUPS:
            raise SpecError("", f"no scene matches {tok!r} under {root}")
        out += [h for h in hit if h not in out]
    return out


def _scene_files_in(p: Path) -> list[Path]:
    if p.is_file():
        return [p]
    out = []
    for f in sorted(p.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out.append(f)  # let load_scene report it
            continue
        if isinstance(d, dict) and "spec_version" in d:
            out.append(f)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.spec", description="Validate scene specs and list views.")
    ap.add_argument("paths", nargs="*", default=[str(SCENES_ROOT)], help="scene files or directories")
    ap.add_argument("--check", action="store_true", help="validate and list views (default action)")
    ap.add_argument("--json", action="store_true", help="print the expanded views as JSON")
    args = ap.parse_args(argv)
    files: list[Path] = []
    for p in args.paths:
        pp = Path(p)
        if not pp.exists():
            print(f"FAIL {p}: no such file or directory")
            return 1
        files += _scene_files_in(pp)
    failed = 0
    summaries = []
    for f in files:
        try:
            scene = load_scene(f)
            views = expand_views(scene)
        except SpecError as e:
            failed += 1
            print(f"FAIL {e}")
            continue
        summaries.append(views_summary(scene, views))
        if not args.json:
            n_tri = sum(o.mesh.n_triangles for o in scene.objects)
            print(f"ok   {scene.name} [{scene.group}, {scene.comparison}] {scene.width}x{scene.height} "
                  f"{len(scene.objects)} objects/{n_tri} tris, {len(scene.lights)} lights, {len(views)} views")
            for v in views:
                extra = f" capture_frame={v.capture_frame} frames={v.frame_range[0]}..{v.frame_range[1]}" \
                    if v.kind == "state" else ""
                print(f"       {v.id:<12} {v.kind:<8} camera={v.station.name}{extra} hash={v.hash[:12]}")
    if args.json:
        print(json.dumps(summaries, indent=1))
    print(f"{len(files) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
