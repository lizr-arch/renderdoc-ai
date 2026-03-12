import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_material_writes_multiple_texture_parameters():
    try:
        from messiah_exporter import build_material_xml
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    xml = build_material_xml(
        shader_kind="pbr",
        fallback="unlit",
        texture_bindings=[
            ("tBaseMap", "11111111-1111-1111-1111-111111111111"),
            ("tNormalMap", "22222222-2222-2222-2222-222222222222"),
        ],
    )

    assert "<ShaderName>PBR</ShaderName>" in xml
    assert "<Parameters count=\"2\"" in xml
    assert "<Name>tBaseMap</Name>" in xml
    assert "11111111-1111-1111-1111-111111111111" in xml
    assert "<Name>tNormalMap</Name>" in xml
    assert "22222222-2222-2222-2222-222222222222" in xml
