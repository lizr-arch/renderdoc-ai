import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_resolve_fbx_backend_prefers_python_binding(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.setitem(sys.modules, "fbx", object())
    assert resolve_fbx_backend() == "python"


def test_resolve_fbx_backend_none_when_missing(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.delitem(sys.modules, "fbx", raising=False)
    assert resolve_fbx_backend() in {"cli", "none"}


def _write_mesh_intermediate(root: Path) -> None:
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


def test_cli_creates_stats(tmp_path, monkeypatch):
    try:
        from export_fbx_assets import main
    except ImportError as exc:
        pytest.fail(f"export_fbx_assets missing: {exc}")

    intermediate = tmp_path / "intermediate"
    _write_mesh_intermediate(intermediate)
    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps({"material": {"textures": []}}), encoding="utf-8"
    )

    monkeypatch.setenv("RDC_FBX_ALLOW_MISSING", "1")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert main(
        [
            "--intermediate",
            str(intermediate),
            "--out",
            str(out_dir),
            "--event",
            "1",
        ]
    ) == 0
    stats_path = out_dir / "event_1" / "stats.json"
    assert stats_path.exists()
