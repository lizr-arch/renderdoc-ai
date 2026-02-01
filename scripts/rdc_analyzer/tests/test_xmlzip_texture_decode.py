import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_decode_texture_rgba():
    try:
        from xmlzip_event_extractor import decode_texture_rgba
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    data = b"\x00" * 4
    rgba = decode_texture_rgba(data, 1, 1, "RGBA8")
    assert len(rgba) == 4
