import os
import subprocess
import sys


def test_cli_requires_args():
    test_dir = os.path.dirname(__file__)
    script_path = os.path.abspath(os.path.join(test_dir, "..", "export_unity_assets.py"))
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "usage" in (result.stderr or "").lower()
