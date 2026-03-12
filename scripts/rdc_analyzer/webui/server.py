#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple local server for WebUI assets.
"""

import argparse
import json
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit
import socket
import threading


def resolve_webui_root(root: str) -> Path:
    resolved = Path(root).resolve()
    analysis_path = resolved / "analysis.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"analysis.json not found under: {resolved}")
    return resolved


def resolve_assets_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_analysis_file(root: str, data: Optional[str]) -> Path:
    if data:
        path = Path(data).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"analysis.json not found: {path}")
        return path
    resolved_root = resolve_webui_root(root)
    return resolved_root / "analysis.json"


def map_request_path(
    request_path: str,
    analysis_file: Path,
    report_root: Path,
    assets_root: Path,
) -> Path:
    parsed = urlsplit(request_path)
    if parsed.path == "/analysis.json":
        return analysis_file
    rel_path = parsed.path.lstrip("/")
    report_root_resolved = report_root.resolve()
    assets_root_resolved = assets_root.resolve()

    if rel_path == "":
        report_index = report_root_resolved / "index.html"
        if report_index.exists():
            return report_index
        return assets_root_resolved / "index.html"

    for root in (report_root_resolved, assets_root_resolved):
        candidate = (root / rel_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists():
            return candidate

    return assets_root_resolved / "index.html"


def pick_port(requested: int) -> int:
    if requested == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", requested))
            return requested
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


def start_server(
    root: str,
    port: int = 8765,
    data: Optional[str] = None,
    jump_handler=None,
):
    analysis_file = resolve_analysis_file(root, data)
    assets_root = resolve_assets_dir()
    report_root = Path(root).resolve()
    handler = partial(
        WebUIRequestHandler,
        analysis_file=analysis_file,
        report_root=report_root,
        assets_root=assets_root,
        jump_handler=jump_handler,
    )
    bound_port = pick_port(port)
    httpd = ThreadingHTTPServer(("127.0.0.1", bound_port), handler)
    httpd.jump_handler = jump_handler
    thread = threading.Thread(
        target=httpd.serve_forever, name="RDCAnalyzerWebUI", daemon=True
    )
    thread.start()
    return httpd, thread, bound_port


class WebUIRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        analysis_file: Path,
        report_root: Path,
        assets_root: Path,
        jump_handler=None,
        **kwargs,
    ):
        self._analysis_file = analysis_file
        self._report_root = report_root
        self._assets_root = assets_root
        self._jump_handler = jump_handler
        super().__init__(*args, directory=str(report_root), **kwargs)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/jump":
            self._handle_jump(parsed)
            return
        super().do_GET()

    def translate_path(self, path: str) -> str:
        mapped = map_request_path(
            path, self._analysis_file, self._report_root, self._assets_root
        )
        return str(mapped)

    def _handle_jump(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        target = (qs.get("target") or ["event"])[0]
        id_str = (qs.get("id") or qs.get("eid") or [None])[0]
        if id_str is None:
            self.send_error(400, "Missing id")
            return
        try:
            target_id = int(id_str)
        except ValueError:
            self.send_error(400, "Invalid id")
            return

        payload = {
            "request_id": int(time.time() * 1000),
            "timestamp": time.time(),
            "target": target,
            "id": target_id,
        }

        if self._jump_handler is not None:
            try:
                self._jump_handler(payload)
            except Exception:
                self.send_error(500, "Jump failed")
                return
        else:
            try:
                _write_jump_request(self._report_root, payload)
            except Exception:
                self.send_error(500, "Jump queue write failed")
                return

        payload = b"{\"ok\": true}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _write_jump_request(report_root: Path, payload: dict) -> Path:
    report_root = report_root.resolve()
    tmp_path = report_root / "rdc_analyzer_jump.tmp"
    dst_path = report_root / "rdc_analyzer_jump.json"
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(dst_path)
    return dst_path


def serve(root: str, port: int = 8765, data: Optional[str] = None) -> None:
    analysis_file = resolve_analysis_file(root, data)
    server, thread, bound_port = start_server(root, port, data)
    print(
        f"WebUI server started: http://127.0.0.1:{bound_port}/ (analysis={analysis_file})"
    )
    thread.join()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RDC Analyzer WebUI server")
    parser.add_argument("--root", required=True, help="Directory containing analysis.json")
    parser.add_argument("--data", default=None, help="Override analysis.json file path")
    parser.add_argument("--port", type=int, default=8765, help="Port to serve (default: 8765)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    serve(args.root, args.port, args.data)


if __name__ == "__main__":
    main()
