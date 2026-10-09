"""tools/metrics.py: every metric recovers a perturbation known in closed form (DESIGN §7, §9)."""

from __future__ import annotations

import json
import math
import subprocess
import sys

import numpy as np
import pytest

from tools import metrics as M
from tools.masks import roi_roles
from tools.spec import timeline_states

H, W = 48, 64


def _ramp(lo=0.2, hi=1.0, tint=(1.0, 0.8, 0.6)):
    """Smooth positive RGB image (H, W, 3)."""
    yy, xx = np.mgrid[0:H, 0:W]
    base = lo + (hi - lo) * (xx / (W - 1) * 0.6 + yy / (H - 1) * 0.4)
    return base[..., None] * np.asarray(tint)[None, None, :]


def test_luminance_weights():
    img = np.zeros((1, 3, 4))
    img[0, 0, 0], img[0, 1, 1], img[0, 2, 2] = 1, 1, 1
    img[..., 3] = 99  # alpha ignored
    np.testing.assert_allclose(M.luminance(img)[0], [0.2126, 0.7152, 0.0722])
    np.testing.assert_allclose(M.luminance(np.full((2, 2, 1), 0.5)), 0.5)
    np.testing.assert_allclose(M.luminance(np.full((2, 2), 0.25)), 0.25)


def test_scaled_image_bias_and_rel_l1():
    T = _ramp()
    s = M.roi_stats(1.05 * T, T)
    assert s["pixels"] == H * W
    assert s["bias"] == pytest.approx(0.05, abs=1e-12)
    assert s["bias_rgb"] == pytest.approx([0.05] * 3, abs=1e-12)
    Y = M.luminance(T)
    assert s["bias_abs"] == pytest.approx(0.05 * Y.mean(), rel=1e-12)
    eps = 0.01 * Y.mean()
    assert s["rel_l1"] == pytest.approx(np.mean(0.05 * Y / (Y + eps)), rel=1e-12)
    assert s["rel_l1"] == pytest.approx(0.05, rel=0.02)
    assert s["ref_mean"] == pytest.approx(Y.mean()) and s["eng_mean"] == pytest.approx(1.05 * Y.mean())
    # constant reference: exact closed forms
    C = np.full((H, W, 3), 0.5)
    c = M.roi_stats(1.05 * C, C)
    assert c["rel_l1"] == pytest.approx(0.05 / 1.01, rel=1e-12)
    assert c["rel_mse"] == pytest.approx(0.05 ** 2 / (1 + 1e-4), rel=1e-12)
    # per-channel bias recovers a per-channel gain; a mask restricts the pixels
    g = M.roi_stats(T * np.array([1.1, 1.0, 0.9]), T)
    assert g["bias_rgb"] == pytest.approx([0.1, 0.0, -0.1], abs=1e-12)
    m = np.zeros((H, W), bool)
    m[10:20, 5:15] = True
    assert M.roi_stats(T, T, m)["pixels"] == 100 and M.roi_stats(T, T, m)["bias"] == 0.0


def test_empty_roi_and_zero_reference_are_none():
    T = _ramp()
    s = M.roi_stats(T, T, np.zeros((H, W), bool))
    assert s["pixels"] == 0 and s["bias"] is None and s["rel_l1"] is None
    z = M.roi_stats(T, np.zeros_like(T))
    assert z["bias"] is None and z["rel_l1"] is None and z["bias_abs"] == pytest.approx(M.luminance(T).mean())
    d = M.roi_stats(T, T, relative=False)
    assert d["bias"] is None and d["rel_mse"] is None and d["bias_abs"] == 0.0
    json.dumps(s), json.dumps(z)


