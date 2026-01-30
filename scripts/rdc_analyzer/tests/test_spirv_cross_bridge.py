import os
import sys

TEST_DIR = os.path.dirname(__file__)
EXPORTERS_DIR = os.path.join(TEST_DIR, "..", "exporters")
sys.path.insert(0, os.path.abspath(EXPORTERS_DIR))

from spirv_cross_bridge import require_spirv_cross, resolve_spirv_cross_path


def test_resolve_spirv_cross_path_cli_over_env(monkeypatch):
    monkeypatch.setenv("SPIRV_CROSS", "C:\\env\\spirv-cross.exe")
    assert resolve_spirv_cross_path("C:\\cli\\spirv-cross.exe") == "C:\\cli\\spirv-cross.exe"


def test_resolve_spirv_cross_path_env(monkeypatch):
    monkeypatch.setenv("SPIRV_CROSS", "C:\\env\\spirv-cross.exe")
    assert resolve_spirv_cross_path(None) == "C:\\env\\spirv-cross.exe"


def test_resolve_spirv_cross_path_none(monkeypatch):
    monkeypatch.delenv("SPIRV_CROSS", raising=False)
    assert resolve_spirv_cross_path(None) is None


def test_require_spirv_cross_for_vulkan():
    try:
        require_spirv_cross("vulkan", None)
        assert False, "expected SystemExit"
    except SystemExit:
        assert True
