#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route-B live replay preflight checker.

This tool diagnoses whether RenderDoc Route-B replay can be executed locally,
via software replay, or via remote server, and reports actionable guidance.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


STATUS_EXIT_CODES = {
    "ok_local": 0,
    "ok_software": 0,
    "ok_remote": 0,
    "module_missing": 20,
    "file_not_found": 21,
    "open_file_failed": 22,
    "needs_remote": 10,
    "unsupported": 11,
    "open_capture_failed": 12,
    "remote_connect_failed": 30,
    "remote_copy_failed": 31,
    "remote_open_capture_failed": 32,
    "error": 40,
}


def build_default_paths(script_path: Optional[Path] = None) -> Tuple[str, str]:
    """Return default RenderDoc bin/pymodule paths relative to repo root."""
    base = script_path or Path(__file__).resolve()
    repo_root = base.parents[2]
    bin_dir = repo_root / "x64" / "Development"
    pymodules_dir = bin_dir / "pymodules"
    return str(bin_dir), str(pymodules_dir)


def _prepend_path(dir_path: str) -> None:
    if not dir_path:
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if dir_path not in parts:
        os.environ["PATH"] = dir_path + (os.pathsep + current if current else "")


def configure_renderdoc_env(bin_dir: str, pymodules_dir: str) -> None:
    _prepend_path(bin_dir)
    if pymodules_dir and pymodules_dir not in sys.path:
        sys.path.insert(0, pymodules_dir)


def import_renderdoc() -> Tuple[bool, Optional[Any], str]:
    try:
        import renderdoc as rd  # type: ignore

        return True, rd, getattr(rd, "__file__", "")
    except Exception as exc:  # pragma: no cover - exercised in integration usage
        return False, None, str(exc)


def result_to_record(result: Any) -> Dict[str, Any]:
    """Normalize RenderDoc ResultDetails into a serializable record."""
    raw = str(result)
    code = None
    message = raw
    ok = False

    try:
        if hasattr(result, "code"):
            code = str(result.code)
    except Exception:
        code = None

    try:
        if hasattr(result, "Message") and callable(result.Message):
            message = str(result.Message())
    except Exception:
        message = raw

    try:
        if hasattr(result, "OK") and callable(result.OK):
            ok = bool(result.OK())
    except Exception:
        ok = False

    if not ok:
        text = (message or raw).lower()
        ok = "success" in text and "fail" not in text and "error" not in text

    return {
        "ok": ok,
        "raw": raw,
        "code": code,
        "message": message,
    }


def classify_replay_support(support: Any) -> str:
    if support is None:
        return "Unknown"

    name = getattr(support, "name", None)
    if isinstance(name, str) and name:
        return name

    text = str(support)
    if "SuggestRemote" in text:
        return "SuggestRemote"
    if "Supported" in text and "SuggestRemote" not in text:
        return "Supported"
    if "Unsupported" in text:
        return "Unsupported"
    return text


def _new_replay_options(rd: Any, force_software: bool = False) -> Any:
    opts = rd.ReplayOptions()
    if force_software and hasattr(rd, "GPUVendor") and hasattr(rd.GPUVendor, "Software"):
        opts.forceGPUVendor = rd.GPUVendor.Software
    return opts


def attempt_local_replay(
    rd: Any,
    rdc_path: str,
    force_software: bool,
    attempt_on_suggest_remote: bool,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "attempted": True,
        "force_software": force_software,
        "open_file": None,
        "driver_name": "",
        "local_replay_support": "Unknown",
        "open_capture": None,
        "root_actions": None,
        "error": None,
    }

    cap = None
    controller = None
    try:
        cap = rd.OpenCaptureFile()
        open_file_result = cap.OpenFile(rdc_path, "", None)
        out["open_file"] = result_to_record(open_file_result)

        if not out["open_file"]["ok"]:
            return out

        try:
            out["driver_name"] = cap.DriverName()
        except Exception:
            out["driver_name"] = ""

        support_value = cap.LocalReplaySupport()
        support_name = classify_replay_support(support_value)
        out["local_replay_support"] = support_name

        should_open_capture = False
        if support_name == "Supported":
            should_open_capture = True
        elif support_name == "SuggestRemote" and attempt_on_suggest_remote:
            should_open_capture = True

        if not should_open_capture:
            return out

        opts = _new_replay_options(rd, force_software=force_software)
        open_capture_result, controller = cap.OpenCapture(opts, None)
        out["open_capture"] = result_to_record(open_capture_result)

        if out["open_capture"]["ok"] and controller is not None:
            try:
                out["root_actions"] = len(controller.GetRootActions())
            except Exception as exc:
                out["root_actions"] = "error: {}".format(exc)

        return out

    except Exception as exc:  # pragma: no cover - exercised in integration usage
        out["error"] = str(exc)
        return out
    finally:
        try:
            if controller is not None:
                controller.Shutdown()
        except Exception:
            pass

        try:
            if cap is not None:
                cap.Shutdown()
        except Exception:
            pass


