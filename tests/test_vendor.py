"""web/vendor/three: unmodified r186 files match manifest.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "web" / "vendor" / "three"


def test_manifest_matches_files():
    m = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
    assert m["version"] == "0.186.1" and m["revision"] == "186"
    assert m["tarball"] == "https://registry.npmjs.org/three/-/three-0.186.1.tgz"
    on_disk = {p.relative_to(VENDOR).as_posix() for p in VENDOR.rglob("*") if p.is_file()} - {"manifest.json",
                                                                                               "VENDOR.md"}
    assert on_disk == set(m["files"])
    for rel, sha in m["files"].items():
        assert hashlib.sha256((VENDOR / rel).read_bytes()).hexdigest() == sha, rel
    assert m["tarball_sha256"] in (VENDOR / "VENDOR.md").read_text(encoding="utf-8")


def test_required_parts_present():
    for rel in ["build/three.module.js", "build/three.core.js", "LICENSE", "package.json", "src/constants.js",
                "src/renderers/WebGLRenderer.js", "src/renderers/WebGLRenderTarget.js",
                "src/renderers/WebGLCubeRenderTarget.js", "src/renderers/shaders/ShaderChunk.js",
                "src/renderers/shaders/ShaderLib/meshlambert.glsl.js", "src/renderers/webgl/WebGLLights.js",
                "src/renderers/webgl/WebGLShadowMap.js", "src/cameras/CubeCamera.js", "src/lights/RectAreaLight.js",
                "examples/jsm/lights/LightProbeGenerator.js", "examples/jsm/lights/RectAreaLightUniformsLib.js",
                "examples/jsm/lights/RectAreaLightTexturesLib.js"]:
        assert (VENDOR / rel).is_file(), rel
    assert json.loads((VENDOR / "package.json").read_text(encoding="utf-8"))["version"] == "0.186.1"
