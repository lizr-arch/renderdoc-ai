#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebUI server tests.
"""

import tempfile
from pathlib import Path
import pytest


def test_resolve_webui_root_requires_analysis_json():
    from rdc_analyzer.webui import server

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        try:
            server.resolve_webui_root(str(root))
            assert False, "should raise"
        except FileNotFoundError:
            pass


def test_map_request_path_routes_to_assets_and_analysis():
    from rdc_analyzer.webui import server

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "analysis.json").write_text("{}", encoding="utf-8")

        assets_root = server.resolve_assets_dir()
        analysis_file = root / "analysis.json"
        assert server.map_request_path("/analysis.json", analysis_file, assets_root) == analysis_file
        assert server.map_request_path("/app.js", analysis_file, assets_root) == (assets_root / "app.js").resolve()


def test_resolve_analysis_file_prefers_data(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    data = tmp_path / "custom.json"
    data.write_text("{}", encoding="utf-8")

    assert server.resolve_analysis_file(str(root), str(data)) == data.resolve()


def test_resolve_analysis_file_requires_existing_data(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    data = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        server.resolve_analysis_file(str(root), str(data))


def test_resolve_analysis_file_falls_back_to_root(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    (root / "analysis.json").write_text("{}", encoding="utf-8")

    assert server.resolve_analysis_file(str(root), None) == (root / "analysis.json").resolve()
