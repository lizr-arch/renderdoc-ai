import sys
import zipfile
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _make_zip(tmp_path):
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as handle:
        handle.writestr("buf_10.bin", b"xx")
    return zip_path


def test_zip_reader_resolves_entries(tmp_path):
    try:
        from xmlzip_event_extractor import load_zip_index, resolve_zip_entry
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    zip_path = _make_zip(tmp_path)
    zip_index = load_zip_index(str(zip_path))

    assert zip_index["buf_10.bin"] == b"xx"
    assert resolve_zip_entry("buf_10.bin", zip_index) == "buf_10.bin"
    assert resolve_zip_entry("missing.bin", zip_index) is None
