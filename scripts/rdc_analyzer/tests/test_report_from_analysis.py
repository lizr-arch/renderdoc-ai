from pathlib import Path

from rdc_analyzer.report_from_analysis import generate_report_from_analysis


def test_generate_report_from_analysis(tmp_path: Path):
    analysis = tmp_path / "analysis.json"
    analysis.write_text("{}", encoding="utf-8")
    generate_report_from_analysis(analysis, tmp_path, "capture")
    assert (tmp_path / "index.html").exists()
