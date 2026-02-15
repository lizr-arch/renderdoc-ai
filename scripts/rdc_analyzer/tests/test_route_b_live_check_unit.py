import sys
from argparse import Namespace
from pathlib import Path

# Ensure local import works when running from repo root
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.rdc_analyzer.route_b_live_check import (
    build_default_paths,
    classify_replay_support,
    infer_final_status,
    build_recommendations,
    run,
    status_to_exit_code,
)


class DummyEnum:
    def __init__(self, name):
        self.name = name


def test_build_default_paths_suffixes():
    script_path = Path("D:/Code/git/renderdoc/scripts/rdc_analyzer/route_b_live_check.py")
    bin_dir, pymod_dir = build_default_paths(script_path=script_path)
    assert bin_dir.endswith("x64\\Development") or bin_dir.endswith("x64/Development")
    assert pymod_dir.endswith("x64\\Development\\pymodules") or pymod_dir.endswith("x64/Development/pymodules")


def test_classify_replay_support_from_enum_name():
    assert classify_replay_support(DummyEnum("Supported")) == "Supported"
    assert classify_replay_support(DummyEnum("SuggestRemote")) == "SuggestRemote"
    assert classify_replay_support(DummyEnum("Unsupported")) == "Unsupported"


def test_classify_replay_support_from_string_fallback():
    assert classify_replay_support("ReplaySupport.SuggestRemote") == "SuggestRemote"
    assert classify_replay_support("ReplaySupport.Supported") == "Supported"
    assert classify_replay_support("ReplaySupport.Unsupported") == "Unsupported"


def test_infer_status_needs_remote_in_local_mode():
    local = {
        "open_file": {"ok": True},
        "local_replay_support": "SuggestRemote",
        "open_capture": {"ok": False},
    }
    software = {"open_capture": None}
    remote = {"open_capture": None}
    assert infer_final_status("local", local, software, remote) == "needs_remote"


def test_infer_status_ok_remote_in_remote_mode():
    local = {
        "open_file": {"ok": True},
        "local_replay_support": "SuggestRemote",
        "open_capture": {"ok": False},
    }
    software = {"open_capture": None}
    remote = {
        "connect": {"ok": True},
        "copy_to_remote": {"ok": True},
        "open_capture": {"ok": True},
    }
    assert infer_final_status("remote", local, software, remote) == "ok_remote"


def test_build_recommendations_remote_has_command_hint():
    recs = build_recommendations("needs_remote")
    joined = "\n".join(recs).lower()
    assert "remoteserver" in joined
    assert "--mode remote" in joined


def test_status_to_exit_code_contract():
    assert status_to_exit_code("ok_local") == 0
    assert status_to_exit_code("needs_remote") == 10
    assert status_to_exit_code("module_missing") == 20
    assert status_to_exit_code("remote_open_capture_failed") == 32
    assert status_to_exit_code("unknown_status") == 40


def test_run_file_not_found_report_shape(tmp_path):
    missing_rdc = tmp_path / "missing_capture.rdc"
    args = Namespace(
        rdc=str(missing_rdc),
        mode="auto",
        remote_url="",
        copy_to_remote=False,
        try_software=False,
        renderdoc_bin_dir="D:/fake/renderdoc/bin",
        renderdoc_pymodules_dir="D:/fake/renderdoc/pymodules",
    )

    exit_code, report = run(args)

    assert exit_code == 21
    assert report["schema_version"] == "1.0"
    assert report["input"]["rdc_path"] == str(missing_rdc)
    assert report["local"]["attempted"] is False
    assert report["software"]["attempted"] is False
    assert report["remote"]["attempted"] is False
    assert report["final"]["status"] == "file_not_found"
    assert isinstance(report["final"]["recommended_actions"], list)
    assert report["final"]["recommended_actions"]
