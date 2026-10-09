#!/usr/bin/env python3
"""Write the scene specs under scenes/ (DESIGN §2, §8). docs/SCENES.md explains what each scene isolates.

The JSON files are the contract that every tool reads; this script is how they were produced, so derived numbers
(the handedness pixel positions, the world-coordinate survey OBJ, the courtyard's boxes and openings) stay
consistent with each other. tests/test_scenes.py checks that the files on disk match this script.

    python scenes/generate.py            # (re)write scenes/<group>/*.json, scenes/meshes/*.obj, phase0_parity.json
    python scenes/generate.py --check    # exit 1 when a file differs from what this script would write
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.oracles import project_point  # noqa: E402

SURVEY_ORIGIN = [346000.0, 6297000.0, 570.0]  # UTM 19S (metres), local frame = world - origin
W, H = 256, 192
REF_CAL = {"spp": 1024, "batches": 4}
REF_FURNACE = {"spp": 4096, "batches": 4}  # rho = 0.8: ~5 bounces per path on average, 4x the samples
REF_TARGETED = {"spp": 4096, "batches": 4}
REF_REALWORLD = {"spp": 2048, "batches": 4}
TIMELINE = {"fps": 60, "end_frame": 359, "steps": (120, 240)}


# ------------------------------------------------------------------------------------------------ helpers

def clean(x):
    """Round floats to 7 decimals (no -0.0) so the JSON is stable and readable."""
    if isinstance(x, float):
        v = round(x, 7) + 0.0
        return v
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def fmt(obj, indent: int = 0, prefix: int = 0, width: int = 118) -> str:
    """JSON with nested structures broken over lines only when they do not fit on one."""
    one = json.dumps(obj, separators=(", ", ": "))  # ASCII only: safe under any default encoding
    if not isinstance(obj, (dict, list)) or not obj or indent + prefix + len(one) <= width:
        return one
    pad, inner = " " * indent, " " * (indent + 2)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            key = json.dumps(k) + ": "
            parts.append(inner + key + fmt(v, indent + 2, len(key), width))
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"
    return "[\n" + ",\n".join(inner + fmt(v, indent + 2, 0, width) for v in obj) + "\n" + pad + "]"


def mat(albedo):
    return {"type": "diffuse", "albedo": list(albedo)}


def box(name, material, lo, hi, transform=None):
    o = {"name": name, "material": material, "shape": {"type": "box", "min": list(lo), "max": list(hi)}}
    if transform:
        o["transform"] = transform
    return o


def quad(name, material, origin, u, v):
    return {"name": name, "material": material, "shape": {"type": "quad", "origin": list(origin), "u": list(u),
                                                         "v": list(v)}}


def room(name, material, lo, hi, thickness, omit=(), openings=()):
    s = {"type": "room", "min": list(lo), "max": list(hi), "thickness": thickness}
    if omit:
        s["omit"] = list(omit)
    if openings:
        s["openings"] = [{"wall": w, "u": list(u), "v": list(v)} for w, u, v in openings]
    return {"name": name, "material": material, "shape": s}


def point(name, position, intensity):
    return {"name": name, "type": "point", "position": list(position), "intensity": list(intensity)}


def sun(name, direction, irradiance):
    return {"name": name, "type": "directional", "direction": list(direction), "irradiance": list(irradiance)}


def rect(name, origin, u, v, radiance, albedo=None):
    d = {"name": name, "type": "rect", "origin": list(origin), "u": list(u), "v": list(v), "radiance": list(radiance)}
    if albedo is not None:
        d["albedo"] = list(albedo)
    return d


def sky(name, radiance):
    return {"name": name, "type": "environment", "radiance": list(radiance)}


def station(name, position, look_at, vfov=60.0, up=None):
    d = {"name": name, "position": list(position), "look_at": list(look_at)}
    if up is not None:
        d["up"] = list(up)
    d["vfov_deg"] = vfov
    return d


def roi(name, role, lo, hi, normal=None, min_cos=None, views=None):
    d = {"name": name, "role": role, "box": {"min": list(lo), "max": list(hi)}}
    if normal is not None:
        d["normal"] = list(normal)
        if min_cos is not None:
            d["min_cos"] = min_cos
    if views is not None:
        d["views"] = list(views)
    return d


def sun_direction(zenith_deg: float, travel_azimuth_deg: float):
    """Unit direction the light travels: azimuth of its horizontal travel (from +x toward +y), angle from zenith."""
    z, a = math.radians(zenith_deg), math.radians(travel_azimuth_deg)
    return [math.sin(z) * math.cos(a), math.sin(z) * math.sin(a), -math.cos(z)]


def scene(name, group, description, *, materials, objects, lights, stations, rois, reference, failure_mode=None,
          comparison=None, origin=None, exposure=1.0, timeline=None, oracle=None, width=W, height=H):
    d = {"spec_version": 1, "name": name, "group": group, "description": description}
    if failure_mode:
        d["failure_mode"] = failure_mode
    if comparison:
        d["comparison"] = comparison
    if origin is not None:
        d["origin"] = list(origin)
    d["image"] = {"width": width, "height": height}
    d["display"] = {"exposure": exposure}
    d.update(materials=materials, objects=objects, lights=lights, stations=stations, rois=rois)
    if timeline is not None:
        d["timeline"] = timeline
    d["reference"] = dict(reference)
    if oracle is not None:
        d["oracle"] = oracle
    return clean(d)


def timeline_block(station_name, actions_by_step):
    steps = [{"frame": f, "actions": acts} for f, acts in zip(TIMELINE["steps"], actions_by_step, strict=True)]
    return {"station": station_name, "fps": TIMELINE["fps"], "end_frame": TIMELINE["end_frame"], "steps": steps}


# ------------------------------------------------------------------------------------------------ calibration

PLANE_ALBEDO = [0.8, 0.65, 0.5]
POINT_PLANE = {"origin": [-4.25, -3.125, 0.0], "u": [8.5, 0.0, 0.0], "v": [0.0, 6.25, 0.0]}
POINT_LAMP = point("lamp", [0.375, -0.25, 1.25], [6.0, 5.0, 4.0])
TOP = station("s0", [0.0, 0.0, 3.5], [0.0, 0.0, 0.0], 60.0, up=[0.0, 1.0, 0.0])
PLANE_ROI = roi("plane", "oracle", [-4.25, -3.125, -0.01], [4.25, 3.125, 0.01], [0, 0, 1], 0.99)


def cal_point_plane():
    return scene(
        "cal_point_plane", "calibration",
        "Point light 1.25 m above a coloured diffuse plane, off-centre, seen from straight above. Checks point-light "
        "intensity units (W/sr), the inverse-square law, the Lambert 1/pi and the light's position (an x/y sign "
        "error moves the hot spot).",
        exposure=1.5,
        materials={"plane": mat(PLANE_ALBEDO)},
        objects=[quad("plane", "plane", **POINT_PLANE)],
        lights=[POINT_LAMP], stations=[TOP], rois=[PLANE_ROI], reference=REF_CAL,
        oracle={"type": "point_plane", "light": "lamp", "object": "plane"})


def survey_obj_text() -> str:
    o, u, v = (POINT_PLANE[k] for k in ("origin", "u", "v"))
    corners = [o, [o[0] + u[0], o[1], o[2]], [o[0] + u[0], o[1] + v[1], o[2]], [o[0], o[1] + v[1], o[2]]]
    lines = ["# cal_survey_origin ground plane in WORLD (survey) coordinates: UTM 19S metres.",
             f"# Survey origin {SURVEY_ORIGIN}; local = world - origin, computed in float64 by the resolver.",
             "# The local plane equals cal_point_plane's quad exactly: x in [-4.25, 4.25], y in [-3.125, 3.125],",
             "# z = 0.",
             "# The y values (e.g. 6296996.875) are not representable in float32 (spacing 0.5 there), so a resolver",
             "# that casts world coordinates to float32 before subtracting the origin moves the plane by up to 0.25 m."]
    for c in corners:
        w = [SURVEY_ORIGIN[i] + c[i] for i in range(3)]
        lines.append("v {:.4f} {:.4f} {:.4f}".format(*w))
    lines.append("f 1 2 3 4")
    return "\n".join(lines) + "\n"


def cal_survey_origin():
    return scene(
        "cal_survey_origin", "calibration",
        "cal_point_plane with a UTM survey origin: the plane is a world-coordinate OBJ "
        "(scenes/meshes/survey_plane.obj) and every other position is local. The image must equal "
        "cal_point_plane's; checks float64 -> float32 local resolution.",
        origin=SURVEY_ORIGIN,
        exposure=1.5,
        materials={"plane": mat(PLANE_ALBEDO)},
        objects=[{"name": "plane", "material": "plane",
                  "shape": {"type": "mesh", "file": "meshes/survey_plane.obj", "coords": "world"}}],
        lights=[POINT_LAMP], stations=[TOP], rois=[PLANE_ROI], reference=REF_CAL,
        oracle={"type": "survey_origin", "light": "lamp", "object": "plane", "equivalent": "cal_point_plane"})


def cal_sun_plane():
    # Plane normal (-0.2, 0.3, 1)/|.|, tilted ~19.5 deg, so every component of the sun direction changes the result:
    # cos = 0.984 as specified, 0.890 with x flipped, 0.740 with y flipped, 0 with the direction reversed.
    u = [10.0, 0.0, 2.0]
    v = [0.48, 8.32, -2.4]
    o = [-(u[i] + v[i]) / 2 for i in range(3)]
    return scene(
        "cal_sun_plane", "calibration",
        "Directional light 30 deg from the zenith on a plane tilted ~19.5 deg about an oblique axis, seen from above. "
        "Checks irradiance units (W/m^2 perpendicular to the beam) and the direction: reversing it darkens the plane, "
        "flipping its x or y component changes the brightness by 10-25 %.",
        exposure=1.5,
        materials={"plane": mat([0.7, 0.75, 0.8])},
        objects=[quad("plane", "plane", o, u, v)],
        lights=[sun("sun", sun_direction(30.0, -60.0), [3.0, 2.6, 2.2])],
        stations=[station("s0", [0.0, 0.0, 4.0], [0.0, 0.0, 0.0], 60.0, up=[0.0, 1.0, 0.0])],
        rois=[roi("plane", "oracle", [-6.0, -5.0, -2.5], [6.0, 5.0, 2.5], [-0.2, 0.3, 1.0], 0.99)],
        reference=REF_CAL,
        oracle={"type": "sun_plane", "light": "sun", "object": "plane"})


def cal_sky_plane():
    return scene(
        "cal_sky_plane", "calibration",
        "Constant environment over a lone horizontal plane, seen obliquely with the horizon in view. An unoccluded "
        "upward plane reflects rho * L_sky; the sky pixels show L_sky (the background). Checks environment units.",
        exposure=2.0,
        materials={"plane": mat([0.6, 0.7, 0.8])},
        objects=[quad("plane", "plane", [-20.0, -8.0, 0.0], [40.0, 0.0, 0.0], [0.0, 40.0, 0.0])],
        lights=[sky("sky", [0.4, 0.5, 0.7])],
        stations=[station("s0", [0.0, -5.0, 2.2], [0.0, 0.0, 0.0], 60.0)],
        rois=[roi("plane", "oracle", [-20.0, -8.0, -0.01], [20.0, 12.0, 0.01], [0, 0, 1], 0.99)],
        reference=REF_CAL,
        oracle={"type": "sky_plane", "light": "sky", "object": "plane"})


def cal_rect_plane():
    return scene(
        "cal_rect_plane", "calibration",
        "A 1.2 x 0.6 m rect light facing down 1.6 m above a plane (entirely above the plane, so it never crosses a "
        "receiver's horizon). The camera, below the light, sees its emitting face. Checks rect radiance units on a "
        "receiver (polygon form factor) and the facing; the emitter ROI checks the emitted radiance seen directly.",
        exposure=1.0,
        materials={"plane": mat([0.75, 0.7, 0.65])},
        objects=[quad("plane", "plane", [-6.0, -6.0, 0.0], [12.0, 0.0, 0.0], [0.0, 12.0, 0.0])],
        lights=[rect("panel", [-0.6, -0.3, 1.6], [0.0, 0.6, 0.0], [1.2, 0.0, 0.0], [9.0, 8.0, 7.0])],
        stations=[station("s0", [0.4, -3.0, 0.7], [0.0, 0.0, 0.45], 60.0)],
        rois=[roi("plane", "oracle", [-3.0, -3.0, -0.01], [3.0, 3.0, 0.01], [0, 0, 1], 0.99),
              roi("emitter", "oracle", [-0.6, -0.3, 1.59], [0.6, 0.3, 1.61], [0, 0, -1], 0.99)],
        reference=REF_CAL,
        oracle={"type": "rect_plane", "light": "panel", "object": "plane"})


HAND_SUN = {"direction": [0.0, 0.0, -1.0], "irradiance": [3.0, 3.0, 3.0]}  # straight down: cos = 1 on the quads


def cal_handedness():
    cam = station("s0", [0.0, 0.0, 4.0], [0.0, 0.0, 0.0], 60.0, up=[0.0, 1.0, 0.0])
    st = SimpleNamespace(position=cam["position"], look_at=cam["look_at"], up=cam["up"], vfov_deg=cam["vfov_deg"])
    size, z = 0.6, 0.01
    specs = [("red", [1.5, 0.0], [0.8, 0.0, 0.0]), ("green", [0.0, 1.2], [0.0, 0.8, 0.0]),
             ("white", [0.0, 0.0], [0.8, 0.8, 0.8])]
    d = HAND_SUN["direction"]
    cos = -d[2] / math.sqrt(sum(c * c for c in d))  # n = +z for every quad
    objects = [quad("floor", "floor", [-4.0, -3.0, 0.0], [8.0, 0.0, 0.0], [0.0, 6.0, 0.0])]
    quads = []
    for name, (cx, cy), albedo in specs:
        objects.append(quad(name, name, [cx - size / 2, cy - size / 2, z], [size, 0.0, 0.0], [0.0, size, 0.0]))
        px, py = project_point(st, W, H, [cx, cy, z])  # a quad parallel to the image plane: centroid = centre
        rad = [a / math.pi * e * cos for a, e in zip(albedo, HAND_SUN["irradiance"], strict=True)]
        quads.append({"object": name, "pixel": [round(px, 3), round(py, 3)], "radiance": rad})
    return scene(
        "cal_handedness", "calibration",
        "Camera above the origin looking down -Z with up +Y. Three diffuse 0.6 m quads 1 cm above a dark floor, lit "
        "by a sun from straight above: red centred at +x (must appear on the image's right), green at +y (top), "
        "white at the origin (centre). Checks handedness, image orientation (row 0 = top) and linear output (each "
        "quad shows rho/pi * E * cos). No rect lights, so every engine can run it.",
        exposure=1.6,
        materials={"floor": mat([0.05, 0.05, 0.05]), "red": mat([0.8, 0.0, 0.0]), "green": mat([0.0, 0.8, 0.0]),
                   "white": mat([0.8, 0.8, 0.8])},
        objects=objects,
        lights=[sun("sun", HAND_SUN["direction"], HAND_SUN["irradiance"])], stations=[cam],
        rois=[roi("quads", "oracle", [-0.35, -0.35, 0.009], [1.85, 1.55, 0.011], [0, 0, 1], 0.99)],
        reference=REF_CAL,
        oracle={"type": "handedness", "light": "sun", "object": "floor", "tolerance_px": 1.0, "quads": quads})


FURNACE_ALBEDO = 0.8  # full = 5 L_e, direct = 1.8 L_e, isolated = 3.2 L_e: one bounce (0.8 L_e) != full GI


def cal_furnace():
    rho = FURNACE_ALBEDO
    Le, albedo, e = [1.0, 0.9, 0.8], [rho] * 3, 0.001  # faces overlap by 1 mm beyond the edges: no cracks
    a, b = 2.0 + 2 * e, -1.0 - e
    faces = [  # (name, origin, u, v) with normalize(u x v) pointing into the box
        ("floor", [b, b, 0.0], [a, 0, 0], [0, a, 0]),
        ("ceiling", [b, b, 2.0], [0, a, 0], [a, 0, 0]),
        ("wall_nx", [-1.0, b, -e], [0, a, 0], [0, 0, a]),
        ("wall_px", [1.0, b, -e], [0, 0, a], [0, a, 0]),
        ("wall_ny", [b, -1.0, -e], [0, 0, a], [a, 0, 0]),
        ("wall_py", [b, 1.0, -e], [a, 0, 0], [0, 0, a]),
    ]
    return scene(
        "cal_furnace", "calibration",
        "White furnace: a closed 2 x 2 x 2 m box whose six inner faces are rect lights with radiance L_e and albedo "
        "0.8, camera inside. full = L_e/(1-rho) = 5 L_e, direct = L_e (1+rho) = 1.8 L_e, isolated = "
        "L_e rho^2/(1-rho) = 3.2 L_e everywhere, so a single bounce (0.8 L_e) is told apart from full GI. Checks "
        "energy conservation. The 'anchor' box below the furnace is never seen (spec v1 needs one object).",
        exposure=0.26,
        materials={"anchor": mat([0.5, 0.5, 0.5])},
        objects=[box("anchor", "anchor", [-0.05, -0.05, -5.05], [0.05, 0.05, -4.95])],
        lights=[rect(n, o, u, v, Le, albedo) for n, o, u, v in faces],
        stations=[station("s0", [0.0, -0.55, 0.9], [0.35, 1.0, 1.25], 75.0)],
        rois=[roi("box", "oracle", [-1.01, -1.01, -0.01], [1.01, 1.01, 2.01])],
        reference=REF_FURNACE,
        oracle={"type": "furnace", "radiance": Le, "albedo": albedo})


# ------------------------------------------------------------------------------------------------ targeted

PLASTER = [0.75, 0.75, 0.72]


def sealed_room():
    return scene(
        "sealed_room", "targeted",
        "Two separate closed rooms (0.25 m walls, 1.5 m apart). A point light in one; the other has no light and no "
        "opening, so in the reference every surface in it is exactly black. One station in each room.",
        failure_mode="light leaking into a sealed, unlit room through 0.25 m walls",
        exposure=0.2,
        materials={"plaster": mat(PLASTER)},
        objects=[room("room_lit", "plaster", [-5.0, -2.0, 0.0], [-1.0, 2.0, 2.5], 0.25),
                 room("room_dark", "plaster", [1.0, -2.0, 0.0], [5.0, 2.0, 2.5], 0.25)],
        lights=[point("lamp", [-3.0, 0.6, 1.9], [12.0, 11.0, 10.0])],
        stations=[station("lit", [-4.6, -1.6, 1.6], [-2.0, 1.0, 0.7], 70.0),
                  station("dark", [1.4, -1.6, 1.6], [4.0, 1.0, 0.7], 70.0)],
        rois=[roi("lit_floor", "lit", [-5.0, -2.0, -0.01], [-1.0, 2.0, 0.01], [0, 0, 1], views=["lit"]),
              roi("dark_room", "dark", [0.99, -2.01, -0.01], [5.01, 2.01, 2.51], views=["dark"])],
        reference=REF_TARGETED)


def thin_wall():
    return scene(
        "thin_wall", "targeted",
        "A 6 x 4 x 2.5 m room split in two by a 5 cm wall (embedded into the floor, ceiling and side walls, so the "
        "unlit half is sealed). A point light 0.3 m from the wall lights one half; the other half is exactly black "
        "in the reference. Stations on both sides.",
        failure_mode="light leaking through a 5 cm wall next to a point light 0.3 m away (shadow-map bias and "
                     "filtering at the base of the wall)",
        exposure=0.6,
        materials={"plaster": mat(PLASTER)},
        objects=[room("room", "plaster", [-3.0, -2.0, 0.0], [3.0, 2.0, 2.5], 0.2),
                 box("wall", "plaster", [-0.025, -2.1, -0.1], [0.025, 2.1, 2.6])],
        lights=[point("lamp", [0.325, 0.0, 1.0], [2.0, 1.9, 1.7])],
        stations=[station("lit", [2.7, -1.7, 1.6], [0.2, 0.6, 0.5], 70.0),
                  station("dark", [-2.7, -1.7, 1.6], [-0.2, 0.6, 0.5], 70.0)],
        rois=[roi("lit_floor", "lit", [0.025, -1.9, -0.01], [1.5, 1.9, 0.01], [0, 0, 1], views=["lit"]),
              roi("base_floor", "dark", [-0.6, -1.9, -0.01], [-0.025, 1.9, 0.01], [0, 0, 1], views=["dark"]),
              roi("base_wall", "dark", [-0.035, -1.9, 0.0], [-0.015, 1.9, 0.6], [-1, 0, 0], views=["dark"]),
              roi("dark_half", "dark", [-3.01, -2.01, -0.01], [-0.02, 2.01, 2.51], views=["dark"])],
        reference=REF_TARGETED)


def _divider(material, door_y=(-0.5, 0.5), door_top=2.0, x=(-0.1, 0.1), y=(-2.1, 2.1), z=(-0.1, 2.6)):
    """Interior wall across a room at x with a doorway: two side pieces and a lintel, embedded into the shell."""
    return [box("divider_s", material, [x[0], y[0], z[0]], [x[1], door_y[0], z[1]]),
            box("divider_n", material, [x[0], door_y[1], z[0]], [x[1], y[1], z[1]]),
            box("lintel", material, [x[0], door_y[0], door_top], [x[1], door_y[1], z[1]])]


def opening():
    return scene(
        "opening", "targeted",
        "Two 4 x 4 m rooms joined by a 1 x 2 m doorway in a 0.2 m wall. A point light in room A (x < 0); both "
        "stations are in room B. The floor just past the doorway gets direct light; room B's far corner gets light "
        "only by bounces.",
        failure_mode="indirect light through a 1 x 2 m doorway into the adjoining room (the far corner is lit only "
                     "by bounces)",
        exposure=1.0,
        materials={"plaster": mat(PLASTER)},
        objects=[room("room", "plaster", [-4.0, -2.0, 0.0], [4.0, 2.0, 2.5], 0.2)] + _divider("plaster"),
        lights=[point("lamp", [-1.5, -1.2, 2.2], [10.0, 9.4, 8.4])],
        stations=[station("toward_door", [3.7, 1.6, 1.6], [0.0, -0.3, 0.8], 70.0),
                  station("far_corner", [0.8, 1.6, 1.7], [4.0, -1.7, 0.4], 70.0)],
        rois=[roi("door_floor", "lit", [0.1, -0.9, -0.01], [1.6, 0.9, 0.01], [0, 0, 1], views=["toward_door"]),
              roi("far_corner", "lit", [2.9, -2.01, -0.01], [4.01, -0.9, 1.2], views=["far_corner"])],
        reference=REF_TARGETED)


def offscreen_source():
    return scene(
        "offscreen_source", "targeted",
        "A 6 x 4 m room lit only by a sun through a window in the -x wall, behind both cameras: the bright floor "
        "patch is never in view, so everything the cameras see is indirect. The +y wall is red; the white floor "
        "and ceiling next to it pick up red bounce light.",
        failure_mode="indirect light from a bright sunlit patch outside the camera's view, with red colour bleeding "
                     "from a side wall",
        exposure=12.0,
        materials={"white": mat([0.8, 0.8, 0.8]), "red": mat([0.8, 0.12, 0.1])},
        objects=[room("room", "white", [0.0, -2.0, 0.0], [6.0, 2.0, 2.7], 0.2, omit=["+y"],
                      openings=[("-x", (-0.8, 0.8), (0.8, 2.2))]),
                 box("red_wall", "red", [0.0, 2.0, 0.0], [6.0, 2.2, 2.7])],
        lights=[sun("sun", sun_direction(50.0, 10.0), [6.0, 5.6, 5.0])],
        stations=[station("s0", [3.1, -1.4, 1.5], [6.0, 0.9, 0.9], 60.0),
                  station("s1", [3.0, -1.6, 1.0], [5.6, 1.7, 2.4], 60.0)],
        rois=[roi("bleed_floor", "bleed", [2.5, 1.0, -0.01], [6.0, 2.0, 0.01], [0, 0, 1], views=["s0"]),
              roi("bleed_ceiling", "bleed", [2.5, 1.0, 2.69], [6.0, 2.0, 2.71], [0, 0, -1], views=["s1"]),
              roi("far_wall", "lit", [5.99, -2.0, 0.0], [6.01, 2.0, 2.7], [-1, 0, 0])],
        reference=REF_TARGETED)


def occluded_canyon():
    return scene(
        "occluded_canyon", "targeted",
        "Two 20 m tall blocks 6 m apart (60 m long) on open ground, under a sun 35 deg high that crosses the street "
        "at 20 deg, plus a sky. No sunlight reaches the street or the lower 15 m of the walls between the blocks; "
        "they see a narrow slot of sky and the sunlit upper part of the east block. Street-level stations.",
        failure_mode="sky and bounce light in a deep, sun-shadowed street canyon (6 m wide, 20 m walls): the sky "
                     "must be occluded and the street lit by bounces from the sunlit upper facade",
        exposure=2.5,
        materials={"ground": mat([0.5, 0.5, 0.5]), "facade": mat([0.7, 0.65, 0.6])},
        objects=[box("ground", "ground", [-60.0, -60.0, -0.3], [60.0, 60.0, 0.0]),
                 box("block_w", "facade", [-23.0, -30.0, -0.1], [-3.0, 30.0, 20.0]),
                 box("block_e", "facade", [3.0, -30.0, -0.1], [23.0, 30.0, 20.0])],
        lights=[sun("sun", sun_direction(55.0, 20.0), [8.0, 7.6, 7.0]), sky("sky", [0.3, 0.4, 0.6])],
        stations=[station("street", [0.0, -12.0, 1.7], [0.3, 10.0, 3.0], 60.0),
                  station("low_wall", [-2.0, 1.0, 1.6], [3.0, 6.0, 1.0], 60.0)],
        rois=[roi("street", "lit", [-3.0, -20.0, -0.01], [3.0, 20.0, 0.01], [0, 0, 1]),
              roi("low_wall_w", "lit", [-3.01, -20.0, 0.0], [-2.99, 20.0, 3.0], [1, 0, 0], views=["street"]),
              roi("low_wall_e", "lit", [2.99, -20.0, 0.0], [3.01, 20.0, 3.0], [-1, 0, 0])],
        reference=REF_TARGETED)


# ------------------------------------------------------------------------------------------------ timeline

def dyn_light_switch():
    on = [10.0, 9.2, 8.0]
    return scene(
        "dyn_light_switch", "targeted",
        "A 6 x 4 m room with a point light that switches off at frame 120 and on again at frame 240 (60 fps). A "
        "shelf shadows part of the floor from the lamp, so that ROI is lit only by bounces.",
        failure_mode="stale indirect light after a light switches off and on (afterglow and re-convergence)",
        exposure=0.5,
        materials={"plaster": mat(PLASTER), "wood": mat([0.6, 0.5, 0.4])},
        objects=[room("room", "plaster", [0.0, 0.0, 0.0], [6.0, 4.0, 2.6], 0.2),
                 box("shelf", "wood", [2.6, 1.0, -0.05], [2.9, 4.05, 1.8])],
        lights=[point("lamp", [1.2, 2.5, 2.0], on)],
        stations=[station("s0", [5.6, 0.4, 1.7], [2.0, 2.6, 0.5], 70.0)],
        rois=[roi("lit_floor", "lit", [0.0, 0.0, -0.01], [2.6, 1.0, 0.01], [0, 0, 1]),
              roi("behind_shelf", "lit", [2.9, 1.2, -0.01], [5.0, 3.8, 0.01], [0, 0, 1])],
        timeline=timeline_block("s0", [[{"op": "set_light", "light": "lamp", "intensity": [0.0, 0.0, 0.0]}],
                                       [{"op": "set_light", "light": "lamp", "intensity": on}]]),
        reference=REF_TARGETED)


def dyn_door():
    return scene(
        "dyn_door", "targeted",
        "Two rooms joined by a doorway; the lamp is in room A (x < 0), the camera in room B. The door closes the "
        "doorway (it overlaps the jambs, lintel and floor, so room B is sealed and black), swings 90 deg open into "
        "room A at frame 120 and closes again at frame 240.",
        failure_mode="stale or missing indirect light when a door between a lit room and the camera's room opens "
                     "and closes",
        exposure=1.0,
        materials={"plaster": mat(PLASTER), "door": mat([0.6, 0.45, 0.3])},
        objects=[room("room", "plaster", [-4.0, -2.0, 0.0], [4.0, 2.0, 2.5], 0.2)] + _divider("plaster")
        + [box("door", "door", [-0.05, -0.52, -0.05], [0.05, 0.52, 2.02])],
        lights=[point("lamp", [-1.8, -1.0, 2.1], [10.0, 9.4, 8.4])],
        stations=[station("s0", [3.7, 1.6, 1.6], [0.0, -0.3, 0.8], 70.0)],
        rois=[roi("door_floor", "lit", [0.1, -0.9, -0.01], [1.6, 0.9, 0.01], [0, 0, 1]),
              roi("room_b", "any", [0.1, -2.01, -0.01], [4.01, 2.01, 2.51])],
        timeline=timeline_block("s0", [
            [{"op": "set_transform", "object": "door",
              "transform": {"translate": [0.0, 0.0, 0.0], "rotate_z_deg": -90.0, "pivot": [0.0, 0.5, 0.0]}}],
            [{"op": "set_transform", "object": "door",
              "transform": {"translate": [0.0, 0.0, 0.0], "rotate_z_deg": 0.0, "pivot": [0.0, 0.0, 0.0]}}]]),
        reference=REF_TARGETED)


def dyn_material():
    return scene(
        "dyn_material", "targeted",
        "A 6 x 4 m white room; a 5.2 x 2.4 m panel on the +y wall changes albedo red -> green (frame 120) -> white "
        "(frame 240) under a fixed point light. The white floor in front of it shows the bounce colour.",
        failure_mode="stale colour bleeding after a large wall changes material (red to green to white)",
        exposure=0.4,
        materials={"white": mat([0.8, 0.8, 0.8]), "paint": mat([0.8, 0.1, 0.08])},
        objects=[room("room", "white", [0.0, 0.0, 0.0], [6.0, 4.0, 2.6], 0.2),
                 box("panel", "paint", [0.4, 3.85, -0.05], [5.6, 4.05, 2.4])],
        lights=[point("lamp", [3.0, 2.6, 2.0], [9.0, 8.6, 8.0])],
        stations=[station("s0", [3.0, 0.3, 1.7], [3.0, 3.3, 0.5], 65.0)],
        rois=[roi("bleed_floor", "bleed", [0.6, 2.6, -0.01], [5.4, 3.85, 0.01], [0, 0, 1]),
              roi("panel", "any", [0.4, 3.84, 0.0], [5.6, 3.86, 2.4], [0, -1, 0])],
        timeline=timeline_block("s0", [[{"op": "set_material", "material": "paint", "albedo": [0.1, 0.7, 0.12]}],
                                       [{"op": "set_material", "material": "paint", "albedo": [0.8, 0.8, 0.8]}]]),
        reference=REF_TARGETED)


# ------------------------------------------------------------------------------------------------ realworld

T_WALL = 0.3
G0, G1 = 0.15, 2.95  # ground storey interior z
U0, U1 = 3.25, 6.05  # upper storey interior z (its floor is the ground storey's ceiling slab)
WIN_G, WIN_U, DOOR_G, FRENCH_U = (1.0, 2.4), (4.1, 5.5), (0.15, 2.35), (3.25, 5.5)
WINGS = {  # interior x/y extents
    "south": ((-11.7, 11.7), (-11.7, -6.3)),
    "north": ((-11.7, 11.7), (6.3, 11.7)),
    "west": ((-11.7, -6.3), (-5.7, 5.7)),
    "east": ((6.3, 11.7), (-5.7, 5.7)),
}


def _w(c, w=1.2):
    return (c - w / 2, c + w / 2)


def _openings(wing: str, storey: str) -> list:
    """(wall, u, v) openings of a wing storey; courtyard walls face the 12 x 12 m courtyard."""
    ops = []
    if wing in ("south", "north"):
        court, outer = ("+y", "-y") if wing == "south" else ("-y", "+y")
        side = -9.0 if wing == "south" else 9.0
        if storey == "ground":
            ops.append((court, (-0.6, 0.6), DOOR_G))
            if wing == "south":
                ops += [(court, _w(-2.6, 1.6), WIN_G), (court, _w(2.6, 1.6), WIN_G),
                        (court, _w(-5.1, 1.0), WIN_G), (court, _w(5.1, 1.0), WIN_G)]
                outer_c = (-9.5, -6.5, 6.5, 9.5)  # none behind the deep room (|x| < 4)
            else:
                ops += [(court, _w(-3.0, 1.4), WIN_G), (court, _w(3.0, 1.4), WIN_G)]
                outer_c = (-9.5, -6.5, -3.5, 3.5, 6.5, 9.5)
            ops += [(outer, _w(c), WIN_G) for c in outer_c]
            ops += [("-x", _w(side), WIN_G), ("+x", _w(side), WIN_G)]
        else:
            if wing == "south":
                ops += [(court, _w(-1.5), FRENCH_U), (court, _w(1.5), FRENCH_U),
                        (court, _w(-4.5), WIN_U), (court, _w(4.5), WIN_U)]
            else:
                ops += [(court, _w(c), WIN_U) for c in (-4.5, -1.5, 1.5, 4.5)]
            ops += [(outer, _w(c), WIN_U) for c in (-9.5, -6.5, -2.0, 2.0, 6.5, 9.5)]
            ops += [("-x", _w(side), WIN_U), ("+x", _w(side), WIN_U)]
    else:
        court, outer = ("+x", "-x") if wing == "west" else ("-x", "+x")
        v = WIN_G if storey == "ground" else WIN_U
        ops += [(court, _w(c), v) for c in (-3.0, 0.0, 3.0)] + [(outer, _w(c), v) for c in (-3.0, 0.0, 3.0)]
    return ops


def _wall_box(wing: str, wall: str, u, v, depth_frac=(0.35, 0.65)):
    """A box inside a wall opening: u/v ranges in the wall plane, spanning depth_frac of the wall's thickness."""
    (x0, x1), (y0, y1) = WINGS[wing]
    t = T_WALL
    if wall in ("+y", "-y"):
        w0 = y1 if wall == "+y" else y0 - t
        a, b = w0 + depth_frac[0] * t, w0 + depth_frac[1] * t
        return [u[0], a, v[0]], [u[1], b, v[1]]
    w0 = x1 if wall == "+x" else x0 - t
    a, b = w0 + depth_frac[0] * t, w0 + depth_frac[1] * t
    return [a, u[0], v[0]], [b, u[1], v[1]]