def test_constant_leak():
    T_iso = _ramp()
    dark = np.zeros((H, W), bool)
    dark[30:40, 40:60] = True
    T_iso[dark] = 0.0
    E_iso = T_iso.copy()
    E_iso[dark] = [0.02, 0.03, 0.04]  # constant leak in the dark ROI
    norm = M.roi_mean(T_iso)
    leak_y = 0.2126 * 0.02 + 0.7152 * 0.03 + 0.0722 * 0.04
    lk = M.leak(E_iso, dark, norm)
    assert lk["leak_abs"] == pytest.approx(leak_y, rel=1e-12)
    assert lk["leak_rel"] == pytest.approx(leak_y / norm, rel=1e-12)
    assert M.leak(T_iso, dark, norm) == {"leak_abs": 0.0, "leak_rel": 0.0}
    assert M.leak(E_iso, dark, 0.0)["leak_rel"] is None


def test_bleed_chromaticity_shift():
    T = np.full((H, W, 3), 0.3)
    E = T * np.array([1.2, 1.0, 0.8])
    b = M.bleed(E, T, None)
    assert b["c_ref"] == pytest.approx([1 / 3] * 3)
    assert b["c_eng"] == pytest.approx([0.4, 1 / 3, 0.8 / 3])
    assert b["dist"] == pytest.approx(math.sqrt((0.4 - 1 / 3) ** 2 + (0.8 / 3 - 1 / 3) ** 2), rel=1e-12)
    assert M.bleed(np.zeros_like(T), T, None)["dist"] is None


def test_energy_ratio():
    T = _ramp()
    assert M.energy(0.9 * T, T) == pytest.approx(-0.1, abs=1e-12)
    assert M.energy(1.25 * T, T) == pytest.approx(0.25, abs=1e-12)
    m = np.zeros((H, W), bool)
    m[:, :32] = True
    E = T.copy()
    E[:, 32:] *= 3  # outside the mask: ignored
    assert M.energy(E, T, m) == pytest.approx(0.0, abs=1e-12)
    assert M.energy(T, np.zeros_like(T)) is None


def test_ref_noise_rel_closed_form():
    mu, s, n = 0.5, 0.01, 200
    ref = np.full((10, 20, 3), mu)
    se = np.full((10, 20, 3), s)
    assert M.ref_noise_abs(se) == pytest.approx(s / math.sqrt(n), rel=1e-12)
    assert M.ref_noise_rel(se, ref) == pytest.approx(s / (mu * math.sqrt(n)), rel=1e-12)
    m = np.zeros((10, 20), bool)
    m[:5, :10] = True
    assert M.ref_noise_rel(se, ref, m) == pytest.approx(s / (mu * math.sqrt(50)), rel=1e-12)
    # empirical check: the standard error of a ROI mean of independent noisy pixels
    rng = np.random.default_rng(3)
    means = [(mu + s * rng.standard_normal((10, 20))).mean() for _ in range(4000)]
    assert np.std(means) == pytest.approx(s / math.sqrt(n), rel=0.05)
    assert M.ref_noise_rel(se, np.zeros_like(ref)) is None


def test_flip_identity_masks_and_black_reference():
    T = _ramp()
    f = M.flip(T, T, {"all": np.ones((H, W), bool)})
    assert f["mean"] == pytest.approx(0.0, abs=1e-7) and f["rois"]["all"] == pytest.approx(0.0, abs=1e-7)
    err, _ = M.flip_error_map(T, 1.3 * T)
    assert err.shape == (H, W) and err.mean() > 0.01
    m = np.zeros((H, W), bool)
    m[:, :20] = True
    g = M.flip(1.3 * T, T, {"left": m, "none": np.zeros((H, W), bool)})
    assert g["rois"]["left"] == pytest.approx(err[m].mean(), rel=1e-6) and g["rois"]["none"] is None
    assert g["mean"] == pytest.approx(err.mean(), rel=1e-6)


def test_flip_black_or_dim_reference_does_not_abort():
    # FLIP's own exposure search exit()s the process for these; run in a child so a regression fails cleanly.
    code = (
        "import numpy as np\n"
        "from tools import metrics as M\n"
        "z = np.zeros((24, 32, 3)); r = np.random.default_rng(0).random((24, 32, 3))\n"
        "d = r * 1e-9; d[:15] = 0\n"
        "print(M.flip(z, z)['mean'], M.flip(r, z)['mean'] > 0, M.flip(d * 1.05, d)['mean'] >= 0)\n")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=False,
                       cwd=str(M.Path(M.__file__).resolve().parent.parent))
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.split() == ["0.0", "True", "True"]


