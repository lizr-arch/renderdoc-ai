#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adreno analyzer tests."""

from rdc_analyzer.config import get_thresholds
from rdc_analyzer.core.context import AnalysisContext
from rdc_analyzer.core.types import ParsedData, TextureInfo, DrawCallInfo


def _make_context():
    parsed = ParsedData(api="Vulkan", file_path="fake.rdc", draws=[])
    return AnalysisContext(
        parsed=parsed,
        platform="mobile",
        thresholds=get_thresholds("mobile"),
    )


def test_adreno_gmem_bandwidth_rule_triggers():
    context = _make_context()
    context.textures = [
        TextureInfo(
            resource_id="rt0",
            name="RT0",
            width=2048,
            height=2048,
            format="R8G8B8A8",
            memory_size=100 * 1024 * 1024,
            is_render_target=True,
        )
    ]

    from rdc_analyzer.analyzers.adreno_analyzer import AdrenoAnalyzer

    issues = AdrenoAnalyzer(context).analyze()
    assert any(issue.code == "ADRENO_001" for issue in issues)


def test_adreno_texture_decompression_rule_triggers():
    context = _make_context()
    context.textures = [
        TextureInfo(
            resource_id=f"tex{i}",
            name=f"Tex{i}",
            width=1024,
            height=1024,
            format="R8G8B8A8",
            memory_size=2 * 1024 * 1024,
            is_render_target=False,
        )
        for i in range(6)
    ]

    from rdc_analyzer.analyzers.adreno_analyzer import AdrenoAnalyzer

    issues = AdrenoAnalyzer(context).analyze()
    assert any(issue.code == "ADRENO_002" for issue in issues)


def test_adreno_shader_alu_rule_triggers():
    context = _make_context()
    context.draw_calls = [
        DrawCallInfo(event_id=1, vertex_count=200000, index_count=0, instance_count=1),
        DrawCallInfo(event_id=2, vertex_count=150000, index_count=0, instance_count=1),
    ]

    from rdc_analyzer.analyzers.adreno_analyzer import AdrenoAnalyzer

    issues = AdrenoAnalyzer(context).analyze()
    assert any(issue.code == "ADRENO_003" for issue in issues)