def courtyard(authored: bool):
    m_wall = {"south": "plaster", "north": "plaster", "west": "plaster", "east": "plaster"}
    materials = {"plaster": mat([0.75, 0.72, 0.68]), "paving": mat([0.5, 0.48, 0.45])}
    if authored:
        m_wall = {"south": "ochre", "north": "lime", "west": "rose", "east": "rose"}
        materials.update({"ochre": mat([0.78, 0.62, 0.42]), "lime": mat([0.8, 0.78, 0.72]),
                          "rose": mat([0.76, 0.58, 0.52]), "terracotta": mat([0.62, 0.36, 0.26]),
                          "frame": mat([0.55, 0.52, 0.48]), "wood": mat([0.55, 0.4, 0.28]),
                          "fabric": mat([0.3, 0.38, 0.6]), "rug": mat([0.62, 0.24, 0.2]),
                          "lawn": mat([0.3, 0.5, 0.2]), "stone": mat([0.66, 0.64, 0.6])})
    objects = [box("ground", "paving", [-60.0, -60.0, -0.5], [60.0, 60.0, 0.0])]
    for wing, ((x0, x1), (y0, y1)) in WINGS.items():
        objects.append(room(f"{wing}_ground", m_wall[wing], [x0, y0, G0], [x1, y1, G1], T_WALL,
                            openings=_openings(wing, "ground")))
        objects.append(room(f"{wing}_upper", m_wall[wing], [x0, y0, U0], [x1, y1, U1], T_WALL, omit=["-z"],
                            openings=_openings(wing, "upper")))
    # South wing, ground storey: a window room (courtyard side) and a deep room behind it, between partitions.
    pm = "plaster" if not authored else "lime"
    objects += [box("part_w", pm, [-4.075, -11.75, 0.1], [-3.925, -6.25, 3.0]),
                box("part_e", pm, [3.925, -11.75, 0.1], [4.075, -6.25, 3.0]),
                box("cross_w", pm, [-4.0, -9.075, 0.1], [-0.5, -8.925, 3.0]),
                box("cross_e", pm, [0.5, -9.075, 0.1], [4.0, -8.925, 3.0]),
                box("cross_lintel", pm, [-0.5, -9.075, 2.25], [0.5, -8.925, 3.0])]
    lights = [sun("sun", sun_direction(45.0, -60.0), [7.5, 7.1, 6.5]), sky("sky", [0.32, 0.42, 0.62])]
    if authored:
        objects += _authored_details()
        lights.append(point("pendant", [-0.6, -10.3, 2.45], [2.2, 1.9, 1.4]))
    name = "courtyard_authored" if authored else "courtyard_simplified"
    desc = ("Two-storey courtyard building (24 x 24 m, 12 x 12 m courtyard, 0.3 m walls) at a Santiago survey "
            "origin under an afternoon sun (45 deg high, from the north-west) and sky. Window and door openings "
            "with rooms behind them; in the south wing a window room facing the courtyard and a windowless deep "
            "room behind it, reached through an internal doorway.")
    if authored:
        desc += (" Authored detail on the same building: window mullions and transoms, a balcony with a railing, "
                 "terracotta roofs, furniture, a lawn and benches, varied albedos and a pendant lamp in the deep room.")
    else:
        desc += " Plain boxes, one plaster albedo."
    rois = [roi("courtyard_ground", "lit", [-6.0, -6.0, -0.01], [6.0, 6.0, 0.04], [0, 0, 1], views=["courtyard"]),
            roi("window_room_floor", "lit", [-3.925, -8.925, 0.14], [3.925, -6.3, 0.17], [0, 0, 1],
                views=["window_room"]),
            roi("deep_room", "any", [-3.925, -11.7, 0.14], [3.925, -9.075, 2.96], views=["deep_room"])]
    return scene(
        name, "realworld", desc, comparison="appearance" if authored else "exact", origin=SURVEY_ORIGIN, exposure=0.7,
        materials=materials, objects=objects, lights=lights,
        stations=[station("courtyard", [2.5, 1.0, 1.7], [-1.0, -6.0, 1.9], 70.0),
                  station("window_room", [3.2, -6.9, 1.6], [-2.0, -8.4, 0.7], 70.0),
                  station("deep_room", [3.2, -11.2, 1.6], [-0.5, -9.0, 1.0], 70.0)],
        rois=rois, reference=REF_REALWORLD)


