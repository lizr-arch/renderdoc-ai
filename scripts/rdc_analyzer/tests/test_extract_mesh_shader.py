import pathlib
import sys

import pytest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_extract_mesh_shader_requires_event():
    from extract_mesh_shader import extract_mesh_shader

    with pytest.raises(ValueError):
        extract_mesh_shader(rdc_path="x.rdc", event_id=None, out_dir="out")
