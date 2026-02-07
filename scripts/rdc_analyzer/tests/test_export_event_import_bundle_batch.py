import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_sample_intermediate_event(root: Path, event_id: int):
    event_root = root / f"event_{event_id}"
    intermediate = event_root / "intermediate"
    mesh_dir = intermediate / "mesh"
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

    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps(
            {
                "material": {
                    "name": "mat0",
                    "shader": "ps",
                    "textures": [],
                    "constants": [],
                }
            }
        ),
        encoding="utf-8",
    )

    (intermediate / "textures").mkdir(parents=True, exist_ok=True)

    shaders_dir = intermediate / "shaders"
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

    event_root.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "api": "Vulkan",
                "sources": {
                    "zip_xml": "capture.zip.xml",
                    "zip_bin": "capture.zip",
                },
            }
        ),
        encoding="utf-8",
    )


def test_discover_event_ids(tmp_path):
    from export_event_import_bundle_batch import discover_event_ids

    _write_sample_intermediate_event(tmp_path, 100)
    (tmp_path / "event_not_number").mkdir()
    (tmp_path / "event_200").mkdir()

    assert discover_event_ids(tmp_path) == [100]


def test_run_batch_success_and_missing(tmp_path):
    from export_event_import_bundle_batch import run_batch

    _write_sample_intermediate_event(tmp_path, 100)

    out_dir = tmp_path / "out"
    summary = run_batch(
        intermediate_root=tmp_path,
        out_root=out_dir,
        event_ids=[100, 101],
        fail_fast=False,
    )

    assert summary["events_total"] == 2
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 1

    status_by_event = {item["event_id"]: item["status"] for item in summary["results"]}
    assert status_by_event[100] == "ok"
    assert status_by_event[101] == "missing_intermediate"

    assert (out_dir / "event_100" / "import_bundle" / "bundle_manifest.json").exists()


def test_main_auto_discover_and_summary_file(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 111)
    out_dir = tmp_path / "out"

    rc = main(["--root", str(tmp_path), "--out", str(out_dir)])
    assert rc == 0

    summary_path = out_dir / "batch_import_bundle_summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["events_total"] == 1
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 0


def test_main_with_explicit_events(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 201)
    _write_sample_intermediate_event(tmp_path, 202)

    out_dir = tmp_path / "out"
    rc = main(["--root", str(tmp_path), "--out", str(out_dir), "--events", "202"])

    assert rc == 0
    assert (out_dir / "event_202" / "import_bundle" / "bundle_manifest.json").exists()
    assert not (out_dir / "event_201" / "import_bundle" / "bundle_manifest.json").exists()


def test_main_returns_nonzero_on_failure(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 301)

    out_dir = tmp_path / "out"
    rc = main(["--root", str(tmp_path), "--out", str(out_dir), "--events", "301,999"])
    assert rc == 2
