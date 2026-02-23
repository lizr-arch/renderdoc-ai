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


def test_ensure_webui_server_starts_and_reuses(tmp_path, monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    calls = {"count": 0}

    class DummyThread:
        def __init__(self, alive=True):
            self._alive = alive

        def is_alive(self):
            return self._alive

    def fake_start(root, port, data):
        calls["count"] += 1
        calls["args"] = (root, port, data)
        return object(), DummyThread(), 9001

    webui_server = type("M", (), {"start_server": fake_start})
    monkeypatch.setitem(sys.modules, "rdc_analyzer.webui.server", webui_server)
    monkeypatch.setitem(sys.modules, "rdc_analyzer.webui", type("P", (), {"server": webui_server}))

    analysis_file = tmp_path / "analysis.json"
    url1 = ext.ensure_webui_server(tmp_path, analysis_file, 8765)
    url2 = ext.ensure_webui_server(tmp_path, analysis_file, 8765)

    assert url1 == "http://127.0.0.1:9001/"
    assert url2 == "http://127.0.0.1:9001/"
    assert calls["count"] == 1
