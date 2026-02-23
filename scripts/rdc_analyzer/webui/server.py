#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple local server for WebUI assets.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit
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


def map_request_path(request_path: str, analysis_file: Path, assets_root: Path) -> Path:
    parsed = urlsplit(request_path)
    if parsed.path == "/analysis.json":
        return analysis_file
    rel_path = parsed.path.lstrip("/")
    candidate = (assets_root / rel_path).resolve()
    assets_root_resolved = assets_root.resolve()
    try:
        candidate.relative_to(assets_root_resolved)
    except ValueError:
        return assets_root_resolved
    return candidate


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


def start_server(root: str, port: int = 8765, data: Optional[str] = None):
    analysis_file = resolve_analysis_file(root, data)
    assets_root = resolve_assets_dir()
    handler = partial(WebUIRequestHandler, analysis_file=analysis_file, assets_root=assets_root)
    bound_port = pick_port(port)
    httpd = ThreadingHTTPServer(("127.0.0.1", bound_port), handler)
    thread = threading.Thread(
        target=httpd.serve_forever, name="RDCAnalyzerWebUI", daemon=True
    )
    thread.start()
    return httpd, thread, bound_port


class WebUIRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, analysis_file: Path, assets_root: Path, **kwargs):
        self._analysis_file = analysis_file
        self._assets_root = assets_root
        super().__init__(*args, directory=str(assets_root), **kwargs)

    def translate_path(self, path: str) -> str:
        mapped = map_request_path(path, self._analysis_file, self._assets_root)
        return str(mapped)


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
