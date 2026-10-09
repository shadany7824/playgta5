"""threejs-web runner (DESIGN §4.3): draws a three.js bundle with the pinned, unmodified three.js r186 WebGL build in
headless Chromium, driven by Playwright.

    python web/runner.py --bundle <dir>/bundle.json --out <capture dir>
        [--adapter <substring>] [--power high-performance|low-power] [--parity] [--backend <name>]

web/ and the bundle directory are served from a ThreadingHTTPServer on 127.0.0.1 (random port). The frame loop runs
here with a fixed timestep: one ``H.frame`` call per frame (web/harness.js). Captures come back as base64 Float32 RGB
(row 0 = top) and are written as EXR via tools/exr.py; parity PNGs via tools/png.py. Writes receipt.json and
timing.json into --out. Exit codes: 0 ok, 2 by-design skip (one JSON line {"skip": reason} on stdout), else failure.

--backend maps to ANGLE (--use-angle=...); --power sets the WebGL powerPreference (plus
--force_high_performance_gpu); --adapter cannot be mapped to a Chromium flag, so it is recorded and checked against
the WebGL renderer string, not enforced. On Linux without /dev/dri, SwiftShader flags are used.
Environment: HARNESS_CHROMIUM (browser executable), HARNESS_CHROMIUM_ARGS (extra flags),
HARNESS_WEB_SOFTWARE=1|0 (force / forbid SwiftShader).
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import platform
import re
import shlex
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

WEB_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEB_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from renderers.threejs import CHROMIUM_SOFTWARE_ARGS, ThreeJsWeb, find_chromium  # noqa: E402
from tools.exr import write_exr  # noqa: E402
from tools.png import save_png  # noqa: E402

RUNNER_REL = "web/runner.py"
BACKEND_FLAGS = {
    "vulkan": ["--use-angle=vulkan", "--enable-features=Vulkan"],
    "d3d11": ["--use-angle=d3d11"],
    "d3d9": ["--use-angle=d3d9"],
    "gl": ["--use-angle=gl"],
    "opengl": ["--use-angle=gl"],
    "gles": ["--use-angle=gles"],
    "metal": ["--use-angle=metal"],
    "swiftshader": list(CHROMIUM_SOFTWARE_ARGS),
}
PASSES = {
    "main": "shadow-map update (three.js renders shadows inside render(); see 'shadow_maps') + every SSAA sample "
            "render + its additive resolve into the accumulation target; in parity mode the canvas render",
    "probe": "CubeCamera.update (6 faces) for the light probe; 0.0 on frames without a probe capture",
}


class Skip(Exception):
    """By-design skip: exit code 2 with {"skip": reason}."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ------------------------------------------------------------------------------------------------ http server

class _Handler(SimpleHTTPRequestHandler):
    """Static files from a few roots (longest URL prefix wins). Explicit MIME types: on Windows the registry can map
    .js to text/plain, which browsers refuse for module scripts. COOP/COEP make the page cross-origin isolated
    (finer performance.now())."""

    routes: ClassVar[list[tuple[str, Path]]] = []
    verbose = False
    extensions_map: ClassVar[dict[str, str]] = {
        **SimpleHTTPRequestHandler.extensions_map,
        "": "application/octet-stream", ".js": "text/javascript", ".mjs": "text/javascript",
        ".json": "application/json", ".html": "text/html", ".bin": "application/octet-stream",
        ".map": "application/json",
    }

    def translate_path(self, path: str) -> str:
        p = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        for prefix, root in self.routes:
            if p.startswith(prefix):
                target = (root / p[len(prefix):].lstrip("/\\")).resolve()
                if target == root or root in target.parents:
                    return str(target)
                break
        return str(WEB_DIR / "__not_found__")

    def list_directory(self, path):  # no directory listings
        self.send_error(404, "Not found")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def log_message(self, format, *args) -> None:
        if self.verbose:
            sys.stdout.write("[http] " + (format % args) + "\n")


def make_server(routes: dict[str, Path], verbose: bool = False) -> ThreadingHTTPServer:
    """HTTP server on 127.0.0.1 with a random port serving {url prefix: directory}."""
    table = sorted(((p if p.endswith("/") else p + "/", Path(d).resolve()) for p, d in routes.items()),
                   key=lambda t: len(t[0]), reverse=True)
    handler = type("HarnessHandler", (_Handler,), {"routes": table, "verbose": verbose})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    return server


