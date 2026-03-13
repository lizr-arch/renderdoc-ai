#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snapshot.v1 compare adapter tests."""

from copy import deepcopy

from rdc_analyzer.parsers.snapshot_compare_adapter import (
    is_snapshot_v1_payload,
    snapshot_to_capture_data,
)


def _make_snapshot() -> dict:
    return {
        "schema_version": "snapshot.v1",
        "meta": {
            "capture_name": "capture",
            "graphics_api": "Vulkan",
            "generated_at": "2026-03-13T16:00:00",
        },
        "overview": {
            "summary": {
                "draw_call_count": 1,
                "dispatch_count": 1,
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
            "status": "partial",
            "missing_fields": ["timings.gpu_ms", "pipelines.viewport"],
        },
        "actions": [
            {
                "event_id": 1,
                "kind": "draw",
                "name": "DrawIndexed",
                "index_count": 300,
                "vertex_count": 0,
                "instance_count": 2,
                "marker_path": ["Frame", "Opaque"],
                "pipeline_ref": "pipe-main",
            },
            {
                "event_id": 2,
                "kind": "dispatch",
                "name": "Dispatch",
                "marker_path": "Frame/Compute",
            },
        ],
        "resources": {
            "textures": [
                {
                    "resource_id": "tex-main",
                    "name": "Color",
                    "width": 1024,
                    "height": 1024,
                    "depth": 1,
                    "array_size": 1,
                    "mip_count": 1,
                    "format": "R8G8B8A8_UNORM",
                    "usage_tags": ["sampled", "render_target"],
                }
            ],
            "buffers": [
                {
                    "resource_id": "buf-main",
                    "name": "VB",
                    "size_bytes": 4096,
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
                "encoding": "dxil",
                "source_high_level": "void main(){}",
            },
            {
                "shader_id": "ps-main",
                "name": "MainPS",
                "stage": "pixel",
                "entry_point": "main",
                "encoding": "dxil",
                "source_asm": "ret",
            },
        ],
        "passes": [{"pass_id": "opaque"}],
        "pipelines": [
            {
                "pipeline_id": "pipe-main",
                "event_id": 1,
                "vs_ref": {"shader_id": "vs-main"},
                "ps_ref": {"shader_id": "ps-main"},
                "blend": {"attachments": [{"enabled": True}]},
                "depth_stencil": {"depthEnable": False},
            }
        ],
        "findings": [{"id": "finding-1"}],
        "recommendations": [{"id": "rec-1"}],
    }


def test_is_snapshot_v1_payload():
    assert is_snapshot_v1_payload({"schema_version": "snapshot.v1"}) is True
    assert is_snapshot_v1_payload({"schema_version": "1.0"}) is False


def test_snapshot_v1_maps_to_capture_data():
    capture = snapshot_to_capture_data(_make_snapshot())

    assert capture["_source_schema"] == "snapshot.v1"
    assert capture["statistics"]["totalDrawCalls"] == 1
    assert capture["statistics"]["dispatchCalls"] == 1
    assert capture["statistics"]["totalTriangles"] == 200
    assert capture["statistics"]["totalVertices"] == 600
    assert capture["statistics"]["textureCount"] == 1
    assert capture["_snapshot_counts"]["findings"] == 1
    assert capture["_snapshot_availability"]["status"] == "partial"
    assert capture["_snapshot_availability"]["missing_fields"] == [
        "timings.gpu_ms",
        "pipelines.viewport",
    ]

    draw_event = capture["events"][0]
    assert draw_event["eventId"] == 1
    assert draw_event["markerPath"] == "Frame/Opaque"
    assert draw_event["pipelineState"]["shaders"]["VS"]["resourceId"] == "vs-main"
    assert draw_event["pipelineState"]["outputMerger"]["blendState"]["renderTargets"][0]["blendEnable"] is True
    assert draw_event["pipelineState"]["depthStencil"]["depthTestEnable"] is False

    texture = capture["textures"][0]
    assert texture["resourceId"] == "tex-main"
    assert texture["usage"] == ["sampled", "render_target"]
    assert texture["memorySize"] == 1024 * 1024 * 4

    shader = capture["shaders"][0]
    assert shader["resourceId"] == "vs-main"
    assert len(shader["hash"]) == 40


def test_alias_fields_are_supported():
    snapshot = _make_snapshot()
    alias_snapshot = deepcopy(snapshot)
    alias_snapshot["meta"] = {
        "capture_name": "capture",
        "driver": "D3D11",
    }
    alias_snapshot["actions"][0] = {
        "event_id": 1,
        "type": "draw",
        "name": "DrawIndexed",
        "indices": 120,
        "instances": 3,
        "marker": "Frame/Opaque",
        "pipeline_id": "pipe-main",
    }
    alias_snapshot["resources"]["textures"][0] = {
        "id": "tex-alias",
        "name": "AliasTex",
        "width": 512,
        "height": 512,
        "format": "R8G8B8A8_UNORM",
        "usage": ["sampled"],
    }
    alias_snapshot["resources"]["buffers"][0] = {
        "id": "buf-alias",
        "name": "AliasBuf",
        "length": 2048,
        "usage": "index",
    }
    alias_snapshot["shaders"][0] = {
        "id": "vs-alias",
        "name": "AliasVS",
        "stage": "vs",
        "entry_point": "main",
        "source_code": "void main(){}",
    }

    capture = snapshot_to_capture_data(alias_snapshot)

    assert capture["apiType"] == "D3D11"
    assert capture["events"][0]["markerPath"] == "Frame/Opaque"
    assert capture["events"][0]["indexCount"] == 120
    assert capture["events"][0]["instanceCount"] == 3
    assert capture["textures"][0]["resourceId"] == "tex-alias"
    assert capture["textures"][0]["usage"] == ["sampled"]
    assert capture["buffers"][0]["resourceId"] == "buf-alias"
    assert capture["buffers"][0]["size"] == 2048
    assert capture["shaders"][0]["resourceId"] == "vs-alias"
    assert len(capture["shaders"][0]["hash"]) == 40
