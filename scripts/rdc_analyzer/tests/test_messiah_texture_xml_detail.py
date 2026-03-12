import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_texture_xml_has_required_sections():
    try:
        from messiah_exporter import _build_texture_xml
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    xml = _build_texture_xml(1, 1, "R8G8B8A8", 4)
    assert "<Texture2DInfo>" in xml
    assert "<RsTextureInfo>" in xml
    assert "<RsTextureSliceData>" in xml
