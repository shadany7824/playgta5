"""JS-side maths of three.js r186, ported operation-for-operation in float64 (as JS numbers are).

Matrices are lists of 16 floats in column-major order, exactly ``Matrix4.elements``; Matrix3 likewise with 9.
Quaternions are (x, y, z, w); vectors are (x, y, z). Every function names the vendored source it ports
(``web/vendor/three/build/three.core.js`` line numbers for the math classes, ``src/cameras/*.js`` for cameras),
so results match what three.js uploads as Float32 uniforms bit for bit wherever the libm calls agree.
"""

from __future__ import annotations

import math
from typing import Sequence

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]
M4 = list[float]
M3 = list[float]

DEG2RAD = math.pi / 180  # three.core.js:2308
CORE = "web/vendor/three/build/three.core.js"


# ------------------------------------------------------------------------------------------------ Vector3

def v3(x) -> Vec3:
    return (float(x[0]), float(x[1]), float(x[2]))


def v3_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v3_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v3_length_sq(v: Vec3) -> float:
    return v[0] * v[0] + v[1] * v[1] + v[2] * v[2]


def v3_length(v: Vec3) -> float:
    """Vector3.length (three.core.js:5563)."""
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def v3_normalize(v: Vec3) -> Vec3:
    """Vector3.normalize = divideScalar(length || 1) = multiplyScalar(1 / s) (three.core.js:5586)."""
    s = 1 / (v3_length(v) or 1)
    return (v[0] * s, v[1] * s, v[2] * s)


def v3_cross(a: Vec3, b: Vec3) -> Vec3:
    """Vector3.crossVectors (three.core.js:5664)."""
    ax, ay, az = a
    bx, by, bz = b
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def v3_apply_matrix4(v: Vec3, e: M4) -> Vec3:
    """Vector3.applyMatrix4 (three.core.js:5244)."""
    x, y, z = v
    w = 1 / (e[3] * x + e[7] * y + e[11] * z + e[15])
    return ((e[0] * x + e[4] * y + e[8] * z + e[12]) * w,
            (e[1] * x + e[5] * y + e[9] * z + e[13]) * w,
            (e[2] * x + e[6] * y + e[10] * z + e[14]) * w)


def v3_transform_direction(v: Vec3, e: M4) -> Vec3:
    """Vector3.transformDirection (three.core.js:5319)."""
    x, y, z = v
    return v3_normalize((e[0] * x + e[4] * y + e[8] * z,
                         e[1] * x + e[5] * y + e[9] * z,
                         e[2] * x + e[6] * y + e[10] * z))


def v3_from_matrix_position(e: M4) -> Vec3:
    """Vector3.setFromMatrixPosition (three.core.js:5850)."""
    return (e[12], e[13], e[14])


# ------------------------------------------------------------------------------------------------ Matrix4

def m4_identity() -> M4:
    return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def m4_set(n11, n12, n13, n14, n21, n22, n23, n24, n31, n32, n33, n34, n41, n42, n43, n44) -> M4:
    """Matrix4.set: row-major arguments -> column-major elements (three.core.js:10133)."""
    return [n11, n21, n31, n41, n12, n22, n32, n42, n13, n23, n33, n43, n14, n24, n34, n44]


def m4_from_elements(a: Sequence[float]) -> M4:
    """Matrix4.fromArray (three.core.js:11282)."""
    if len(a) != 16:
        raise ValueError("Matrix4 needs 16 elements")
    return [float(x) for x in a]