def _authored_details() -> list:
    objs = []
    k = 0
    for wing in WINGS:
        for storey in ("ground", "upper"):
            for wall, u, v in _openings(wing, storey):
                if v == DOOR_G:
                    continue
                k += 1
                width = u[1] - u[0]
                if width >= 1.0:  # vertical mullion
                    c = (u[0] + u[1]) / 2
                    lo, hi = _wall_box(wing, wall, (c - 0.03, c + 0.03), (v[0] - 0.02, v[1] + 0.02))
                    objs.append(box(f"mullion_{k}", "frame", lo, hi))
                t0 = v[0] + 0.65 * (v[1] - v[0])  # transom
                lo, hi = _wall_box(wing, wall, (u[0] - 0.02, u[1] + 0.02), (t0, t0 + 0.05))
                objs.append(box(f"transom_{k}", "frame", lo, hi))
    # Balcony in front of the south wing's upper French windows (courtyard side, sunlit).
    objs += [box("balcony_slab", "stone", [-2.6, -6.0, 3.05], [2.6, -4.9, 3.25]),
             box("balcony_rail", "frame", [-2.6, -4.95, 4.15], [2.6, -4.9, 4.25]),
             box("balcony_rail_w", "frame", [-2.6, -6.0, 4.15], [-2.55, -4.9, 4.25]),
             box("balcony_rail_e", "frame", [2.55, -6.0, 4.15], [2.6, -4.9, 4.25])]
    for i in range(9):
        x = -2.6 + 0.025 + i * (5.2 - 0.05) / 8
        objs.append(box(f"baluster_{i}", "frame", [x - 0.02, -4.95, 3.2], [x + 0.02, -4.91, 4.2]))
    # Terracotta roof covering on every wing, overhanging the walls by 5 cm.
    for wing, ((x0, x1), (y0, y1)) in WINGS.items():
        e = T_WALL + 0.05
        objs.append(box(f"roof_{wing}", "terracotta", [x0 - e, y0 - e, U1 + T_WALL],
                        [x1 + e, y1 + e, U1 + T_WALL + 0.12]))
    # Courtyard: lawn, benches, planters.
    objs += [box("lawn", "lawn", [-3.5, -1.5, -0.05], [3.5, 3.5, 0.03]),
             box("bench_w", "wood", [-5.4, -2.0, -0.05], [-4.9, 0.0, 0.45]),
             box("bench_e", "wood", [4.9, 2.0, -0.05], [5.4, 4.0, 0.45])]
    for i, (cx, cy) in enumerate(((-5.1, -5.1), (5.1, -5.1), (-5.1, 5.1), (5.1, 5.1))):
        objs.append(box(f"planter_{i}", "terracotta", [cx - 0.45, cy - 0.45, -0.05], [cx + 0.45, cy + 0.45, 0.6]))
    # Window room furniture (x in [-3.925, 3.925], y in [-8.925, -6.3], floor at 0.15).
    objs += [box("rug", "rug", [-2.4, -8.5, 0.1], [0.8, -6.9, 0.16]),
             box("table_top", "wood", [-1.6, -8.1, 0.87], [0.2, -7.3, 0.92])]
    for i, (lx, ly) in enumerate(((-1.55, -8.05), (0.15, -8.05), (-1.55, -7.35), (0.15, -7.35))):
        objs.append(box(f"table_leg_{i}", "wood", [lx - 0.03, ly - 0.03, 0.1], [lx + 0.03, ly + 0.03, 0.87]))
    objs += [box("sofa", "fabric", [-3.85, -8.85, 0.1], [-3.0, -7.0, 0.6]),
             box("sofa_back", "fabric", [-3.95, -8.85, 0.1], [-3.75, -7.0, 1.0]),
             box("shelves", "wood", [3.5, -8.6, 0.1], [3.95, -7.6, 2.0])]
    # Deep room furniture (x in [-3.925, 3.925], y in [-11.7, -9.075]).
    objs += [box("bed", "fabric", [-1.6, -11.75, 0.1], [0.4, -9.8, 0.55]),
             box("headboard", "wood", [-1.6, -11.75, 0.1], [0.4, -11.62, 1.1]),
             box("nightstand", "wood", [0.55, -11.75, 0.1], [1.0, -11.3, 0.6]),
             box("wardrobe", "wood", [-3.95, -11.0, 0.1], [-3.35, -9.6, 2.1])]
    return objs


