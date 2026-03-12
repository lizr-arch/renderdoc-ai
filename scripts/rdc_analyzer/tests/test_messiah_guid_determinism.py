import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_guid_hash_is_deterministic():
    try:
        from engine_guid import hash_guid
    except ImportError as exc:
        pytest.fail(f"engine_guid missing: {exc}")

    assert hash_guid("Mesh", 100, "vb0") == hash_guid("Mesh", 100, "vb0")