def attempt_remote_replay(
    rd: Any,
    rdc_path: str,
    remote_url: str,
    copy_to_remote: bool,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "attempted": True,
        "url": remote_url,
        "connect": None,
        "copy_to_remote": None,
        "remote_path": None,
        "open_capture": None,
        "error": None,
    }

    remote = None
    controller = None

    try:
        connect_result, remote = rd.CreateRemoteServerConnection(remote_url)
        out["connect"] = result_to_record(connect_result)
        if not out["connect"]["ok"] or remote is None:
            return out

        remote_path = rdc_path
        if copy_to_remote:
            copied_path = remote.CopyCaptureToRemote(rdc_path, None)
            remote_path = str(copied_path) if copied_path else ""
            out["copy_to_remote"] = {
                "ok": bool(remote_path),
                "raw": str(copied_path),
                "message": str(copied_path),
            }
            if not remote_path:
                return out

        out["remote_path"] = remote_path
        opts = _new_replay_options(rd, force_software=False)
        open_capture_result, controller = remote.OpenCapture(
            rd.RemoteServer.NoPreference, remote_path, opts, None
        )
        out["open_capture"] = result_to_record(open_capture_result)
        return out

    except Exception as exc:  # pragma: no cover - exercised in integration usage
        out["error"] = str(exc)
        return out
    finally:
        try:
            if controller is not None:
                controller.Shutdown()
        except Exception:
            pass

        try:
            if remote is not None:
                remote.ShutdownServerAndConnection()
        except Exception:
            pass


def infer_final_status(mode: str, local: Dict[str, Any], software: Dict[str, Any], remote: Dict[str, Any]) -> str:
    local_open_file_ok = bool(local.get("open_file") and local["open_file"].get("ok"))
    support = local.get("local_replay_support", "Unknown")
    local_open_capture_ok = bool(local.get("open_capture") and local["open_capture"].get("ok"))

    software_ok = bool(software.get("open_capture") and software["open_capture"].get("ok"))
    remote_connect_ok = bool(remote.get("connect") and remote["connect"].get("ok"))
    remote_copy_ok = (
        remote.get("copy_to_remote") is None or bool(remote.get("copy_to_remote", {}).get("ok"))
    )
    remote_open_capture_ok = bool(remote.get("open_capture") and remote["open_capture"].get("ok"))

    if not local_open_file_ok:
        return "open_file_failed"

    if mode == "local":
        if local_open_capture_ok:
            return "ok_local"
        if support == "SuggestRemote":
            return "needs_remote"
        if support == "Unsupported":
            return "unsupported"
        return "open_capture_failed"

    if mode == "software":
        if software_ok:
            return "ok_software"
        if support == "SuggestRemote":
            return "needs_remote"
        return "open_capture_failed"

    if mode == "remote":
        if not remote_connect_ok:
            return "remote_connect_failed"
        if not remote_copy_ok:
            return "remote_copy_failed"
        if remote_open_capture_ok:
            return "ok_remote"
        return "remote_open_capture_failed"

    # auto mode
    if local_open_capture_ok:
        return "ok_local"

    if software_ok:
        return "ok_software"

    if remote_open_capture_ok:
        return "ok_remote"

    if support == "SuggestRemote":
        return "needs_remote"

    if support == "Unsupported":
        return "unsupported"

    return "open_capture_failed"


def build_recommendations(status: str) -> List[str]:
    if status in ("ok_local", "ok_software", "ok_remote"):
        return ["Replay preflight passed. Route-B can proceed with this mode."]

    if status == "module_missing":
        return [
            "Run with py -3.6.",
            "Ensure x64/Development is in PATH and x64/Development/pymodules is on sys.path.",
            "Verify renderdoc.pyd can be imported before running Route-B scripts.",
        ]

    if status == "file_not_found":
        return [
            "Provide a valid .rdc file path.",
            "Use absolute path to avoid cwd ambiguity.",
        ]

    if status == "needs_remote":
        return [
            "Start remote server on a compatible GPU host: renderdoccmd remoteserver --listen 0.0.0.0 --port 39920",
            "Rerun with --mode remote --remote-url <host:39920> --copy-to-remote.",
            "If remote is unavailable, use Route-A/Route-C fallback and annotate limitation.",
        ]

    if status == "unsupported":
        return [
            "Local replay is unsupported for this capture.",
            "Try --mode software (if available) or --mode remote on a compatible GPU.",
            "Fallback to Route-A/Route-C for offline analysis.",
        ]

    if status in ("remote_connect_failed", "remote_copy_failed", "remote_open_capture_failed"):
        return [
            "Validate remote URL/network/firewall and remote server status.",
            "Check that remote host has compatible GPU/driver/extensions for this capture.",
            "If remote remains unavailable, fallback to Route-A/Route-C and record the gap.",
        ]

    return [
        "Inspect open_capture error details in JSON output.",
        "Try --mode software and/or --mode remote.",
    ]


