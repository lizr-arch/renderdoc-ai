import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_sample_intermediate(root: Path, *, texture_format: str = "R8G8B8A8"):
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
    mesh_dir.joinpath("mesh.json").write_text(json.dumps(mesh), encoding="utf-8")

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    vertex_bytes = b"".join(struct.pack("<fff", *v) for v in vertices)
    mesh_dir.joinpath("vertex.bin").write_bytes(vertex_bytes)
    mesh_dir.joinpath("index.bin").write_bytes(b"\x00\x00\x01\x00\x02\x00")

    material_dir = root / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps(
            {
                "material": {
                    "name": "mat0",
                    "shader": "ps",
                    "textures": [
                        {
                            "slot": "albedo",
                            "texture_id": 7,
                            "path": "tex_7.bin",
                            "sampler": "s0",
                            "width": 2,
                            "height": 1,
                            "format": texture_format,
                        }
                    ],
                    "constants": [{"name": "_BaseColor", "type": "float4", "value": [1, 1, 1, 1]}],
                }
            }
        ),
        encoding="utf-8",
    )

    textures_dir = root / "textures"
    textures_dir.mkdir(parents=True, exist_ok=True)
    textures_dir.joinpath("tex_7.bin").write_bytes(
        bytes(
            [
                255,
                0,
                0,
                255,
                0,
                255,
                0,
                255,
            ]
        )
    )

    shaders_dir = root / "shaders"
    shaders_dir.mkdir(parents=True, exist_ok=True)
    shaders_dir.joinpath("vs.json").write_text(
        json.dumps(
            {
                "shader": {
                    "stage": "vs",
                    "bytecode_format": "dxbc",
                    "entry": "main",
                    "disassembly": "dcl_input v0.xyz",
                }
            }
        ),
        encoding="utf-8",
    )
    shaders_dir.joinpath("vs.bin").write_bytes(b"DXBC")


@pytest.mark.parametrize(
    "texture_format,expected_status,expected_suffix",
    [
        ("R8G8B8A8", "decoded_rgba8_png", ".png"),
        ("UNKNOWN_FMT", "raw_copy", ".bin"),
    ],
)
def test_export_event_import_bundle(tmp_path, texture_format, expected_status, expected_suffix):
    try:
        from export_event_import_bundle import export_event_import_bundle
    except ImportError as exc:
        pytest.fail(f"export_event_import_bundle missing: {exc}")

    event_id = 100
    event_root = tmp_path / f"event_{event_id}"
    intermediate = event_root / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)

    _write_sample_intermediate(intermediate, texture_format=texture_format)

    manifest_path = event_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "api": "D3D11",
                "sources": {
                    "zip_xml": "capture.zip.xml",
                    "zip_bin": "capture.zip",
                },
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    bundle_root = export_event_import_bundle(str(intermediate), str(out_dir), event_id=event_id)

    assert bundle_root == out_dir / f"event_{event_id}" / "import_bundle"
    assert (bundle_root / "mesh" / "mesh.obj").exists()
    assert (bundle_root / "mesh" / "mesh.mtl").exists()
    assert (bundle_root / "materials" / "materials.json").exists()
    assert (bundle_root / "shaders" / "vs.json").exists()
    assert (bundle_root / "shaders" / "vs.bin").exists()
    assert (bundle_root / "bundle_manifest.json").exists()

    materials = json.loads((bundle_root / "materials" / "materials.json").read_text(encoding="utf-8"))
    texture_entry = materials["materials"][0]["textures"][0]
    assert texture_entry["status"] == expected_status
    assert texture_entry["output_path"].endswith(expected_suffix)

    output_texture = bundle_root / texture_entry["output_path"]
    assert output_texture.exists()

    bundle_manifest = json.loads((bundle_root / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert bundle_manifest["api"] == "D3D11"
    assert bundle_manifest["statistics"]["vertex_count"] == 3
    assert bundle_manifest["statistics"]["index_count"] == 3
    assert bundle_manifest["statistics"]["texture_count"] == 1



def test_export_event_import_bundle_empty_texture_marks_missing_source(tmp_path):
    from export_event_import_bundle import export_event_import_bundle

    event_id = 101
    event_root = tmp_path / f"event_{event_id}"
    intermediate = event_root / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)

    _write_sample_intermediate(intermediate, texture_format="R8G8B8A8")
    (intermediate / "textures" / "tex_7.bin").write_bytes(b"")

    manifest_path = event_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "api": "Vulkan",
                "sources": {"zip_xml": "capture.zip.xml", "zip_bin": "capture.zip"},
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    bundle_root = export_event_import_bundle(str(intermediate), str(out_dir), event_id=event_id)

    materials = json.loads((bundle_root / "materials" / "materials.json").read_text(encoding="utf-8"))
    texture_entry = materials["materials"][0]["textures"][0]

    assert texture_entry["status"] == "missing_source"
    assert texture_entry["output_path"] == ""
