"""The bundle's three.js scene (DESIGN §5.2) as plain objects, its timeline ops, and the WebGLLights port.

``SceneState`` mirrors what the web runner builds with three.js: meshes with ``MeshLambertMaterial``, visible rect
emitters, PointLight / DirectionalLight / RectAreaLight / HemisphereLight, an optional LightProbe and a colour
background. ``light_uniforms`` ports ``WebGLLights.setup`` + ``setupView`` (src/renderers/webgl/WebGLLights.js) and
``object_uniforms`` the per-draw matrices of ``WebGLRenderer.renderObject`` (WebGLRenderer.js:2160-2161).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import three_math as tm

__all__ = ["Material", "Drawable", "Light", "SceneState", "light_uniforms", "object_uniforms", "light_counts"]


@dataclass
class Material:
    """MeshLambertMaterial: color, emissive (x emissiveIntensity = 1), side."""
    name: str
    color: list[float]
    emissive: list[float]
    side: str = "DoubleSide"


@dataclass
class Drawable:
    """A Mesh (or a rect-light emitter mesh) with its geometry arrays and Matrix4 elements."""
    name: str
    material: Material
    positions: np.ndarray  # (N,3) f32
    normals: np.ndarray  # (N,3) f32
    indices: np.ndarray  # (M,3) u32
    matrix: list[float]  # column-major Matrix4.elements (matrixWorld; parent is the Scene)
    cast_shadow: bool = True
    receive_shadow: bool = True
    emitter: bool = False
    gpu: dict = field(default_factory=dict)


@dataclass
class Light:
    """One three.js light in bundle terms; ``shadow`` holds the LightShadow settings."""
    name: str
    type: str  # PointLight | DirectionalLight | RectAreaLight | HemisphereLight
    color: list[float]
    intensity: float
    data: dict
    cast_shadow: bool = False
    shadow: dict | None = None

    @property
    def matrix_world(self) -> list[float]:
        """Light.matrixWorld: compose(position, quaternion, 1) (three.core.js:13035)."""
        q = tuple(self.data.get("quaternion", (0.0, 0.0, 0.0, 1.0)))
        return tm.m4_compose(tm.v3(self.data["position"]), q)


def _light_from_bundle(d: dict, default_up) -> Light:
    t = d["type"]
    if t == "PointLight":
        return Light(d["name"], t, list(d["color"]), float(d["intensity"]),
                     {"position": d["position"], "distance": float(d.get("distance", 0)),
                      "decay": float(d.get("decay", 2))}, bool(d.get("castShadow", False)), d.get("shadow"))
    if t == "DirectionalLight":
        return Light(d["name"], t, list(d["color"]), float(d["intensity"]),
                     {"position": d["position"], "target": d.get("target", [0.0, 0.0, 0.0])},
                     bool(d.get("castShadow", False)), d.get("shadow"))
    if t == "RectAreaLight":
        return Light(d["name"], t, list(d["color"]), float(d["intensity"]),
                     {"position": d["position"], "quaternion": d["quaternion"], "width": float(d["width"]),
                      "height": float(d["height"])})
    if t == "HemisphereLight":
        # HemisphereLight.position = Object3D.DEFAULT_UP at construction; the bundle gives it as "up".
        return Light(d["name"], t, list(d["skyColor"]), float(d["intensity"]),
                     {"position": d.get("up", default_up), "groundColor": list(d.get("groundColor", [0, 0, 0]))})
    raise ValueError(f"unsupported light type {t!r}")


class SceneState:
    """Mutable scene built from a bundle; ``apply_events(frame)`` runs that frame's timeline ops."""

    def __init__(self, bundle: dict, arrays: dict[str, np.ndarray]):
        ed = bundle["engine_data"]
        if str(ed.get("three_revision")) != "186":
            raise ValueError(f"bundle is for three.js r{ed.get('three_revision')}, port is r186")
        # Object3D.DEFAULT_UP (three.core.js:13578) stays three.js's default, as in the unmodified original: it is
        # the up of every camera nobody sets one for (the directional shadow camera). frame.up only fills in
        # missing per-camera / hemisphere ups.
        self.default_up = (0.0, 1.0, 0.0)
        self.frame_up = tm.v3(ed.get("frame", {}).get("up", [0.0, 0.0, 1.0]))
        self.materials = {n: Material(n, list(m["color"]), list(m.get("emissive", [0, 0, 0])),
                                      m.get("side", "FrontSide")) for n, m in ed["materials"].items()}
        for n, m in ed["materials"].items():
            if m.get("type", "MeshLambertMaterial") != "MeshLambertMaterial":
                raise ValueError(f"material {n}: only MeshLambertMaterial is supported")
        self.drawables: list[Drawable] = []
        for m in ed["meshes"]:
            self.drawables.append(Drawable(
                m["name"], self.materials[m["material"]], arrays[m["position"]].astype(np.float32),
                arrays[m["normal"]].astype(np.float32), arrays[m["index"]].astype(np.uint32),
                tm.m4_from_elements(m["matrix"]), bool(m.get("castShadow", True)), bool(m.get("receiveShadow", True))))
        for e in ed.get("emitters", []):
            mat = Material("emitter:" + e["name"], list(e.get("color", [0, 0, 0])), list(e["emissive"]),
                           e.get("side", "FrontSide"))
            self.materials[mat.name] = mat
            self.drawables.append(Drawable(
                e["name"], mat, arrays[e["position"]].astype(np.float32), arrays[e["normal"]].astype(np.float32),
                arrays[e["index"]].astype(np.uint32), tm.m4_from_elements(e["matrix"]),
                bool(e.get("castShadow", True)), bool(e.get("receiveShadow", True)), emitter=True))
        self.lights = [_light_from_bundle(d, self.frame_up) for d in ed["lights"]]
        self.background = None if ed.get("background") is None else [float(c) for c in ed["background"]]
        self.cameras = ed["cameras"]
        self.probe_cfg = ed.get("probe", {"enabled": False, "dynamic": False})
        self.renderer_cfg = ed.get("renderer", {})
        self.events: dict[int, list[dict]] = {}
        tl = ed.get("timeline")
        if tl:
            for ev in tl["events"]:
                self.events.setdefault(int(ev["frame"]), []).extend(ev["ops"])
        self.probe_sh: np.ndarray | None = None  # (9, 3) float64 LightProbe.sh.coefficients
        self.probe_intensity = 1.0

    def light(self, name: str) -> Light:
        return next(lt for lt in self.lights if lt.name == name)

    def drawable(self, name: str) -> Drawable:
        return next(d for d in self.drawables if d.name == name)

    def apply_events(self, frame: int) -> bool:
        """Apply timeline ops scheduled at ``frame`` (DESIGN §1 Time). Returns True when something changed."""
        ops = self.events.get(int(frame), [])
        for op in ops:
            kind = op["op"]
            if kind == "light":
                lt = self.light(op["name"])
                lt.intensity = float(op["intensity"])
                lt.color = list(op.get("color", lt.color))
                if "emissive" in op:  # rect light: its emitter mesh changes with it
                    for d in self.drawables:
                        if d.emitter and d.name == lt.name:
                            d.material.emissive = list(op["emissive"])
                if "background" in op:  # environment light: scene.background = L
                    self.background = [float(c) for c in op["background"]]
            elif kind == "matrix":
                self.drawable(op["mesh"]).matrix = tm.m4_from_elements(op["matrix"])
            elif kind == "material":
                self.materials[op["name"]].color = list(op["color"])
            else:
                raise ValueError(f"unknown timeline op {kind!r}")
        return bool(ops)

    def shadow_lights(self) -> list[Light]:
        return [lt for lt in self.lights if lt.cast_shadow and lt.type in ("PointLight", "DirectionalLight")]


