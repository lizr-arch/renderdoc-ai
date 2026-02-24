#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebUI server tests.
"""

import tempfile
from pathlib import Path
import pytest
import socket
import time
import urllib.request


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
        report_root = root
        assert (
            server.map_request_path("/analysis.json", analysis_file, report_root, assets_root)
            == analysis_file
        )
        assert (
            server.map_request_path("/app.js", analysis_file, report_root, assets_root)
            == (assets_root / "app.js").resolve()
        )


def test_map_request_path_prefers_report_index(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    (root / "analysis.json").write_text("{}", encoding="utf-8")
    (root / "index.html").write_text("<html>report</html>", encoding="utf-8")

    assets_root = server.resolve_assets_dir()
    analysis_file = root / "analysis.json"
    report_index = (root / "index.html").resolve()
    assert server.map_request_path("/", analysis_file, root, assets_root) == report_index
    assert server.map_request_path("/index.html", analysis_file, root, assets_root) == report_index


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


def test_pick_port_prefers_requested_when_free():
    from rdc_analyzer.webui import server

    port = server.pick_port(0)
    assert port > 0


def test_pick_port_falls_back_when_busy():
    from rdc_analyzer.webui import server

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    busy_port = sock.getsockname()[1]

    try:
        fallback = server.pick_port(busy_port)
        assert fallback != busy_port
        assert fallback > 0
    finally:
        sock.close()


def test_start_server_background_serves_analysis(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    (root / "analysis.json").write_text("{\"ok\": true}", encoding="utf-8")

    httpd, thread, port = server.start_server(str(root), 0, None)
    try:
        assert thread.is_alive()
        url = f"http://127.0.0.1:{port}/analysis.json"
        for _ in range(10):
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    body = resp.read().decode("utf-8")
                assert "\"ok\": true" in body
                break
            except Exception:
                time.sleep(0.1)
        else:
            assert False, "server did not respond"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)
