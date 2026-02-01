import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_mesh_xml_has_vertex_format_and_streams():
    try:
        from messiah_exporter import _build_mesh_xml
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    xml = _build_mesh_xml(vertex_count=3, index_count=3, stream0_size=72, index_size=6)
    assert "<VertexFormat" in xml
    assert "<Streams" in xml
    assert "<BoundingBox>" in xml
