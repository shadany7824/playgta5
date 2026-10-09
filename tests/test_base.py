"""renderers/base.py + registry: launch exit-code mapping, runner.log, NotWired stubs, capabilities."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from renderers import get_engine, list_engines
from renderers.base import (ALL_CAPABILITIES, Engine, LOG_TAIL_LINES, ModeInfo, NotWired, Unsupported, launch,
                            needs_capabilities)


class ScriptEngine(Engine):
    """Engine whose runner is a Python snippet (stands in for a real runner)."""

    name = "script"

    def __init__(self, script: Path, caps=ALL_CAPABILITIES):
        self.script, self.caps = script, set(caps)

    def modes(self):
        return {"direct": ModeInfo("direct", "direct", False, "-", "-")}

    def capabilities(self):
        return self.caps

    def check_available(self):
        pass

    def build_bundle(self, scene, mode, views, capture, out_dir):
        raise NotImplementedError

    def runner_argv(self, bundle_json, out_dir, extra):
        return [sys.executable, str(self.script), "--bundle", str(bundle_json), "--out", str(out_dir), *extra]

    def runner_env(self):
        return {"HARNESS_TEST_VAR": "42"}

    def version(self):
        return "0"


def _engine(tmp_path, body: str) -> ScriptEngine:
    p = tmp_path / "runner.py"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return ScriptEngine(p)


def test_launch_ok_writes_log(tmp_path):
    eng = _engine(tmp_path, """
        import os, sys
        print("hello", os.environ["HARNESS_TEST_VAR"], sys.argv[1:])
        print("to stderr", file=sys.stderr)
    """)
    r = launch(eng, tmp_path / "b" / "bundle.json", tmp_path / "out", timeout_s=60, extra=["--parity"])
    assert r.status == "ok" and r.ok and r.returncode == 0 and r.reason == ""
    log = (tmp_path / "out" / "runner.log").read_text(encoding="utf-8")
    assert "hello 42" in log and "to stderr" in log and "--parity" in log and r.log == tmp_path / "out" / "runner.log"
    assert any("hello 42" in ln for ln in r.log_tail)


def test_launch_skip(tmp_path):
    eng = _engine(tmp_path, """
        import json, sys
        print("probing")
        print(json.dumps({"skip": "no rect lights here"}))
        sys.exit(2)
    """)
    r = launch(eng, tmp_path / "bundle.json", tmp_path / "out", timeout_s=60)
    assert r.status == "skipped" and r.by_design and r.reason == "no rect lights here"


def test_launch_failure_tail(tmp_path):
    eng = _engine(tmp_path, """
        for i in range(100):
            print("line", i)
        raise SystemExit("boom: shader did not compile")
    """)
    r = launch(eng, tmp_path / "bundle.json", tmp_path / "out", timeout_s=60)
    assert r.status == "failed" and r.returncode == 1 and "boom" in r.reason
    assert len(r.log_tail) == LOG_TAIL_LINES and r.log_tail[-1].startswith("boom")


def test_launch_timeout(tmp_path):
    eng = _engine(tmp_path, """
        import time
        print("start", flush=True)
        time.sleep(60)
    """)
    r = launch(eng, tmp_path / "bundle.json", tmp_path / "out", timeout_s=1.5)
    assert r.status == "failed" and "timeout" in r.reason and r.seconds < 30
    assert "start" in (tmp_path / "out" / "runner.log").read_text(encoding="utf-8")


def test_launch_never_raises(tmp_path):
    eng = ScriptEngine(tmp_path / "missing.py")
    eng.runner_argv = lambda b, o, e: [str(tmp_path / "no-such-binary")]
    r = launch(eng, tmp_path / "bundle.json", tmp_path / "out", timeout_s=5)
    assert r.status == "failed" and "could not start" in r.reason
    eng.runner_argv = lambda b, o, e: (_ for _ in ()).throw(NotWired("no GPU"))
    r = launch(eng, tmp_path / "bundle.json", tmp_path / "out", timeout_s=5)
    assert r.status == "skipped" and r.reason == "no GPU"


def test_registry():
    assert list_engines() == ["threejs-native", "threejs-web", "future", "fake"]
    with pytest.raises(ValueError):
        get_engine("unity")
    for name in ("future", "fake"):
        eng = get_engine(name)
        if Path(__file__).resolve().parent.parent.joinpath("renderers", "future.py").exists():
            continue  # a later phase wired it
        assert eng.name == name and eng.modes() == {}
        with pytest.raises(NotWired) as e:
            eng.check_available()
        assert e.value.reason == "module not present"
    nat, web = get_engine("threejs-native"), get_engine("threejs-web")
    assert nat.name == "threejs-native" and web.name == "threejs-web"
    argv = nat.runner_argv(Path("b/bundle.json"), Path("o"), ["--parity"])
    assert argv[0] == sys.executable and argv[1].replace("\\", "/").endswith("native/runner.py")
    assert argv[2:] == ["--bundle", str(Path("b/bundle.json")), "--out", "o", "--parity"]
    assert web.runner_argv(Path("b"), Path("o"), [])[1].replace("\\", "/").endswith("web/runner.py")
    assert nat.runner_env()["WGPU_BACKEND_TYPE"]


def test_needs_capabilities_and_unsupported(tiny_scene, tmp_path):
    room = tiny_scene("mini_room")
    assert needs_capabilities(room) == {"light:point", "light:directional", "light:rect", "light:environment"}
    tl = tiny_scene("mini_timeline")
    assert needs_capabilities(tl) == {"light:point", "light:directional", "timeline", "op:set_light",
                                      "op:set_transform", "op:set_material"}
    assert "shape:mesh" in needs_capabilities(tiny_scene("mini_survey"))
    eng = ScriptEngine(tmp_path / "x.py", caps={"light:point", "light:directional"})
    with pytest.raises(Unsupported) as e:
        eng.check_supports(room)
    assert e.value.missing == ["light:environment", "light:rect"] and "light:rect" in e.value.reason
    eng.check_supports(tiny_scene("mini_point_plane"))
    assert eng.direct_mode() == "direct"


@pytest.mark.native
def test_native_check_available(monkeypatch):
    """With a runner present, availability depends only on wgpu seeing a Vulkan adapter."""
    from renderers.threejs import ThreeJsNative
    monkeypatch.setattr(ThreeJsNative, "runner_rel", "tools/spec.py")  # any existing file stands in
    eng = ThreeJsNative()
    try:
        eng.check_available()
    except NotWired as e:
        assert e.reason and "not present" not in e.reason
    else:
        assert any(a.get("backend_type") == "Vulkan" for a in eng.adapters())


@pytest.mark.web
def test_web_check_available(monkeypatch):
    from renderers.threejs import ThreeJsWeb, find_chromium
    monkeypatch.setattr(ThreeJsWeb, "runner_rel", "tools/spec.py")
    try:
        ThreeJsWeb().check_available()
    except NotWired as e:
        assert e.reason and "not present" not in e.reason
    else:
        assert find_chromium() is not None


def test_missing_runner_is_not_wired(monkeypatch):
    from renderers.threejs import ThreeJsNative, ThreeJsWeb
    for cls in (ThreeJsNative, ThreeJsWeb):
        monkeypatch.setattr(cls, "runner_rel", "no/such/runner.py")
        with pytest.raises(NotWired) as e:
            cls().check_available()
        assert e.value.reason == "no/such/runner.py not present"
