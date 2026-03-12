import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))


def test_material_follows_shader_or_fallback():
    try:
        from messiah_exporter import build_material_xml
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    xml = build_material_xml(shader_kind="ps", fallback="unlit")
    assert "Unlit" in xml


def test_material_has_pbr_params_when_shader_pbr():
    try:
        from messiah_exporter import build_material_xml
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    xml = build_material_xml(shader_kind="pbr", fallback="unlit")
    assert "<ShaderName>PBR</ShaderName>" in xml
    assert "tBaseMap" in xml
