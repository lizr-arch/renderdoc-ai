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
    assert summary["options"]["skip_mesh_incompatible"] is False
    assert summary["texture_status_totals"]["total"] == 0
    assert summary["skipped_count"] == 0
    assert summary["skipped_event_ids"] == []

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
    assert summary["selection"]["scan_rank"] == "mesh_likely"
    assert summary["selection"]["selected"][0]["event_id"] == 602
    assert summary["options"]["scan_rank"] == "mesh_likely"


def test_select_events_from_scan_ranking_modes(tmp_path):
    from export_event_import_bundle_batch import _select_events_from_scan

    scan_path = tmp_path / "scan_rank.json"
    scan_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": 900,
                        "texture_count": 9,
                        "index_count": 12,
                        "vertex_offset": 9,
                        "first_index": 12000,
                        "pipeline": 1,
                        "shader_stages": ["vs", "ps"],
                    },
                    {
                        "event_id": 901,
                        "texture_count": 6,
                        "index_count": 12,
                        "vertex_offset": 0,
                        "first_index": 0,
                        "pipeline": 1,
                        "shader_stages": ["vs", "ps"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    mesh_ids, mesh_rows = _select_events_from_scan(
        scan_path=scan_path,
        top_textured=0,
        min_textures=1,
        scan_rank="mesh_likely",
    )
    assert mesh_ids[:2] == [901, 900]
    assert mesh_rows[0]["mesh_likely_score"] > mesh_rows[1]["mesh_likely_score"]

    texture_ids, _ = _select_events_from_scan(
        scan_path=scan_path,
        top_textured=0,
        min_textures=1,
        scan_rank="texture_count",
    )
    assert texture_ids[:2] == [900, 901]




def test_select_events_from_scan_preserves_mesh_flags(tmp_path):
    from export_event_import_bundle_batch import _select_events_from_scan

    scan_path = tmp_path / "scan_mesh_flags.json"
    scan_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": 910,
                        "texture_count": 3,
                        "index_count": 8,
                        "pipeline": 11,
                        "has_vertex_binding": True,
                        "has_index_binding": True,
                        "mesh_compatible": True,
                    },
                    {
                        "event_id": 911,
                        "texture_count": 2,
                        "index_count": 6,
                        "pipeline": 12,
                        "has_vertex_binding": False,
                        "has_index_binding": True,
                        "mesh_compatible": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    _, rows = _select_events_from_scan(
        scan_path=scan_path,
        top_textured=0,
        min_textures=1,
        scan_rank="mesh_likely",
    )

    assert rows[0]["event_id"] == 910
    assert rows[0]["has_vertex_binding"] is True
    assert rows[0]["has_index_binding"] is True
    assert rows[0]["mesh_compatible"] is True

    assert rows[1]["event_id"] == 911
    assert rows[1]["has_vertex_binding"] is False
    assert rows[1]["has_index_binding"] is True
    assert rows[1]["mesh_compatible"] is False


def test_run_batch_from_capture_uses_capture_retry_command(tmp_path, monkeypatch):
    import export_event_import_bundle_batch as batch_mod

    capture_xml = tmp_path / "sample.zip.xml"
    capture_zip = tmp_path / "sample.zip"
    capture_xml.write_text("<rdc></rdc>", encoding="utf-8")
    capture_zip.write_bytes(b"PK")

    def _raise_extract(**kwargs):
        raise RuntimeError("extract failed")

    monkeypatch.setattr(batch_mod, "_extract_then_export", _raise_extract)

    summary = batch_mod.run_batch_from_capture(
        capture_xml=capture_xml,
        capture_zip=capture_zip,
        out_root=tmp_path / "out",
        event_ids=[777],
        vertex_stride=16,
        texture_mode="raw",
        raw_source_kinds={"vulkan_device_memory_raw"},
    )

    assert summary["failed_count"] == 1
    assert summary["failed_event_ids"] == [777]
    assert summary["skipped_count"] == 0
    assert summary["skipped_event_ids"] == []
    assert summary["inputs"]["mode"] == "capture_zip"
    assert "--xml" in summary["retry_command"]
    assert "--zip" in summary["retry_command"]
    assert "--vertex-stride 16" in summary["retry_command"]
    assert "--texture-mode \"raw\"" in summary["retry_command"]


def test_run_batch_from_capture_skips_mesh_incompatible_by_default(tmp_path, monkeypatch):
    import export_event_import_bundle_batch as batch_mod

    capture_xml = tmp_path / "sample_skip.zip.xml"
    capture_zip = tmp_path / "sample_skip.zip"
    capture_xml.write_text("<rdc></rdc>", encoding="utf-8")
    capture_zip.write_bytes(b"PK")

    def _raise_mesh_incompatible(**kwargs):
        raise ValueError("mesh.json missing vertex_layout/vertex_count/index_count")

    monkeypatch.setattr(batch_mod, "_extract_then_export", _raise_mesh_incompatible)

    summary = batch_mod.run_batch_from_capture(
        capture_xml=capture_xml,
        capture_zip=capture_zip,
        out_root=tmp_path / "out_skip",
        event_ids=[888],
    )

    assert summary["failed_count"] == 0
    assert summary["failed_event_ids"] == []
    assert summary["skipped_count"] == 1
    assert summary["skipped_event_ids"] == [888]
    assert summary["results"][0]["status"] == "skipped_mesh_incompatible"
    assert summary["results"][0]["skip_reason"] == "mesh_layout_incomplete"


def test_run_batch_from_capture_strict_mesh_treats_incompatible_as_error(tmp_path, monkeypatch):
    import export_event_import_bundle_batch as batch_mod

    capture_xml = tmp_path / "sample_strict.zip.xml"
    capture_zip = tmp_path / "sample_strict.zip"
    capture_xml.write_text("<rdc></rdc>", encoding="utf-8")
    capture_zip.write_bytes(b"PK")

    def _raise_mesh_incompatible(**kwargs):
        raise ValueError("vertex_layout missing POSITION")

    monkeypatch.setattr(batch_mod, "_extract_then_export", _raise_mesh_incompatible)

    summary = batch_mod.run_batch_from_capture(
        capture_xml=capture_xml,
        capture_zip=capture_zip,
        out_root=tmp_path / "out_strict",
        event_ids=[889],
        skip_mesh_incompatible=False,
    )

    assert summary["failed_count"] == 1
    assert summary["failed_event_ids"] == [889]
    assert summary["skipped_count"] == 0
    assert summary["skipped_event_ids"] == []
    assert summary["results"][0]["status"] == "error"




def test_build_skip_diagnostics_includes_scan_hints():
    import export_event_import_bundle_batch as batch_mod

    summary = {
        "results": [
            {
                "event_id": 911,
                "status": "skipped_mesh_incompatible",
                "error": "event 911 has no vertex buffer binding",
                "skip_reason": "missing_vertex_buffer_binding",
            }
        ]
    }
    selection = {
        "selected": [
            {
                "event_id": 911,
                "texture_count": 4,
                "index_count": 20,
                "mesh_hint": "incompatible",
                "mesh_likely_score": 3,
                "has_vertex_binding": False,
                "has_index_binding": True,
                "mesh_compatible": False,
                "mesh_incompatible_reasons": ["missing_vertex_binding"],
            }
        ]
    }

    diagnostics = batch_mod._build_skip_diagnostics(summary, selection=selection)
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag["event_id"] == 911
    assert diag["reason_code"] == "missing_vertex_buffer_binding"
    assert diag["scan_hints"]["has_vertex_binding"] is False
    assert diag["scan_hints"]["mesh_incompatible_reasons"] == ["missing_vertex_binding"]


def test_build_skip_report_markdown_groups_by_reason_code():
    import export_event_import_bundle_batch as batch_mod

    report = batch_mod._build_skip_report_markdown(
        [
            {"event_id": 100, "reason_code": "mesh_layout_incomplete", "status": "skipped_mesh_incompatible", "error": "x"},
            {"event_id": 101, "reason_code": "mesh_layout_incomplete", "status": "skipped_mesh_incompatible", "error": "y"},
            {"event_id": 102, "reason_code": "missing_vertex_buffer_binding", "status": "skipped_mesh_incompatible", "error": "z"},
        ]
    )

    assert "mesh_layout_incomplete: 2 event(s)" in report
    assert "missing_vertex_buffer_binding: 1 event(s)" in report
    assert "events: 100, 101" in report



def test_main_capture_mode_writes_skip_diagnostics(tmp_path, monkeypatch):
    import export_event_import_bundle_batch as batch_mod

    capture_xml = tmp_path / "capture_skip.zip.xml"
    capture_zip = tmp_path / "capture_skip.zip"
    capture_xml.write_text("<rdc></rdc>", encoding="utf-8")
    capture_zip.write_bytes(b"PK")

    scan_path = tmp_path / "scan_capture_skip.json"
    scan_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": 710,
                        "texture_count": 3,
                        "index_count": 10,
                        "pipeline": 1,
                        "has_vertex_binding": False,
                        "has_index_binding": True,
                        "mesh_compatible": False,
                        "mesh_exportable": False,
                        "mesh_incompatible_reasons": ["missing_vertex_binding"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def _fake_run_batch_from_capture(**kwargs):
        return {
            "schema_version": "1.0",
            "schema_path": "schema/batch_import_bundle_summary.schema.json",
            "root": str(kwargs["capture_xml"].parent),
            "out": str(kwargs["out_root"]),
            "events_total": 1,
            "success_count": 0,
            "failed_count": 0,
            "failed_event_ids": [],
            "skipped_count": 1,
            "skipped_event_ids": [710],
            "retry_events_arg": "",
            "retry_command": "",
            "inputs": {
                "mode": "capture_zip",
                "xml": str(kwargs["capture_xml"]),
                "zip": str(kwargs["capture_zip"]),
                "vertex_stride": int(kwargs.get("vertex_stride", 0)),
            },
            "options": {
                "texture_mode": str(kwargs.get("texture_mode") or "auto"),
                "raw_source_kinds": sorted(kwargs.get("raw_source_kinds") or set()),
                "skip_mesh_incompatible": bool(kwargs.get("skip_mesh_incompatible", True)),
            },
            "texture_status_totals": {
                "decoded_rgba8_png": 0,
                "rgba_bytes_png": 0,
                "copied_image": 0,
                "raw_copy": 0,
                "missing_source": 0,
                "other": 0,
                "total": 0,
            },
            "results": [
                {
                    "event_id": 710,
                    "status": "skipped_mesh_incompatible",
                    "bundle_dir": "",
                    "error": "event 710 has no vertex buffer binding",
                    "skip_reason": "missing_vertex_buffer_binding",
                }
            ],
        }

    monkeypatch.setattr(batch_mod, "run_batch_from_capture", _fake_run_batch_from_capture)

    out_dir = tmp_path / "out_capture_skip"
    rc = batch_mod.main(
        [
            "--xml",
            str(capture_xml),
            "--zip",
            str(capture_zip),
            "--out",
            str(out_dir),
            "--events-from-scan",
            str(scan_path),
            "--top-textured",
            "1",
        ]
    )
    assert rc == 0

    summary = json.loads((out_dir / "batch_import_bundle_summary.json").read_text(encoding="utf-8"))
    assert summary["skip_diagnostics"][0]["event_id"] == 710
    assert summary["skip_diagnostics"][0]["reason_code"] == "missing_vertex_buffer_binding"
    assert summary["skip_diagnostics"][0]["scan_hints"]["has_vertex_binding"] is False
    assert summary["skip_files"]["skip_diagnostics"]
    assert summary["skip_files"]["skip_report"]

    skip_diag_path = Path(summary["skip_files"]["skip_diagnostics"])
    assert skip_diag_path.exists()
    skip_payload = json.loads(skip_diag_path.read_text(encoding="utf-8"))
    assert skip_payload[0]["event_id"] == 710

    skip_report_path = Path(summary["skip_files"]["skip_report"])
    assert skip_report_path.exists()
    skip_report_text = skip_report_path.read_text(encoding="utf-8")
    assert "missing_vertex_buffer_binding" in skip_report_text

def test_main_capture_mode_from_scan_invokes_capture_runner(tmp_path, monkeypatch):
    import export_event_import_bundle_batch as batch_mod

    capture_xml = tmp_path / "capture.zip.xml"
    capture_zip = tmp_path / "capture.zip"
    capture_xml.write_text("<rdc></rdc>", encoding="utf-8")
    capture_zip.write_bytes(b"PK")

    scan_path = tmp_path / "scan_capture.json"
    scan_path.write_text(
        json.dumps(
            {
                "events": [
                    {"event_id": 700, "texture_count": 1, "index_count": 10, "pipeline": 1},
                    {"event_id": 701, "texture_count": 4, "index_count": 20, "pipeline": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    captured = {}

    def _fake_run_batch_from_capture(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": "1.0",
            "schema_path": "schema/batch_import_bundle_summary.schema.json",
            "root": str(kwargs["capture_xml"].parent),
            "out": str(kwargs["out_root"]),
            "events_total": len(kwargs["event_ids"]),
            "success_count": len(kwargs["event_ids"]),
            "failed_count": 0,
            "failed_event_ids": [],
            "skipped_count": 0,
            "skipped_event_ids": [],
            "retry_events_arg": "",
            "retry_command": "",
            "inputs": {
                "mode": "capture_zip",
                "xml": str(kwargs["capture_xml"]),
                "zip": str(kwargs["capture_zip"]),
                "vertex_stride": int(kwargs.get("vertex_stride", 0)),
            },
            "options": {
                "texture_mode": str(kwargs.get("texture_mode") or "auto"),
                "raw_source_kinds": sorted(kwargs.get("raw_source_kinds") or set()),
                "skip_mesh_incompatible": bool(kwargs.get("skip_mesh_incompatible", True)),
            },
            "texture_status_totals": {
                "decoded_rgba8_png": 0,
                "rgba_bytes_png": 0,
                "copied_image": 0,
                "raw_copy": 0,
                "missing_source": 0,
                "other": 0,
                "total": 0,
            },
            "results": [],
        }

    monkeypatch.setattr(batch_mod, "run_batch_from_capture", _fake_run_batch_from_capture)

    out_dir = tmp_path / "out_capture"
    rc = batch_mod.main(
        [
            "--xml",
            str(capture_xml),
            "--zip",
            str(capture_zip),
            "--out",
            str(out_dir),
            "--events-from-scan",
            str(scan_path),
            "--top-textured",
            "1",
            "--raw-source-kinds",
            "vulkan_device_memory_raw",
        ]
    )
    assert rc == 0

    assert captured["event_ids"] == [701]
    assert captured["capture_xml"] == capture_xml
    assert captured["capture_zip"] == capture_zip
    assert captured["skip_mesh_incompatible"] is True

    summary = json.loads((out_dir / "batch_import_bundle_summary.json").read_text(encoding="utf-8"))
    assert summary["selection"]["scan_rank"] == "mesh_likely"
    assert summary["selection"]["selected"][0]["event_id"] == 701
    assert summary["options"]["scan_rank"] == "mesh_likely"
    assert summary["inputs"]["mode"] == "capture_zip"


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
