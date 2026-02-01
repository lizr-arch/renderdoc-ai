import pathlib
import subprocess
import sys


SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1]


def _run_cli(args, expect_fail=False):
    cmd = [sys.executable, str(SCRIPT_DIR / "extract_mesh_shader.py"), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if expect_fail:
        assert result.returncode != 0
    else:
        assert result.returncode == 0
    return (result.stdout or "") + (result.stderr or "")


def test_cli_help_outputs_usage():
    output = _run_cli(["--help"])
    assert "extract_mesh_shader" in output
    assert "--rdc" in output
    assert "--event" in output


def test_cli_writes_manifest(tmp_path):
    _run_cli(
        ["--rdc", "x.rdc", "--event", "100", "--out", str(tmp_path)],
        expect_fail=True,
    )
    assert (tmp_path / "manifest.json").exists()
