"""WebGLShadowMap r186 (PCFShadowMap) ported: depth-texture shadow maps, directional ortho camera, point cube faces.

Source: src/renderers/webgl/WebGLShadowMap.js (render loop 92-380, getDepthMaterial side rules 429-516),
src/lights/LightShadow.js (updateMatrices 213-224, _updateMatrix 235-268), DirectionalLightShadow.js,
PointLightShadow.js. Depth only: the shadow render target's colour attachment is never read in r186 (WebGLLights
binds ``shadow.map.depthTexture`` for PCF, WebGLLights.js:257-269), so the native pass has no fragment stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import three_math as tm

__all__ = ["CUBE_DIRECTIONS", "CUBE_UPS", "ShadowSetup", "shadow_setups", "SHADOW_SIDE", "DEPTH_FORMAT"]

# WebGLShadowMap.js:21-29
CUBE_DIRECTIONS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
CUBE_UPS = [(0, -1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0), (0, -1, 0)]
# WebGLShadowMap.js:51: shadowSide = { FrontSide: BackSide, BackSide: FrontSide, DoubleSide: DoubleSide }
SHADOW_SIDE = {"FrontSide": "BackSide", "BackSide": "FrontSide", "DoubleSide": "DoubleSide"}
# DepthTexture( w, h, UnsignedIntType ) with DepthFormat -> WebGL2 DEPTH_COMPONENT24 (WebGLShadowMap.js:249-254)
DEPTH_FORMAT = "depth24plus"


@dataclass
class ShadowFace:
    camera: object  # PerspectiveCamera | OrthographicCamera with projection_matrix / matrix_world_inverse


@dataclass
class ShadowSetup:
    """Per shadow-casting light: map size, cameras (1 or 6 faces), the shadow matrix and near/far uniforms."""
    light: str
    kind: str  # "directional" | "point"
    map_size: tuple[int, int]
    faces: list[ShadowFace]
    matrix: list[float]
    near: float
    far: float
    gpu: dict = field(default_factory=dict)

    def info(self) -> dict:
        return {"matrix": self.matrix, "mapSize": self.map_size, "near": self.near, "far": self.far}


def _clamp_map_size(map_size, max_texture_size: int) -> tuple[int, int]:
    """WebGLShadowMap.js:172-198 (frame extents are (1, 1) for directional and point shadows in r186)."""
    w, h = int(map_size[0]), int(map_size[1])
    if w > max_texture_size:
        w = max_texture_size
    if h > max_texture_size:
        h = max_texture_size
    return w, h


def _directional(lt, default_up, max_tex: int) -> ShadowSetup:
    s = lt.shadow
    c = s["camera"]
    cam = tm.OrthographicCamera(c["left"], c["right"], c["top"], c["bottom"], c["near"], c["far"], up=default_up)
    # LightShadow.updateMatrices (LightShadow.js:213-224)
    cam.position = tm.v3_from_matrix_position(lt.matrix_world)
    cam.look_at(lt.data["target"])
    cam.update_matrix_world()
    proj_screen = tm.m4_multiply(cam.projection_matrix, cam.matrix_world_inverse)  # LightShadow.js:237
    bias = tm.m4_set(0.5, 0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 1.0)  # :257-262
    matrix = tm.m4_multiply(bias, proj_screen)  # shadowMatrix.multiply( _projScreenMatrix )
    return ShadowSetup(lt.name, "directional", _clamp_map_size(s["mapSize"], max_tex), [ShadowFace(cam)], matrix,
                       float(c["near"]), float(c["far"]))


def _point(lt, default_up, max_tex: int) -> ShadowSetup:
    s = lt.shadow
    size = _clamp_map_size(s["mapSize"], max_tex)
    near, far = float(s.get("near", 0.5)), float(s.get("far", 500))
    far = lt.data.get("distance", 0) or far  # const far = light.distance || camera.far  (WebGLShadowMap.js:302)
    pos = tm.v3_from_matrix_position(lt.matrix_world)
    faces = []
    for face in range(6):  # WebGLShadowMap.js:297-325
        cam = tm.PerspectiveCamera(90, 1, near, far, up=default_up)  # PointLightShadow: PerspectiveCamera(90, 1, ..)
        cam.position = pos
        cam.up = tm.v3(CUBE_UPS[face])
        cam.look_at(tm.v3_add(pos, tm.v3(CUBE_DIRECTIONS[face])))
        cam.update_matrix_world()
        faces.append(ShadowFace(cam))
    matrix = tm.m4_make_translation(-pos[0], -pos[1], -pos[2])  # shadowMatrix.makeTranslation( -lightPos )
    return ShadowSetup(lt.name, "point", size, faces, matrix, near, far)


def shadow_setups(scene, max_texture_size: int) -> list[ShadowSetup]:
    """Shadow cameras and matrices for every shadow-casting light, in WebGLLights order."""
    out = []
    for lt in scene.shadow_lights():
        if lt.type == "DirectionalLight":
            out.append(_directional(lt, scene.default_up, max_texture_size))
        else:
            out.append(_point(lt, scene.default_up, max_texture_size))
    return out