def m4_multiply(a: M4, b: M4) -> M4:
    """Matrix4.multiplyMatrices(a, b) (three.core.js:10570)."""
    a11, a12, a13, a14 = a[0], a[4], a[8], a[12]
    a21, a22, a23, a24 = a[1], a[5], a[9], a[13]
    a31, a32, a33, a34 = a[2], a[6], a[10], a[14]
    a41, a42, a43, a44 = a[3], a[7], a[11], a[15]
    b11, b12, b13, b14 = b[0], b[4], b[8], b[12]
    b21, b22, b23, b24 = b[1], b[5], b[9], b[13]
    b31, b32, b33, b34 = b[2], b[6], b[10], b[14]
    b41, b42, b43, b44 = b[3], b[7], b[11], b[15]
    te = [0.0] * 16
    te[0] = a11 * b11 + a12 * b21 + a13 * b31 + a14 * b41
    te[4] = a11 * b12 + a12 * b22 + a13 * b32 + a14 * b42
    te[8] = a11 * b13 + a12 * b23 + a13 * b33 + a14 * b43
    te[12] = a11 * b14 + a12 * b24 + a13 * b34 + a14 * b44
    te[1] = a21 * b11 + a22 * b21 + a23 * b31 + a24 * b41
    te[5] = a21 * b12 + a22 * b22 + a23 * b32 + a24 * b42
    te[9] = a21 * b13 + a22 * b23 + a23 * b33 + a24 * b43
    te[13] = a21 * b14 + a22 * b24 + a23 * b34 + a24 * b44
    te[2] = a31 * b11 + a32 * b21 + a33 * b31 + a34 * b41
    te[6] = a31 * b12 + a32 * b22 + a33 * b32 + a34 * b42
    te[10] = a31 * b13 + a32 * b23 + a33 * b33 + a34 * b43
    te[14] = a31 * b14 + a32 * b24 + a33 * b34 + a34 * b44
    te[3] = a41 * b11 + a42 * b21 + a43 * b31 + a44 * b41
    te[7] = a41 * b12 + a42 * b22 + a43 * b32 + a44 * b42
    te[11] = a41 * b13 + a42 * b23 + a43 * b33 + a44 * b43
    te[15] = a41 * b14 + a42 * b24 + a43 * b34 + a44 * b44
    return te


def m4_invert(te: M4) -> M4:
    """Matrix4.invert (three.core.js:10743, after gl-matrix)."""
    n11, n21, n31, n41 = te[0], te[1], te[2], te[3]
    n12, n22, n32, n42 = te[4], te[5], te[6], te[7]
    n13, n23, n33, n43 = te[8], te[9], te[10], te[11]
    n14, n24, n34, n44 = te[12], te[13], te[14], te[15]
    t1 = n11 * n22 - n21 * n12
    t2 = n11 * n32 - n31 * n12
    t3 = n11 * n42 - n41 * n12
    t4 = n21 * n32 - n31 * n22
    t5 = n21 * n42 - n41 * n22
    t6 = n31 * n42 - n41 * n32
    t7 = n13 * n24 - n23 * n14
    t8 = n13 * n34 - n33 * n14
    t9 = n13 * n44 - n43 * n14
    t10 = n23 * n34 - n33 * n24
    t11 = n23 * n44 - n43 * n24
    t12 = n33 * n44 - n43 * n34
    det = t1 * t12 - t2 * t11 + t3 * t10 + t4 * t9 - t5 * t8 + t6 * t7
    if det == 0:
        return [0.0] * 16
    d = 1 / det
    return [(n22 * t12 - n32 * t11 + n42 * t10) * d, (n31 * t11 - n21 * t12 - n41 * t10) * d,
            (n24 * t6 - n34 * t5 + n44 * t4) * d, (n33 * t5 - n23 * t6 - n43 * t4) * d,
            (n32 * t9 - n12 * t12 - n42 * t8) * d, (n11 * t12 - n31 * t9 + n41 * t8) * d,
            (n34 * t3 - n14 * t6 - n44 * t2) * d, (n13 * t6 - n33 * t3 + n43 * t2) * d,
            (n12 * t11 - n22 * t9 + n42 * t7) * d, (n21 * t9 - n11 * t11 - n41 * t7) * d,
            (n14 * t5 - n24 * t3 + n44 * t1) * d, (n23 * t3 - n13 * t5 - n43 * t1) * d,
            (n22 * t8 - n12 * t10 - n32 * t7) * d, (n11 * t10 - n21 * t8 + n31 * t7) * d,
            (n24 * t2 - n14 * t4 - n34 * t1) * d, (n13 * t4 - n23 * t2 + n33 * t1) * d]


