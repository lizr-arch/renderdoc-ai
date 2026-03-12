#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tile-Based analyzer tests."""

from rdc_analyzer.config import get_thresholds
from rdc_analyzer.core.context import AnalysisContext
from rdc_analyzer.core.types import ParsedData, PassInfo
from rdc_analyzer.rules import RuleRunner, register_all_rules


def _make_context(draws, passes=None):
    parsed = ParsedData(api="Vulkan", file_path="fake.rdc", draws=draws)
    context = AnalysisContext(
        parsed=parsed,
        platform="mobile",
        thresholds=get_thresholds("mobile"),
    )
    context.frame_summary.viewport_width = 100
    context.frame_summary.viewport_height = 100
    if passes is not None:
        context.passes = passes
    return context


def test_tile_based_overdraw_rule_triggers():
    draws = [
        {
            "event_id": 1,
            "state": {"blend_enabled": True},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
        {
            "event_id": 2,
            "state": {"blend_enabled": True},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
        {
            "event_id": 3,
            "state": {"blend_enabled": True},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
    ]
    context = _make_context(draws)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_001"])
    issues = runner.run()

    assert any(issue.code == "TILE_001" for issue in issues)


def test_tile_based_memory_rule_triggers():
    draws = [
        {
            "event_id": 10,
            "state": {"blend_enabled": False},
            "render_targets": ["rt0", "rt1", "rt2", "rt3", "rt4", "rt5", "rt6", "rt7"],
            "sample_count": 8,
            "depth_target": True,
        },
    ]
    context = _make_context(draws)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_002"])
    issues = runner.run()

    assert any(issue.code == "TILE_002" for issue in issues)


def test_tile_based_load_store_rule_triggers():
    draws = [
        {
            "event_id": 1,
            "state": {"blend_enabled": False},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
    ]
    passes = [
        PassInfo(
            index=1,
            name="Pass_1",
            draw_count=1,
            color_attachments=[{
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
                "loadOp": "VK_ATTACHMENT_LOAD_OP_LOAD",
                "storeOp": "VK_ATTACHMENT_STORE_OP_STORE",
            }],
            sample_count=1,
        )
    ]
    context = _make_context(draws, passes=passes)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_003"])
    issues = runner.run()

    assert any(issue.code == "TILE_003" for issue in issues)


def test_tile_based_msaa_resolve_rule_triggers():
    draws = [
        {
            "event_id": 2,
            "state": {"blend_enabled": False},
            "render_targets": ["rt0"],
            "sample_count": 4,
        },
    ]
    passes = [
        PassInfo(
            index=1,
            name="Pass_1",
            draw_count=1,
            color_attachments=[{
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
                "loadOp": "VK_ATTACHMENT_LOAD_OP_CLEAR",
                "storeOp": "VK_ATTACHMENT_STORE_OP_STORE",
                "sampleCount": 4,
            }],
            sample_count=4,
            has_resolve=False,
        )
    ]
    context = _make_context(draws, passes=passes)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_004"])
    issues = runner.run()

    assert any(issue.code == "TILE_004" for issue in issues)


def test_tile_based_transient_rule_triggers():
    draws = [
        {
            "event_id": 3,
            "state": {"blend_enabled": False},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
    ]
    passes = [
        PassInfo(
            index=1,
            name="Pass_1",
            draw_count=1,
            color_attachments=[{
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
                "loadOp": "VK_ATTACHMENT_LOAD_OP_CLEAR",
                "storeOp": "VK_ATTACHMENT_STORE_OP_DONT_CARE",
            }],
            depth_attachment={
                "format": "VK_FORMAT_D24_UNORM_S8_UINT",
                "loadOp": "VK_ATTACHMENT_LOAD_OP_CLEAR",
                "storeOp": "VK_ATTACHMENT_STORE_OP_STORE",
                "flags": "",
            },
            sample_count=1,
            has_transient_attachment=False,
        )
    ]
    context = _make_context(draws, passes=passes)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_005"])
    issues = runner.run()

    assert any(issue.code == "TILE_005" for issue in issues)


def test_tile_based_marker_rule_triggers():
    draws = [
        {
            "event_id": 4,
            "state": {"blend_enabled": False},
            "render_targets": ["rt0"],
            "sample_count": 1,
        },
    ]
    passes = [
        PassInfo(
            index=1,
            name="Pass_1",
            draw_count=1,
            marker_name="",
            color_attachments=[{
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
                "loadOp": "VK_ATTACHMENT_LOAD_OP_CLEAR",
                "storeOp": "VK_ATTACHMENT_STORE_OP_STORE",
            }],
            sample_count=1,
        )
    ]
    context = _make_context(draws, passes=passes)

    from rdc_analyzer.analyzers.tile_based_analyzer import TileBasedAnalyzer

    TileBasedAnalyzer(context).analyze()
    register_all_rules()
    runner = RuleRunner(context)
    runner.enable_only(["TILE_006"])
    issues = runner.run()

    assert any(issue.code == "TILE_006" for issue in issues)
