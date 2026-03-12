import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_manifest_records_zip_and_decode():
    try:
        from xmlzip_event_extractor import build_decode_manifest
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    manifest = build_decode_manifest(zip_entry="buffers/buffer12", decode_status="ok")
    assert manifest["zip_entry"] == "buffers/buffer12"
    assert manifest["decode_status"] == "ok"
