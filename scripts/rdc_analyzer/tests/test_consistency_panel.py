import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import analyze_rdc
import generate_offline_report


def test_v3_report_includes_consistency_panel(tmp_path):
    analysis_results = [
        {
            "summary": {
                "file": "demo.rdc",
                "file_name": "demo.rdc",
                "analyzed_shaders": 1,
                "cycles": {"average": 0.0, "max": 0.0, "min": 0.0, "total": 0.0},
                "spilling_shaders": 0,
                "total_draw_events": 2,
                "texture_source": "chunk",
                "texture_data_reason": "no manifest",
            },
            "textures": [{"resource_id": 1}],
            "shaders": [{"id": "s1"}],
        }
    ]
    output_path = tmp_path / "demo_report.html"
    analyze_rdc.generate_html_report(analysis_results, str(output_path))
    html = output_path.read_text(encoding="utf-8")
    assert "consistency-panel" in html
    assert "manifestData" in html


def test_offline_report_includes_consistency_panel(tmp_path):
    output_path = tmp_path / "demo_report_xml.html"
    report_links = {"v3": "demo_report.html", "texture": "demo_report_xml.html"}
    generate_offline_report.generate_offline_html(
        textures=[],
        rdc_name="demo",
        output_path=str(output_path),
        report_links=report_links,
    )
    html = output_path.read_text(encoding="utf-8")
    assert "consistency-panel" in html
    assert "reportLinks" in html
