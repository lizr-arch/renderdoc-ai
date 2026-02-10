import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_mesh_intermediate(root: Path):
    mesh_dir = root / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    mesh_payload = {
        "schema_version": "1.0",
        "schema_path": "schema/intermediate_mesh.schema.json",
        "mesh": {
            "axis": "unknown",
            "unit_scale": 1.0,
            "topology": "triangle_list",
            "vertex_layout": [
                {"semantic": "POSITION", "format": "float3", "offset": 0, "stride": 12}
            ],
            "vertex_count": 3,
            "index_format": "uint16",
            "index_count": 3
        },
    }
    mesh_dir.joinpath("mesh.json").write_text(json.dumps(mesh_payload), encoding="utf-8")

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    vertex_bytes = b"".join(struct.pack("<fff", *v) for v in vertices)
    mesh_dir.joinpath("vertex.bin").write_bytes(vertex_bytes)
    mesh_dir.joinpath("index.bin").write_bytes(b"\x00\x00\x01\x00\x02\x00")


def _write_minimal_intermediate(intermediate: Path):
    _write_mesh_intermediate(intermediate)

    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps({"material": {"name": "mat0", "shader": "ps", "textures": []}}),
        encoding="utf-8",
    )

    # Keep textures/shaders dirs empty to match exporter tests (shader_import_plan.shader_count == 0)
    (intermediate / "textures").mkdir(parents=True, exist_ok=True)
    (intermediate / "shaders").mkdir(parents=True, exist_ok=True)


def test_orchestrator_generates_artifact_index(tmp_path, monkeypatch):
    monkeypatch.setenv("RDC_FBX_ALLOW_MISSING", "1")

    try:
        from event_asset_orchestrator import orchestrate_event_assets
    except ImportError as exc:
        pytest.fail(f"event_asset_orchestrator missing: {exc}")

    event_id = 100
    event_root = tmp_path / f"event_{event_id}"
    intermediate = event_root / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    _write_minimal_intermediate(intermediate)

    # Source manifest used for api/sources fallback
    (event_root / "manifest.json").write_text(
        json.dumps(
            {
                "api": "Vulkan",
                "sources": {"zip_xml": "capture.zip.xml", "zip_bin": "capture.zip"},
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    artifact_index_path = orchestrate_event_assets(
        out_dir=str(out_dir),
        intermediate_dir=str(intermediate),
        event_id=event_id,
        allow_missing_fbx_backend=True,
    )

    assert artifact_index_path == out_dir / f"event_{event_id}" / "artifact_index.json"
    assert artifact_index_path.exists()

    payload = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["schema_path"].endswith("schema/artifact_index.schema.json")
    assert payload["event_id"] == event_id
    assert payload["api"] == "Vulkan"

    assert payload["stages"][0]["name"] == "extract_intermediate"
    assert payload["stages"][0]["status"] == "reused"

    # Even if FBX backend is missing, we should degrade and still produce index.
    fbx_stage = [s for s in payload["stages"] if s["name"] == "export_fbx_assets"][0]
    assert fbx_stage["status"] in {"ok", "degraded_missing_fbx_backend"}

    # Validate key artifact references exist (bundle files created by import bundle step)
    event_out = out_dir / f"event_{event_id}"
    assert (event_out / "import_bundle" / "bundle_manifest.json").exists()
    assert (event_out / "import_bundle" / "materials" / "materials.json").exists()
    assert (event_out / "import_bundle" / "mesh" / "mesh.obj").exists()

    # shader plans should exist even if shader count is 0
    assert (event_out / "fbx" / "unity" / "shader_import_plan.json").exists()
    assert (event_out / "fbx" / "unreal" / "shader_import_plan.json").exists()


def test_orchestrator_xml_zip_branch_with_mock_extract(tmp_path, monkeypatch):
    import event_asset_orchestrator as orchestrator

    monkeypatch.setenv("RDC_FBX_ALLOW_MISSING", "1")

    xml_path = tmp_path / "capture_export.zip.xml"
    zip_path = tmp_path / "capture_export.zip"
    xml_path.write_text("<capture />", encoding="utf-8")
    zip_path.write_bytes(b"PK")

    def _fake_extract_event_intermediate(xml_path, zip_path, event_id, out_dir, vertex_stride=0):
        event_root = Path(out_dir) / f"event_{int(event_id)}"
        intermediate = event_root / "intermediate"
        intermediate.mkdir(parents=True, exist_ok=True)
        _write_minimal_intermediate(intermediate)

        (event_root / "manifest.json").write_text(
            json.dumps(
                {
                    "api": "D3D11",
                    "sources": {"zip_xml": str(xml_path), "zip_bin": str(zip_path)},
                }
            ),
            encoding="utf-8",
        )
        return intermediate

    monkeypatch.setattr(orchestrator, "extract_event_intermediate", _fake_extract_event_intermediate)

    out_dir = tmp_path / "out"
    artifact_index_path = orchestrator.orchestrate_event_assets(
        out_dir=str(out_dir),
        event_id=7,
        xml_path=str(xml_path),
        zip_path=str(zip_path),
        allow_missing_fbx_backend=True,
    )

    payload = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    assert payload["event_id"] == 7
    assert payload["api"] == "D3D11"
    assert payload["stages"][0]["name"] == "extract_intermediate"
    assert payload["stages"][0]["status"] == "ok"


def test_orchestrator_schema_file_exists():
    from event_asset_orchestrator import _ARTIFACT_SCHEMA_PATH

    assert _ARTIFACT_SCHEMA_PATH.name == "artifact_index.schema.json"
    assert _ARTIFACT_SCHEMA_PATH.exists()
