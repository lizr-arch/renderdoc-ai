import json
from pathlib import Path

from rdc_analyzer.report_from_analysis import generate_report_from_analysis


def test_report_exports_issues(tmp_path: Path) -> None:
    analysis = {
        "summary": {"draw_calls": 0},
        "events": [],
        "textures": [],
        "shaders": [],
        "issues": [
            {
                "severity": "warning",
                "category": "performance",
                "code": "TEST001",
                "message": "Test issue",
                "event_id": 7,
                "resource_id": "res_1",
            }
        ],
    }

    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    generate_report_from_analysis(analysis_path, tmp_path, "capture")

    json_export = tmp_path / "issues_export.json"
    csv_export = tmp_path / "issues_export.csv"
    assert json_export.exists()
    assert csv_export.exists()
    content = json_export.read_text(encoding="utf-8")
    assert "Test issue" in content
    assert "res_1" in content
