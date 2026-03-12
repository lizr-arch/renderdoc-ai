import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(EXPORTERS_DIR))


def test_repository_layout(tmp_path):
    try:
        from messiah_exporter import write_repo_skeleton
    except ImportError as exc:
        pytest.fail(f"messiah_exporter missing: {exc}")

    root = write_repo_skeleton(tmp_path, event_id=100)
    assert (root / "resource.repository").exists()
    assert "rdc_event_100.local" in str(root)


def test_cli_minimal_visible_export(tmp_path):
    try:
        from export_messiah_assets import main
    except ImportError as exc:
        pytest.fail(f"export_messiah_assets missing: {exc}")

    try:
        from engine_guid import hash_guid
    except ImportError as exc:
        pytest.fail(f"engine_guid missing: {exc}")

    intermediate = tmp_path / "intermediate"
    mesh_dir = intermediate / "mesh"
    material_dir = intermediate / "materials"
    texture_dir = intermediate / "textures"
    shader_dir = intermediate / "shaders"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    material_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)
    shader_dir.mkdir(parents=True, exist_ok=True)

    mesh_dir.joinpath("mesh.json").write_text(
        '{"mesh": {"vertex_count": 3, "index_count": 3, "index_format": "uint16"}}',
        encoding="utf-8",
    )
    mesh_dir.joinpath("vertex.bin").write_bytes(b"\x00" * 72)
    mesh_dir.joinpath("index.bin").write_bytes(b"\x00\x00\x01\x00\x02\x00")

    material_dir.joinpath("material.json").write_text(
        '{"material": {"textures": [{"texture_id": 0, "path": "tex_0.bin", "width": 1, "height": 1, "format": "RGBA8"}]}}',
        encoding="utf-8",
    )
    texture_dir.joinpath("tex_0.bin").write_bytes(b"\x01\x02\x03\x04")
    shader_dir.joinpath("ps.json").write_text(
        '{"shader": {"stage": "ps"}}', encoding="utf-8"
    )

    out_dir = tmp_path / "out"
    main(
        [
            "--intermediate",
            str(intermediate),
            "--out",
            str(out_dir),
            "--event",
            "100",
        ]
    )

    repo_root = (
        out_dir / "messiah" / "Package" / "Repository" / "rdc_event_100.local"
    )
    assert (repo_root / "resource.repository").exists()

    mesh_guid = hash_guid("Mesh", 100, "mesh")
    material_guid = hash_guid("Material", 100, "material")
    model_guid = hash_guid("Model", 100, "model")
    model_path = repo_root / "Model" / model_guid[:2] / model_guid / "resource.xml"
    model_xml = model_path.read_text(encoding="utf-8")
    assert f"{{{mesh_guid}}}" in model_xml
    assert f"{{{material_guid}}}" in model_xml
