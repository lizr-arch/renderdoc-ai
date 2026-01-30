from pathlib import Path

from rdc_analyzer.analyze_rdc import generate_html_report


def test_html_includes_data_gap_reasons(tmp_path):
    results = [{
        "summary": {
            "file_name": "dummy.rdc",
            "analyzed_shaders": 0,
            "cycles": {"average": 0.0, "max": 0.0},
            "spilling_shaders": 0,
            "total_draw_events": 0,
            "total_pipelines": 0,
            "shader_data_reason": "shader missing",
            "texture_data_reason": "texture missing",
        },
        "shaders": [],
        "textures": [],
    }]

    out_path = tmp_path / "report.html"
    generate_html_report(results, str(out_path))
    html = Path(out_path).read_text(encoding="utf-8")

    assert "shader missing" in html
    assert "texture missing" in html