def m4_determinant_affine(te: M4) -> float:
    """Matrix4.determinantAffine (three.core.js:10669)."""
    n11, n12, n13 = te[0], te[4], te[8]
    n21, n22, n23 = te[1], te[5], te[9]
    n31, n32, n33 = te[2], te[6], te[10]
    return n11 * (n22 * n33 - n23 * n32) - n12 * (n21 * n33 - n23 * n31) + n13 * (n21 * n32 - n22 * n31)


def m4_compose(position: Vec3, q: Quat, scale: Vec3 = (1.0, 1.0, 1.0)) -> M4:
    """Matrix4.compose (three.core.js:11030)."""
    x, y, z, w = q
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    sx, sy, sz = scale
    return [(1 - (yy + zz)) * sx, (xy + wz) * sx, (xz - wy) * sx, 0.0,
            (xy - wz) * sy, (1 - (xx + zz)) * sy, (yz + wx) * sy, 0.0,
            (xz + wy) * sz, (yz - wx) * sz, (1 - (xx + yy)) * sz, 0.0,
            position[0], position[1], position[2], 1.0]


def m4_decompose(te: M4) -> tuple[Vec3, Quat, Vec3]:
    """Matrix4.decompose (three.core.js:11079) -> (position, quaternion, scale)."""
    position = (te[12], te[13], te[14])
    det = m4_determinant_affine(te)
    if det == 0:
        return position, (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)
    sx = v3_length((te[0], te[1], te[2]))
    sy = v3_length((te[4], te[5], te[6]))
    sz = v3_length((te[8], te[9], te[10]))
    if det < 0:
        sx = -sx
    m = list(te)
    isx, isy, isz = 1 / sx, 1 / sy, 1 / sz
    m[0] *= isx
    m[1] *= isx
    m[2] *= isx
    m[4] *= isy
    m[5] *= isy
    m[6] *= isy
    m[8] *= isz
    m[9] *= isz
    m[10] *= isz
    return position, quat_from_rotation_matrix(m), (sx, sy, sz)


def m4_look_at_rotation(eye: Vec3, target: Vec3, up: Vec3) -> M4:
    """Matrix4.lookAt (three.core.js:10491); only the rotation part (all callers use only that)."""
    z = v3_sub(eye, target)
    if v3_length_sq(z) == 0:
        z = (z[0], z[1], 1.0)
    z = v3_normalize(z)
    x = v3_cross(up, z)
    if v3_length_sq(x) == 0:
        if abs(up[2]) == 1:
            z = (z[0] + 0.0001, z[1], z[2])
        else:
            z = (z[0], z[1], z[2] + 0.0001)
        z = v3_normalize(z)
        x = v3_cross(up, z)
    x = v3_normalize(x)
    y = v3_cross(z, x)
    return [x[0], x[1], x[2], 0.0, y[0], y[1], y[2], 0.0, z[0], z[1], z[2], 0.0, 0.0, 0.0, 0.0, 1.0]


def m4_extract_rotation(me: M4) -> M4:
    """Matrix4.extractRotation (three.core.js:10297)."""
    if m4_determinant_affine(me) == 0:
        return m4_identity()
    sx = 1 / v3_length((me[0], me[1], me[2]))
    sy = 1 / v3_length((me[4], me[5], me[6]))
    sz = 1 / v3_length((me[8], me[9], me[10]))
    return [me[0] * sx, me[1] * sx, me[2] * sx, 0.0, me[4] * sy, me[5] * sy, me[6] * sy, 0.0,
            me[8] * sz, me[9] * sz, me[10] * sz, 0.0, 0.0, 0.0, 0.0, 1.0]


def m4_make_translation(x: float, y: float, z: float) -> M4:
    """Matrix4.makeTranslation (three.core.js:10841)."""
    return m4_set(1, 0, 0, x, 0, 1, 0, y, 0, 0, 1, z, 0, 0, 0, 1)