# ------------------------------------------------------------------------------------------------ view_metrics

def _reference():
    full = _ramp(0.3, 1.2)
    direct = 0.7 * full
    lit = np.ones((H, W), bool)
    dark = np.zeros((H, W), bool)
    dark[5:15, 5:20] = True
    bleed = np.zeros((H, W), bool)
    bleed[30:40, 30:50] = True
    full[dark] = direct[dark]  # no indirect light in the dark ROI
    se = np.full((H, W, 3), 1e-3)
    ref = {"full": full, "direct": direct, "full_stderr": se, "direct_stderr": se * 0.5, "isolated_stderr": se * 0.8}
    masks = {"all": lit, "dark_box": dark, "wall": bleed}
    roles = {"all": "any", "dark_box": "dark", "wall": "bleed"}
    return ref, masks, roles


def test_view_metrics_direct_and_isolated():
    ref, masks, roles = _reference()
    eng_direct = 1.02 * ref["direct"]
    d = M.view_metrics(scene="s", view="v", engine="fake", mode="direct", kind="direct", final=eng_direct,
                       ref=ref, masks=masks, roles=roles, files={"capture": "a.exr"})
    assert d["status"] == "ok" and d["component"] == "direct" and d["reason"] is None
    assert d["rois"]["all"]["bias"] == pytest.approx(0.02, abs=1e-9) and d["energy"] == pytest.approx(0.02)
    assert d["rois"]["all"]["role"] == "any" and d["rois"]["all"]["pixels"] == H * W
    assert d["rois"]["all"]["ref_noise_rel"] == pytest.approx(
        5e-4 / math.sqrt(H * W) / M.roi_mean(ref["direct"]), rel=1e-9)
    assert d["files"] == {"capture": "a.exr", "direct_capture": None, "sheet": None}
    assert d["flip"]["mean"] > 0 and set(d["flip"]["rois"]) == set(masks)

    T_iso = ref["full"] - ref["direct"]
    E_iso = 0.9 * T_iso
    E_iso[masks["dark_box"]] = 0.01  # leak in the dark ROI
    E_iso[masks["wall"]] *= np.array([1.1, 1.0, 1.0])  # red bleed
    final = eng_direct + E_iso
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect", final=final,
                       direct_final=eng_direct, ref=ref, masks=masks, roles=roles, convergence={"settle_frames": 4})
    assert r["status"] == "ok" and r["component"] == "isolated" and r["convergence"] == {"settle_frames": 4}
    dk = r["rois"]["dark_box"]
    assert dk["role"] == "dark" and dk["bias"] is None and dk["rel_l1"] is None
    norm = M.roi_mean(T_iso, masks["all"])
    assert dk["leak_abs"] == pytest.approx(0.01) and dk["leak_rel"] == pytest.approx(0.01 / norm)
    assert dk["ref_leak_abs"] == 0.0 and dk["ref_leak_rel"] == 0.0
    assert dk["leak_noise_rel"] == pytest.approx(8e-4 / math.sqrt(150) / norm, rel=1e-9)
    w = r["bleed"]["wall"]
    assert w["c_eng"][0] > w["c_ref"][0] and w["dist"] > 0 and set(r["bleed"]) == {"wall"}
    assert r["rois"]["wall"]["bias_rgb"] == pytest.approx([0.9 * 1.1 - 1, -0.1, -0.1], abs=1e-9)
    json.dumps(r, allow_nan=False)


def test_scene_leak_normalisers():
    got = M.scene_leak_normalisers({"lit": {"direct": 0.5, "isolated": 0.12}, "dark": {"direct": 0.0, "isolated": 0.0},
                                    "dim": {"direct": 0.2, "isolated": None}})
    assert got == {"direct": 0.5, "isolated": 0.12}  # max over the scene's views, per component
    assert M.scene_leak_normalisers({"a": {"direct": 0.0}, "b": {"direct": None}}) == {"direct": None}  # black scene
    assert M.scene_leak_normalisers({}) == {}


