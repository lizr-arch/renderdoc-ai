#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc GUI helper for real-RDC analyzer export smoke.

This helper is intended to run via:
  qrenderdoc.exe --ui-python renderdoc_gui_refresh_export.py <capture.rdc>

The script executes inside RenderDoc's PythonShell context after the main UI is
open. In that context `pyrenderdoc` is a UI-marshalled wrapper, so we run the
workflow synchronously:
1. Wait for the capture to finish loading.
2. Open the Analyzer Report viewer.
3. Call RefreshReport().
4. Poll for analyzer auto-export artifacts.
"""

import json
import os
import time


def _resolve_out_dir():
    out_dir = os.environ.get("RENDERDOC_ANALYZER_AUTO_EXPORT_DIR", "").strip()
    if not out_dir:
        out_dir = os.path.join(os.environ.get("TEMP", "."), "renderdoc_real_smoke")
    return out_dir


OUT_DIR = _resolve_out_dir()
AUTO_EXPORT_ENV_ENABLED = bool(os.environ.get("RENDERDOC_ANALYZER_AUTO_EXPORT_DIR", "").strip())
STATE_PATH = os.environ.get("RDC_REAL_SMOKE_STATE_FILE", "").strip()
if not STATE_PATH:
    STATE_PATH = os.path.join(OUT_DIR, "gui_state.json")

EXPECTED_EXPORTS = [
    "snapshot.v1.json",
    "analysis.json",
    "capture_context.json",
]

STATE = {
    "phase": "bootstrap",
    "capture_loaded": False,
    "capture_filename": "",
    "viewer_present": False,
    "refresh_called": False,
    "replay_processing_seconds": 0.0,
    "export_files": {},
    "error": "",
    "notes": [],
}


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)


def _flush():
    _ensure_parent(STATE_PATH)
    temp_path = STATE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(STATE, handle, ensure_ascii=False, indent=2, sort_keys=True)
    last_error = None
    for _ in range(20):
        try:
            os.replace(temp_path, STATE_PATH)
            return
        except PermissionError as ex:
            last_error = ex
            time.sleep(0.05)
    if last_error is not None:
        raise last_error


def _note(message):
    STATE["notes"].append(str(message))
    _flush()


def _record_exports():
    files = {}
    for name in EXPECTED_EXPORTS:
        path = os.path.join(OUT_DIR, name)
        files[name] = {
            "path": path,
            "exists": os.path.exists(path),
            "size": os.path.getsize(path) if os.path.exists(path) else 0,
        }
    STATE["export_files"] = files
    try:
        STATE["replay_processing_seconds"] = float(pyrenderdoc.Replay().GetCurrentProcessingTime())
    except Exception:
        STATE["replay_processing_seconds"] = 0.0


def _wait_for_capture_loaded(timeout_seconds):
    STATE["phase"] = "waiting_capture"
    _flush()
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        if pyrenderdoc.IsCaptureLoaded():
            STATE["phase"] = "capture_loaded"
            STATE["capture_loaded"] = True
            STATE["capture_filename"] = str(pyrenderdoc.GetCaptureFilename())
            _flush()
            return
        time.sleep(0.5)
    raise RuntimeError("Timed out waiting for capture load")


def _wait_for_viewer(timeout_seconds):
    STATE["phase"] = "viewer_requested"
    _flush()
    deadline = time.time() + float(timeout_seconds)
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            pyrenderdoc.ShowAnalyzerReportViewer()
        except Exception:
            pass

        STATE["viewer_present"] = bool(pyrenderdoc.HasAnalyzerReportViewer())
        if STATE["viewer_present"]:
            time.sleep(0.5)
            viewer = pyrenderdoc.GetAnalyzerReportViewer()
            if viewer is not None:
                STATE["phase"] = "viewer_present"
                _flush()
                return viewer

        if attempt % 10 == 0:
            _note("waiting for Analyzer Report viewer")
        _flush()
        time.sleep(0.5)
    raise RuntimeError("Timed out waiting for Analyzer Report viewer")


def _wait_for_exports(timeout_seconds):
    STATE["phase"] = "waiting_export"
    _record_exports()
    _flush()
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        _record_exports()
        if all(STATE["export_files"][name]["exists"] for name in EXPECTED_EXPORTS):
            STATE["phase"] = "exports_ready"
            _flush()
            return
        _flush()
        time.sleep(0.5)
    raise RuntimeError("Timed out waiting for analyzer auto export")


def _run():
    _ensure_parent(os.path.join(OUT_DIR, "placeholder"))
    capture_wait = float(os.environ.get("RDC_REAL_SMOKE_CAPTURE_WAIT_SECONDS", "240"))
    viewer_wait = float(os.environ.get("RDC_REAL_SMOKE_VIEWER_WAIT_SECONDS", "120"))
    export_wait = float(os.environ.get("RDC_REAL_SMOKE_EXPORT_WAIT_SECONDS", "600"))

    _wait_for_capture_loaded(capture_wait)
    viewer = _wait_for_viewer(viewer_wait)
    if viewer is None:
        raise RuntimeError("Analyzer Report viewer handle is null")

    if AUTO_EXPORT_ENV_ENABLED:
        _note("auto-export env active; helper issuing RefreshReport via ui-python")

    STATE["phase"] = "refresh_calling"
    _flush()
    viewer.RefreshReport()
    STATE["phase"] = "refresh_called"
    STATE["refresh_called"] = True
    _note("RefreshReport returned via ui-python context")

    _wait_for_exports(export_wait)
    STATE["phase"] = "done"
    _flush()


try:
    _run()
except Exception as ex:
    _record_exports()
    STATE["phase"] = "error"
    STATE["error"] = repr(ex)
    _flush()
