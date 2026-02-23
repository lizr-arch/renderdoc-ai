#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc UI extension: RDC Analyzer panel.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

import qrenderdoc as qrd

CONFIG_FILENAME = "extension_config.json"
DEFAULT_SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    return Path(__file__).resolve().parent / CONFIG_FILENAME


def _load_config(config_path: Optional[Path] = None) -> dict:
    path = config_path or _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_scripts_root(config_path: Optional[Path] = None) -> Path:
    env_root = os.getenv("RDC_ANALYZER_SCRIPTS")
    if env_root:
        return Path(env_root).expanduser().resolve()

    config = _load_config(config_path)
    scripts_root = config.get("scripts_root")
    if scripts_root:
        return Path(scripts_root).expanduser().resolve()

    return DEFAULT_SCRIPTS_ROOT


def derive_output_dir(capture_path: str) -> Path:
    if not capture_path:
        raise ValueError("capture_path is required")
    capture = Path(capture_path).expanduser().resolve()
    return capture.parent / "rdc_analyzer" / capture.stem


SCRIPT_ROOT = resolve_scripts_root()
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))


def ensure_scripts_path() -> Path:
    root = resolve_scripts_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_analysis(capture_path: str, output_dir: Path) -> Path:
    ensure_scripts_path()
    from rdc_analyzer.tools import renderdoc_shell_analyze as shell

    return shell.run(capture_path, str(output_dir))


_webui_server = None
_webui_thread = None
_webui_port = None
_webui_analysis = None
_webui_view = None


def stop_webui_server() -> None:
    global _webui_server, _webui_thread, _webui_port, _webui_analysis
    server = _webui_server
    thread = _webui_thread
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
    if thread is not None:
        try:
            thread.join(timeout=1)
        except Exception:
            pass
    _webui_server = None
    _webui_thread = None
    _webui_port = None
    _webui_analysis = None


def ensure_webui_server(output_dir: Path, analysis_file: Path, port: int = 8765) -> str:
    global _webui_server, _webui_thread, _webui_port, _webui_analysis

    analysis_resolved = analysis_file.resolve()
    if _webui_server is not None and _webui_thread is not None:
        if _webui_thread.is_alive() and _webui_analysis == analysis_resolved:
            return f"http://127.0.0.1:{_webui_port}/"
        stop_webui_server()

    from rdc_analyzer.webui import server as webui_server

    httpd, thread, bound_port = webui_server.start_server(
        str(output_dir), port, str(analysis_resolved)
    )
    _webui_server = httpd
    _webui_thread = thread
    _webui_port = bound_port
    _webui_analysis = analysis_resolved
    return f"http://127.0.0.1:{bound_port}/"


def get_capture_filename(ctx) -> str:
    if hasattr(ctx, "CaptureFilename"):
        try:
            return ctx.CaptureFilename()
        except Exception:
            pass
    if hasattr(ctx, "CaptureFileName"):
        try:
            return ctx.CaptureFileName()
        except Exception:
            pass
    return ""


def prepare_webui(ctx, port: int = 8765):
    capture = get_capture_filename(ctx)
    if not capture:
        return None, "No capture loaded."

    output_dir = derive_output_dir(capture)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        analysis_file = run_analysis(capture, output_dir)
    except Exception as exc:
        return None, f"Analysis failed: {exc}"

    try:
        url = ensure_webui_server(output_dir, analysis_file, port)
    except Exception as exc:
        return None, f"WebUI server failed: {exc}"

    return url, None


def open_webui_task(ctx, on_ready, on_error, port: int = 8765, run_in_thread: bool = True):
    def work():
        url, error = prepare_webui(ctx, port)
        if error:
            on_error(error)
        else:
            on_ready(url)

    if run_in_thread:
        thread = threading.Thread(
            target=work, name="RDCAnalyzerWebUIPrepare", daemon=True
        )
        thread.start()
        return thread

    work()
    return None


def _try_show_webui_view(ctx: qrd.CaptureContext, url: str) -> bool:
    global _webui_view
    try:
        from PySide2 import QtCore, QtWebEngineWidgets
    except Exception:
        return False

    if _webui_view is None:
        view = QtWebEngineWidgets.QWebEngineView()
        view.setObjectName("RDCAnalyzerWebUI")
        _webui_view = view
        if ctx.HasEventBrowser():
            ctx.AddDockWindow(
                _webui_view,
                qrd.DockReference.TopOf,
                ctx.GetEventBrowser().Widget(),
                0.3,
            )
        else:
            ctx.AddDockWindow(_webui_view, qrd.DockReference.MainToolArea, None)

    _webui_view.setUrl(QtCore.QUrl(url))
    ctx.RaiseDockWindow(_webui_view)
    return True


def open_webui_callback(ctx: qrd.CaptureContext, _data):
    mqt = ctx.Extensions().GetMiniQtHelper()

    def on_ready(url: str):
        def show():
            if _try_show_webui_view(ctx, url):
                return
            ctx.Extensions().MessageDialog(
                "PySide2/QtWebEngine 不可用，已改用外部浏览器打开。",
                "RDC Analyzer",
            )
            webbrowser.open(url)

        try:
            mqt.InvokeOntoUIThread(show)
        except Exception:
            show()

    def on_error(message: str):
        def show():
            ctx.Extensions().ErrorDialog(message, "RDC Analyzer")

        try:
            mqt.InvokeOntoUIThread(show)
        except Exception:
            show()

    open_webui_task(ctx, on_ready, on_error, run_in_thread=True)