def test_view_metrics_leak_normalised_by_the_scene():
    """A view whose isolated reference is black everywhere (a sealed room, a light switched off) still gets a
    leak_rel: relative to the scene's brightest view of the same component (DESIGN §7)."""
    ref, masks, roles = _reference()
    black = {k: np.zeros_like(v) for k, v in ref.items()}
    black["direct"] = ref["direct"]
    black["full"] = ref["direct"].copy()  # isolated = 0 in the whole view
    eng_direct = ref["direct"].copy()
    final = eng_direct + 0.01
    kw = dict(scene="s", view="dark", engine="fake", mode="probe", kind="indirect", final=final,
              direct_final=eng_direct, ref=black, masks=masks, roles=roles)
    own = M.view_metrics(**kw)
    assert own["rois"]["dark_box"]["leak_rel"] is None and own["leak_norm"] == 0.0  # the view's own mean is 0
    norms = M.scene_leak_normalisers({"lit": {"isolated": M.roi_mean(ref["full"] - ref["direct"], masks["all"]),
                                              "direct": M.roi_mean(ref["direct"], masks["all"])},
                                      "dark": {"isolated": 0.0, "direct": M.roi_mean(ref["direct"], masks["all"])}})
    r = M.view_metrics(**kw, leak_norm=norms)
    dk = r["rois"]["dark_box"]
    assert r["leak_norm"] == pytest.approx(norms["isolated"]) and norms["isolated"] > 0
    assert dk["leak_abs"] == pytest.approx(0.01) and dk["leak_rel"] == pytest.approx(0.01 / norms["isolated"])
    assert dk["ref_leak_rel"] == 0.0
    assert dk["leak_noise_rel"] == 0.0  # zero standard error over the scene normaliser
    # the direct row uses the direct component's normaliser
    d = M.view_metrics(scene="s", view="dark", engine="fake", mode="direct", kind="direct", final=eng_direct,
                       ref=ref, masks=masks, roles=roles, leak_norm={"direct": 2.0})
    assert d["leak_norm"] == 2.0
    assert d["rois"]["dark_box"]["leak_rel"] == pytest.approx(M.roi_mean(eng_direct, masks["dark_box"]) / 2.0)
    # a component missing from leak_norm leaves leak_rel undefined rather than silently using the view's own mean
    m = M.view_metrics(**kw, leak_norm={"direct": 2.0})
    assert m["leak_norm"] is None and m["rois"]["dark_box"]["leak_rel"] is None


def test_view_metrics_isolated_bias_on_lit_roi():
    ref, masks, _ = _reference()
    lit = np.zeros((H, W), bool)
    lit[20:28, :] = True
    masks = {"all": masks["all"], "lit": lit}
    T_iso = ref["full"] - ref["direct"]
    eng_direct = ref["direct"].copy()
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect",
                       final=eng_direct + 0.8 * T_iso, direct_final=eng_direct, ref=ref, masks=masks,
                       roles={"lit": "lit"})
    assert r["rois"]["lit"]["bias"] == pytest.approx(-0.2, abs=1e-9)
    assert r["rois"]["lit"]["rel_l1"] == pytest.approx(0.2, rel=0.02)
    assert r["energy"] == pytest.approx(-0.2, abs=1e-9)
    assert "ref_within_noise" not in r["rois"]["lit"]


