import os
import subprocess


def test_export_contract(tmp_path):
    rdc = os.environ.get("RDC_SAMPLE_PATH")
    event = os.environ.get("RDC_SAMPLE_EVENT")
    if not rdc or not event:
        return
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            "py",
            "-3",
            "scripts/rdc_analyzer/export_unity_assets.py",
            "--rdc",
            rdc,
            "--event",
            str(event),
            "--api",
            "d3d11",
            "--out",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (out_dir / "manifest.json").exists()
