#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebUI jump queue tests.
"""

import json
import time
import urllib.request
import sys
import types


def test_jump_queue_written_when_no_handler(tmp_path):
    from rdc_analyzer.webui import server

    root = tmp_path / "root"
    root.mkdir()
    (root / "analysis.json").write_text("{}", encoding="utf-8")

    httpd, thread, port = server.start_server(str(root), 0, None, jump_handler=None)
    try:
        url = f"http://127.0.0.1:{port}/api/jump?target=event&eid=7"
        with urllib.request.urlopen(url, timeout=2) as resp:
            body = resp.read().decode("utf-8")
        assert "\"ok\": true" in body

        jump_path = root / "rdc_analyzer_jump.json"
        for _ in range(10):
            if jump_path.exists():
                break
            time.sleep(0.05)
        assert jump_path.exists()

        payload = json.loads(jump_path.read_text(encoding="utf-8"))
        assert payload["target"] == "event"
        assert payload["id"] == 7
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)


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
    dummy.WindowMenu = types.SimpleNamespace(Window=object(), Tools=object())
    dummy.DockReference = types.SimpleNamespace(TopOf=object(), MainToolArea=object())
    monkeypatch.setitem(sys.modules, "qrenderdoc", dummy)


def test_dispatch_jump_event_calls_seteventid(monkeypatch):
    _install_dummy_qrenderdoc(monkeypatch)
    from rdc_analyzer.ui_extension import analyzer_extension as ext

    class DummyCtx:
        def __init__(self):
            self.calls = []

        def SetEventID(self, *args):
            self.calls.append(args)

    ctx = DummyCtx()

    ok = ext.dispatch_jump(ctx, {"target": "event", "id": 7})
    assert ok is True
    assert ctx.calls
    args = ctx.calls[-1]
    assert args[1] == 7
    assert args[2] == 7