def test_view_metrics_reference_zero_within_noise_has_no_ratios():
    """full - direct of a lone plane is ~1e-13 (float noise): ratios to it are noise, only bias_abs is kept."""
    ref, masks, _ = _reference()
    rng = np.random.default_rng(3)
    ref["full"] = ref["direct"] + rng.normal(0.0, 1e-13, ref["direct"].shape) + 2e-15
    ref["isolated_stderr"] = np.full((H, W, 3), 1e-13)
    masks = {"all": masks["all"]}
    eng_direct = ref["direct"].copy()
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect",
                       final=eng_direct + 0.01, direct_final=eng_direct, ref=ref, masks=masks)
    a = r["rois"]["all"]
    assert r["status"] == "ok" and a["ref_within_noise"] is True
    assert a["bias"] is None and a["rel_l1"] is None and a["rel_mse"] is None and a["bias_rgb"] is None
    assert a["bias_abs"] == pytest.approx(0.01, rel=1e-6) and r["energy"] is None
    # a reference well above its noise keeps every ratio
    ref["full"] = ref["direct"] + 0.05
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect",
                       final=eng_direct + 0.06, direct_final=eng_direct, ref=ref, masks=masks)
    assert r["rois"]["all"]["bias"] == pytest.approx(0.2, rel=1e-6) and r["energy"] == pytest.approx(0.2, rel=1e-6)


def test_view_metrics_nan_and_shape_failures():
    ref, masks, roles = _reference()
    bad = ref["direct"].copy()
    bad[3, 4, 1] = np.nan
    bad[5, 6, :] = np.inf
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="direct", kind="direct", final=bad, ref=ref,
                       masks=masks, roles=roles)
    assert r["status"] == "failed" and "non-finite" in r["reason"] and "2 non-finite pixels" in r["reason"]
    assert "NaN 1, inf 1" in r["reason"] and r["rois"] == {} and r["flip"] is None
    json.dumps(r, allow_nan=False)
    # the indirect mode's own direct capture is checked too
    r2 = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect", final=ref["full"],
                        direct_final=bad, ref=ref, masks=masks, roles=roles)
    assert r2["status"] == "failed" and "engine direct capture" in r2["reason"]
    r3 = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect", final=ref["full"][:10],
                        direct_final=None, ref=ref, masks=masks, roles=roles)
    assert r3["status"] == "failed" and "shape" in r3["reason"] and "missing" in r3["reason"]


def test_view_metrics_appearance_is_flip_only():
    ref, masks, roles = _reference()
    r = M.view_metrics(scene="s", view="v", engine="fake", mode="probe", kind="indirect", final=1.1 * ref["full"],
                       direct_final=None, ref={"full": ref["full"]}, masks=masks, roles=roles,
                       comparison="appearance")
    assert r["status"] == "ok" and r["rois"] == {} and r["energy"] is None and r["bleed"] == {}
    assert r["flip"]["mean"] > 0 and set(r["flip"]["rois"]) == set(masks)


def test_result_entry_shape():
    e = M.result_entry("s", "v", "future", "direct", "direct", status="skipped", reason="NotWired", by_design=False)
    assert set(e) == {"scene", "view", "engine", "mode", "kind", "status", "reason", "by_design", "component",
                      "rois", "energy", "bleed", "flip", "convergence", "files"}
    assert e["component"] == "direct" and e["status"] == "skipped"


def test_isolated_stderr_fallback():
    a, b = np.full((2, 2, 3), 3.0), np.full((2, 2, 3), 4.0)
    np.testing.assert_allclose(M.isolated_stderr({"full_stderr": a, "direct_stderr": b}), 5.0)
    assert M.isolated_stderr({}) is None


def test_load_reference_images(tmp_path):
    from tools.exr import write_exr
    write_exr(tmp_path / "full.exr", np.full((4, 5, 3), 2.0, np.float32), channels="R,G,B")
    write_exr(tmp_path / "direct.exr", np.full((4, 5, 3), 1.0, np.float32), channels="R,G,B")
    ref = M.load_reference_images(tmp_path)
    assert set(ref) == {"full", "direct"} and ref["full"].shape == (4, 5, 3) and ref["full"][0, 0, 0] == 2.0


# ------------------------------------------------------------------------------------------------ temporal

def test_split_states_and_window(tiny_scene):
    sc = tiny_scene("mini_timeline")
    assert M.split_states(sc.timeline) == timeline_states(sc) == [(0, 3), (4, 7), (8, 11)]
    assert M.split_states({"steps": [{"frame": 120}, {"frame": 240}], "end_frame": 359}) == \
        [(0, 119), (120, 239), (240, 359)]
    assert M.split_states([5], end_frame=9) == [(0, 4), (5, 9)]
    assert M.window(0, 119) == 10 and M.window(0, 19) == 5 and M.window(4, 7) == 1 and M.window(0, 1) == 1
    with pytest.raises(ValueError):
        M.split_states([5])


