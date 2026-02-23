#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI extension install script tests.
"""

from __future__ import annotations

from pathlib import Path


def test_install_extension_copies_and_writes_config(tmp_path):
    from rdc_analyzer.tools import install_ui_extension as installer

    source = tmp_path / "src"
    source.mkdir()
    (source / "__init__.py").write_text("x=1\n", encoding="utf-8")
    (source / "extension.json").write_text("{\"extension_api\":1}\n", encoding="utf-8")

    dest_root = tmp_path / "exts"
    scripts_root = tmp_path / "scripts"

    dest = installer.install_extension(
        source_dir=source,
        scripts_root=scripts_root,
        dest_root=dest_root,
        name="rdc_analyzer",
    )

    assert dest.exists()
    assert (dest / "__init__.py").exists()
    assert (dest / "extension.json").exists()
    assert (dest / "extension_config.json").exists()