@contextlib.contextmanager
def serve(routes: dict[str, Path], verbose: bool = False):
    """Run make_server(routes) in a background thread; yields the base URL (no trailing slash)."""
    server = make_server(routes, verbose)
    th = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    th.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


# ------------------------------------------------------------------------------------------------ chromium

def software_required() -> tuple[bool, str]:
    """Whether to use SwiftShader: HARNESS_WEB_SOFTWARE=1|0 decides; else Linux without /dev/dri."""
    env = os.environ.get("HARNESS_WEB_SOFTWARE", "").strip().lower()
    if env in ("1", "true", "yes"):
        return True, "HARNESS_WEB_SOFTWARE=1"
    if env in ("0", "false", "no"):
        return False, ""
    if sys.platform.startswith("linux") and not Path("/dev/dri").exists():
        return True, "Linux without /dev/dri (no GPU device)"
    return False, ""


def chromium_flags(backend: str | None, power: str | None, adapter: str | None, software: bool,
                   software_reason: str = "") -> tuple[list[str], dict]:
    """Chromium flags for the requested backend/power (DESIGN §4.3) and notes on how each request was handled."""
    flags: list[str] = []
    notes: dict[str, str] = {}
    if software:
        flags += CHROMIUM_SOFTWARE_ARGS
        notes["software"] = f"SwiftShader ({software_reason or 'requested'})"
        if backend and backend.lower() != "swiftshader":
            notes["backend"] = f"'{backend}' ignored: software rendering in use"
    else:
        flags.append("--ignore-gpu-blocklist")
        if backend:
            b = backend.lower()
            if b not in BACKEND_FLAGS:
                raise SystemExit(f"--backend {backend!r}: choose from {sorted(BACKEND_FLAGS)}")
            flags += [f for f in BACKEND_FLAGS[b] if f not in flags]
            notes["backend"] = f"'{backend}' -> {' '.join(BACKEND_FLAGS[b])}"
        else:
            notes["backend"] = "browser default (ANGLE picks the platform backend)"
    if power:
        notes["power"] = f"WebGL powerPreference '{power}'"
        if power == "high-performance" and not software:
            flags.append("--force_high_performance_gpu")
            notes["power"] += " + --force_high_performance_gpu"
    if adapter:
        notes["adapter"] = (f"'{adapter}' recorded, not enforced: Chromium has no adapter-by-name flag; "
                            "device.adapter_matches says whether the WebGL renderer string contains it")
    extra = os.environ.get("HARNESS_CHROMIUM_ARGS", "").strip()
    if extra:
        flags += shlex.split(extra, posix=os.name != "nt")
        notes["extra"] = "HARNESS_CHROMIUM_ARGS"
    return flags, notes


def adapter_type(renderer: str) -> str:
    """DiscreteGPU | IntegratedGPU | CPU | Unknown, guessed from the WebGL renderer string."""
    r = renderer.lower()
    if any(k in r for k in ("swiftshader", "llvmpipe", "lavapipe", "softpipe", "software", "basic render")):
        return "CPU"
    if any(k in r for k in ("nvidia", "geforce", "quadro", "tesla")) or re.search(r"\barc\b", r) or \
            re.search(r"radeon\s*(\(tm\)\s*)?(rx|pro|r9|r7|vii)", r):
        return "DiscreteGPU"
    if any(k in r for k in ("intel", "apple", "adreno", "mali", "radeon(tm) graphics", "radeon graphics", "vega")):
        return "IntegratedGPU"
    return "Unknown"


def angle_backend(renderer: str) -> str:
    """ANGLE backend named in the WebGL renderer string."""
    for pat, name in ((r"direct3d11|d3d11", "D3D11"), (r"d3d9|direct3d9", "D3D9"), (r"vulkan", "Vulkan"),
                      (r"metal", "Metal"), (r"opengl es", "OpenGL ES"), (r"opengl", "OpenGL")):
        if re.search(pat, renderer, re.IGNORECASE):
            return name
    return "unknown"


