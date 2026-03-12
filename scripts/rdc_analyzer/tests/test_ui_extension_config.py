#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI extension config path resolution tests.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))


def _write_config(path: Path, scripts_root: Path) -> None:
    path.write_text(
        '{\n  "scripts_root": "%s"\n}\n' % str(scripts_root).replace("\\", "\\\\"),
        encoding="utf-8",
    )


def _install_dummy_qrenderdoc(monkeypatch) -> None:
    try:
        import qrenderdoc as qrd  # type: ignore

        if hasattr(qrd, "CaptureViewer"):
            return
    except Exception:
        pass

    dummy = types.SimpleNamespace()
    dummy.CaptureViewer = type("CaptureViewer", (), {})
    dummy.MiniQtHelper = type("MiniQtHelper", (), {})
    dummy.CaptureContext = type("CaptureContext", (), {})
    dummy.WindowMenu = types.SimpleNamespace(Window=object())
    dummy.DockReference = types.SimpleNamespace(TopOf=object(), MainToolArea=object())
    monkeypatch.setitem(sys.modules, "qrenderdoc", dummy)


def test_resolve_scripts_root_prefers_env(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    env_root = tmp_path / "from_env"
    cfg_root = tmp_path / "from_config"
    cfg_path = tmp_path / "extension_config.json"
    _write_config(cfg_path, cfg_root)

    monkeypatch.setenv("RDC_ANALYZER_SCRIPTS", str(env_root))

    resolved = ext.resolve_scripts_root(cfg_path)
    assert resolved == env_root.resolve()


def test_resolve_scripts_root_uses_config_when_env_missing(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    monkeypatch.delenv("RDC_ANALYZER_SCRIPTS", raising=False)

    cfg_root = tmp_path / "from_config"
    cfg_path = tmp_path / "extension_config.json"
    _write_config(cfg_path, cfg_root)

    resolved = ext.resolve_scripts_root(cfg_path)
    assert resolved == cfg_root.resolve()


def test_resolve_scripts_root_falls_back_to_default(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    monkeypatch.delenv("RDC_ANALYZER_SCRIPTS", raising=False)

    cfg_path = tmp_path / "missing.json"
    resolved = ext.resolve_scripts_root(cfg_path)
    assert resolved == ext.DEFAULT_SCRIPTS_ROOT


def test_derive_output_dir_uses_capture_parent(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    capture_dir = tmp_path / "caps"
    capture_path = capture_dir / "frame42231.rdc"

    expected = capture_dir / "rdc_analyzer" / "frame42231"
    assert ext.derive_output_dir(str(capture_path)) == expected


def test_run_analysis_invokes_shell_run(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    calls = {}

    def fake_run(rdc_path, output_dir, output_name="analysis.json", overwrite=True):
        calls["args"] = (rdc_path, output_dir, output_name, overwrite)
        return Path(output_dir) / output_name

    monkeypatch.setitem(
        sys.modules, "rdc_analyzer.tools.renderdoc_shell_analyze", type("M", (), {"run": fake_run})
    )

    capture = r"D:\captures\frame.rdc"
    out = ext.run_analysis(capture, tmp_path)
    assert calls["args"][0] == capture
    assert Path(calls["args"][1]) == tmp_path
    assert out == tmp_path / "analysis.json"


def test_run_analysis_uses_alias_package(monkeypatch, tmp_path):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    fake_root = types.ModuleType("rdc_analyzer")
    fake_root.__path__ = [str(tmp_path)]
    monkeypatch.setitem(sys.modules, "rdc_analyzer", fake_root)

    fake_pkg = types.SimpleNamespace(__name__="fakepkg")
    monkeypatch.setattr(ext, "_load_analyzer_package", lambda _root: fake_pkg)

    calls = {}

    def fake_run(rdc_path, output_dir, output_name="analysis.json", overwrite=True):
        calls["args"] = (rdc_path, output_dir, output_name, overwrite)
        return Path(output_dir) / output_name

    fake_shell = types.ModuleType("fakepkg.tools.renderdoc_shell_analyze")
    fake_shell.run = fake_run
    monkeypatch.setitem(sys.modules, "fakepkg.tools.renderdoc_shell_analyze", fake_shell)

    out = ext.run_analysis("X.rdc", tmp_path)
    assert calls["args"][0] == "X.rdc"
    assert Path(calls["args"][1]) == tmp_path
    assert out == tmp_path / "analysis.json"


def test_ui_extension_logs_missing_dataclasses(monkeypatch, tmp_path):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    monkeypatch.setattr(ext, "_log_path", lambda: tmp_path / "rdc_analyzer.log")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dataclasses":
            raise ModuleNotFoundError("No module named 'dataclasses'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    class Ctx:
        def CaptureFilename(self):
            return str(tmp_path / "cap.rdc")

    url, error = ext.prepare_webui(Ctx())
    assert url is None
    assert error is not None
    assert "dataclasses" in error.lower()

    log_path = tmp_path / "rdc_analyzer.log"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "Missing 'dataclasses' module" in log_text


def test_ui_extension_falls_back_to_vendor_dataclasses(monkeypatch, tmp_path):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    vendor_dir = tmp_path / "rdc_analyzer" / "_vendor" / "dataclasses"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "dataclasses.py").write_text("value = 42\n", encoding="utf-8")

    monkeypatch.setattr(ext, "resolve_scripts_root", lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(ext, "_log_path", lambda: tmp_path / "rdc_analyzer.log")

    import builtins
    import importlib.util

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dataclasses":
            if str(vendor_dir) in sys.path:
                spec = importlib.util.spec_from_file_location(
                    "dataclasses", vendor_dir / "dataclasses.py"
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules["dataclasses"] = module
                assert spec.loader is not None
                spec.loader.exec_module(module)
                return module
            raise ModuleNotFoundError("No module named 'dataclasses'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    ok, error = ext._check_dataclasses_available()
    assert ok is True
    assert error is None
    assert "dataclasses" in sys.modules


def test_tools_init_does_not_import_install_ui_extension(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)

    for name in list(sys.modules):
        if name.startswith("rdc_analyzer.tools"):
            sys.modules.pop(name, None)

    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rdc_analyzer.tools" and fromlist and "install_ui_extension" in fromlist:
            raise SyntaxError("future feature annotations is not defined")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    import rdc_analyzer.tools as tools  # noqa: F401

    assert "rdc_analyzer.tools.install_ui_extension" not in sys.modules


def test_get_capture_filename_prefers_new_api(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class Ctx:
        def CaptureFilename(self):
            return "A.rdc"

    assert ext.get_capture_filename(Ctx()) == "A.rdc"


def test_get_capture_filename_falls_back(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class Ctx:
        def CaptureFileName(self):
            return "B.rdc"

    assert ext.get_capture_filename(Ctx()) == "B.rdc"


def test_get_capture_filename_supports_getcapture(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class Ctx:
        def GetCaptureFilename(self):
            return "C.rdc"

    assert ext.get_capture_filename(Ctx()) == "C.rdc"


def test_ensure_webui_server_starts_and_reuses(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    calls = {"count": 0}

    class DummyThread:
        def __init__(self, alive=True):
            self._alive = alive

        def is_alive(self):
            return self._alive

    def fake_start(root, port, data, jump_handler=None):
        calls["count"] += 1
        calls["args"] = (root, port, data, jump_handler)
        return object(), DummyThread(), 9001

    webui_server = type("M", (), {"start_server": fake_start})
    monkeypatch.setitem(sys.modules, "rdc_analyzer.webui.server", webui_server)
    monkeypatch.setitem(sys.modules, "rdc_analyzer.webui", type("P", (), {"server": webui_server}))

    analysis_file = tmp_path / "analysis.json"
    url1 = ext.ensure_webui_server(tmp_path, analysis_file, 8765, jump_handler=lambda _e: None)
    url2 = ext.ensure_webui_server(tmp_path, analysis_file, 8765, jump_handler=lambda _e: None)

    assert url1 == "http://127.0.0.1:9001/"
    assert url2 == "http://127.0.0.1:9001/"
    assert calls["count"] == 1


def test_prepare_webui_requires_capture(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class Ctx:
        pass

    url, error = ext.prepare_webui(Ctx())
    assert url is None
    assert "capture" in error.lower()


def test_prepare_webui_happy_path(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class Ctx:
        def CaptureFilename(self):
            return "C:\\caps\\frame.rdc"

    calls = {}
    monkeypatch.setattr(ext, "derive_output_dir", lambda _p: tmp_path)
    monkeypatch.setattr(ext, "run_analysis", lambda _p, _d: tmp_path / "analysis.json")
    monkeypatch.setattr(ext, "_load_report_generator", lambda _r: lambda *_a, **_k: calls.setdefault("report", True))
    monkeypatch.setattr(
        ext,
        "ensure_webui_server",
        lambda _d, _a, _p=8765, jump_handler=None: "http://127.0.0.1:9001/",
    )

    url, error = ext.prepare_webui(Ctx())
    assert error is None
    assert url == "http://127.0.0.1:9001/"
    assert calls.get("report") is True


def test_open_webui_task_calls_ready(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    monkeypatch.setattr(ext, "prepare_webui", lambda _ctx, _p=8765: ("http://x", None))

    calls = {}

    def on_ready(url):
        calls["url"] = url

    def on_error(err):
        calls["err"] = err

    ext.open_webui_task(object(), on_ready, on_error, run_in_thread=False)
    assert calls.get("url") == "http://x"
    assert "err" not in calls


def test_open_webui_task_calls_error(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    monkeypatch.setattr(ext, "prepare_webui", lambda _ctx, _p=8765: (None, "boom"))

    calls = {}

    def on_ready(url):
        calls["url"] = url

    def on_error(err):
        calls["err"] = err

    ext.open_webui_task(object(), on_ready, on_error, run_in_thread=False)
    assert calls.get("err") == "boom"
    assert "url" not in calls


def test_open_webui_callback_invokes_task(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    calls = {}

    def fake_open_webui_task(ctx, on_ready, on_error, port=8765, run_in_thread=True):
        calls["args"] = (ctx, on_ready, on_error, port, run_in_thread)

    monkeypatch.setattr(ext, "open_webui_task", fake_open_webui_task)

    class DummyMqt:
        def InvokeOntoUIThread(self, _fn):
            pass

    class DummyExt:
        def GetMiniQtHelper(self):
            return DummyMqt()

    class DummyCtx:
        def Extensions(self):
            return DummyExt()

    ctx = DummyCtx()
    ext.open_webui_callback(ctx, None)

    assert calls["args"][0] is ctx
    assert calls["args"][4] is True


def test_get_provider_class_ignores_extension_package(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    fake_pkg = types.ModuleType("rdc_analyzer")
    fake_pkg.__path__ = [str(Path(__file__).parent)]
    monkeypatch.setitem(sys.modules, "rdc_analyzer", fake_pkg)
    monkeypatch.setenv("RDC_ANALYZER_SCRIPTS", str(SCRIPT_ROOT))

    provider_cls = ext.get_provider_class()
    assert provider_cls.__name__ == "QRenderDocProvider"


def test_extension_reload_sets_spec(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    import importlib
    import imp

    ext_dir = Path(__file__).resolve().parents[1] / "ui_extension"

    parent = types.ModuleType("rdc_analyzer")
    parent.__path__ = [str(ext_dir)]
    monkeypatch.setitem(sys.modules, "rdc_analyzer", parent)

    module = imp.load_source("rdc_analyzer.analyzer_extension", str(ext_dir / "analyzer_extension.py"))
    importlib.reload(module)


def test_extension_exec_without_spec_sets_spec(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    ext_dir = Path(__file__).resolve().parents[1] / "ui_extension"
    module_path = ext_dir / "analyzer_extension.py"

    parent = types.ModuleType("rdc_analyzer")
    parent.__path__ = [str(ext_dir)]
    monkeypatch.setitem(sys.modules, "rdc_analyzer", parent)

    module = types.ModuleType("rdc_analyzer.analyzer_extension")
    module.__file__ = str(module_path)
    module.__package__ = "rdc_analyzer"
    module.__spec__ = None
    sys.modules["rdc_analyzer.analyzer_extension"] = module

    exec(compile(module_path.read_text(encoding="utf-8"), module.__file__, "exec"), module.__dict__)
    assert module.__spec__ is not None


def test_extension_file_avoids_future_annotations():
    extension_file = Path(__file__).resolve().parents[1] / "ui_extension" / "analyzer_extension.py"
    content = extension_file.read_text(encoding="utf-8")
    assert "from __future__ import annotations" not in content


def test_gui_pipeline_files_avoid_future_annotations():
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "tools" / "renderdoc_shell_analyze.py",
        root / "webui" / "server.py",
    ]
    for path in candidates:
        content = path.read_text(encoding="utf-8")
        assert "from __future__ import annotations" not in content


def test_webui_falls_back_when_socket_missing(monkeypatch, tmp_path):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    fake_analysis = tmp_path / "analysis.json"
    fake_analysis.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def fake_import():
        raise ModuleNotFoundError("_socket")

    monkeypatch.setattr(ext, "_import_webui_server", fake_import)
    monkeypatch.setattr(ext, "_start_external_webui_server", lambda *_args, **_kwargs: "http://127.0.0.1:9999/")

    url = ext.ensure_webui_server(out_dir, fake_analysis, 8765)
    assert url == "http://127.0.0.1:9999/"