def status_to_exit_code(status: str) -> int:
    return STATUS_EXIT_CODES.get(status, STATUS_EXIT_CODES["error"])


def run(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    bin_dir = args.renderdoc_bin_dir
    pymodules_dir = args.renderdoc_pymodules_dir

    report: Dict[str, Any] = {
        "schema_version": "1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "input": {
            "rdc_path": args.rdc,
            "mode": args.mode,
            "remote_url": args.remote_url,
            "copy_to_remote": args.copy_to_remote,
            "try_software": args.try_software,
        },
        "env": {
            "python": {
                "version": sys.version,
                "executable": sys.executable,
            },
            "renderdoc": {
                "import_ok": False,
                "module_path": "",
            },
            "paths": {
                "renderdoc_bin_dir": bin_dir,
                "renderdoc_pymodules_dir": pymodules_dir,
            },
        },
        "local": {"attempted": False},
        "software": {"attempted": False},
        "remote": {"attempted": False},
        "final": {},
    }

    if not os.path.exists(args.rdc):
        status = "file_not_found"
        report["final"] = {
            "status": status,
            "exit_code": status_to_exit_code(status),
            "recommended_actions": build_recommendations(status),
        }
        return status_to_exit_code(status), report

    configure_renderdoc_env(bin_dir, pymodules_dir)
    ok, rd, module_info = import_renderdoc()
    report["env"]["renderdoc"] = {
        "import_ok": ok,
        "module_path": module_info if ok else "",
        "import_error": "" if ok else module_info,
    }

    if not ok or rd is None:
        status = "module_missing"
        report["final"] = {
            "status": status,
            "exit_code": status_to_exit_code(status),
            "recommended_actions": build_recommendations(status),
        }
        return status_to_exit_code(status), report

    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    try:
        # Local attempt
        attempt_on_suggest_remote = args.mode in ("local", "software")
        report["local"] = attempt_local_replay(
            rd,
            args.rdc,
            force_software=False,
            attempt_on_suggest_remote=attempt_on_suggest_remote,
        )

        # Software attempt
        if args.mode == "software" or (args.mode == "auto" and args.try_software):
            report["software"] = attempt_local_replay(
                rd,
                args.rdc,
                force_software=True,
                attempt_on_suggest_remote=True,
            )

        # Remote attempt
        should_try_remote = args.mode == "remote" or (
            args.mode == "auto"
            and args.remote_url
            and report["local"].get("local_replay_support") == "SuggestRemote"
        )
        if should_try_remote:
            if not args.remote_url:
                report["remote"] = {
                    "attempted": True,
                    "error": "remote_url is required for remote mode",
                }
            else:
                report["remote"] = attempt_remote_replay(
                    rd,
                    args.rdc,
                    args.remote_url,
                    args.copy_to_remote,
                )

        status = infer_final_status(args.mode, report["local"], report["software"], report["remote"])
        report["final"] = {
            "status": status,
            "exit_code": status_to_exit_code(status),
            "recommended_actions": build_recommendations(status),
        }

        return status_to_exit_code(status), report
    finally:
        rd.ShutdownReplay()


def print_summary(report: Dict[str, Any]) -> None:
    final = report.get("final", {})
    local = report.get("local", {})
    print("[route-b] status: {}".format(final.get("status", "unknown")))
    print("[route-b] mode: {}".format(report.get("input", {}).get("mode", "unknown")))

    if local.get("attempted"):
        print("[route-b] local replay support: {}".format(local.get("local_replay_support", "Unknown")))
        open_file = local.get("open_file")
        if open_file:
            print("[route-b] open file: {}".format(open_file.get("message", open_file.get("raw", ""))))
        open_capture = local.get("open_capture")
        if open_capture:
            print("[route-b] local open capture: {}".format(open_capture.get("message", open_capture.get("raw", ""))))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    default_bin, default_pymodules = build_default_paths()
    parser = argparse.ArgumentParser(description="Route-B live replay preflight checker")
    parser.add_argument("rdc", help="Path to .rdc capture file")
    parser.add_argument(
        "--mode",
        choices=("auto", "local", "software", "remote"),
        default="auto",
        help="Replay mode to check (default: auto)",
    )
    parser.add_argument("--renderdoc-bin-dir", default=default_bin, help="Path to RenderDoc binary dir")
    parser.add_argument(
        "--renderdoc-pymodules-dir",
        default=default_pymodules,
        help="Path to RenderDoc pymodules dir",
    )
    parser.add_argument("--remote-url", default="", help="Remote replay server URL, e.g. host:39920")
    parser.add_argument("--copy-to-remote", action="store_true", help="Copy capture to remote before opening")
    parser.add_argument(
        "--try-software",
        action="store_true",
        help="In auto mode, also attempt software replay when local replay is not ready",
    )
    parser.add_argument("--json-out", default="", help="Write report JSON to file")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable summary")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    exit_code, report = run(args)

    if not args.quiet:
        print_summary(report)

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(payload)
            f.write("\n")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