def _chrome_rss_bytes() -> int | None:
    """Sum of RSS over this process's Chromium descendants (psutil, else /proc on Linux); None if unknown."""
    try:
        import psutil  # optional
    except ImportError:
        psutil = None
    if psutil is not None:
        total = 0
        try:
            for c in psutil.Process().children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    if "chrom" in c.name().lower():
                        total += c.memory_info().rss
        except psutil.Error:
            return None
        return total
    if not sys.platform.startswith("linux"):
        return None
    try:
        kids: dict[int, list[int]] = {}
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                with contextlib.suppress(OSError, IndexError, ValueError):
                    ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
                    kids.setdefault(ppid, []).append(int(d.name))
        total, todo = 0, list(kids.get(os.getpid(), []))
        while todo:
            pid = todo.pop()
            todo += kids.get(pid, [])
            with contextlib.suppress(OSError, ValueError):
                if "chrom" in Path(f"/proc/{pid}/comm").read_text().lower():
                    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                        if line.startswith("VmRSS:"):
                            total += int(line.split()[1]) * 1024
        return total
    except OSError:
        return None


class Browser:
    """One headless Chromium + harness page; ``call`` evaluates and surfaces page errors."""

    def __init__(self, pw, exe: Path, flags: list[str], base_url: str, headless: bool = True):
        self.flags = list(flags)
        self.errors: list[str] = []
        self.console_errors: list[str] = []
        self._seen: dict[str, int] = {}
        self.browser = pw.chromium.launch(executable_path=str(exe), headless=headless, args=self.flags)
        self.version = self.browser.version
        self.page = self.browser.new_page(device_scale_factor=1)
        self.page.on("console", self._console)
        self.page.on("pageerror", self._pageerror)
        self.page.goto(base_url + "/harness.html")
        deadline = time.monotonic() + 60.0
        while not self.page.evaluate("() => !!(window.H && window.H.ready === true)"):
            if self.errors or time.monotonic() > deadline:
                detail = (self.errors or self.console_errors or ["timeout"])[0]
                raise RuntimeError(f"harness page did not load: {detail}")
            self.page.wait_for_timeout(25)

    def _console(self, msg) -> None:
        text = msg.text
        n = self._seen.get(text, 0)
        self._seen[text] = n + 1
        if msg.type == "error":
            self.console_errors.append(text)
        if n < 3:
            print(f"[console.{msg.type}] {text}" + (" (repeats suppressed)" if n == 2 else ""), flush=True)

    def _pageerror(self, err) -> None:
        self.errors.append(str(err))
        print(f"[pageerror] {err}", flush=True)

    def call(self, fn: str, arg=None):
        result = self.page.evaluate(fn, arg)
        if self.errors:
            raise RuntimeError(f"page error: {self.errors[0]}")
        return result

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.browser.close()


# ------------------------------------------------------------------------------------------------ helpers

def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def decode_rgb(b64: str, width: int, height: int) -> np.ndarray:
    """base64 little-endian Float32 RGB (row 0 = top) -> (H, W, 3) float32."""
    return np.frombuffer(base64.b64decode(b64), dtype="<f4").reshape(height, width, 3).astype(np.float32)


def decode_rgb8(b64: str, width: int, height: int) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype=np.uint8).reshape(height, width, 3).copy()


def rel_change(prev: np.ndarray | None, last: np.ndarray) -> float | None:
    """sum |Y(last) - Y(prev)| / sum |Y(last)| (DESIGN §1 luminance)."""
    if prev is None:
        return None
    w = np.array([0.2126, 0.7152, 0.0722])
    y1, y0 = last.astype(np.float64) @ w, prev.astype(np.float64) @ w
    den = float(np.abs(y1).sum())
    return float(np.abs(y1 - y0).sum() / den) if den > 0 else 0.0


