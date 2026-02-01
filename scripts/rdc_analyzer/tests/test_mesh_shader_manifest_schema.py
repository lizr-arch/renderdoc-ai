import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


SCHEMA_PATH = SCRIPT_DIR / "schema" / "mesh_shader_manifest.schema.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _assert_type(value, expected, path):
    if expected == "object":
        assert isinstance(value, dict), f"{path}: expected object"
        return
    if expected == "array":
        assert isinstance(value, list), f"{path}: expected array"
        return
    if expected == "string":
        assert isinstance(value, str), f"{path}: expected string"
        return
    if expected == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), f"{path}: expected integer"
        return
    if expected == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{path}: expected number"
        return
    if expected == "boolean":
        assert isinstance(value, bool), f"{path}: expected boolean"
        return
    raise AssertionError(f"{path}: unsupported schema type {expected!r}")


def _validate(schema, data, path="root"):
    expected_type = schema.get("type")
    if expected_type:
        _assert_type(data, expected_type, path)

    if "enum" in schema:
        assert data in schema["enum"], f"{path}: value not in enum"

    if expected_type == "object":
        for req in schema.get("required", []):
            assert req in data, f"{path}: missing required field {req}"
        for key, subschema in schema.get("properties", {}).items():
            if key in data:
                _validate(subschema, data[key], f"{path}.{key}")

    if expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(data):
                _validate(item_schema, item, f"{path}[{idx}]")


def test_manifest_schema_required_fields():
    schema = _load_schema()
    assert schema.get("type") == "object"
    assert "required" in schema
    assert "properties" in schema


def test_manifest_schema_accepts_minimal_manifest():
    schema = _load_schema()
    manifest = {
        "schema_version": "1.0",
        "schema_path": "schema/mesh_shader_manifest.schema.json",
        "rdc_path": "capture.rdc",
        "event_id": 100,
        "outputs": {
            "vertex_buffers": "vertex_buffers/",
            "index_buffers": "index_buffers/",
            "shaders": "shaders/",
        },
        "data_provenance": {
            "pipeline_state": "ReplayController.GetPipelineState()",
            "buffers": "ReplayController.GetBufferData(resourceId, offset, len)",
            "shader_disassembly": "ReplayController.DisassembleShader(...)",
        },
        "status": "ok",
    }
    _validate(schema, manifest)
