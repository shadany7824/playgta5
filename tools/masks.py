"""Engine-neutral pixel masks from the reference AOVs of a view (DESIGN §7).

Every view has ROI ``all`` (the valid pixels: ``|normal| > 0.99`` and ``depth > 0``, DESIGN §6). A spec ROI keeps
the pixels whose first-hit ``position`` lies inside its box (inclusive), optionally whose shading normal satisfies
``dot(normalize(normal), roi.normal) >= min_cos`` (the AOV normal as stored in the mesh, not flipped toward the
viewer), restricted to the view ids in ``roi.views`` when given, and intersected with ``all``. Every mask is then
eroded by one pixel (4-neighbourhood) so silhouette and ROI-edge pixels, which mix surfaces, are dropped. The image
border is not an edge: pixels outside the image count as copies of the border pixel.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["ALL_ROI", "AUX_FILES", "erode", "load_aux", "roi_mask", "roi_roles", "valid_mask", "view_masks"]

ALL_ROI = "all"
AUX_FILES = {"depth": "depth.exr", "normal": "normal.exr", "position": "position.exr"}


def load_aux(ref_dir) -> dict[str, np.ndarray]:
    """Read depth (H,W), normal (H,W,3) and position (H,W,3) from a reference view directory."""
    from .exr import read_exr

    d = Path(ref_dir)
    out = {}
    for key, name in AUX_FILES.items():
        img = read_exr(d / name)
        out[key] = img[..., 0] if key == "depth" else img[..., :3]
    return out


def _aux(ref: Any) -> dict[str, np.ndarray]:
    if isinstance(ref, (str, Path)):
        return load_aux(ref)
    if isinstance(ref, Mapping):
        missing = [k for k in AUX_FILES if k not in ref]
        if missing:
            raise KeyError(f"aux dict lacks {missing} (needs depth, normal, position)")
        return dict(ref)
    raise TypeError(f"expected a reference directory or an aux dict, got {type(ref).__name__}")


def _depth2d(depth: np.ndarray) -> np.ndarray:
    d = np.asarray(depth, dtype=np.float64)
    return d[..., 0] if d.ndim == 3 else d


def valid_mask(aux: Mapping[str, np.ndarray]) -> np.ndarray:
    """DESIGN §6 valid pixels (not eroded): |normal| > 0.99 and depth > 0; non-finite AOVs are invalid."""
    n = np.asarray(aux["normal"], dtype=np.float64)[..., :3]
    d = _depth2d(aux["depth"])
    with np.errstate(invalid="ignore"):
        ok = (np.linalg.norm(n, axis=-1) > 0.99) & (d > 0)
    return ok & np.isfinite(n).all(axis=-1) & np.isfinite(d)


def roi_mask(roi, aux: Mapping[str, np.ndarray], valid: np.ndarray | None = None) -> np.ndarray:
    """Pixels of one spec ROI (box on position, optional normal/min_cos) intersected with ``valid`` (not eroded)."""
    p = np.asarray(aux["position"], dtype=np.float64)[..., :3]
    lo = np.asarray(roi.box_min, dtype=np.float64)
    hi = np.asarray(roi.box_max, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        m = np.all((p >= lo) & (p <= hi), axis=-1)
        if roi.normal is not None:
            n = np.asarray(aux["normal"], dtype=np.float64)[..., :3]
            ln = np.linalg.norm(n, axis=-1)
            cos = (n @ np.asarray(roi.normal, dtype=np.float64)) / np.where(ln > 0, ln, 1.0)
            min_cos = 0.9 if roi.min_cos is None else float(roi.min_cos)
            m &= cos >= min_cos
    v = valid_mask(aux) if valid is None else valid
    return m & v


def erode(mask: np.ndarray, pixels: int = 1) -> np.ndarray:
    """Binary erosion with the 4-neighbourhood, ``pixels`` times; the image border is edge-padded."""
    m = np.asarray(mask, dtype=bool)
    for _ in range(max(0, int(pixels))):
        p = np.pad(m, 1, mode="edge")
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def _view_id(view: Any) -> str | None:
    if view is None or isinstance(view, str):
        return view
    return view["id"] if isinstance(view, Mapping) else getattr(view, "id", None)


def _view_rois(view: Any) -> list:
    if view is None or isinstance(view, str):
        return []
    state = view.get("state") if isinstance(view, Mapping) else getattr(view, "state", None)
    if state is not None and hasattr(state, "rois"):
        return list(state.rois)
    return list(getattr(view, "rois", []) or [])


def view_masks(view, ref, rois: Iterable | None = None, erode_px: int = 1) -> dict[str, np.ndarray]:
    """{name: bool (H,W)} for ROI 'all' and every spec ROI that applies to ``view``.

    view: a spec View (its id filters ``roi.views``; its state supplies the ROIs), or a view id when ``rois`` is
    given. ref: a reference view directory (reads depth/normal/position.exr) or a dict with those arrays.
    A ROI whose ``views`` list excludes this view is left out of the result.
    """
    aux = _aux(ref)
    vid = _view_id(view)
    rois = _view_rois(view) if rois is None else list(rois)
    valid = valid_mask(aux)
    out = {ALL_ROI: erode(valid, erode_px)}
    for roi in rois:
        if roi.views is not None and vid is not None and vid not in roi.views:
            continue
        out[roi.name] = erode(roi_mask(roi, aux, valid), erode_px)
    return out


def roi_roles(scene) -> dict[str, str]:
    """{roi name: role} including the implicit 'all' (role 'any')."""
    roles = {ALL_ROI: "any"}
    for roi in getattr(scene, "rois", []) or []:
        roles[roi.name] = roi.role
    return roles
