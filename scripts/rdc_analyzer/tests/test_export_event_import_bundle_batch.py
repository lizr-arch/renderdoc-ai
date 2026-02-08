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
        texture_mode="raw",
        raw_source_kinds={"vulkan_device_memory_raw"},
    )

    assert summary["events_total"] == 2
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["schema_path"] == "schema/batch_import_bundle_summary.schema.json"
    assert summary["failed_event_ids"] == [101]
    assert summary["retry_events_arg"] == "101"
    assert "--events \"101\"" in summary["retry_command"]
    assert "--texture-mode \"raw\"" in summary["retry_command"]
    assert "--raw-source-kinds \"vulkan_device_memory_raw\"" in summary["retry_command"]

    assert summary["options"]["texture_mode"] == "raw"
    assert summary["options"]["raw_source_kinds"] == ["vulkan_device_memory_raw"]
    assert summary["texture_status_totals"]["total"] == 0

    status_by_event = {item["event_id"]: item["status"] for item in summary["results"]}
    assert status_by_event[100] == "ok"
    assert status_by_event[101] == "missing_intermediate"

    ok_result = [item for item in summary["results"] if item["event_id"] == 100][0]
    assert ok_result["statistics"]["vertex_count"] == 3
    assert ok_result["texture_status_counts"]["total"] == 0

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
    assert summary["schema_path"] == "schema/batch_import_bundle_summary.schema.json"
    assert summary["failed_event_ids"] == []


def test_main_with_explicit_events(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 201)
    _write_sample_intermediate_event(tmp_path, 202)

    out_dir = tmp_path / "out"
    rc = main(["--root", str(tmp_path), "--out", str(out_dir), "--events", "202"])

    assert rc == 0
    assert (out_dir / "event_202" / "import_bundle" / "bundle_manifest.json").exists()
    assert not (out_dir / "event_201" / "import_bundle" / "bundle_manifest.json").exists()


def test_main_events_from_scan_selects_top_textured(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 601)
    _write_sample_intermediate_event(tmp_path, 602)

    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "events": [
                    {"event_id": 601, "texture_count": 2, "index_count": 100, "pipeline": 10},
                    {"event_id": 602, "texture_count": 5, "index_count": 200, "pipeline": 20},
                ]
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out_scan"
    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out",
            str(out_dir),
            "--events-from-scan",
            str(scan_path),
            "--top-textured",
            "1",
            "--min-textures",
            "1",
        ]
    )
    assert rc == 0

    assert (out_dir / "event_602" / "import_bundle" / "bundle_manifest.json").exists()
    assert not (out_dir / "event_601" / "import_bundle" / "bundle_manifest.json").exists()

    summary = json.loads((out_dir / "batch_import_bundle_summary.json").read_text(encoding="utf-8"))
    assert summary["selection"]["top_textured"] == 1
    assert summary["selection"]["selected"][0]["event_id"] == 602


def test_main_returns_nonzero_on_failure_and_writes_retry_files(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 301)

    out_dir = tmp_path / "out"
    rc = main(["--root", str(tmp_path), "--out", str(out_dir), "--events", "301,999"])
    assert rc == 2

    summary = json.loads((out_dir / "batch_import_bundle_summary.json").read_text(encoding="utf-8"))
    assert summary["failed_event_ids"] == [999]
    assert (out_dir / "batch_import_bundle_failed_events.txt").exists()
    assert (out_dir / "batch_import_bundle_retry_command.txt").exists()


def test_main_from_summary_retries_failed_event_ids(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 401)
    _write_sample_intermediate_event(tmp_path, 402)

    previous_summary = tmp_path / "previous_summary.json"
    previous_summary.write_text(
        json.dumps(
            {
                "root": str(tmp_path),
                "out": str(tmp_path / "old_out"),
                "failed_event_ids": [402],
            }
        ),
        encoding="utf-8",
    )

    retry_out = tmp_path / "retry_out"
    rc = main(["--from-summary", str(previous_summary), "--out", str(retry_out)])
    assert rc == 0

    assert (retry_out / "event_402" / "import_bundle" / "bundle_manifest.json").exists()
    assert not (retry_out / "event_401" / "import_bundle" / "bundle_manifest.json").exists()

    new_summary = json.loads((retry_out / "batch_import_bundle_summary.json").read_text(encoding="utf-8"))
    assert new_summary.get("source_summary") == str(previous_summary)


def test_main_from_summary_uses_results_when_failed_list_missing(tmp_path):
    from export_event_import_bundle_batch import main

    _write_sample_intermediate_event(tmp_path, 501)
    _write_sample_intermediate_event(tmp_path, 502)

    previous_summary = tmp_path / "previous_summary_results.json"
    previous_summary.write_text(
        json.dumps(
            {
                "root": str(tmp_path),
                "out": str(tmp_path / "old_out"),
                "results": [
                    {"event_id": 501, "status": "ok"},
                    {"event_id": 502, "status": "error"},
                ],
            }
        ),
        encoding="utf-8",
    )

    retry_out = tmp_path / "retry_out2"
    rc = main(["--from-summary", str(previous_summary), "--out", str(retry_out)])
    assert rc == 0

    assert (retry_out / "event_502" / "import_bundle" / "bundle_manifest.json").exists()
    assert not (retry_out / "event_501" / "import_bundle" / "bundle_manifest.json").exists()


def test_main_from_summary_requires_root_or_summary_root(tmp_path):
    from export_event_import_bundle_batch import main

    bad_summary = tmp_path / "bad_summary.json"
    bad_summary.write_text(json.dumps({"failed_event_ids": [1]}), encoding="utf-8")

    with pytest.raises(ValueError, match="--root is required"):
        main(["--from-summary", str(bad_summary), "--out", str(tmp_path / "out")])
