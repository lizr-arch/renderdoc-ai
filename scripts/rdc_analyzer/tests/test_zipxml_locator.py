import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zipxml_locator import find_zipxml_sidecar


def test_find_same_name_zipxml_pair(tmp_path: Path):
    capture = tmp_path / "cap.rdc"
    capture.write_text("", encoding="utf-8")

    zip_path = tmp_path / "cap.zip"
    xml_path = tmp_path / "cap.zip.xml"
    zip_path.write_text("", encoding="utf-8")
    xml_path.write_text("", encoding="utf-8")

    z, x, _ = find_zipxml_sidecar(capture)
    assert z == zip_path
    assert x == xml_path


def test_find_export_zip_with_base_xml(tmp_path: Path):
    capture = tmp_path / "ef_r8.rdc"
    capture.write_text("", encoding="utf-8")

    zip_path = tmp_path / "ef_r8_export.zip"
    xml_path = tmp_path / "ef_r8.xml"
    zip_path.write_text("", encoding="utf-8")
    xml_path.write_text("", encoding="utf-8")

    z, x, tried = find_zipxml_sidecar(capture)
    assert z == zip_path
    assert x == xml_path
    assert any("ef_r8_export.zip" in t for t in tried)


def test_find_with_explicit_hints(tmp_path: Path):
    capture = tmp_path / "demo.rdc"
    capture.write_text("", encoding="utf-8")

    zip_path = tmp_path / "custom_assets.zip"
    xml_path = tmp_path / "custom_assets.xml"
    zip_path.write_text("", encoding="utf-8")
    xml_path.write_text("", encoding="utf-8")

    z, x, tried = find_zipxml_sidecar(capture, zip_hint=zip_path, xml_hint=xml_path)
    assert z == zip_path
    assert x == xml_path
    assert tried == []


def test_find_returns_none_when_missing(tmp_path: Path):
    capture = tmp_path / "missing.rdc"
    capture.write_text("", encoding="utf-8")

    z, x, tried = find_zipxml_sidecar(capture)
    assert z is None
    assert x is None
    assert isinstance(tried, list)
