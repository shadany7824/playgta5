"""tools/inspector.py and the Windows launchers.

The inspector is built on a synthetic run (tiny EXRs, one engine with a direct and an indirect mode, a by-design
skip): manifests, .f16/.u8 sizes and values, ROI masks, copied links, that index.html and its assets reference only
local files, and the HTTP server. No browser is opened. When Node.js is installed, viewer.js is syntax-checked and its
pure helpers (float16 decoding, number formats, colour scale, ROI outline) are run against the Python side.
The launchers must use CRLF line endings.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pytest

from tools.exr import write_exr
from tools.inspector import ASSETS, build_inspector, main, make_server, to_f16
from tools.layout import RunLayout, write_latest
from tools.png import save_png

REPO = Path(__file__).resolve().parent.parent
H, W = 6, 8
SCENE = {
    "spec_version": 1, "name": "insp_scene", "group": "targeted", "failure_mode": "test failure mode",
    "image": {"width": W, "height": H}, "materials": {"grey": {"type": "diffuse", "albedo": [0.5, 0.5, 0.5]}},
    "objects": [{"name": "plane", "material": "grey",
                 "shape": {"type": "quad", "origin": [0, 0, 0], "u": [8, 0, 0], "v": [0, 6, 0]}}],
    "lights": [{"name": "lamp", "type": "point", "position": [4, 3, 2], "intensity": [1, 1, 1]}],
    "stations": [{"name": "s0", "position": [4, 3, 5], "look_at": [4, 3, 0], "up": [0, 1, 0], "vfov_deg": 60}],
    "rois": [{"name": "left", "role": "lit", "box": {"min": [-1, -1, -1], "max": [3.5, 10, 1]}},
             {"name": "corner", "role": "dark", "box": {"min": [5.5, -1, -1], "max": [10, 10, 1]}}],
}


def _img(seed: float) -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W]
    return np.stack([seed + xx / W, seed + yy / H, np.full((H, W), seed)], -1).astype(np.float32)


@pytest.fixture
def run(tmp_path) -> Path:
    """runs/r1 with a reference, captures of engine 'fake' (direct, gi), metrics/run/views JSON and a sheet."""
    from tools.spec import load_scene, views_summary

    scenes = tmp_path / "scenes" / "targeted"
    scenes.mkdir(parents=True)
    (scenes / "insp_scene.json").write_text(json.dumps(SCENE), encoding="utf-8")
    run = tmp_path / "runs" / "r1"
    L = RunLayout(run)
    scene = load_scene(scenes / "insp_scene.json")
    L.views_json("insp_scene").parent.mkdir(parents=True)
    L.views_json("insp_scene").write_text(json.dumps(views_summary(scene)), encoding="utf-8")
    rdir = L.reference_dir("insp_scene", "s0")
    rdir.mkdir(parents=True)
    full, direct = _img(1.0), _img(0.25)
    full[0, 0] = [2.0e5, 1.0, 1.0]  # beyond float16: clipped to 65504
    yy, xx = np.mgrid[0:H, 0:W]
    aux = {"depth.exr": np.ones((H, W, 1), np.float32),
           "normal.exr": np.tile(np.array([0, 0, 1], np.float32), (H, W, 1)),
           "position.exr": np.stack([xx, yy, np.zeros((H, W))], -1).astype(np.float32),
           "full.exr": full, "direct.exr": direct, "full_stderr.exr": np.full((H, W, 3), 0.01, np.float32),
           "direct_stderr.exr": np.full((H, W, 3), 0.002, np.float32),
           "isolated_stderr.exr": np.full((H, W, 3), 0.02, np.float32)}
    for name, a in aux.items():
        write_exr(rdir / name, a, channels=["Z"] if name == "depth.exr" else None)
    (rdir / "receipt.json").write_text("{}", encoding="utf-8")
    d_final, g_final = _img(0.3), _img(1.1)
    g_final[5, 7] = np.nan
    for mode, img in (("direct", d_final), ("gi", g_final)):
        p = L.station_capture("fake", "insp_scene", mode, "s0")
        p.parent.mkdir(parents=True)
        write_exr(p, img)
    save_png(L.sheet_png("insp_scene", "s0"), np.zeros((4, 4, 3), np.uint8))
    rows = [{"scene": "insp_scene", "view": "s0", "engine": "fake", "mode": m, "kind": k, "status": "ok",
             "reason": None, "by_design": False, "component": c,
             "rois": {"all": {"role": "any", "pixels": 24, "bias": 0.1, "rel_l1": 0.1, "rel_mse": 0.01,
                              "ref_noise_rel": 0.001}},
             "energy": 0.1, "bleed": {}, "flip": {"mean": 0.05, "rois": {}},
             "files": {"capture": f"fake/insp_scene/stations/{m}/s0/final.exr", "sheet": "sheets/insp_scene/s0.png"}}
            for m, k, c in (("direct", "direct", "direct"), ("gi", "indirect", "isolated"))]
    rows.append({"scene": "insp_scene", "view": None, "engine": "future", "mode": None, "kind": None,
                 "status": "skipped", "reason": "future engine not wired", "by_design": True, "rois": {}})
    metrics = {"metrics_version": 1, "run": "r1", "git": "abc1234",
               "engines": {"fake": {"status": "ok", "modes": {"direct": {"kind": "direct", "dynamic": False},
                                                              "gi": {"kind": "indirect", "dynamic": True}}},
                           "future": {"status": "skipped", "reason": "future engine not wired", "modes": {}}},
               "scenes": {"insp_scene": {"group": "targeted", "comparison": "exact",
                                         "views": [{"id": "s0", "kind": "station"}]}},
               "results": rows}
    L.metrics_json.write_text(json.dumps(metrics), encoding="utf-8")
    L.run_json.write_text(json.dumps({"run": "r1", "git": "abc1234",
                                      "config": {"pairs": {"scenes_root": str(tmp_path / "scenes")}}}),
                          encoding="utf-8")
    L.report_md.write_text("# report\n", encoding="utf-8")
    return run


def _f16(path: Path, channels: int) -> np.ndarray:
    return np.frombuffer(path.read_bytes(), "<f2").astype(np.float64).reshape(H, W, channels)


def test_build_manifest_files_and_values(run):
    from tools.masks import view_masks
    from tools.spec import expand_views, load_scene

    root = build_inspector(run, log=None)
    assert root == RunLayout(run).inspect_dir
    for name in (*ASSETS, "manifest.json"):
        assert (root / name).is_file(), name
    top = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert top["inspect_version"] == 1 and top["run"] == "r1" and top["git"] == "abc1234"
    assert top["links"]["report"] == "links/report.md" and (root / "links" / "report.md").is_file()
    (sc,) = top["scenes"]
    assert sc["name"] == "insp_scene" and sc["failure_mode"] == "test failure mode"
    (v,) = sc["views"]
    assert v["error"] is None and (root / v["manifest"]).is_file()
    vm = json.loads((root / v["manifest"]).read_text(encoding="utf-8"))
    assert (vm["width"], vm["height"], vm["comparison"]) == (W, H, "exact") and not vm["warnings"]
    vdir = (root / v["manifest"]).parent
    # every file has the size its manifest entry declares
    entries = [f for c in vm["columns"] for f in list(c["files"].values()) + list(c.get("noise", {}).values())]
    entries += vm["rois"]
    assert entries
    for f in entries:
        per = 2 if f["dtype"] == "float16" else 1
        assert (vdir / f["file"]).stat().st_size == H * W * f["channels"] * per, f
    cols = {c["id"]: c for c in vm["columns"]}
    assert list(cols) == ["reference", "fake/direct", "fake/gi", "future"]
    assert cols["future"]["status"] == "skipped" and cols["future"]["by_design"] and not cols["future"]["files"]
    assert cols["fake/direct"]["files"]["component"] == cols["fake/direct"]["files"]["final"]
    assert cols["fake/gi"]["component"] == "isolated" and cols["fake/gi"]["dynamic"] is True
    # values: float16 of the reference and of final(gi) - final(direct), clipped beyond the float16 range
    full, direct = _img(1.0).astype(np.float64), _img(0.25).astype(np.float64)
    full[0, 0, 0] = 65504.0
    np.testing.assert_allclose(_f16(vdir / "ref_full.f16", 3), full, rtol=1e-3)
    np.testing.assert_allclose(_f16(vdir / "ref_isolated.f16", 3), full - direct, rtol=1e-3)
    iso = _f16(vdir / cols["fake/gi"]["files"]["component"]["file"], 3)
    expect = _img(1.1).astype(np.float64) - _img(0.3)
    assert np.isnan(iso[5, 7]).all()  # NaN kept, so the viewer can mark it
    ok = np.ones((H, W), bool)
    ok[5, 7] = False
    np.testing.assert_allclose(iso[ok], expect[ok], rtol=2e-3, atol=1e-3)
    se = _f16(vdir / "ref_se_isolated.f16", 1)[..., 0]
    np.testing.assert_allclose(se, 0.02, rtol=1e-3)  # per-pixel s.e. of Y (channels fully correlated)
    # ROI masks equal the metrics' masks (eroded), roles from the spec
    scene = load_scene(Path(run).parent.parent / "scenes" / "targeted" / "insp_scene.json")
    masks = view_masks(expand_views(scene)[0], RunLayout(run).reference_dir("insp_scene", "s0"))
    rois = {r["name"]: r for r in vm["rois"]}
    assert set(rois) == {"all", "left", "corner"} and rois["corner"]["role"] == "dark"
    for name, r in rois.items():
        m = np.frombuffer((vdir / r["file"]).read_bytes(), np.uint8).reshape(H, W).astype(bool)
        np.testing.assert_array_equal(m, masks[name])
        assert r["pixels"] == int(masks[name].sum())
    assert rois["left"]["pixels"] > 0
    # exposures and error epsilons, metrics rows and links
    assert vm["exposure"]["final"] > 0 and vm["eps"]["isolated"] > 0
    assert [r["engine"] for r in vm["metrics"]] == ["fake", "fake", "future"]
    assert vm["links"]["sheet"] == "links/sheets/insp_scene/s0.png" and (root / vm["links"]["sheet"]).is_file()


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("src", "href", "action", "data") and v is not None:
                self.refs.append(v)


def test_assets_reference_only_local_files(run):
    root = build_inspector(run, log=None)
    p = _Refs()
    p.feed((root / "index.html").read_text(encoding="utf-8"))
    assert p.refs and "viewer.js" in p.refs and "style.css" in p.refs
    for ref in p.refs:
        if ref.startswith("data:"):
            continue  # inline (the empty favicon)
        assert not re.match(r"^[a-z][a-z0-9+.-]*:|^//", ref, re.I), ref
        assert (root / ref).is_file(), ref
    for name in ASSETS:
        text = (root / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://|@import|\bimportScripts\b|\bimport\s*\(", text), name
        assert (root / name).read_bytes() == (REPO / "tools" / "inspector_web" / name).read_bytes()


def test_scene_filter_rebuild_and_errors(run, tmp_path):
    root = build_inspector(run, scene="insp_scene", log=None)
    top = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert top["default_scene"] == "insp_scene"
    stale = root / "data" / "old_scene"
    stale.mkdir()
    build_inspector(run, log=None)
    assert not stale.exists()  # data/ is rebuilt from scratch
    with pytest.raises(ValueError, match="not in run"):
        build_inspector(run, scene="nope", log=None)
    empty = tmp_path / "empty_run"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        build_inspector(empty, log=None)
    # without a loadable spec the masks fall back to ROI 'all' and the view still builds
    L = RunLayout(run)
    L.run_json.write_text(json.dumps({"config": {"pairs": {"scenes_root": str(tmp_path / "missing")}}}),
                          encoding="utf-8")
    root = build_inspector(run, scenes_root=tmp_path / "no_specs", log=None)
    vm = json.loads((root / "data" / "insp_scene" / "s0" / "manifest.json").read_text(encoding="utf-8"))
    assert [r["name"] for r in vm["rois"]] == ["all"]
    assert any("spec not loadable" in w for w in json.loads((root / "manifest.json").read_text())["warnings"])


def test_cli_build_only(run, capsys):
    assert main(["--run", str(run), "--no-serve", "--no-open"]) == 0
    assert "built" in capsys.readouterr().out
    write_latest(run, run.parent)
    assert main(["insp_scene", "--runs-root", str(run.parent), "--no-serve"]) == 0  # LATEST + positional scene
    top = json.loads((RunLayout(run).inspect_dir / "manifest.json").read_text(encoding="utf-8"))
    assert top["default_scene"] == "insp_scene"
    assert main(["--run", str(run.parent / "missing"), "--no-serve"]) == 1
    assert main(["--runs-root", str(run.parent / "nothing_here"), "--no-serve"]) == 1
    assert main(["--run", str(run), "--scene", "nope", "--no-serve"]) == 1


def test_server_serves_the_inspect_dir(run):
    root = build_inspector(run, log=None)
    server = make_server(root, port=0)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    try:
        host, port = server.server_address
        assert host == "127.0.0.1"
        base = f"http://127.0.0.1:{port}/"
        with urllib.request.urlopen(base + "index.html", timeout=10) as r:
            assert r.status == 200 and r.headers["Content-Type"].startswith("text/html")
        with urllib.request.urlopen(base + "viewer.js", timeout=10) as r:
            assert r.headers["Content-Type"].startswith("text/javascript")
        with urllib.request.urlopen(base + "data/insp_scene/s0/ref_full.f16", timeout=10) as r:
            assert r.headers["Content-Type"] == "application/octet-stream" and len(r.read()) == H * W * 3 * 2
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "../metrics.json", timeout=10)
        # a taken port moves on to the next free one
        other = make_server(root, port=port)
        assert other.server_address[1] != port
        other.server_close()
    finally:
        server.shutdown()
        server.server_close()


def test_to_f16():
    a = to_f16(np.array([1.0, -7e5, 7e5, np.inf, np.nan, 1e-9]))
    assert a.dtype == np.dtype("<f2")
    assert a[0] == 1 and a[1] == -65504 and a[2] == 65504 and np.isinf(a[3]) and np.isnan(a[4])


# ------------------------------------------------------------------------------------------------ viewer.js (Node)

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js not installed")
def test_viewer_js_helpers_match_python(tmp_path):
    from tools import report
    from tools.png import DIVERGING_ANCHORS

    js = REPO / "tools" / "inspector_web" / "viewer.js"
    subprocess.run([NODE, "--check", str(js)], check=True, capture_output=True, timeout=60)
    vals = [0.0, 1.0, -2.5, 1e-5, 65504.0, 6.0e-8, 0.333, np.inf, -np.inf]
    f16 = tmp_path / "v.f16"
    f16.write_bytes(to_f16(np.array(vals)).tobytes())
    nums = [0.099, 1.0, 12.34, 123.4, 1234.5, 1.234e-5, -0.0012345, 0.0, 0.1, -0.00123, 0.004]
    script = f"""