def m4_make_perspective(left, right, top, bottom, near, far) -> M4:
    """Matrix4.makePerspective, WebGLCoordinateSystem, no reversed depth (three.core.js:11148)."""
    x = 2 * near / (right - left)
    y = 2 * near / (top - bottom)
    a = (right + left) / (right - left)
    b = (top + bottom) / (top - bottom)
    c = - (far + near) / (far - near)
    d = (-2 * far * near) / (far - near)
    return [x, 0.0, 0.0, 0.0, 0.0, y, 0.0, 0.0, a, b, c, -1.0, 0.0, 0.0, d, 0.0]


def m4_make_orthographic(left, right, top, bottom, near, far) -> M4:
    """Matrix4.makeOrthographic, WebGLCoordinateSystem, no reversed depth (three.core.js:11208)."""
    x = 2 / (right - left)
    y = 2 / (top - bottom)
    a = - (right + left) / (right - left)
    b = - (top + bottom) / (top - bottom)
    c = -2 / (far - near)
    d = - (far + near) / (far - near)
    return [x, 0.0, 0.0, 0.0, 0.0, y, 0.0, 0.0, 0.0, 0.0, c, 0.0, a, b, d, 1.0]


# ------------------------------------------------------------------------------------------------ Matrix3

def m3_normal_matrix(m: M4) -> M3:
    """Matrix3.getNormalMatrix = setFromMatrix4(m).invert().transpose() (three.core.js:6406, 6227, 6347, 6386)."""
    te = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]]  # setFromMatrix4 keeps column-major order
    n11, n21, n31 = te[0], te[1], te[2]
    n12, n22, n32 = te[3], te[4], te[5]
    n13, n23, n33 = te[6], te[7], te[8]
    t11 = n33 * n22 - n32 * n23
    t12 = n32 * n13 - n33 * n12
    t13 = n23 * n12 - n22 * n13
    det = n11 * t11 + n21 * t12 + n31 * t13
    if det == 0:
        inv = [0.0] * 9
    else:
        d = 1 / det
        inv = [t11 * d, (n31 * n23 - n33 * n21) * d, (n32 * n21 - n31 * n22) * d,
               t12 * d, (n33 * n11 - n31 * n13) * d, (n31 * n12 - n32 * n11) * d,
               t13 * d, (n21 * n13 - n23 * n11) * d, (n22 * n11 - n21 * n12) * d]
    i = inv
    return [i[0], i[3], i[6], i[1], i[4], i[7], i[2], i[5], i[8]]  # transpose


# ------------------------------------------------------------------------------------------------ Quaternion

def quat_from_rotation_matrix(te: M4) -> Quat:
    """Quaternion.setFromRotationMatrix (three.core.js:4289)."""
    m11, m12, m13 = te[0], te[4], te[8]
    m21, m22, m23 = te[1], te[5], te[9]
    m31, m32, m33 = te[2], te[6], te[10]
    trace = m11 + m22 + m33
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        return ((m32 - m23) * s, (m13 - m31) * s, (m21 - m12) * s, 0.25 / s)
    if m11 > m22 and m11 > m33:
        s = 2.0 * math.sqrt(1.0 + m11 - m22 - m33)
        return (0.25 * s, (m12 + m21) / s, (m13 + m31) / s, (m32 - m23) / s)
    if m22 > m33:
        s = 2.0 * math.sqrt(1.0 + m22 - m11 - m33)
        return ((m12 + m21) / s, 0.25 * s, (m23 + m32) / s, (m13 - m31) / s)
    s = 2.0 * math.sqrt(1.0 + m33 - m11 - m22)
    return ((m13 + m31) / s, (m23 + m32) / s, 0.25 * s, (m21 - m12) / s)


# ------------------------------------------------------------------------------------------------ Object3D / Camera

def object_look_at_quaternion(position: Vec3, target: Vec3, up: Vec3, is_camera_or_light: bool = True) -> Quat:
    """Object3D.lookAt for a parentless object (three.core.js:12585): cameras/lights look down local -Z."""
    if is_camera_or_light:
        m = m4_look_at_rotation(position, target, up)
    else:
        m = m4_look_at_rotation(target, position, up)
    return quat_from_rotation_matrix(m)


