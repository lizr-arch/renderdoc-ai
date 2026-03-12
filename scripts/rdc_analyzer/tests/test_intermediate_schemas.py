import json
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_intermediate_schema_files_exist():
    schema_dir = SCRIPT_DIR / "schema"
    assert (schema_dir / "intermediate_mesh.schema.json").exists()
    assert (schema_dir / "intermediate_material.schema.json").exists()
    assert (schema_dir / "intermediate_shader.schema.json").exists()
    assert (schema_dir / "intermediate_manifest.schema.json").exists()


def test_validate_mesh_schema_minimal(tmp_path):
    from extract_event_intermediate import validate_json_file

    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/intermediate_mesh.schema.json",
        "mesh": {
            "axis": "unknown",
            "unit_scale": 1.0,
            "topology": "triangle_list",
            "vertex_layout": [],
            "index_format": "uint16",
            "vertex_count": 0,
            "index_count": 0,
        },
    }
    json_path = tmp_path / "mesh.json"
    _write_json(json_path, payload)

    validate_json_file(json_path, SCRIPT_DIR / "schema" / "intermediate_mesh.schema.json")


def test_validate_material_schema_minimal(tmp_path):
    from extract_event_intermediate import validate_json_file

    payload = {
        "material": {
            "name": "",
            "shader": "",
            "textures": [],
            "constants": [],
        }
    }
    json_path = tmp_path / "material.json"
    _write_json(json_path, payload)

    validate_json_file(json_path, SCRIPT_DIR / "schema" / "intermediate_material.schema.json")


def test_validate_shader_schema_minimal(tmp_path):
    from extract_event_intermediate import validate_json_file

    payload = {
        "shader": {
            "stage": "vs",
            "bytecode_format": "spirv",
            "entry": "main",
            "disassembly": "",
        }
    }
    json_path = tmp_path / "vs.json"
    _write_json(json_path, payload)

    validate_json_file(json_path, SCRIPT_DIR / "schema" / "intermediate_shader.schema.json")


def test_validate_manifest_schema_minimal(tmp_path):
    from extract_event_intermediate import validate_json_file

    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/intermediate_manifest.schema.json",
        "event_id": 100,
        "api": "Vulkan",
        "sources": {
            "zip_xml": "sample.zip.xml",
            "zip_bin": "sample.zip",
        },
        "buffers": {
            "index": {
                "resource_id": 1,
                "memory_id": 2,
                "memory_offset": 3,
                "zip_entry": "000001",
                "byte_offset": 4,
                "byte_size": 6,
            },
            "vertex": {
                "resource_id": 7,
                "memory_id": 8,
                "memory_offset": 9,
                "zip_entry": "000002",
                "byte_offset": 10,
                "byte_size": 12,
                "layout_source": "heuristic",
            },
        },
        "texture_decode": [],
    }

    json_path = tmp_path / "manifest.json"
    _write_json(json_path, payload)

    validate_json_file(json_path, SCRIPT_DIR / "schema" / "intermediate_manifest.schema.json")


def test_validate_manifest_schema_rejects_missing_field(tmp_path):
    from extract_event_intermediate import validate_json_file

    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/intermediate_manifest.schema.json",
        "event_id": 100,
        "api": "Vulkan",
        "sources": {
            "zip_xml": "sample.zip.xml",
            "zip_bin": "sample.zip",
        },
        "texture_decode": [],
    }

    json_path = tmp_path / "manifest_bad.json"
    _write_json(json_path, payload)

    with pytest.raises(ValueError, match="missing required field buffers"):
        validate_json_file(json_path, SCRIPT_DIR / "schema" / "intermediate_manifest.schema.json")
