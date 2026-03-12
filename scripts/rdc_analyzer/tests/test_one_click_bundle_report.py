import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import one_click_bundle_report as cli


def test_build_convert_command_zip_xml():
    cmd = cli.build_convert_command(
        "renderdoccmd",
        Path("in.rdc"),
        Path("out.zip.xml"),
        convert_format="zip.xml",
    )
    assert cmd == [
        "renderdoccmd",
        "convert",
        "-f",
        "in.rdc",
        "-o",
        "out.zip.xml",
        "-c",
        "zip.xml",
    ]


def test_build_convert_command_plain_xml():
    cmd = cli.build_convert_command(
        "renderdoccmd",
        Path("a.rdc"),
        Path("b.xml"),
        convert_format="xml",
    )
    assert cmd[-1] == "xml"
    assert "-f" in cmd


def test_build_bundle_command_with_optional_args():
    cmd = cli.build_bundle_command(
        python_exec="py",
        xml_to_bundle_script=Path("xml_to_bundle.py"),
        xml_path=Path("capture.zip.xml"),
        output_dir=Path("out_dir"),
        rdc_path=Path("capture.rdc"),
        zip_path=Path("capture.zip"),
        texture_dir=Path("textures"),
        spirv_cross="spirv-cross.exe",
        verbose=True,
    )
    assert cmd == [
        "py",
        "xml_to_bundle.py",
        "capture.zip.xml",
        "-o",
        "out_dir",
        "--rdc",
        "capture.rdc",
        "--zip",
        "capture.zip",
        "--texture-dir",
        "textures",
        "--spirv-cross",
        "spirv-cross.exe",
        "-v",
    ]


def test_resolve_zip_sidecar_prefers_zipxml_sidecar(tmp_path: Path):
    xml_path = tmp_path / "capture.zip.xml"
    rdc_path = tmp_path / "capture.rdc"
    xml_path.write_text("", encoding="utf-8")
    rdc_path.write_text("", encoding="utf-8")

    zip_sidecar = tmp_path / "capture.zip"
    zip_sidecar.write_text("", encoding="utf-8")

    resolved = cli.resolve_zip_sidecar(xml_path, rdc_path)
    assert resolved == zip_sidecar


def test_default_output_dir_for_rdc(tmp_path: Path):
    rdc = tmp_path / "demo.rdc"
    expected = tmp_path / "demo_report"
    assert cli.default_output_dir_for_rdc(rdc) == expected


def test_build_thumbnail_audit_command():
    cmd = cli.build_thumbnail_audit_command(
        python_exec="py",
        audit_script=Path("thumbnail_audit.py"),
        report_dir=Path("out_dir"),
        texture_dir=Path("out_dir/textures"),
        sentinel_count=12,
        verbose=True,
    )
    assert cmd == [
        "py",
        "thumbnail_audit.py",
        "--report-dir",
        "out_dir",
        "--texture-dir",
        str(Path("out_dir") / "textures"),
        "--count",
        "12",
        "-v",
    ]
