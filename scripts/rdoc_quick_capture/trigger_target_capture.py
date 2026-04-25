#!/usr/bin/env python3
"""Trigger one RenderDoc target-control capture and report the resulting RDC path."""

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_RENDERDOC_DIR = Path(r"D:\Code\git\renderdoc\x64\Development")
DEFAULT_PYMODULES_DIR = DEFAULT_RENDERDOC_DIR / "pymodules"
DEFAULT_TARGET_CONTROL_PORT = 38920
DEFAULT_CLIENT_NAME = "codex_target_capture.py"

_DLL_HANDLES = []


def configure_renderdoc_import(renderdoc_dir: Path, pymodules_dir: Path) -> Any:
    """Prepare sys.path/DLL lookup, then import the local development renderdoc module."""
    renderdoc_dir = renderdoc_dir.resolve()
    pymodules_dir = pymodules_dir.resolve()
    renderdoc_dll = renderdoc_dir / "renderdoc.dll"

    if not renderdoc_dll.exists():
        raise FileNotFoundError(f"RenderDoc DLL not found: {renderdoc_dll}")
    if not pymodules_dir.exists():
        raise FileNotFoundError(f"RenderDoc pymodules directory not found: {pymodules_dir}")

    if str(pymodules_dir) not in sys.path:
        sys.path.insert(0, str(pymodules_dir))

    os.environ["PATH"] = str(renderdoc_dir) + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        _DLL_HANDLES.append(os.add_dll_directory(str(renderdoc_dir)))

    return importlib.import_module("renderdoc")


def _message_is_new_capture(renderdoc_module: Any, message: Any) -> bool:
    return message is not None and message.type == renderdoc_module.TargetControlMessageType.NewCapture


def _capture_result_from_message(target: Any, message: Any) -> Dict[str, object]:
    new_capture = message.newCapture
    capture_path = str(Path(str(new_capture.path)))
    capture_api = str(new_capture.api) if getattr(new_capture, "api", "") else str(target.GetAPI())
    return {
        "path": capture_path,
        "frame": int(new_capture.frameNumber),
        "api": capture_api,
        "pid": int(target.GetPID()),
    }


def trigger_capture(
    renderdoc_module: Any,
    target_control_port: int = DEFAULT_TARGET_CONTROL_PORT,
    timeout_sec: float = 60.0,
    poll_interval_sec: float = 0.1,
    client_name: str = DEFAULT_CLIENT_NAME,
) -> Dict[str, object]:
    """Connect to target-control, TriggerCapture(1), and wait for NewCapture."""
    target = renderdoc_module.CreateTargetControl("localhost", int(target_control_port), client_name, True)
    if target is None:
        raise RuntimeError(f"Could not connect to target-control port {target_control_port}")

    deadline = time.monotonic() + float(timeout_sec)
    try:
        target.TriggerCapture(1)
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for NewCapture on port {target_control_port}")

            message = target.ReceiveMessage(None)
            if _message_is_new_capture(renderdoc_module, message):
                return _capture_result_from_message(target, message)

            if poll_interval_sec > 0:
                time.sleep(poll_interval_sec)
    finally:
        target.Shutdown()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger a RenderDoc target-control capture")
    parser.add_argument(
        "--target-control-port",
        type=int,
        default=DEFAULT_TARGET_CONTROL_PORT,
        help="Target-control ident/port to connect to",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=60.0,
        help="Seconds to wait for a NewCapture message",
    )
    parser.add_argument(
        "--poll-interval-sec",
        type=float,
        default=0.1,
        help="Delay between ReceiveMessage polls",
    )
    parser.add_argument(
        "--renderdoc-dir",
        type=Path,
        default=DEFAULT_RENDERDOC_DIR,
        help="Development RenderDoc output directory containing renderdoc.dll",
    )
    parser.add_argument(
        "--pymodules-dir",
        type=Path,
        default=DEFAULT_PYMODULES_DIR,
        help="Development RenderDoc pymodules directory",
    )
    parser.add_argument(
        "--client-name",
        default=DEFAULT_CLIENT_NAME,
        help="Client name sent to target-control",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only a JSON result object",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        renderdoc_module = configure_renderdoc_import(args.renderdoc_dir, args.pymodules_dir)
        result = trigger_capture(
            renderdoc_module=renderdoc_module,
            target_control_port=args.target_control_port,
            timeout_sec=args.timeout_sec,
            poll_interval_sec=args.poll_interval_sec,
            client_name=args.client_name,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"CAPTURE_PATH={result['path']}")
        print(f"FRAME={result['frame']}")
        print(f"API={result['api']}")
        print(f"PID={result['pid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
