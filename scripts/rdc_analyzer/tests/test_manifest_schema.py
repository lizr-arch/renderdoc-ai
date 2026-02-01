import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from schema import rdc_manifest


def test_manifest_requires_reason_for_missing():
    with pytest.raises(ValueError):
        rdc_manifest.build_manifest(
            capture_id="sha256:demo",
            source="A",
            counts={"events": 1, "textures": 0, "shaders": 0},
            count_reason={"events": "xml"},
            missing=[{"field": "x", "reason": ""}],
            report_links={"v3": "demo_report.html"},
        )