const v = require({json.dumps(str(js))});
const fs = require('fs');
const buf = fs.readFileSync({json.dumps(str(f16))});
const dec = Array.from(v.decodeF16(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length)))
  .map((x) => isFinite(x) ? x : String(x));
const nums = {json.dumps(nums)};
const mask = [0,0,0,0, 0,1,1,0, 0,1,1,0, 0,0,0,0];
const full = [1,1,1, 1,1,1, 1,1,1];
console.log(JSON.stringify({{dec: dec, sig: nums.map((x) => v.fmtSig(x)), pct: nums.map((x) => v.fmtPct(x)),
  pctu: nums.map((x) => v.fmtPct(x, false)), lo: v.diverging(-1), mid: v.diverging(0), hi: v.diverging(5),
  nan: v.diverging(NaN), outline: v.outline(mask, 4, 4), border: v.outline(full, 3, 3),
  srgb: [v.srgb8(0), v.srgb8(1), v.srgb8(0.5), v.srgb8(NaN)],
  err: v.relError(1.1, 1.0, 0.0)}}));
"""
    out = subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True, timeout=60).stdout
    r = json.loads(out)
    expect = np.array(vals, dtype=np.float16).astype(np.float64)
    for got, want in zip(r["dec"], expect):
        if np.isfinite(want):
            assert got == pytest.approx(float(want), rel=0, abs=0)
        else:
            assert got == ("Infinity" if want > 0 else "-Infinity")
    # number formats identical to the report's (JS writes exponents without the zero padding)
    for x, s, p, pu in zip(nums, r["sig"], r["pct"], r["pctu"]):
        assert s == report.fmt_sig(x).replace("e-0", "e-").replace("e+0", "e+"), x
        assert p == report.fmt_pct(x).replace("e-0", "e-").replace("e+0", "e+"), x
        assert pu == report.fmt_pct(x, signed=False).replace("e-0", "e-").replace("e+0", "e+"), x
    assert r["lo"] == DIVERGING_ANCHORS[0, 1:].tolist() and r["hi"] == DIVERGING_ANCHORS[-1, 1:].tolist()
    assert r["mid"] == [247, 247, 247] and r["nan"] is None
    assert sorted(r["outline"]) == [5, 6, 9, 10] and r["border"] == []  # the image border is not an edge
    assert r["srgb"] == [0, 255, 188, 0] and r["err"] == pytest.approx(0.1)


# ------------------------------------------------------------------------------------------------ launchers

LAUNCHERS = ("Setup.cmd", "Inspect.cmd", "Run-Harness.cmd")


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launchers_use_crlf(name):
    data = (REPO / name).read_bytes()
    assert data.endswith(b"\r\n") and b"\r\n" in data
    assert data.count(b"\n") == data.count(b"\r\n"), "every line must end in CRLF"
    assert b"\r\r" not in data
    data.decode("ascii")  # plain ASCII: cmd.exe reads batch files in the OEM code page


def test_launcher_contents():
    setup, insp, run = ((REPO / n).read_text(encoding="ascii") for n in LAUNCHERS)
    assert setup.index("py -3 -c") < setup.index("python -c")  # py launcher first, then python
    assert "sys.version_info >= (3, 11)" in setup and "-m venv .venv" in setup
    assert "-m pip install -r requirements.txt" in setup and "-m playwright install chromium" in setup
    assert "Next steps" in setup
    for text, cmd in ((insp, "-m tools.inspector --run LATEST %*"), (run, "-m tools.run_all %*")):
        assert 'cd /d "%~dp0"' in text and cmd in text
        assert text.index(r".venv\Scripts\python.exe") < text.index("py -3 -c") < text.index("python -c")
    assert "pause" in insp.split("%PY% -m tools.inspector")[1].split(":find_python")[0]  # pause on error
    tail = run.split("%PY% -m tools.run_all")[1].split(":find_python")[0]
    assert "pause" in tail and 'if "%RC%"=="0"' in tail  # pause at the end, either way