def camera_matrix_world_inverse(matrix_world: M4) -> M4:
    """Camera.updateMatrixWorld's view matrix: invert, excluding scale (src/cameras/Camera.js:112-130)."""
    pos, q, s = m4_decompose(matrix_world)
    if s[0] == 1 and s[1] == 1 and s[2] == 1:
        return m4_invert(matrix_world)
    return m4_invert(m4_compose(pos, q, (1.0, 1.0, 1.0)))


class PerspectiveCamera:
    """src/cameras/PerspectiveCamera.js (zoom 1, filmOffset 0) + Object3D world transform for a parentless camera."""

    def __init__(self, fov=50.0, aspect=1.0, near=0.1, far=2000.0, up: Vec3 = (0.0, 1.0, 0.0)):
        self.fov, self.aspect, self.near, self.far = float(fov), float(aspect), float(near), float(far)
        self.zoom = 1.0
        self.view: dict | None = None
        self.up = v3(up)
        self.position: Vec3 = (0.0, 0.0, 0.0)
        self.quaternion: Quat = (0.0, 0.0, 0.0, 1.0)
        self.parent_matrix_world: M4 | None = None
        self.update_projection_matrix()
        self.update_matrix_world()

    def set_view_offset(self, full_width, full_height, x, y, width, height) -> None:
        """PerspectiveCamera.setViewOffset (PerspectiveCamera.js:304)."""
        self.aspect = full_width / full_height
        self.view = {"enabled": True, "fullWidth": full_width, "fullHeight": full_height, "offsetX": x,
                     "offsetY": y, "width": width, "height": height}
        self.update_projection_matrix()

    def clear_view_offset(self) -> None:
        """PerspectiveCamera.clearViewOffset (PerspectiveCamera.js:337)."""
        if self.view is not None:
            self.view["enabled"] = False
        self.update_projection_matrix()

    def update_projection_matrix(self) -> None:
        """PerspectiveCamera.updateProjectionMatrix (PerspectiveCamera.js:353-381)."""
        near = self.near
        top = near * math.tan(DEG2RAD * 0.5 * self.fov) / self.zoom
        height = 2 * top
        width = self.aspect * height
        left = -0.5 * width
        view = self.view
        if view is not None and view["enabled"]:
            full_width, full_height = view["fullWidth"], view["fullHeight"]
            left += view["offsetX"] * width / full_width
            top -= view["offsetY"] * height / full_height
            width *= view["width"] / full_width
            height *= view["height"] / full_height
        self.projection_matrix = m4_make_perspective(left, left + width, top, top - height, near, self.far)

    def look_at(self, target) -> None:
        """Object3D.lookAt for a parentless camera (three.core.js:12585)."""
        self.quaternion = object_look_at_quaternion(self.position, v3(target), self.up, True)

    def update_matrix_world(self) -> None:
        """Object3D.updateMatrix/updateMatrixWorld + Camera.updateMatrixWorld (three.core.js:13035, 13067;
        Camera.js:112)."""
        self.matrix = m4_compose(self.position, self.quaternion)
        if self.parent_matrix_world is None:
            self.matrix_world = list(self.matrix)
        else:
            self.matrix_world = m4_multiply(self.parent_matrix_world, self.matrix)
        self.matrix_world_inverse = camera_matrix_world_inverse(self.matrix_world)

    @property
    def world_position(self) -> Vec3:
        return v3_from_matrix_position(self.matrix_world)


