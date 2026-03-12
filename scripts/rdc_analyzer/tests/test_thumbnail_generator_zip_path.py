import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from thumbnail_generator import ThumbnailGenerator


def test_infer_zip_from_zipxml_name(tmp_path: Path):
    xml_path = tmp_path / "capture.zip.xml"
    zip_path = tmp_path / "capture.zip"
    xml_path.write_text("", encoding="utf-8")
    zip_path.write_text("", encoding="utf-8")

    gen = ThumbnailGenerator(xml_path)
    assert gen.zip_path == zip_path


def test_infer_zip_from_plain_xml_name(tmp_path: Path):
    xml_path = tmp_path / "capture.xml"
    zip_path = tmp_path / "capture.zip"
    xml_path.write_text("", encoding="utf-8")
    zip_path.write_text("", encoding="utf-8")

    gen = ThumbnailGenerator(xml_path)
    assert gen.zip_path == zip_path


def test_infer_zip_fallback_path_when_missing(tmp_path: Path):
    xml_path = tmp_path / "capture.xml"
    xml_path.write_text("", encoding="utf-8")

    gen = ThumbnailGenerator(xml_path)
    assert gen.zip_path == (tmp_path / "capture.zip")
