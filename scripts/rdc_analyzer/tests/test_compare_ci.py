#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI verdict synthesis tests for compare_rdc."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from compare_rdc import build_ci_verdict, run_comparison
from diff import RegressionRuleId


RULE_THRESHOLDS = {
    RegressionRuleId.REG001: 10.0,
    RegressionRuleId.REG002: 50.0,
    RegressionRuleId.REG003: 0.0,
    RegressionRuleId.REG004: 30.0,
    RegressionRuleId.REG005: 20.0,
    RegressionRuleId.REG006: 0.0,
    RegressionRuleId.REG007: 0.0,
}


def _make_capture(*, draw_calls: int, triangles: int, texture_memory_mb: int, buffer_memory_mb: int) -> dict:
    return {
        "apiType": "D3D12",
        "statistics": {
            "totalDrawCalls": draw_calls,
            "dispatchCalls": 0,
            "totalTriangles": triangles,
            "totalVertices": triangles * 3,
            "textureCount": 1,
            "bufferCount": 1,
            "shaderCount": 1,
        },
        "events": [
            {
                "eventId": index + 1,
                "name": "DrawIndexed",
                "indexCount": 300,
                "instanceCount": 1,
            }
            for index in range(draw_calls)
        ],
        "textures": [
            {
                "resourceId": "tex-main",
                "name": "Color",
                "width": 1024,
                "height": 1024,
                "format": "RGBA8",
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
        "shaders": [{"resourceId": "vs-main", "name": "MainVS", "type": "VS", "hash": "hash-vs"}],
    }


def _attach_snapshot_context(capture: dict, actions: int) -> dict:
    return {
        **capture,
        "_source_schema": "snapshot.v1",
        "_snapshot_counts": {
            "actions": actions,
            "draw_calls": actions,
            "dispatch_calls": 0,
            "triangles": int(capture["statistics"]["totalTriangles"]),
            "vertices": int(capture["statistics"]["totalVertices"]),
            "textures": 1,
            "buffers": 1,
            "shaders": 1,
            "passes": 1,
            "pipelines": 1,
            "findings": 0,
            "recommendations": 0,
        },
        "_snapshot_availability": {"status": "partial", "missing_fields": []},
    }


def _run_ci(baseline: dict, target: dict):
    custom_thresholds = {
        RegressionRuleId.REG001: 10.0,
        RegressionRuleId.REG004: 30.0,
        RegressionRuleId.REG005: 20.0,
    }
    diff_result, regression_report = run_comparison(
        baseline,
        target,
        "baseline.json",
        "target.json",
        custom_thresholds=custom_thresholds,
    )
    verdict = build_ci_verdict(
        diff_result=diff_result,
        regression_report=regression_report,
        baseline_data=_attach_snapshot_context(baseline, int(baseline["statistics"]["totalDrawCalls"])),
        target_data=_attach_snapshot_context(target, int(target["statistics"]["totalDrawCalls"])),
        rule_thresholds=RULE_THRESHOLDS,
        texture_mem_threshold=0.3,
        buffer_mem_threshold=0.3,
    )
    return diff_result, regression_report, verdict


def test_warning_scenario_returns_1():
    baseline = _make_capture(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)
    target = _make_capture(draw_calls=12, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)

    _, regression_report, verdict = _run_ci(baseline, target)

    assert verdict.exit_code == 1
    assert verdict.status == "warning"
    assert verdict.failing_checks == ["draw_calls"]
    assert regression_report.results


def test_critical_scenario_returns_2_and_fills_results():
    baseline = _make_capture(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)
    target = _make_capture(draw_calls=12, triangles=15000, texture_memory_mb=84, buffer_memory_mb=8)

    _, regression_report, verdict = _run_ci(baseline, target)

    assert verdict.exit_code == 2
    assert verdict.status == "critical"
    assert verdict.failing_checks == ["draw_calls", "triangles", "texture_memory"]
    assert regression_report.results
    metric_names = [result.metric_name for result in regression_report.results]
    assert "draw_calls" in metric_names
    assert "triangles" in metric_names
    assert "texture_memory" in metric_names


def test_clean_scenario_returns_0():
    baseline = _make_capture(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)
    target = _make_capture(draw_calls=10, triangles=12000, texture_memory_mb=64, buffer_memory_mb=8)

    _, regression_report, verdict = _run_ci(baseline, target)

    assert verdict.exit_code == 0
    assert verdict.status == "pass"
    assert verdict.failing_checks == []
    assert regression_report.results == []
