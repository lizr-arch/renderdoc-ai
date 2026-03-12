import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_mesh_schema_has_axis_and_unit():
    try:
        from intermediate_schema import build_mesh_schema
    except ImportError as exc:
        pytest.fail(f"intermediate_schema missing: {exc}")

    mesh = build_mesh_schema()
    assert "axis" in mesh and "unit_scale" in mesh