def _sorted_lights(lights: list[Light]) -> list[Light]:
    """lights.sort( shadowCastingAndTexturingLightsFirst ) (WebGLLights.js:153, 245); Array.sort is stable."""
    return sorted(lights, key=lambda lt: -(2 if lt.cast_shadow and lt.type in ("PointLight", "DirectionalLight")
                                           else 0))


def light_counts(scene: SceneState, with_probe: bool) -> dict:
    """WebGLPrograms parameters derived from WebGLLights.state (numDirLights, ..., numLightProbes)."""
    c = {"numDirLights": 0, "numPointLights": 0, "numRectAreaLights": 0, "numHemiLights": 0,
         "numDirLightShadows": 0, "numPointLightShadows": 0, "numLightProbes": 1 if with_probe else 0}
    for lt in scene.lights:
        if lt.type == "DirectionalLight":
            c["numDirLights"] += 1
            c["numDirLightShadows"] += int(lt.cast_shadow)
        elif lt.type == "PointLight":
            c["numPointLights"] += 1
            c["numPointLightShadows"] += int(lt.cast_shadow)
        elif lt.type == "RectAreaLight":
            c["numRectAreaLights"] += 1
        elif lt.type == "HemisphereLight":
            c["numHemiLights"] += 1
    return c


def light_uniforms(scene: SceneState, view_matrix: list[float], shadow_info: dict[str, dict],
                   with_probe: bool) -> dict:
    """WebGLLights.setup + setupView (WebGLLights.js:221-643) -> uniform values by GLSL name.
    ``shadow_info[light.name]`` = {"matrix": Matrix4 elements, "mapSize": (w, h), "near", "far"} from shadows.py."""
    lights = _sorted_lights(scene.lights)
    u: dict = {"ambientLightColor": [0.0, 0.0, 0.0]}
    probe = np.zeros((9, 3))
    directional, dir_shadow, dir_shadow_matrix = [], [], []
    point, point_shadow, point_shadow_matrix = [], [], []
    rect, hemi = [], []
    for lt in lights:
        color = [c * lt.intensity for c in lt.color]  # uniforms.color.copy( color ).multiplyScalar( intensity )
        if lt.type == "DirectionalLight":
            # direction = position - target, transformDirection( viewMatrix )  (WebGLLights.js:575-584)
            d = tm.v3_sub(tm.v3(lt.data["position"]), tm.v3(lt.data["target"]))
            directional.append({"direction": tm.v3_transform_direction(d, view_matrix), "color": color})
            if lt.cast_shadow:  # WebGLLights.js:334-352
                s = lt.shadow
                dir_shadow.append({"shadowIntensity": float(s.get("intensity", 1)), "shadowBias": float(s["bias"]),
                                   "shadowNormalBias": float(s["normalBias"]), "shadowRadius": float(s["radius"]),
                                   "shadowMapSize": list(shadow_info[lt.name]["mapSize"])})
                dir_shadow_matrix.append(shadow_info[lt.name]["matrix"])
        elif lt.type == "PointLight":
            pos = tm.v3_apply_matrix4(tm.v3(lt.data["position"]), view_matrix)  # WebGLLights.js:621-628
            point.append({"position": pos, "color": color, "distance": lt.data["distance"],
                          "decay": lt.data["decay"]})
            if lt.cast_shadow:  # WebGLLights.js:430-450
                s = lt.shadow
                si = shadow_info[lt.name]
                point_shadow.append({"shadowIntensity": float(s.get("intensity", 1)), "shadowBias": float(s["bias"]),
                                     "shadowNormalBias": float(s["normalBias"]), "shadowRadius": float(s["radius"]),
                                     "shadowMapSize": list(si["mapSize"]), "shadowCameraNear": si["near"],
                                     "shadowCameraFar": si["far"]})
                point_shadow_matrix.append(si["matrix"])
        elif lt.type == "RectAreaLight":  # WebGLLights.js:409-420, 600-619
            mw = lt.matrix_world
            pos = tm.v3_apply_matrix4(tm.v3_from_matrix_position(mw), view_matrix)
            rot = tm.m4_extract_rotation(tm.m4_multiply(view_matrix, mw))  # matrix4.copy(mw).premultiply(view)
            hw = tm.v3_apply_matrix4((lt.data["width"] * 0.5, 0.0, 0.0), rot)
            hh = tm.v3_apply_matrix4((0.0, lt.data["height"] * 0.5, 0.0), rot)
            rect.append({"color": color, "position": pos, "halfWidth": hw, "halfHeight": hh})
        elif lt.type == "HemisphereLight":  # WebGLLights.js:456-466, 630-637
            sky = color
            ground = [c * lt.intensity for c in lt.data["groundColor"]]
            direction = tm.v3_transform_direction(tm.v3(lt.data["position"]), view_matrix)
            hemi.append({"direction": direction, "skyColor": sky, "groundColor": ground})
    if with_probe and scene.probe_sh is not None:  # state.probe[ j ].addScaledVector( sh[ j ], intensity )
        probe = probe + scene.probe_sh * scene.probe_intensity
    u["lightProbe"] = probe.tolist()
    u.update(directionalLights=directional, directionalLightShadows=dir_shadow,
             directionalShadowMatrix=dir_shadow_matrix, pointLights=point, pointLightShadows=point_shadow,
             pointShadowMatrix=point_shadow_matrix, rectAreaLights=rect, hemisphereLights=hemi)
    return u


def object_uniforms(d: Drawable, view_matrix: list[float]) -> dict:
    """Per-draw uniforms: modelViewMatrix = view * matrixWorld, normalMatrix = getNormalMatrix(modelView)
    (WebGLRenderer.js:2160-2161), material refreshUniformsCommon (WebGLMaterials.js:138-152), receiveShadow."""
    mv = tm.m4_multiply(view_matrix, d.matrix)
    return {"modelMatrix": d.matrix, "modelViewMatrix": mv, "normalMatrix": tm.m3_normal_matrix(mv),
            "diffuse": d.material.color, "emissive": d.material.emissive, "opacity": 1.0,
            "receiveShadow": d.receive_shadow}
