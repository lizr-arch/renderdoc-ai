#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc UI extension: RDC Analyzer panel.
"""

import json
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import qrenderdoc as qrd
from rdc_analyzer.report_from_analysis import generate_report_from_analysis

if __spec__ is None:
    import importlib.util as _importlib_util

    _spec = _importlib_util.spec_from_file_location(__name__, __file__)
    if _spec is not None:
        __spec__ = _spec
        __loader__ = _spec.loader
        if __package__ is None:
            __package__ = __name__.rpartition(".")[0]

CONFIG_FILENAME = "extension_config.json"
DEFAULT_SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
LOG_BASENAME = "rdc_analyzer"
_LOG_TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
_LOG_FILE = Path(__file__).resolve().parent / f"{LOG_BASENAME}_{_LOG_TIMESTAMP}.log"
_LATEST_LOG_FILE = Path(__file__).resolve().parent / f"{LOG_BASENAME}_latest.log"


def _log_path() -> Path:
    return _LOG_FILE


def _log_event(message: str, exc: Optional[BaseException] = None) -> None:
    path = _log_path()
    try:
        lines = [
            f"[{datetime.utcnow().isoformat()}] {message}",
            f"Python: {sys.version}",
            f"Executable: {sys.executable}",
            "sys.path:",
        ]
        lines.extend(f"  {entry}" for entry in sys.path)
        if exc is not None:
            lines.append("Traceback:")
            lines.extend(traceback.format_exception(type(exc), exc, exc.__traceback__))
        lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        log_text = "\n".join(lines)
        for target in (path, _LATEST_LOG_FILE):
            with target.open("a", encoding="utf-8") as handle:
                handle.write(log_text)
                if not log_text.endswith("\n"):
                    handle.write("\n")
    except Exception:
        pass


def _check_dataclasses_available() -> Tuple[bool, Optional[str]]:
    try:
        import dataclasses  # noqa: F401
    except Exception as exc:
        vendor_path = None
        try:
            root = resolve_scripts_root()
            vendor_path = root / "rdc_analyzer" / "_vendor" / "dataclasses"
        except Exception:
            vendor_path = None

        if vendor_path is not None and vendor_path.exists():
            if str(vendor_path) not in sys.path:
                sys.path.insert(0, str(vendor_path))
            try:
                import dataclasses  # noqa: F401

                _log_event(f"Loaded 'dataclasses' from vendor path: {vendor_path}")
                return True, None
            except Exception as exc2:
                _log_event(
                    f"Vendor 'dataclasses' load failed from: {vendor_path}", exc2
                )

        _log_event("Missing 'dataclasses' module", exc)
        return (
            False,
            "Embedded Python is missing standard library module 'dataclasses'. "
            "This usually means Python < 3.7 or an incomplete runtime. "
            "You can either upgrade the embedded Python runtime or install the "
            "dataclasses backport into scripts/rdc_analyzer/_vendor/dataclasses. "
            f"See log: {_log_path()} (latest: {_LATEST_LOG_FILE})",
        )
    return True, None


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
    root = ensure_scripts_path()
    package = _load_analyzer_package(root)

    import importlib

    shell = importlib.import_module(f"{package.__name__}.tools.renderdoc_shell_analyze")
    return shell.run(capture_path, str(output_dir))


_webui_server = None
_webui_thread = None
_webui_port = None
_webui_analysis = None
_webui_view = None
_webui_process = None
_webui_external_url = None


_ANALYZER_MODULE_NAME = "_rdc_analyzer_pkg"


def _load_analyzer_package(root: Path):
    module = sys.modules.get(_ANALYZER_MODULE_NAME)
    if module is not None:
        return module

    import importlib.util

    package_root = root / "rdc_analyzer"
    package_init = package_root / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        _ANALYZER_MODULE_NAME,
        str(package_init),
        submodule_search_locations=[str(package_root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load rdc_analyzer package from scripts_root.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_ANALYZER_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def get_provider_class():
    root = ensure_scripts_path()
    package = _load_analyzer_package(root)

    import importlib

    providers = importlib.import_module(f"{package.__name__}.providers")
    return providers.QRenderDocProvider


def stop_webui_server() -> None:
    global _webui_server, _webui_thread, _webui_port, _webui_analysis
    global _webui_process, _webui_external_url
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
    process = _webui_process
    if process is not None:
        try:
            process.terminate()
        except Exception:
            pass
    _webui_process = None
    _webui_external_url = None


def _import_webui_server():
    from rdc_analyzer.webui import server as webui_server

    return webui_server


def _start_external_webui_server(output_dir: Path, analysis_file: Path, port: int) -> str:
    global _webui_process, _webui_external_url

    if _webui_process is not None and _webui_external_url:
        return _webui_external_url

    scripts_root = resolve_scripts_root()
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(scripts_root) + (os.pathsep + python_path if python_path else "")
    )
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        "py",
        "-3",
        "-u",
        "-m",
        "rdc_analyzer.webui.server",
        "--root",
        str(output_dir),
        "--data",
        str(analysis_file),
        "--port",
        str(port),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        env=env,
    )
    _webui_process = process
    output_lines = []
    deadline = time.time() + 8.0
    url = None

    if process.stdout is not None:
        while time.time() < deadline:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            line = line.strip()
            if line:
                output_lines.append(line)
            if "http://127.0.0.1:" in line:
                start = line.find("http://127.0.0.1:")
                end = line.find("/", start + len("http://127.0.0.1:"))
                if end == -1:
                    end = len(line)
                url = line[start:end] + "/"
                break

    if url:
        _webui_external_url = url
        _log_event(f"External WebUI server started: {url}")
        return url

    if process.poll() is not None:
        _log_event(
            "External WebUI server exited early. Output: " + " | ".join(output_lines)
        )
        raise RuntimeError("External WebUI server failed to start (see log).")

    _log_event(
        "External WebUI server did not provide startup line. Output: "
        + " | ".join(output_lines)
    )
    raise RuntimeError("External WebUI server did not report startup URL (see log).")


def ensure_webui_server(
    output_dir: Path,
    analysis_file: Path,
    port: int = 8765,
    jump_handler=None,
) -> str:
    global _webui_server, _webui_thread, _webui_port, _webui_analysis, _webui_external_url

    analysis_resolved = analysis_file.resolve()
    if _webui_server is not None and _webui_thread is not None:
        if _webui_thread.is_alive() and _webui_analysis == analysis_resolved:
            return f"http://127.0.0.1:{_webui_port}/"
        stop_webui_server()

    try:
        webui_server = _import_webui_server()
    except Exception as exc:
        missing_name = getattr(exc, "name", None)
        if missing_name is None and isinstance(exc, ModuleNotFoundError):
            missing_name = exc.args[0] if exc.args else None
        if isinstance(exc, ModuleNotFoundError) and missing_name in ("_socket", "socket"):
            _log_event("Embedded Python missing _socket; using external WebUI server", exc)
            url = _start_external_webui_server(output_dir, analysis_resolved, 0)
            _webui_external_url = url
            return url
        _log_event("WebUI server import failed", exc)
        raise

    httpd, thread, bound_port = webui_server.start_server(
        str(output_dir), port, str(analysis_resolved), jump_handler=jump_handler
    )
    _webui_server = httpd
    _webui_thread = thread
    _webui_port = bound_port
    _webui_analysis = analysis_resolved
    return f"http://127.0.0.1:{bound_port}/"


def get_capture_filename(ctx) -> str:
    if hasattr(ctx, "IsCaptureLoaded"):
        try:
            if not ctx.IsCaptureLoaded():
                return ""
        except Exception:
            pass
    if hasattr(ctx, "GetCaptureFilename"):
        try:
            filename = ctx.GetCaptureFilename()
            return filename or ""
        except Exception:
            pass
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

    ok, error = _check_dataclasses_available()
    if not ok:
        return None, error

    output_dir = derive_output_dir(capture)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        analysis_file = run_analysis(capture, output_dir)
    except Exception as exc:
        _log_event("Analysis failed", exc)
        return None, f"Analysis failed: {exc}. See log: {_log_path()} (latest: {_LATEST_LOG_FILE})"

    try:
        capture_name = Path(capture).name if capture else "capture"
        generate_report_from_analysis(analysis_file, output_dir, capture_name)
    except Exception as exc:
        _log_event("Report generation failed; falling back to WebUI assets", exc)

    def jump_handler(eid: int):
        if not hasattr(ctx, "SetEventID"):
            return False
        try:
            try:
                ctx.SetEventID([], eid, eid, True)
            except TypeError:
                ctx.SetEventID([], eid, eid)
            return True
        except Exception as exc:
            _log_event("Jump to event failed", exc)
            return False

    try:
        url = ensure_webui_server(output_dir, analysis_file, port, jump_handler=jump_handler)
    except Exception as exc:
        _log_event("WebUI server failed", exc)
        return None, f"WebUI server failed: {exc}. See log: {_log_path()} (latest: {_LATEST_LOG_FILE})"

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
        provider_cls = get_provider_class()
        provider = provider_cls(self.ctx)
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
