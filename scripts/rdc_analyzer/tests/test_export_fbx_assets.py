import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_resolve_fbx_backend_prefers_python_binding(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.setitem(sys.modules, "fbx", object())
    assert resolve_fbx_backend() == "python"


def test_resolve_fbx_backend_none_when_missing(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.delitem(sys.modules, "fbx", raising=False)
    assert resolve_fbx_backend() in {"cli", "none"}
