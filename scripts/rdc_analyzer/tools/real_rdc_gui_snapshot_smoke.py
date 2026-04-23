#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formal real-RDC GUI smoke for the verified B -> A pipeline.

Flow:
1. Launch qrenderdoc.exe with a repo-native GUI helper script.
2. Wait for Analyzer Report RefreshReport() to finish and auto-export:
   - snapshot.v1.json
   - analysis.json
   - capture_context.json
3. Run A-line live probe commands against the same GUI session:
   - get_capture_status
   - get_frame_summary
4. Run snapshot_consume.py --execute against the exported snapshot.
5. Emit a summary JSON file that captures commands, outputs, and pass/fail.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
GIT_ROOT = REPO_ROOT.parent


def _default_qrenderdoc():
    return GIT_ROOT / "renderdoc-agentb-r3" / "x64" / "Development" / "qrenderdoc.exe"


def _default_run_query():
    return GIT_ROOT / "renderdoc-agenta-r3" / "scripts" / "rdc_analyzer" / "mcp_examples" / "run_query.py"


def _default_snapshot_consume():
    return (
        GIT_ROOT
        / "renderdoc-agenta-r3"
        / "scripts"
        / "rdc_analyzer"
        / "mcp_examples"
        / "snapshot_consume.py"
    )


def _helper_script():
    return Path(__file__).resolve().with_name("renderdoc_gui_refresh_export.py")


def _parse_args():
    parser = argparse.ArgumentParser(description="Run real-RDC GUI export + MCP smoke.")
    parser.add_argument("--capture", required=True, help="Absolute path to the real .rdc capture")
    parser.add_argument("--out-dir", required=True, help="Directory for smoke outputs")
    parser.add_argument("--qrenderdoc", default=str(_default_qrenderdoc()), help="Path to qrenderdoc.exe")
    parser.add_argument("--run-query", default=str(_default_run_query()), help="Path to run_query.py")
    parser.add_argument(
        "--snapshot-consume",
        default=str(_default_snapshot_consume()),
        help="Path to snapshot_consume.py",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python executable used for run_query.py and snapshot_consume.py",
    )
    parser.add_argument("--launch-timeout", type=int, default=600, help="Seconds to wait for GUI export")
    parser.add_argument("--query-timeout", type=int, default=120, help="Seconds to wait per MCP query")
    parser.add_argument(
        "--consume-timeout",
        type=int,
        default=180,
        help="Seconds to wait for snapshot_consume.py --execute",
    )
    return parser.parse_args()


def _ensure_exists(path, label):
    if not Path(path).exists():
        raise FileNotFoundError("%s not found: %s" % (label, path))


