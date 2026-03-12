import os
import subprocess


def test_outputs_present(tmp_path):
    rdc = os.environ.get("RDC_SAMPLE_PATH")
    event = os.environ.get("RDC_SAMPLE_EVENT")
    if not rdc or not event:
        return
    out_dir = tmp_path / "out"
    subprocess.call(
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
        ]
    )
    assert (out_dir / "mesh").exists()
    assert (out_dir / "textures").exists()
    assert (out_dir / "shaders").exists()
