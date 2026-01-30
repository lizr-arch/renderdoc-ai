import subprocess
import sys


def test_cli_requires_args():
    result = subprocess.run(
        [sys.executable, "scripts/rdc_analyzer/export_unity_assets.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "usage" in (result.stderr or "").lower()
