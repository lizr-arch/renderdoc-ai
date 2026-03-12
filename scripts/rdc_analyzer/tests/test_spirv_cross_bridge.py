import os
import sys

TEST_DIR = os.path.dirname(__file__)
EXPORTERS_DIR = os.path.join(TEST_DIR, "..", "exporters")
sys.path.insert(0, os.path.abspath(EXPORTERS_DIR))

import spirv_cross_bridge as bridge
from spirv_cross_bridge import require_spirv_cross, resolve_spirv_cross_path


def test_resolve_spirv_cross_path_cli_over_env(monkeypatch):
    monkeypatch.setenv("SPIRV_CROSS", "C:\\env\\spirv-cross.exe")
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    assert resolve_spirv_cross_path("C:\\cli\\spirv-cross.exe") == "C:\\cli\\spirv-cross.exe"


def test_resolve_spirv_cross_path_env(monkeypatch):
    monkeypatch.setenv("SPIRV_CROSS", "C:\\env\\spirv-cross.exe")
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    assert resolve_spirv_cross_path(None) == "C:\\env\\spirv-cross.exe"


def test_resolve_spirv_cross_path_none(monkeypatch):
    monkeypatch.delenv("SPIRV_CROSS", raising=False)
    monkeypatch.delenv("SPIRV_CROSS_PATH", raising=False)
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    monkeypatch.setattr(bridge, "_iter_windows_spirv_cross_candidates", lambda: [])
    monkeypatch.setattr(bridge, "_resolve_with_everything", lambda: None)
    assert resolve_spirv_cross_path(None) is None


def test_resolve_spirv_cross_path_windows_known_location(monkeypatch, tmp_path):
    candidate = tmp_path / "spirv-cross.exe"
    candidate.write_bytes(b"MZ")

    monkeypatch.delenv("SPIRV_CROSS", raising=False)
    monkeypatch.delenv("SPIRV_CROSS_PATH", raising=False)
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    monkeypatch.setattr(bridge.os, "name", "nt", raising=False)
    monkeypatch.setattr(bridge, "_iter_windows_spirv_cross_candidates", lambda: [candidate])
    monkeypatch.setattr(bridge, "_resolve_with_everything", lambda: None)

    assert resolve_spirv_cross_path(None) == str(candidate)


def test_resolve_spirv_cross_path_windows_everything_fallback(monkeypatch):
    monkeypatch.delenv("SPIRV_CROSS", raising=False)
    monkeypatch.delenv("SPIRV_CROSS_PATH", raising=False)
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    monkeypatch.setattr(bridge.os, "name", "nt", raising=False)
    monkeypatch.setattr(bridge, "_iter_windows_spirv_cross_candidates", lambda: [])
    monkeypatch.setattr(bridge, "_resolve_with_everything", lambda: "D:/tools/spirv-cross.exe")

    assert resolve_spirv_cross_path(None) == "D:/tools/spirv-cross.exe"


def test_require_spirv_cross_for_vulkan():
    try:
        require_spirv_cross("vulkan", None)
        assert False, "expected SystemExit"
    except SystemExit:
        assert True