def _load_json(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_json_with_retry(path, attempts=5, sleep_seconds=0.2):
    last_error = None
    for _ in range(int(attempts)):
        try:
            return _load_json(path), None
        except (json.JSONDecodeError, OSError, ValueError) as ex:
            last_error = repr(ex)
            time.sleep(float(sleep_seconds))
    return None, last_error


def _safe_read(path):
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8", errors="replace")


def _command_string(command):
    return subprocess.list2cmdline([str(part) for part in command])


def _run_command(command, timeout_seconds):
    completed = subprocess.run(
        [str(part) for part in command],
        capture_output=True,
        text=True,
        timeout=int(timeout_seconds),
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": _command_string(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_json_command(command, timeout_seconds):
    result = _run_command(command, timeout_seconds)
    stdout = result.get("stdout", "").strip()
    if stdout:
        result["json"] = json.loads(stdout)
    else:
        result["json"] = None
    return result


def _wait_for_json_command(command, timeout_seconds, predicate):
    deadline = time.time() + float(timeout_seconds)
    attempts = 0
    last_result = None
    while time.time() < deadline:
        attempts += 1
        remaining = max(1.0, deadline - time.time())
        last_result = _run_json_command(command, min(35, remaining))
        payload = last_result.get("json") or {}
        if predicate(last_result, payload):
            last_result["attempt_count"] = attempts
            return last_result
        if time.time() >= deadline:
            break
        time.sleep(2.0)
    if last_result is None:
        last_result = {"command": _command_string(command), "returncode": -1, "stdout": "", "stderr": "", "json": None}
    last_result["attempt_count"] = attempts
    return last_result


def _wait_for_gui_result(state_path, process, timeout_seconds):
    deadline = time.time() + float(timeout_seconds)
    last_state = None
    last_load_error = None
    while time.time() < deadline:
        if Path(state_path).exists():
            loaded_state, load_error = _load_json_with_retry(state_path)
            if loaded_state is not None:
                last_state = loaded_state
                last_load_error = None
                phase = str(last_state.get("phase", ""))
                if phase == "done":
                    return last_state
                if phase == "error":
                    raise RuntimeError("GUI helper reported error: %s" % last_state.get("error", "unknown"))
            else:
                last_load_error = load_error
        if process.poll() is not None:
            if last_load_error:
                raise RuntimeError(
                    "qrenderdoc exited before smoke completed; last gui_state load error: %s" % last_load_error
                )
            raise RuntimeError("qrenderdoc exited before smoke completed")
        time.sleep(1.0)
    if last_load_error:
        raise RuntimeError(
            "Timed out waiting for GUI smoke completion; last gui_state load error: %s; last state: %s"
            % (last_load_error, last_state or {})
        )
    raise RuntimeError("Timed out waiting for GUI smoke completion: %s" % (last_state or {}))


def _shutdown_process(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    process.kill()
    process.wait(timeout=10)


def _cleanup_bridge_ipc():
    ipc_dir = Path(tempfile.gettempdir()) / "renderdoc_mcp"
    removed = []
    errors = []
    for name in ("request.json", "response.json", "lock"):
        path = ipc_dir / name
        if not path.exists():
            continue
        try:
            path.unlink()
            removed.append(str(path))
        except Exception as ex:
            errors.append("%s: %s" % (path, ex))
    return {"ipc_dir": str(ipc_dir), "removed": removed, "errors": errors}


def _cleanup_previous_outputs(paths):
    removed = []
    errors = []
    for path in paths:
        target = Path(path)
        if not target.exists():
            continue
        try:
            target.unlink()
            removed.append(str(target))
        except Exception as ex:
            errors.append("%s: %s" % (target, ex))
    return {"removed": removed, "errors": errors}


def run_smoke(
    capture,
    out_dir,
    qrenderdoc,
    run_query,
    snapshot_consume,
    python_exe,
    launch_timeout,
    query_timeout,
    consume_timeout,
):
    capture_path = Path(capture)
    out_path = Path(out_dir)
    qrenderdoc_path = Path(qrenderdoc)
    run_query_path = Path(run_query)
    snapshot_consume_path = Path(snapshot_consume)
    helper_path = _helper_script()

    _ensure_exists(capture_path, "capture")
    _ensure_exists(qrenderdoc_path, "qrenderdoc")
    _ensure_exists(run_query_path, "run_query.py")
    _ensure_exists(snapshot_consume_path, "snapshot_consume.py")
    _ensure_exists(helper_path, "GUI helper")

    out_path.mkdir(parents=True, exist_ok=True)

    state_path = out_path / "gui_state.json"
    summary_path = out_path / "real_rdc_gui_snapshot_smoke.summary.json"
    stdout_log = out_path / "qrenderdoc.stdout.log"
    stderr_log = out_path / "qrenderdoc.stderr.log"
    consumer_json = out_path / "consumer.execute.json"
    consumer_md = out_path / "consumer.execute.md"
    consumer_cmd = out_path / "consumer.execute.cmds.txt"

    env = os.environ.copy()
    env["RENDERDOC_ANALYZER_AUTO_EXPORT_DIR"] = str(out_path)
    env["RENDERDOC_ANALYZER_AUTO_EXPORT_EXIT"] = "0"
    env["RDC_REAL_SMOKE_STATE_FILE"] = str(state_path)

    gui_command = [str(qrenderdoc_path), "--ui-python", str(helper_path), str(capture_path)]

    summary = {
        "success": False,
        "capture": str(capture_path),
        "out_dir": str(out_path),
        "qrenderdoc": str(qrenderdoc_path),
        "helper_script": str(helper_path),
        "run_query": str(run_query_path),
        "snapshot_consume": str(snapshot_consume_path),
        "commands": {
            "gui_launch": _command_string(gui_command),
        },
        "artifacts": {
            "state_file": str(state_path),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
            "summary_json": str(summary_path),
            "consumer_json": str(consumer_json),
            "consumer_md": str(consumer_md),
            "consumer_cmd": str(consumer_cmd),
        },
        "bridge_cleanup": _cleanup_bridge_ipc(),
        "output_cleanup": _cleanup_previous_outputs(
            [
                state_path,
                summary_path,
                stdout_log,
                stderr_log,
                consumer_json,
                consumer_md,
                consumer_cmd,
                out_path / "gui_state.json.tmp",
                out_path / "analyzer_auto_export_trace.log",
                out_path / "snapshot.v1.json",
                out_path / "analysis.json",
                out_path / "capture_context.json",
                out_path / "issues_export.csv",
                out_path / "issues_export.md",
            ]
        ),
    }

    stdout_handle = open(str(stdout_log), "w", encoding="utf-8", errors="replace")
    stderr_handle = open(str(stderr_log), "w", encoding="utf-8", errors="replace")
    process = None

    try:
        process = subprocess.Popen(
            gui_command,
            stdout=stdout_handle,
            stderr=stderr_handle,
            env=env,
            cwd=str(REPO_ROOT),
        )
        summary["pid"] = int(process.pid)
        summary["gui_state"] = _wait_for_gui_result(state_path, process, launch_timeout)

        snapshot_path = out_path / "snapshot.v1.json"
        analysis_path = out_path / "analysis.json"
        capture_context_path = out_path / "capture_context.json"
        for expected in (snapshot_path, analysis_path, capture_context_path):
            if not expected.exists():
                raise RuntimeError("Missing expected export artifact: %s" % expected)

        query_capture_command = [
            str(python_exe),
            str(run_query_path),
            "--method",
            "get_capture_status",
            "--params",
            "{}",
        ]
        query_frame_command = [
            str(python_exe),
            str(run_query_path),
            "--method",
            "get_frame_summary",
            "--params",
            "{}",
        ]
        summary["commands"]["get_capture_status"] = _command_string(query_capture_command)
        summary["commands"]["get_frame_summary"] = _command_string(query_frame_command)

        capture_status = _wait_for_json_command(
            query_capture_command,
            query_timeout,
            lambda result, payload: (
                result.get("returncode") == 0
                and bool(payload.get("ok"))
                and bool(((payload.get("data") or {}).get("loaded")))
            ),
        )
        frame_summary = _wait_for_json_command(
            query_frame_command,
            query_timeout,
            lambda result, payload: result.get("returncode") == 0 and bool(payload.get("ok")),
        )
        summary["mcp"] = {
            "get_capture_status": capture_status,
            "get_frame_summary": frame_summary,
        }

        capture_ok = bool((capture_status.get("json") or {}).get("ok"))
        capture_loaded = bool((((capture_status.get("json") or {}).get("data") or {}).get("loaded")))
        frame_ok = bool((frame_summary.get("json") or {}).get("ok"))
        if not capture_ok or not capture_loaded:
            raise RuntimeError("get_capture_status did not report loaded=true")
        if not frame_ok:
            raise RuntimeError("get_frame_summary failed")

        consume_command = [
            str(python_exe),
            str(snapshot_consume_path),
            "--snapshot",
            str(snapshot_path),
            "--execute",
            "--out-json",
            str(consumer_json),
            "--out-md",
            str(consumer_md),
            "--out-cmd",
            str(consumer_cmd),
        ]
        summary["commands"]["snapshot_consume"] = _command_string(consume_command)
        consume_result = _run_command(consume_command, consume_timeout)
        if not consumer_json.exists():
            raise RuntimeError("snapshot_consume.py did not write consumer.execute.json")
        summary["consumer"] = {
            "command": consume_result["command"],
            "returncode": consume_result["returncode"],
            "stdout": consume_result["stdout"],
            "stderr": consume_result["stderr"],
            "json": _load_json(consumer_json),
        }
        if consume_result["returncode"] != 0:
            raise RuntimeError("snapshot_consume.py returned non-zero exit status")

        enrichment = ((summary["consumer"]["json"] or {}).get("enrichment") or {})
        health_probe = ((summary["consumer"]["json"] or {}).get("health_probe") or {})
        if enrichment.get("status") != "executed":
            raise RuntimeError("snapshot_consume.py did not reach executed status")
        if not bool(health_probe.get("ok")):
            raise RuntimeError("snapshot_consume.py health probe did not report ok=true")

        summary["exports"] = {
            "snapshot_v1_json": str(snapshot_path),
            "analysis_json": str(analysis_path),
            "capture_context_json": str(capture_context_path),
            "snapshot_size": snapshot_path.stat().st_size,
            "analysis_size": analysis_path.stat().st_size,
            "capture_context_size": capture_context_path.stat().st_size,
        }
        summary["success"] = True
        return summary
    finally:
        stdout_handle.flush()
        stderr_handle.flush()
        stdout_handle.close()
        stderr_handle.close()
        if process is not None:
            _shutdown_process(process)
        summary["logs"] = {
            "stdout_tail": _safe_read(stdout_log)[-2000:],
            "stderr_tail": _safe_read(stderr_log)[-2000:],
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def main():
    args = _parse_args()
    summary = run_smoke(
        capture=args.capture,
        out_dir=args.out_dir,
        qrenderdoc=args.qrenderdoc,
        run_query=args.run_query,
        snapshot_consume=args.snapshot_consume,
        python_exe=args.python_exe,
        launch_timeout=args.launch_timeout,
        query_timeout=args.query_timeout,
        consume_timeout=args.consume_timeout,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