def _settings(bundle: dict, info: dict, parity: bool, flags: list[str], notes: dict, power: str | None) -> dict:
    ed = bundle["engine_data"]
    r = ed["renderer"]
    shadows = {lt["name"]: {"type": lt["type"], **lt.get("shadow", {})} for lt in ed["lights"] if lt.get("castShadow")}
    probe = dict(ed.get("probe", {}))
    if probe.get("enabled"):
        probe["capture"] = ("CubeCamera(near, far, WebGLCubeRenderTarget(cubeSize, {type})) at the camera position; "
                            "LightProbeGenerator.fromCubeRenderTarget (async readback); one LightProbe in the scene")
        probe["schedule"] = ("every frame, previous probe active (starts from zero SH at each view)" if probe.get("dynamic")
                             else "first frame of each view and right after each timeline event; probe intensity 0 "
                                  "during capture")
        probe["capture_sees_background"] = True  # CubeCamera.update renders scene.background like any render
    n = 1 if parity else int(r["ssaa"])
    return {
        "three": {"revision": ed.get("three_revision"), "build": "web/vendor/three/build/three.module.js (unmodified)"},
        "renderer": {"class": "WebGLRenderer", "antialias": False, "alpha": False, "preserveDrawingBuffer": True,
                     "powerPreference": power or "default", "pixelRatio": 1, "outputBufferType": "UnsignedByteType",
                     "precision": info["webgl"].get("precision")},
        "measurement": None if parity else {
            "target": "WebGLRenderTarget RGBAFormat FloatType, colorSpace LinearSRGBColorSpace, NearestFilter",
            "toneMapping": "NoToneMapping", "outputColorSpace": "srgb-linear (render targets are linear in r186)",
            "ssaa": n, "ssaa_offsets": r["ssaa_offsets"], "ssaa_method": "camera.setViewOffset(W, H, dx, dy, W, H)",
            "resolve": ("GPU: additive blend (ONE, ONE) of each sample x 1/n into a FloatType target"
                        if info.get("float_blend") else "CPU: readRenderTargetPixels per sample, float64 mean")},
        "parity": {"samples": 1, "view_offset": None, "target": "canvas (RGBA8 drawing buffer)",
                   "toneMapping": r["parity"]["toneMapping"], "toneMappingExposure": r["parity"]["exposure"],
                   "outputColorSpace": r["parity"]["outputColorSpace"], "readback": "gl.readPixels RGBA/UNSIGNED_BYTE",
                   "linear_exr": "same single sample, no offset, FloatType target, NoToneMapping"} if parity else None,
        "shadow_maps": {"enabled": True, "type": r["shadowMapType"],
                        "update": "once per frame: shadowMap.autoUpdate=false, needsUpdate=true at frame start; the "
                                  "first render() of the frame redraws them (the probe pass on probe-capture frames, "
                                  "else the main pass)",
                        "lights": shadows},
        "probe": probe,
        "rect_area_lights": "RectAreaLightUniformsLib.init() (LTC tables)" if any(
            lt["type"] == "RectAreaLight" for lt in ed["lights"]) else None,
        "colour": "Color.setRGB(r, g, b, LinearSRGBColorSpace); ColorManagement enabled (no conversion)",
        "outputs": {"station": "EXR FLOAT32 ZIP R,G,B", "timeline": "EXR HALF ZIP R,G,B",
                    "parity_png": "8-bit sRGB after the tone map" if parity else None},
        "frame_loop": "Python drives one H.frame per frame (fixed timestep); frame k applies its timeline ops, then "
                      "draws; frames not captured are still drawn",
        "timing": {"gpu": "EXT_disjoint_timer_query_webgl2 TIME_ELAPSED_EXT" if info.get("timer_query") else None,
                   "cpu": "performance.now() around the frame (ops + probe + main submit), readback excluded",
                   "passes": PASSES,
                   "shadow_pass": "not reported separately: inside three.js render(), counted in whichever pass "
                                  "renders first in the frame"},
        "chromium": {"flags": flags, "headless": True, "notes": notes},
    }


# ------------------------------------------------------------------------------------------------ run

