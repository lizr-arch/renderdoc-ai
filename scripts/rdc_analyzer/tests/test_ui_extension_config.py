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