from rdc_analyzer.providers import QRenderDocProvider


class AnalyzerWindow(qrd.CaptureViewer):
    def __init__(self, ctx: qrd.CaptureContext):
        super().__init__()
        self.ctx = ctx
        self.mqt: qrd.MiniQtHelper = ctx.Extensions().GetMiniQtHelper()
        self.top_window = self.mqt.CreateToplevelWidget("RDC Analyzer", self._on_closed)

        container = self.mqt.CreateVerticalContainer()
        self.mqt.AddWidget(self.top_window, container)

        self._title = self.mqt.CreateLabel()
        self.mqt.SetWidgetText(self._title, "RDC Analyzer")
        self.mqt.AddWidget(container, self._title)

        self._status = self.mqt.CreateLabel()
        self.mqt.AddWidget(container, self._status)

        self._shader_label = self.mqt.CreateLabel()
        self._texture_label = self.mqt.CreateLabel()
        self._event_label = self.mqt.CreateLabel()

        self.mqt.AddWidget(container, self._shader_label)
        self.mqt.AddWidget(container, self._texture_label)
        self.mqt.AddWidget(container, self._event_label)

        self._set_counts("N/A", "N/A", "N/A")
        self._set_status("No capture loaded.")

        ctx.AddCaptureViewer(self)

    def _on_closed(self, _ctx, _widget, _data):
        window_closed()

    def _set_status(self, message: str) -> None:
        self.mqt.SetWidgetText(self._status, message)

    def _set_counts(self, shaders: str, textures: str, events: str) -> None:
        self.mqt.SetWidgetText(self._shader_label, f"Shaders: {shaders}")
        self.mqt.SetWidgetText(self._texture_label, f"Textures: {textures}")
        self.mqt.SetWidgetText(self._event_label, f"Events: {events}")

    def _notify_error(self, message: str) -> None:
        try:
            self.ctx.Extensions().MessageDialog(message, "RDC Analyzer")
        except Exception:
            pass

    def _collect_counts(self) -> Tuple[int, int, int]:
        provider = QRenderDocProvider(self.ctx)
        capture_name = get_capture_filename(self.ctx)

        provider.open_capture(capture_name)

        def gather(_controller):
            return (
                len(provider.list_shaders()),
                len(provider.list_textures()),
                len(provider.list_events()),
            )

        return self.ctx.Replay().BlockInvoke(gather)

    def OnCaptureLoaded(self):
        print("RDC Analyzer: capture loaded, collecting counts...")
        self._set_status("Loading analysis...")
        try:
            shader_count, texture_count, event_count = self._collect_counts()
        except Exception as exc:
            error_message = f"Error: {exc}"
            print(f"RDC Analyzer: {error_message}")
            self._set_status(error_message)
            self._notify_error(error_message)
            self._set_counts("N/A", "N/A", "N/A")
            return

        self._set_status("Ready.")
        self._set_counts(str(shader_count), str(texture_count), str(event_count))
        print(
            "RDC Analyzer: counts ready "
            f"(shaders={shader_count}, textures={texture_count}, events={event_count})"
        )

    def OnCaptureClosed(self):
        self._set_status("No capture loaded.")
        self._set_counts("N/A", "N/A", "N/A")
        print("RDC Analyzer: capture closed.")

    def OnSelectedEventChanged(self, _event):
        pass


cur_window: Optional[AnalyzerWindow] = None
extiface_version = ""


def window_closed():
    global cur_window
    if cur_window is not None:
        cur_window.ctx.RemoveCaptureViewer(cur_window)
    cur_window = None


def window_callback(ctx: qrd.CaptureContext, _data):
    global cur_window
    if cur_window is None:
        cur_window = AnalyzerWindow(ctx)
        if ctx.HasEventBrowser():
            ctx.AddDockWindow(
                cur_window.top_window,
                qrd.DockReference.TopOf,
                ctx.GetEventBrowser().Widget(),
                0.25,
            )
        else:
            ctx.AddDockWindow(cur_window.top_window, qrd.DockReference.MainToolArea, None)

    ctx.RaiseDockWindow(cur_window.top_window)
    print("RDC Analyzer: window opened.")


def register(version: str, ctx: qrd.CaptureContext):
    global extiface_version
    extiface_version = version
    print(f"Registering RDC Analyzer extension for RenderDoc {version}")
    ctx.Extensions().RegisterWindowMenu(qrd.WindowMenu.Window, ["Analyzer"], window_callback)
    ctx.Extensions().RegisterWindowMenu(
        qrd.WindowMenu.Tools, ["RDC Analyzer", "Open WebUI"], open_webui_callback
    )


def unregister():
    print("Unregistering RDC Analyzer extension")
    global cur_window
    if cur_window is not None:
        cur_window.ctx.Extensions().GetMiniQtHelper().CloseToplevelWidget(cur_window.top_window)
        cur_window = None
