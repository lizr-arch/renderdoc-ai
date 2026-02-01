import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import analyze_rdc


def test_v3_report_writes_manifest(tmp_path):
    analysis_results = [
        {
            "summary": {
                "file": "demo.rdc",
                "file_name": "demo.rdc",
                "analyzed_shaders": 2,
                "total_draw_events": 3,
                "texture_source": "chunk",
                "texture_data_reason": "no manifest",
            },
            "textures": [{"resource_id": 1}],
            "shaders": [{"id": "s1"}],
        }
    ]
    output_path = tmp_path / "demo_report.html"
    analyze_rdc.write_v3_manifest(output_path, analysis_results, capture_id="sha256:demo")
    assert (tmp_path / "rdc_manifest.json").exists()