def _exp_step(pre, post, step, end, tau_frames):
    k = np.arange(end + 1, dtype=np.float64)
    y = np.where(k < step, pre, post + (pre - post) * np.exp(-(k - step) / tau_frames))
    return y


@pytest.mark.parametrize("tau", [3.0, 7.3, 12.5])
def test_t90_exponential(tau):
    step, end = 120, 359
    y = _exp_step(1.0, 0.25, step, end, tau)
    pre, post = M.settled(y, 0, step - 1), M.settled(y, step, end)
    assert pre == pytest.approx(1.0) and post == pytest.approx(0.25, abs=1e-6)
    n = M.t90(y, step, end, pre, post)
    assert abs(n - tau * math.log(10)) <= 1.0
    assert n == math.ceil(tau * math.log(10))
    steps = M.temporal_steps(y, [(0, step - 1), (step, end)], fps=60)
    assert steps[0]["frame"] == step and steps[0]["t90_frames"] == n and steps[0]["t90_s"] == pytest.approx(n / 60)
    assert steps[0]["timed"] is True and steps[0]["afterglow"] is None
    rising = _exp_step(0.25, 1.0, step, end, tau)
    assert M.t90(rising, step, end, 0.25, M.settled(rising, step, end)) == n


def test_t90_instant_unsettled_and_no_change():
    y = np.r_[np.full(10, 1.0), np.full(10, 0.5)]
    assert M.t90(y, 10, 19, 1.0, 0.5) == 0
    assert M.t90(np.r_[np.full(10, 1.0), np.linspace(1.0, 0.5, 10)], 10, 19, 1.0, 0.4) is None  # still moving
    flat = np.full(20, 1.0)
    flat[10:] += 1e-5
    st = M.temporal_steps(flat, [(0, 9), (10, 19)], fps=60)
    assert st[0]["timed"] is False and st[0]["t90_frames"] is None
    assert not M.is_change(1.0, 1.0 + 5e-4) and M.is_change(1.0, 1.002) and not M.is_change(None, 1.0)


def test_afterglow_known_decay():
    fps, step, end = 60.0, 120, 299
    tau_s = 0.2
    ref_pre, ref_post = 2.0, 0.5
    resid = 0.03  # engine settles 3 % of the drop above the reference
    k = np.arange(end + 1, dtype=np.float64)
    t = (k - step) / fps
    den = ref_pre - ref_post
    y = np.where(k < step, ref_pre, ref_post + resid * den + (1 - resid) * den * np.exp(-np.clip(t, 0, None) / tau_s))
    post = M.settled(y, step, end)
    ag = M.afterglow(y, step, end, ref_pre, ref_post, post, fps)
    for ts in (0.1, 0.25, 0.5, 1.0):
        expect = resid + (1 - resid) * math.exp(-ts / tau_s)
        assert ag["r"][str(ts)] == pytest.approx(expect, rel=1e-9)
    n_expect = math.ceil(tau_s * fps * math.log((1 - resid) / (0.05 - resid)))
    assert ag["t05_frames"] == n_expect and ag["t05_s"] == pytest.approx(n_expect / fps)
    assert ag["residual"] == pytest.approx(resid, abs=1e-6)
    # rising reference: no afterglow; r past the state's end is None
    assert M.afterglow(y, step, end, ref_post, ref_pre, post, fps) is None
    short = M.afterglow(y[:140], step, 139, ref_pre, ref_post, post, fps)
    assert short["r"]["0.1"] is not None and short["r"]["1.0"] is None
    # a residual above the threshold never settles
    assert M.afterglow(y + 0.2 * den, step, end, ref_pre, ref_post, post + 0.2 * den, fps)["t05_frames"] is None
    st = M.temporal_steps(y, [(0, step - 1), (step, end)], fps, ref_means=[ref_pre, ref_post])
    assert st[0]["afterglow"]["residual"] == pytest.approx(resid, abs=1e-6)


