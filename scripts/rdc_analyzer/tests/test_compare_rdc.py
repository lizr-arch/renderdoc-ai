#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_rdc.py CLI and JSON output tests."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from compare_rdc import (
    build_ci_verdict,
    export_html_report,
    export_json_diff,
    load_json_data,
    main,
    run_comparison,
)
from diff import RegressionRuleId


def _write_json(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


def _make_capture_data(
    *,
    draw_calls: int,
    triangles: int,
    texture_memory_mb: int,
    buffer_memory_mb: int,
    shader_suffix: str = "main",
) -> dict:
    events = [
        {
            "eventId": index + 1,
            "name": "DrawIndexed",
            "indexCount": 300,
            "vertexCount": 0,
            "instanceCount": 1,
            "markerPath": "Frame/Opaque",
            "pipelineState": {
                "shaders": {
                    "VS": {"resourceId": f"vs-{shader_suffix}"},
                    "PS": {"resourceId": f"ps-{shader_suffix}"},
                }
            },
        }
        for index in range(draw_calls)
    ]
    return {
        "apiType": "D3D12",
        "statistics": {
            "totalDrawCalls": draw_calls,
            "dispatchCalls": 0,
            "totalTriangles": triangles,
            "totalVertices": triangles * 3,
            "textureCount": 1,
            "bufferCount": 1,
            "shaderCount": 2,
        },
        "events": events,
        "textures": [
            {
                "resourceId": "tex-main",
                "name": "Color",
                "width": 4096,
                "height": 4096,
                "format": "R8G8B8A8_UNORM",
                "memorySize": texture_memory_mb * 1024 * 1024,
            }
        ],
        "buffers": [
            {
                "resourceId": "buf-main",
                "name": "VB",
                "size": buffer_memory_mb * 1024 * 1024,
                "usage": "vertex",
            }
        ],
        "shaders": [
            {"resourceId": f"vs-{shader_suffix}", "name": "MainVS", "type": "VS", "hash": f"hash-vs-{shader_suffix}"},
            {"resourceId": f"ps-{shader_suffix}", "name": "MainPS", "type": "PS", "hash": f"hash-ps-{shader_suffix}"},
        ],
    }


def _make_snapshot(
    *,
    draw_calls: int,
    triangles: int,
    texture_memory_mb: int,
    buffer_memory_mb: int,
    availability_status: str = "partial",
) -> dict:
    actions = [
        {
            "event_id": index + 1,
            "kind": "draw",
            "name": "DrawIndexed",
            "index_count": 300,
            "vertex_count": 0,
            "instance_count": 1,
            "marker_path": ["Frame", "Opaque"],
            "pipeline_ref": "pipe-main",
        }
        for index in range(draw_calls)
    ]
    return {
        "schema_version": "snapshot.v1",
        "meta": {
            "capture_name": "capture",
            "graphics_api": "D3D12",
            "generated_at": "2026-03-13T16:00:00",
        },
        "overview": {
            "summary": {
                "draw_call_count": draw_calls,
                "dispatch_count": 0,
                "total_triangles": triangles,
                "total_vertices": triangles * 3,
                "texture_count": 1,
                "buffer_count": 1,
                "shader_count": 2,
                "pass_count": 1,
                "pipeline_count": 1,
                "finding_count": 1,
                "recommendation_count": 1,
            }
        },
        "availability": {
            "status": availability_status,
            "missing_fields": ["timings.gpu_ms"] if availability_status == "partial" else [],
        },
        "actions": actions,
        "resources": {
            "textures": [
                {
                    "resource_id": "tex-main",
                    "name": "Color",
                    "width": 4096,
                    "height": 4096,
                    "format": "R8G8B8A8_UNORM",
                    "size_bytes": texture_memory_mb * 1024 * 1024,
                    "usage_tags": ["sampled"],
                }
            ],
            "buffers": [
                {
                    "resource_id": "buf-main",
                    "name": "VB",
                    "size_bytes": buffer_memory_mb * 1024 * 1024,
                    "usage": "vertex",
                }
            ],
        },
        "shaders": [
            {
                "shader_id": "vs-main",
                "name": "MainVS",
                "stage": "vertex",
                "entry_point": "main",
                "source_high_level": "void main(){}",
            },
            {
                "shader_id": "ps-main",
                "name": "MainPS",
                "stage": "pixel",
                "entry_point": "main",
                "source_high_level": "float4 main():SV_Target{return 1;}",
            },
        ],
        "passes": [{"pass_id": "opaque"}],
        "pipelines": [
            {
                "pipeline_id": "pipe-main",
                "event_id": 1,
                "vs_ref": {"shader_id": "vs-main"},
                "ps_ref": {"shader_id": "ps-main"},
                "blend": {"attachments": [{"enabled": False}]},
                "depth_stencil": {"depthEnable": True},
            }
        ],
        "findings": [{"id": "finding-1"}],
        "recommendations": [{"id": "rec-1"}],
    }


def _make_canonical_v1(draw_calls: int = 1, triangles: int = 300) -> dict:
    return {
        "schema_version": "1.0",
        "meta": {"capture_name": "canonical"},
        "summary": {
            "draw_call_count": draw_calls,
            "total_triangles": triangles,
            "total_vertices": triangles * 3,
        },
        "events": [
            {
                "eventId": index + 1,
                "name": "DrawIndexed",
                "indexCount": 300,
                "vertexCount": 0,
                "instanceCount": 1,
            }
            for index in range(draw_calls)
        ],
        "resources": {
            "textures": {
                "tex-main": {
                    "name": "Color",
                    "width": 1024,
                    "height": 1024,
                    "format": "RGBA8",
                    "size_bytes": 4 * 1024 * 1024,
                    "mips": 1,
                }
            },
            "buffers": {
                "buf-main": {
                    "name": "VB",
                    "size_bytes": 1024,
                    "usage": "vertex",
                }
            },
            "shaders": {
                "vs-main": {
                    "name": "MainVS",
                    "type": "VS",
                    "hash": "hash-vs",
                }
            },
        },
    }


@pytest.fixture
def snapshot_baseline_file(tmp_path) -> str:
    return _write_json(
        tmp_path / "baseline.snapshot.json",
        _make_snapshot(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
    )


@pytest.fixture
def snapshot_target_file(tmp_path) -> str:
    return _write_json(
        tmp_path / "target.snapshot.json",
        _make_snapshot(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8),
    )


class TestLoadJsonData:
    def test_load_valid_json(self, snapshot_baseline_file):
        data = load_json_data(snapshot_baseline_file)
        assert data["schema_version"] == "snapshot.v1"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_json_data("missing.json")

    def test_invalid_json(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{ invalid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_json_data(str(bad_path))

    def test_phase1_list_rejected(self, tmp_path):
        list_path = tmp_path / "phase1.json"
        list_path.write_text(json.dumps([{"x": 1}]), encoding="utf-8")
        with pytest.raises(ValueError):
            load_json_data(str(list_path))


class TestRunComparison:
    def test_basic_capturedata_comparison(self):
        diff_result, regression_report = run_comparison(
            _make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
            _make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8),
            "baseline.json",
            "target.json",
        )

        assert diff_result.baseline_file == "baseline.json"
        assert diff_result.target_file == "target.json"
        assert diff_result.summary.draw_calls.delta == 2
        assert diff_result.summary.triangles.delta == 3000
        assert regression_report.has_critical

    def test_custom_threshold(self):
        diff_result, regression_report = run_comparison(
            _make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
            _make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8),
            "baseline.json",
            "target.json",
            custom_thresholds={
                RegressionRuleId.REG001: 50.0,
                RegressionRuleId.REG005: 50.0,
            },
        )

        assert diff_result.summary.draw_calls.delta_percent == 20.0
        assert not regression_report.has_critical
        assert not regression_report.has_warning


class TestExport:
    def test_export_html(self, tmp_path):
        diff_result, regression_report = run_comparison(
            _make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
            _make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8),
            "baseline.json",
            "target.json",
        )
        output_path = tmp_path / "report.html"
        export_html_report(diff_result, regression_report, str(output_path))
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "baseline.json" in content

    def test_export_json_contains_ci_and_snapshot_sections(self, tmp_path):
        baseline_data = _make_snapshot(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)
        target_data = _make_snapshot(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8)
        diff_result, regression_report = run_comparison(
            baseline_data=_make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
            target_data=_make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8),
            baseline_name="baseline.json",
            target_name="target.json",
            custom_thresholds={
                RegressionRuleId.REG001: 10.0,
                RegressionRuleId.REG004: 30.0,
                RegressionRuleId.REG005: 20.0,
            },
        )
        ci_verdict = build_ci_verdict(
            diff_result=diff_result,
            regression_report=regression_report,
            baseline_data={"_source_schema": "snapshot.v1", **_make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8), "_snapshot_counts": {"actions": 10}, "_snapshot_availability": {"status": "partial", "missing_fields": ["timings.gpu_ms"]}},
            target_data={"_source_schema": "snapshot.v1", **_make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8), "_snapshot_counts": {"actions": 12}, "_snapshot_availability": {"status": "partial", "missing_fields": ["timings.gpu_ms"]}},
            rule_thresholds={
                RegressionRuleId.REG001: 10.0,
                RegressionRuleId.REG002: 50.0,
                RegressionRuleId.REG003: 0.0,
                RegressionRuleId.REG004: 30.0,
                RegressionRuleId.REG005: 20.0,
                RegressionRuleId.REG006: 0.0,
                RegressionRuleId.REG007: 0.0,
            },
            texture_mem_threshold=0.3,
            buffer_mem_threshold=0.3,
        )
        output_path = tmp_path / "diff.json"
        export_json_diff(
            diff_result,
            regression_report,
            str(output_path),
            baseline_data={"_source_schema": "snapshot.v1", **_make_capture_data(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8), "_snapshot_counts": {"actions": 10}, "_snapshot_availability": {"status": "partial", "missing_fields": ["timings.gpu_ms"]}},
            target_data={"_source_schema": "snapshot.v1", **_make_capture_data(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8), "_snapshot_counts": {"actions": 12}, "_snapshot_availability": {"status": "partial", "missing_fields": ["timings.gpu_ms"]}},
            ci_verdict=ci_verdict,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["input"]["baseline_kind"] == "snapshot.v1"
        assert payload["ci"]["status"] == "critical"
        assert payload["ci"]["exit_code"] == 2
        assert payload["ci"]["failing_checks"] == ["draw_calls", "triangles", "texture_memory"]
        assert "snapshot_summary" in payload


class TestCLI:
    def test_help(self):
        with patch.object(sys, "argv", ["compare_rdc.py", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_version(self):
        with patch.object(sys, "argv", ["compare_rdc.py", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_quiet_requires_output(self, snapshot_baseline_file, snapshot_target_file):
        with patch.object(sys, "argv", ["compare_rdc.py", snapshot_baseline_file, snapshot_target_file, "-q"]):
            assert main() == 3

    def test_snapshot_json_output_and_exit_code(self, snapshot_baseline_file, snapshot_target_file, tmp_path):
        output_json = tmp_path / "diff.json"
        with patch.object(
            sys,
            "argv",
            [
                "compare_rdc.py",
                snapshot_baseline_file,
                snapshot_target_file,
                "--json",
                str(output_json),
                "-q",
            ],
        ):
            result = main()

        assert result == 2
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert payload["input"]["baseline_kind"] == "snapshot.v1"
        assert payload["input"]["target_kind"] == "snapshot.v1"
        assert payload["input"]["compat_mode"] == "snapshot_aliases"
        assert payload["snapshot_summary"]["counts"]["actions"]["baseline"] == 10
        assert payload["snapshot_summary"]["counts"]["actions"]["target"] == 12
        assert payload["ci"]["status"] == "critical"
        assert payload["ci"]["exit_code"] == 2
        assert payload["ci"]["failing_checks"] == ["draw_calls", "triangles", "texture_memory"]

    def test_texture_threshold_affects_ci_verdict(self, tmp_path):
        baseline_file = _write_json(
            tmp_path / "baseline.texture.json",
            _make_snapshot(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8),
        )
        target_file = _write_json(
            tmp_path / "target.texture.json",
            _make_snapshot(draw_calls=10, triangles=12000, texture_memory_mb=90, buffer_memory_mb=8),
        )

        with patch.object(
            sys,
            "argv",
            ["compare_rdc.py", baseline_file, target_file, "--json", str(tmp_path / "warn.json"), "-q"],
        ):
            warning_result = main()

        with patch.object(
            sys,
            "argv",
            [
                "compare_rdc.py",
                baseline_file,
                target_file,
                "--json",
                str(tmp_path / "pass.json"),
                "--texture-mem-threshold",
                "0.5",
                "-q",
            ],
        ):
            pass_result = main()

        assert warning_result == 1
        assert pass_result == 0

    def test_legacy_canonical_json_still_supported(self, tmp_path):
        baseline_file = _write_json(tmp_path / "baseline.canonical.json", _make_canonical_v1())
        target_file = _write_json(tmp_path / "target.canonical.json", _make_canonical_v1())

        with patch.object(
            sys,
            "argv",
            ["compare_rdc.py", baseline_file, target_file, "--json", str(tmp_path / "canonical.diff.json"), "-q"],
        ):
            result = main()

        assert result == 0
        payload = json.loads((tmp_path / "canonical.diff.json").read_text(encoding="utf-8"))
        assert payload["input"]["baseline_kind"] == "canonical.v1"
        assert payload["ci"]["status"] == "pass"
