import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_mesh_intermediate(root: Path) -> Path:
    mesh_dir = root / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    mesh = {
        "mesh": {
            "vertex_layout": [
                {"semantic": "POSITION", "format": "float3", "offset": 0, "stride": 12}
            ],
            "vertex_count": 3,
            "index_format": "uint16",
            "index_count": 3,
        }
    }
    mesh_dir.joinpath("mesh.json").write_text(
        json.dumps(mesh), encoding="utf-8"
    )

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    vertex_bytes = b"".join(struct.pack("<fff", *v) for v in vertices)
    mesh_dir.joinpath("vertex.bin").write_bytes(vertex_bytes)
    mesh_dir.joinpath("index.bin").write_bytes(b"\x00\x00\x01\x00\x02\x00")
    return mesh_dir


def test_write_obj_outputs_files(tmp_path):
    try:
        from converters.obj_writer import write_obj
    except ImportError as exc:
        pytest.fail(f"obj_writer missing: {exc}")

    intermediate = tmp_path / "intermediate"
    _write_mesh_intermediate(intermediate)
    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps({"material": {"textures": []}}), encoding="utf-8"
    )

    out_dir = write_obj(str(intermediate), str(tmp_path), event_id=1)
    obj_path = out_dir / "mesh.obj"
    mtl_path = out_dir / "mesh.mtl"
    assert obj_path.exists()
    assert mtl_path.exists()

    obj_text = obj_path.read_text(encoding="utf-8")
    assert "v 0.0 0.0 0.0" in obj_text
    assert "f 1 2 3" in obj_text
