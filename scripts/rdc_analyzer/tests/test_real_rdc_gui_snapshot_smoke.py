import os
import threading
import time
from pathlib import Path

import pytest


def test_real_rdc_gui_snapshot_smoke_exports_run_smoke():
    from rdc_analyzer.tools.real_rdc_gui_snapshot_smoke import run_smoke

    assert callable(run_smoke)


def test_load_json_with_retry_tolerates_partial_state_file(tmp_path):
    from rdc_analyzer.tools.real_rdc_gui_snapshot_smoke import _load_json_with_retry

    state_path = tmp_path / "gui_state.json"
    state_path.write_text("", encoding="utf-8")

    def _complete_write():
        time.sleep(0.2)
        state_path.write_text('{"phase":"waiting_export","refresh_called":true}', encoding="utf-8")

    thread = threading.Thread(target=_complete_write, daemon=True)
    thread.start()
    payload, error = _load_json_with_retry(state_path, attempts=10, sleep_seconds=0.1)
    thread.join(timeout=1.0)

    assert error is None
    assert payload["phase"] == "waiting_export"
    assert payload["refresh_called"] is True


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RDC_REAL_SMOKE", "0") != "1",
    reason="Real RDC GUI smoke is opt-in (set RDC_REAL_SMOKE=1)",
)
def test_real_rdc_gui_snapshot_smoke_runs(tmp_path):
    capture = os.environ.get("RDC_REAL_SMOKE_CAPTURE", "").strip()
    if not capture:
        pytest.skip("RDC_REAL_SMOKE_CAPTURE not set")

    qrenderdoc = os.environ.get("RDC_REAL_SMOKE_QRENDERDOC", "").strip()
    run_query = os.environ.get("RDC_REAL_SMOKE_RUN_QUERY", "").strip()
    snapshot_consume = os.environ.get("RDC_REAL_SMOKE_SNAPSHOT_CONSUME", "").strip()
    out_dir = os.environ.get("RDC_REAL_SMOKE_OUT_DIR", "").strip()

    from rdc_analyzer.tools.real_rdc_gui_snapshot_smoke import run_smoke

    result = run_smoke(
        capture=capture,
        out_dir=out_dir or str(tmp_path / "real_rdc_smoke"),
        qrenderdoc=qrenderdoc or str(Path(__file__).resolve().parents[4] / "renderdoc-agentb-r3" / "x64" / "Development" / "qrenderdoc.exe"),
        run_query=run_query or str(Path(__file__).resolve().parents[4] / "renderdoc-agenta-r3" / "scripts" / "rdc_analyzer" / "mcp_examples" / "run_query.py"),
        snapshot_consume=snapshot_consume or str(Path(__file__).resolve().parents[4] / "renderdoc-agenta-r3" / "scripts" / "rdc_analyzer" / "mcp_examples" / "snapshot_consume.py"),
        python_exe=os.environ.get("RDC_REAL_SMOKE_PYTHON", "").strip() or os.sys.executable,
        launch_timeout=int(os.environ.get("RDC_REAL_SMOKE_LAUNCH_TIMEOUT", "600")),
        query_timeout=int(os.environ.get("RDC_REAL_SMOKE_QUERY_TIMEOUT", "120")),
        consume_timeout=int(os.environ.get("RDC_REAL_SMOKE_CONSUME_TIMEOUT", "180")),
    )

    assert result.get("success") is True, result
    assert Path(result["exports"]["snapshot_v1_json"]).is_file()
    assert result["consumer"]["json"]["enrichment"]["status"] == "executed"
