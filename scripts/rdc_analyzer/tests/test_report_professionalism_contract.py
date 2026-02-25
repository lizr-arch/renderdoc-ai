import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from report_bundle_generator import ReportBundleGenerator  # noqa: E402


def test_set_performance_data_prefers_suggestions_contract(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_performance_data(
        {
            "suggestions": [
                {
                    "id": "SUG-001",
                    "title": "Prefer suggestions",
                    "detail": "from suggestions",
                    "priority": "high",
                }
            ],
            "recommendations": [
                {
                    "id": "REC-001",
                    "title": "fallback recommendations",
                    "detail": "from recommendations",
                }
            ],
        }
    )

    recs = gen.stats.get("recommendations", [])
    assert len(recs) == 1
    assert recs[0].get("title") == "Prefer suggestions"


def test_index_renders_canonical_issue_fields(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_performance_data(
        {
            "issues": [
                {
                    "severity": "warning",
                    "code": "BIND001",
                    "message": "Draw call too high",
                    "event_ids": [42],
                    "resource_ids": ["tex_1"],
                    "evidence": {"actual": 4000, "threshold": 2000},
                }
            ]
        }
    )

    html = gen.generate_index()
    assert "[BIND001] Draw call too high" in html
    assert "EID 42" in html


def test_index_renders_quality_panel_from_coverage(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_performance_data(
        {
            "coverage": {
                "overall": "medium",
                "confidence_reasons": ["Pipeline State 使用估算值"],
            },
            "preflight": {"status": "warning", "missing_data": [{"key": "markers"}]},
            "data_richness": {
                "routes": {
                    "A": {"coverage": "partial"},
                    "C": {"coverage": "summary_only"},
                }
            },
        }
    )

    html = gen.generate_index()
    assert "数据可信度" in html
    assert "medium" in html
    assert "warning" in html
    assert "Pipeline State 使用估算值" in html

