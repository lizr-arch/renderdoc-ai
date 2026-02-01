import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import analyze_xml_report
import generate_offline_report


def test_offline_manifest_writes_files(tmp_path):
    output_path = tmp_path / "demo_report_xml.html"
    performance_data = {
        "events": [{"eid": 1}],
        "summary": {"total_draw_calls": 1, "unique_textures": 2},
    }
    textures = [{"resource_id": 1}]
    shader_data = [{"id": "s1"}]
    analyze_xml_report.write_offline_manifest(
        output_path,
        performance_data=performance_data,
        textures=textures,
        shader_data=shader_data,
        capture_id="sha256:demo",
    )
    assert (tmp_path / "rdc_manifest.json").exists()
    assert (tmp_path / "report_links.json").exists()


def test_offline_report_embeds_links(tmp_path):
    output_path = tmp_path / "demo_report_xml.html"
    report_links = {"v3": "demo_report.html", "texture": "demo_report_xml.html"}
    generate_offline_report.generate_offline_html(
        textures=[],
        rdc_name="demo",
        output_path=str(output_path),
        report_links=report_links,
    )
    html = output_path.read_text(encoding="utf-8")
    assert "const reportLinks" in html