def run(args) -> int:
    started, t0 = _utc(), time.perf_counter()
    bundle_json = Path(args.bundle).resolve()
    out = Path(args.out).resolve()
    bundle = json.loads(bundle_json.read_text(encoding="utf-8"))
    if bundle.get("bundle_version") != 1 or bundle.get("engine") != "threejs":
        raise ValueError(f"{bundle_json}: not a three.js bundle v1 (engine={bundle.get('engine')!r}, "
                         f"bundle_version={bundle.get('bundle_version')!r})")
    kind = bundle["kind"]
    if kind not in ("stations", "timeline"):
        raise ValueError(f"unknown bundle kind {kind!r}")
    width, height = int(bundle["image"]["width"]), int(bundle["image"]["height"])
    measure = bundle.get("measure", {})
    parity = bool(args.parity or measure.get("parity", False))
    warm = int(measure.get("warmup_frames", 0))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise Skip("playwright is not installed (pip install playwright)") from None
    exe = Path(args.chromium) if args.chromium else find_chromium()
    if exe is None or not exe.is_file():
        raise Skip("no Chromium found (set HARNESS_CHROMIUM or PLAYWRIGHT_BROWSERS_PATH, or run "
                   "'python -m playwright install chromium')")

    software, why = software_required()
    if (args.backend or "").lower() == "swiftshader":
        software, why = True, "--backend swiftshader"
    cfg = {"bundleUrl": "/bundle/bundle.json", "parity": parity,
           "powerPreference": args.power or "default", "gpuResolve": not args.cpu_resolve}
    out.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    convergence: dict = {}
    rss_samples: list[int] = []

    def sample_rss():
        v = _chrome_rss_bytes()
        if v is not None:
            rss_samples.append(v)

    routes = {"/bundle/": bundle_json.parent, "/": WEB_DIR}
    with serve(routes, verbose=args.verbose) as base_url, sync_playwright() as pw:
        flags, notes = chromium_flags(args.backend, args.power, args.adapter, software, why)
        browser = Browser(pw, exe, flags, base_url, headless=not args.headful)
        try:
            info = browser.call("cfg => H.init(cfg)", cfg)
            fallback_env = os.environ.get("HARNESS_WEB_SOFTWARE", "").strip().lower() in ("0", "false", "no")
            if "skip" in info and "WebGL2 unavailable" in info["skip"] and not software and not fallback_env:
                print(f"[runner] {info['skip']}; retrying with SwiftShader", flush=True)
                browser.close()
                flags, notes = chromium_flags(args.backend, args.power, args.adapter, True, "WebGL2 fallback")
                notes["software_fallback"] = info["skip"]
                browser = Browser(pw, exe, flags, base_url, headless=not args.headful)
                info = browser.call("cfg => H.init(cfg)", cfg)
            if "skip" in info:
                raise Skip(info["skip"])
            webgl = info["webgl"]
            print(f"[runner] {browser.version} | {webgl['renderer']} | float_blend={info['float_blend']} "
                  f"timer_query={info['timer_query']} | {bundle['scene']}/{bundle['mode']} {kind}"
                  f"{' parity' if parity else ''}", flush=True)
            sample_rss()

            if kind == "stations":
                for st in bundle["capture"]["stations"]:
                    name, settle = st["name"], max(1, int(st.get("settle_frames", 1)))
                    browser.call("a => H.beginView(a)", {"camera": st.get("camera", name)})
                    prev = last = None
                    png = None
                    for f in range(settle):
                        cap = f >= settle - 2
                        r = browser.call("a => H.frame(a)", {"frame": f, "station": name, "warmup": f < warm,
                                                             "capture": cap})
                        if cap:
                            prev, last = last, decode_rgb(r["rgb"], width, height)
                            png = r.get("png")
                        if f % 16 == 15:
                            sample_rss()
                    write_exr(out / name / "final.exr", last, pixel_type="float", compression="zip")
                    outputs.append(f"{name}/final.exr")
                    if parity:
                        save_png(out / name / "final.png", decode_rgb8(png, width, height))
                        outputs.append(f"{name}/final.png")
                    convergence[name] = {"settle_frames": settle, "last_rel_change": rel_change(prev, last)}
                    sample_rss()
            else:
                tl = bundle["capture"]["timeline"]
                end, frames = int(tl["end_frame"]), {int(k) for k in tl["frames"]}
                browser.call("a => H.beginView(a)", {"camera": tl["camera"]})
                for k in range(end + 1):
                    cap = k in frames
                    r = browser.call("a => H.frame(a)", {"frame": k, "station": tl["camera"], "warmup": k < warm,
                                                         "capture": cap})
                    if cap:
                        write_exr(out / "frames" / f"{k:05d}.exr", decode_rgb(r["rgb"], width, height),
                                  pixel_type="half", compression="zip")
                        outputs.append(f"frames/{k:05d}.exr")
                        if parity:
                            save_png(out / "frames" / f"{k:05d}.png", decode_rgb8(r["png"], width, height))
                            outputs.append(f"frames/{k:05d}.png")
                    if k % 16 == 15:
                        sample_rss()
            sample_rss()
            timing = browser.call("() => H.finish()")
        finally:
            browser.close()

    # ---- timing.json (DESIGN §4.3)
    mem = timing["memory"]
    timing_doc = {
        "timing_version": 1, "units": "ms", "gpu_timestamps": bool(timing["gpu_timestamps"]), "warmup_frames": warm,
        "frames": timing["frames"],
        "memory": {"gpu_texture_bytes": int(mem["gpu_texture_bytes"]), "gpu_buffer_bytes": int(mem["gpu_buffer_bytes"]),
                   "peak_rss_bytes": max(rss_samples) if rss_samples else None,
                   "peak_rss_source": "max sampled sum of RSS over Chromium processes" if rss_samples
                   else "unavailable (no psutil and not Linux)",
                   "gpu_bytes_source": mem.get("estimate"), "texture_items": mem.get("texture_items"),
                   "renderer_info": mem.get("renderer_info")},
        "precompute": timing["precompute"],
        "passes": PASSES,
        "gpu_resolved_frames": timing.get("gpu_resolved_frames"),
        "disjoint_events": timing.get("disjoint_events"),
    }
    (out / "timing.json").write_text(json.dumps(timing_doc, indent=1) + "\n", encoding="utf-8")

    # ---- receipt.json (DESIGN §4.3)
    renderer = webgl["renderer"]
    device = {
        "adapter": renderer, "backend": f"WebGL2 / ANGLE {angle_backend(renderer)}",
        "adapter_type": adapter_type(renderer), "vendor": webgl["vendor"], "driver": webgl["version"],
        "browser": f"Chromium {browser.version}", "browser_executable": str(exe), "user_agent": info["user_agent"],
        "webgl_renderer": renderer, "glsl": webgl["glsl"], "flags": flags, "headless": not args.headful,
        "software_rendering": adapter_type(renderer) == "CPU",
        "extensions": sorted(e for e in webgl["extensions"] if e.startswith(("EXT_", "OES_", "KHR_"))),
        "float_blend": info["float_blend"], "timer_query": info["timer_query"],
        "cross_origin_isolated": info["cross_origin_isolated"],
        "requested": {"adapter": args.adapter, "power": args.power, "backend": args.backend},
        "adapter_matches": (args.adapter.lower() in renderer.lower()) if args.adapter else None,
    }
    receipt = {
        "receipt_version": 1, "engine": "threejs-web", "engine_version": ThreeJsWeb().version(),
        "runner": RUNNER_REL, "scene": bundle["scene"], "mode": bundle["mode"], "kind": kind, "parity": parity,
        "settings": _settings(bundle, info, parity, flags, notes, args.power),
        "device": device,
        "frames": {"fps": bundle.get("fps", 60), "rendered": int(timing["frames_rendered"]), "timestep": "fixed",
                   "probe_captures": int(timing.get("probe_captures", 0))},
        "seed": bundle.get("seed"),
        "convergence": convergence,
        "outputs": outputs,
        "started_utc": started, "finished_utc": _utc(), "wall_seconds": round(time.perf_counter() - t0, 3),
        "host": {"os": platform.platform(), "python": platform.python_version(),
                 "cpu": platform.processor() or platform.machine(), "cpu_count": os.cpu_count()},
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    print(f"[runner] ok: {len(outputs)} outputs, {receipt['frames']['rendered']} frames, "
          f"{receipt['wall_seconds']:.1f} s", flush=True)
    return 0


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True, help="bundle.json written by renderers/threejs.py")
    ap.add_argument("--out", required=True, help="capture directory (RunLayout.capture_dir)")
    ap.add_argument("--adapter", help="adapter name substring (recorded and checked; Chromium cannot select by name)")
    ap.add_argument("--power", choices=("high-performance", "low-power"), help="WebGL powerPreference")
    ap.add_argument("--parity", action="store_true", help="one sample, ACES + sRGB canvas render, PNG + linear EXR")
    ap.add_argument("--backend", help=f"ANGLE backend: {', '.join(sorted(BACKEND_FLAGS))} (default: browser's)")
    ap.add_argument("--chromium", help="browser executable (default: find_chromium())")
    ap.add_argument("--cpu-resolve", action="store_true", help="average SSAA samples on the CPU (debug)")
    ap.add_argument("--headful", action="store_true", help="show the browser window (debug)")
    ap.add_argument("--verbose", action="store_true", help="log HTTP requests")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except Skip as e:
        print(json.dumps({"skip": e.reason}), flush=True)
        return 2
    except Exception:  # noqa: BLE001 - reported through runner.log
        traceback.print_exc()
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    sys.exit(main())
