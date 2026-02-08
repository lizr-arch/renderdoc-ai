import json
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from export_event_import_bundle_batch import _validate_summary_payload  # noqa: E402


def test_batch_summary_schema_exists():
    schema_path = SCRIPT_DIR / "schema" / "batch_import_bundle_summary.schema.json"
    assert schema_path.exists()


def test_batch_summary_schema_validates_minimal():
    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": "D:/root",
        "out": "D:/out",
        "events_total": 2,
        "success_count": 1,
        "failed_count": 1,
        "failed_event_ids": [101],
        "retry_events_arg": "101",
        "retry_command": "py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py --root D:/root --out D:/out --events 101",
        "results": [
            {"event_id": 100, "status": "ok", "bundle_dir": "D:/out/event_100/import_bundle", "error": ""},
            {"event_id": 101, "status": "missing_intermediate", "bundle_dir": "", "error": "missing directory"},
        ],
    }

    _validate_summary_payload(payload)


def test_batch_summary_schema_accepts_extended_fields():
    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": "D:/root",
        "out": "D:/out",
        "events_total": 1,
        "success_count": 1,
        "failed_count": 0,
        "failed_event_ids": [],
        "skipped_count": 1,
        "skipped_event_ids": [100],
        "retry_events_arg": "",
        "retry_command": "",
        "inputs": {
            "mode": "capture_zip",
            "xml": "D:/capture.zip.xml",
            "zip": "D:/capture.zip",
            "vertex_stride": 0,
        },
        "options": {
            "texture_mode": "auto",
            "raw_source_kinds": ["vulkan_device_memory_raw"],
            "skip_mesh_incompatible": True,
        },
        "texture_status_totals": {
            "decoded_rgba8_png": 1,
            "rgba_bytes_png": 0,
            "copied_image": 0,
            "raw_copy": 0,
            "missing_source": 0,
            "other": 0,
            "total": 1,
        },
        "selection": {
            "source": "D:/scan.json",
            "top_textured": 1,
            "min_textures": 1,
            "selected": [
                {"event_id": 100, "texture_count": 3, "index_count": 123, "pipeline": 456},
            ],
        },
        "results": [
            {
                "event_id": 100,
                "status": "ok",
                "bundle_dir": "D:/out/event_100/import_bundle",
                "error": "",
                "statistics": {
                    "vertex_count": 3,
                    "index_count": 3,
                    "triangle_count": 1,
                    "shader_count": 2,
                    "texture_count": 1,
                    "decoded_texture_count": 1,
                },
                "texture_status_counts": {
                    "decoded_rgba8_png": 1,
                    "rgba_bytes_png": 0,
                    "copied_image": 0,
                    "raw_copy": 0,
                    "missing_source": 0,
                    "other": 0,
                    "total": 1,
                },
            },
        ],
    }

    _validate_summary_payload(payload)


def test_batch_summary_schema_rejects_missing_field():
    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": "D:/root",
        # missing required: out
        "events_total": 0,
        "success_count": 0,
        "failed_count": 0,
        "failed_event_ids": [],
        "retry_events_arg": "",
        "retry_command": "",
        "results": [],
    }

    with pytest.raises(ValueError, match="missing required field out"):
        _validate_summary_payload(payload)
