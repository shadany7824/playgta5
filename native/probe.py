"""Light probe capture: CubeCamera faces + LightProbeGenerator.fromCubeRenderTarget, ported.

* ``cube_cameras(position, near, far)``: src/cameras/CubeCamera.js (constructor 47-100, fov = -90, aspect 1;
  updateCoordinateSystem for WebGLCoordinateSystem 115-133; children's matrixWorld = cube.matrixWorld * matrix).
* ``sh_from_cube_faces(faces, type)``: examples/jsm/lights/LightProbeGenerator.js:157-308 (fromCubeRenderTarget)
  with SphericalHarmonics3.getBasisAt (three.core.js:48429). Faces are the six cube layers in GL memory row order
  (what ``readRenderTargetPixels`` returns); a HalfFloatType target is read as half floats and widened exactly
  (DataUtils.fromHalfFloat), then ``convertColorToLinear`` is the identity for the target's NoColorSpace texture.
"""

from __future__ import annotations

import numpy as np

from . import three_math as tm

__all__ = ["cube_cameras", "sh_from_cube_faces", "sh_basis"]

# CubeCamera.updateCoordinateSystem, WebGLCoordinateSystem branch (CubeCamera.js:117-133): (up, lookAt target)
_FACES = [((0, 1, 0), (1, 0, 0)), ((0, 1, 0), (-1, 0, 0)), ((0, 0, -1), (0, 1, 0)), ((0, 0, 1), (0, -1, 0)),
          ((0, 1, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, -1))]


def cube_cameras(position, near: float, far: float) -> list[tm.PerspectiveCamera]:
    """The six CubeCamera children (px, nx, py, ny, pz, nz) for a CubeCamera at ``position`` (no rotation)."""
    cube_world = tm.m4_compose(tm.v3(position), (0.0, 0.0, 0.0, 1.0))
    cams = []
    for up, target in _FACES:
        cam = tm.PerspectiveCamera(-90, 1, near, far, up=up)  # const fov = - 90; aspect = 1 (CubeCamera.js:5-6)
        cam.look_at(target)  # looked at while detached (updateCoordinateSystem removes the children first)
        cam.parent_matrix_world = cube_world
        cam.update_matrix_world()
        cams.append(cam)
    return cams


def sh_basis(d: np.ndarray) -> np.ndarray:
    """SphericalHarmonics3.getBasisAt (three.core.js:48429-48448) for unit directions d (..., 3) -> (..., 9)."""
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    return np.stack([np.full_like(x, 0.282095), 0.488603 * y, 0.488603 * z, 0.488603 * x, 1.092548 * x * y,
                     1.092548 * y * z, 0.315392 * (3 * z * z - 1), 1.092548 * x * z, 0.546274 * (x * x - y * y)],
                    axis=-1)


def sh_from_cube_faces(faces: list[np.ndarray], flip: int = -1) -> np.ndarray:
    """LightProbeGenerator.fromCubeRenderTarget: six (S, S, >=3) linear RGB faces in readRenderTargetPixels order
    (row 0 first) -> SH9 coefficients (9, 3) float64. ``flip`` = -1 for WebGLCoordinateSystem (line 159)."""
    S = faces[0].shape[0]
    pixel_size = 2 / S  # line 212
    idx = np.arange(S * S, dtype=np.float64)
    colf = (1 - ((idx % S) + 0.5) * pixel_size) * flip  # line 248
    row = 1 - (np.floor(idx / S) + 0.5) * pixel_size  # line 250
    total_weight = 0.0
    coeffs = np.zeros((9, 3), dtype=np.float64)
    for face_index in range(6):
        rgb = np.asarray(faces[face_index], dtype=np.float64)[:, :, :3].reshape(-1, 3)
        one = np.ones_like(idx)
        if face_index == 0:
            coord = np.stack([-1 * flip * one, row, colf * flip], axis=-1)  # line 254
        elif face_index == 1:
            coord = np.stack([1 * flip * one, row, -colf * flip], axis=-1)
        elif face_index == 2:
            coord = np.stack([colf, one, -row], axis=-1)
        elif face_index == 3:
            coord = np.stack([colf, -one, row], axis=-1)
        elif face_index == 4:
            coord = np.stack([colf, row, one], axis=-1)
        else:
            coord = np.stack([-colf, row, -one], axis=-1)
        length_sq = np.sum(coord * coord, axis=-1)  # line 270
        weight = 4 / (np.sqrt(length_sq) * length_sq)  # line 272
        total_weight += float(np.sum(weight))
        d = coord * (1 / np.sqrt(length_sq))[:, None]  # dir.copy( coord ).normalize()
        basis = sh_basis(d)
        coeffs += np.einsum("pj,pc->jc", basis * weight[:, None], rgb)  # line 283-289
    norm = (4 * np.pi) / total_weight  # line 296
    return coeffs * norm

