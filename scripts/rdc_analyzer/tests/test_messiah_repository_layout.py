import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_repository_layout(tmp_path):
    try:
        from messiah_exporter import write_repo_skeleton
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    root = write_repo_skeleton(tmp_path, event_id=100)
    assert (root / "resource.repository").exists()
    assert "rdc_event_100.local" in str(root)