class OrthographicCamera:
    """src/cameras/OrthographicCamera.js (zoom 1, no view offset) for the directional shadow camera."""

    def __init__(self, left=-1.0, right=1.0, top=1.0, bottom=-1.0, near=0.1, far=2000.0,
                 up: Vec3 = (0.0, 1.0, 0.0)):
        self.left, self.right, self.top, self.bottom = float(left), float(right), float(top), float(bottom)
        self.near, self.far = float(near), float(far)
        self.zoom = 1.0
        self.up = v3(up)
        self.position: Vec3 = (0.0, 0.0, 0.0)
        self.quaternion: Quat = (0.0, 0.0, 0.0, 1.0)
        self.update_projection_matrix()
        self.update_matrix_world()

    def update_projection_matrix(self) -> None:
        """OrthographicCamera.updateProjectionMatrix (OrthographicCamera.js:195-223)."""
        dx = (self.right - self.left) / (2 * self.zoom)
        dy = (self.top - self.bottom) / (2 * self.zoom)
        cx = (self.right + self.left) / 2
        cy = (self.top + self.bottom) / 2
        self.projection_matrix = m4_make_orthographic(cx - dx, cx + dx, cy + dy, cy - dy, self.near, self.far)

    def look_at(self, target) -> None:
        self.quaternion = object_look_at_quaternion(self.position, v3(target), self.up, True)

    def update_matrix_world(self) -> None:
        self.matrix = m4_compose(self.position, self.quaternion)
        self.matrix_world = list(self.matrix)
        self.matrix_world_inverse = camera_matrix_world_inverse(self.matrix_world)


# ------------------------------------------------------------------------------------------------ colour

def srgb_transfer_oetf(c: float) -> float:
    """LinearToSRGB (three.core.js:6888): the JS-side sRGB encode used by Color.getRGB for clear colours."""
    return c * 12.92 if c < 0.0031308 else 1.055 * (math.pow(c, 0.41666)) - 0.055


def js_to_fixed(v: float, digits: int) -> str:
    """Number.prototype.toFixed for the finite values used here (-0 prints without a sign, as in JS)."""
    if v == 0:
        v = 0.0
    s = format(v, f".{digits}f")
    return s


# Matrix3.set row-major arguments (three.core.js:6682-6692)
LINEAR_REC709_TO_XYZ = (0.4123908, 0.3575843, 0.1804808, 0.2126390, 0.7151687, 0.0721923,
                        0.0193308, 0.1191948, 0.9505322)
XYZ_TO_LINEAR_REC709 = (3.2409699, -1.5373832, -0.4986108, -0.9692436, 1.8759675, 0.0415551,
                        0.0556301, -0.203977, 1.0569715)
REC709_LUMINANCE_COEFFICIENTS = (0.2126, 0.7152, 0.0722)  # three.core.js:6848


def _m3_set_rows(r) -> M3:
    """Matrix3.set(n11..n33) -> column-major elements (three.core.js:6153)."""
    return [r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8]]


def m3_multiply(a: M3, b: M3) -> M3:
    """Matrix3.multiplyMatrices (three.core.js:6275)."""
    a11, a12, a13 = a[0], a[3], a[6]
    a21, a22, a23 = a[1], a[4], a[7]
    a31, a32, a33 = a[2], a[5], a[8]
    b11, b12, b13 = b[0], b[3], b[6]
    b21, b22, b23 = b[1], b[4], b[7]
    b31, b32, b33 = b[2], b[5], b[8]
    return [a11 * b11 + a12 * b21 + a13 * b31, a21 * b11 + a22 * b21 + a23 * b31, a31 * b11 + a32 * b21 + a33 * b31,
            a11 * b12 + a12 * b22 + a13 * b32, a21 * b12 + a22 * b22 + a23 * b32, a31 * b12 + a32 * b22 + a33 * b32,
            a11 * b13 + a12 * b23 + a13 * b33, a21 * b13 + a22 * b23 + a23 * b33, a31 * b13 + a32 * b23 + a33 * b33]


def working_to_output_matrix() -> M3:
    """ColorManagement._getMatrix(working=srgb-linear, target=srgb|srgb-linear) = toXYZ * fromXYZ of the same
    Rec.709 primaries (three.core.js:6803-6808); feeds WebGLProgram.getEncodingComponents."""
    return m3_multiply(_m3_set_rows(LINEAR_REC709_TO_XYZ), _m3_set_rows(XYZ_TO_LINEAR_REC709))
