import os
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RDC_UI_SMOKE", "0") != "1",
    reason="UI smoke is opt-in (set RDC_UI_SMOKE=1)",
)
def test_ui_headless_smoke_runs(tmp_path):
    """Run the headless UI smoke tool against an already-generated bundle report.

    This is intentionally opt-in because it requires Playwright.

    Required env:
      - RDC_UI_SMOKE=1
      - RDC_UI_SMOKE_REPORT_DIR=<path to bundle output dir> (contains textures.html/shaders.html)

    Optional env:
      - RDC_UI_SMOKE_OUT_DIR=<path to write artifacts> (defaults to tmpdir)
    """

    report_dir = os.environ.get("RDC_UI_SMOKE_REPORT_DIR", "").strip()
    if not report_dir:
        pytest.skip("RDC_UI_SMOKE_REPORT_DIR not set")

    report_path = Path(report_dir)
    if not report_path.is_dir():
        pytest.skip(f"RDC_UI_SMOKE_REPORT_DIR is not a directory: {report_dir}")

    # quick sanity so errors are readable
    if not (report_path / "textures.html").is_file():
        pytest.skip(f"textures.html not found in report_dir: {report_dir}")
    if not (report_path / "shaders.html").is_file():
        pytest.skip(f"shaders.html not found in report_dir: {report_dir}")

    out_dir = os.environ.get("RDC_UI_SMOKE_OUT_DIR", "").strip()
    out_path = Path(out_dir) if out_dir else (tmp_path / "ui_smoke")
    out_path.mkdir(parents=True, exist_ok=True)

    try:
        # Lazy import so environments without Playwright can still collect tests.
        from rdc_analyzer.tools.ui_headless_smoke import run_smoke
    except Exception as ex:
        pytest.skip(f"UI smoke tool unavailable (likely missing Playwright): {ex}")

    result = run_smoke(
        report_dir=report_path,
        out_dir=out_path,
        viewports=[(1366, 768)],
        capture_screenshots=False,
    )
    assert result.get("overall_pass") is True, result
