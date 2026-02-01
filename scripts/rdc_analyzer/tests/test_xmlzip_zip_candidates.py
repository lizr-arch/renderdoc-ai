import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_zip_entry_candidate_resolution():
    try:
        from xmlzip_event_extractor import resolve_zip_entry_candidates
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    zip_index = {"buffers/buffer12": b"x"}
    assert resolve_zip_entry_candidates(12, zip_index) == "buffers/buffer12"
