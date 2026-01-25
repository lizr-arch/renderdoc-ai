#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tile-Based analyzer tests."""

from rdc_analyzer.config import get_thresholds
from rdc_analyzer.core.context import AnalysisContext
from rdc_analyzer.core.types import ParsedData
from rdc_analyzer.rules import RuleRunner, register_all_rules


def _make_context(draws):
    parsed = ParsedData(api="Vulkan", file_path="fake.rdc", draws=draws)
    context = AnalysisContext(
        parsed=parsed,
        platform="mobile",
        thresholds=get_thresholds("mobile"),
    )
    context.frame_summary.viewport_width = 100
    context.frame_summary.viewport_height = 100
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