def test_flicker_known_gaussian_noise():
    rng = np.random.default_rng(7)
    mu, sigma = 0.5, 0.02
    T, h, w = 10, 30, 40
    frames = mu + sigma * rng.standard_normal((T, h, w))
    f = M.flicker(frames)
    c4 = math.sqrt(2 / (T - 1)) * math.gamma(T / 2) / math.gamma((T - 1) / 2)  # E[s] = c4 sigma
    assert f["temporal_cv"] == pytest.approx(c4 * sigma / mu, rel=0.03)
    assert f["frames"] == T and f["pixels"] == h * w
    # f2f: E|y(k) - y(k-1)| = 2 sigma_m / sqrt(pi) with sigma_m = sigma / sqrt(N); long window for a tight estimate
    long = mu + sigma * rng.standard_normal((800, 10, 20))
    g = M.flicker(long)
    expect = 2 * (sigma / math.sqrt(200)) / math.sqrt(math.pi) / mu
    assert g["f2f"] == pytest.approx(expect, rel=0.08)
    # RGB frames and masks; deterministic engine has zero flicker
    rgb = np.repeat(frames[..., None], 3, axis=-1)
    m = np.zeros((h, w), bool)
    m[:10] = True
    assert M.flicker(rgb, m)["pixels"] == 10 * w
    still = M.flicker(np.repeat(np.full((1, h, w, 3), 0.3), 6, axis=0))
    assert still["temporal_cv"] == 0.0 and still["f2f"] == 0.0
    assert M.flicker(frames[:1])["temporal_cv"] is None


def test_series_from_dict_and_nan_frames():
    y = {0: 1.0, 1: 1.0, 2: None, 3: 2.0}
    assert M.settled(y, 0, 3, W=4) == pytest.approx(4 / 3)
    assert M.frame_to_frame([1.0, 2.0, 1.0]) == pytest.approx(1.0 / (4 / 3))
    assert M.frame_to_frame([0.0, 0.0]) is None


def test_roi_roles_mini_room(tiny_scene):
    assert roi_roles(tiny_scene("mini_room")) == {"all": "any", "floor": "lit", "back_wall": "dark"}


@pytest.mark.reference
def test_end_to_end_on_mitsuba_reference(tiny_scene, tmp_path):
    """Masks from real AOVs + metrics on a real reference: a fake engine's known gains are recovered."""
    pytest.importorskip("mitsuba")
    from tools import masks as MK
    from tools import reference as R
    from tools.spec import expand_views

    sc = tiny_scene("mini_room")
    roles = MK.roi_roles(sc)
    for v in expand_views(sc):
        d, _ = R.ensure_reference(v, tmp_path / "cache", {"spp": 16, "batches": 2, "aov_spp": 4})
        masks = MK.view_masks(v, d)
        ref = M.load_reference_images(d)
        assert ("back_wall" in masks) == (v.id == "outside") and masks["floor"].sum() > 20
        r = M.view_metrics(scene=sc.name, view=v.id, engine="fake", mode="direct", kind="direct",
                           final=1.05 * ref["direct"], ref=ref, masks=masks, roles=roles)
        assert r["status"] == "ok"
        assert r["rois"]["floor"]["bias"] == pytest.approx(0.05, abs=1e-5)
        assert r["rois"]["floor"]["ref_noise_rel"] > 0 and r["energy"] == pytest.approx(0.05, abs=1e-5)
        iso = ref["full"] - ref["direct"]
        r = M.view_metrics(scene=sc.name, view=v.id, engine="fake", mode="probe", kind="indirect",
                           final=ref["direct"] + 0.9 * iso, direct_final=ref["direct"], ref=ref, masks=masks,
                           roles=roles)
        assert r["rois"]["all"]["bias"] == pytest.approx(-0.1, abs=1e-5)
        assert r["flip"]["mean"] > 0
        json.dumps(r, allow_nan=False)