# ------------------------------------------------------------------------------------------------ outputs

SCENES = {
    "calibration": [cal_point_plane, cal_sun_plane, cal_sky_plane, cal_rect_plane, cal_handedness, cal_furnace,
                    cal_survey_origin],
    "targeted": [sealed_room, thin_wall, opening, offscreen_source, occluded_canyon, dyn_light_switch, dyn_door,
                 dyn_material],
    "realworld": [lambda: courtyard(False), lambda: courtyard(True)],
}

PHASE0_PARITY = {
    "parity_version": 1,
    "description": "Views for the Phase 0 parity and performance gates (DESIGN section 5.4): both three.js runners in "
                   "--parity on each (scene, view, mode). Covers a point light on a plane, shadows at a thin wall, "
                   "a doorway, an off-screen sunlit patch and the realworld courtyard (sun + sky), each in direct "
                   "and probe mode (offscreen_source in probe only: its direct view is black by design).",
    "views": [
        {"scene": "cal_point_plane", "view": "s0", "modes": ["direct"]},
        {"scene": "thin_wall", "view": "lit", "modes": ["direct", "probe"]},
        {"scene": "opening", "view": "toward_door", "modes": ["direct", "probe"]},
        {"scene": "offscreen_source", "view": "s0", "modes": ["probe"]},
        {"scene": "courtyard_simplified", "view": "courtyard", "modes": ["direct", "probe"]},
    ],
}


def outputs() -> dict[Path, str]:
    """{path: text} of every generated file."""
    out = {}
    for group, fns in SCENES.items():
        for fn in fns:
            d = fn()
            assert d["group"] == group
            out[ROOT / group / f"{d['name']}.json"] = fmt(d) + "\n"
    out[ROOT / "meshes" / "survey_plane.obj"] = survey_obj_text()
    out[ROOT / "phase0_parity.json"] = fmt(PHASE0_PARITY) + "\n"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python scenes/generate.py", description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare instead of writing; exit 1 on a difference")
    args = ap.parse_args(argv)
    stale = []
    for path, text in outputs().items():
        old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else None
        if old == text:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    rel = [p.relative_to(REPO).as_posix() for p in stale]
    if args.check:
        print("up to date" if not stale else "stale: " + ", ".join(rel))
        return 1 if stale else 0
    print(f"wrote {len(stale)} file(s)" + (": " + ", ".join(rel) if rel else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
