#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMLToContextBridge 集成测试脚本
================================

使用真实 XML 数据测试 Bridge 功能。

TASK-007 集成测试
Created: 2026-01-19
"""

import sys
from pathlib import Path

import pytest

# 项目根目录
_project_root = Path(__file__).parent.parent

# 使用包内绝对导入，避免相对导入越界问题
from rdc_analyzer.parse_rdc_xml import parse_rdc_xml
from rdc_analyzer.core.bridge import XMLToContextBridge
from rdc_analyzer.core.context import AnalysisContext


def test_real_xml_file():
    """使用真实 XML 文件测试"""
    xml_file = _project_root / "g145_capture.xml"
    
    if not xml_file.exists():
        pytest.skip(f"Test file not found: {xml_file}")
    
    print(f"[INFO] Testing with: {xml_file}")
    
    # 解析 XML
    xml_data = parse_rdc_xml(str(xml_file))
    
    print(f"[INFO] XML keys: {list(xml_data.keys())}")
    print(f"[INFO] API Type: {xml_data.get('apiType', 'Unknown')}")
    print(f"[INFO] Events count: {len(xml_data.get('events', []))}")
    print(f"[INFO] Textures count: {len(xml_data.get('textures', []))}")
    print(f"[INFO] Buffers count: {len(xml_data.get('buffers', []))}")
    
    # 转换为 AnalysisContext
    context = XMLToContextBridge.convert(xml_data, str(xml_file))
    
    # 验证基本结构
    assert isinstance(context, AnalysisContext), "Should return AnalysisContext"
    
    print("\n--- Conversion Results ---")
    print(f"  API: {context.api}")
    print(f"  File Path: {context.file_path}")
    print(f"  Draw Calls: {len(context.draw_calls)}")
    print(f"  Textures: {len(context.textures)}")
    print(f"  Buffers: {len(context.buffers)}")
    
    # 帧摘要
    summary = context.frame_summary
    print(f"\n--- Frame Summary ---")
    print(f"  Draw Call Count: {summary.draw_call_count}")
    print(f"  Dispatch Count: {summary.dispatch_count}")
    print(f"  Vertex Count: {summary.vertex_count}")
    print(f"  Primitive Count: {summary.primitive_count}")
    print(f"  Texture Count: {summary.texture_count}")
    print(f"  Buffer Count: {summary.buffer_count}")
    print(f"  Shader Changes: {summary.shader_changes}")
    print(f"  RT Switches: {summary.rt_switches}")
    
    # 验证 ParsedData 保留
    assert context.parsed is not None, "ParsedData should be preserved"
    print(f"\n--- ParsedData ---")
    print(f"  API: {context.parsed.api}")
    print(f"  Total Events: {context.parsed.total_events}")
    print(f"  Draws: {len(context.parsed.draws)}")
    print(f"  Dispatches: {len(context.parsed.dispatches)}")
    
    # 如果有 Draw Call，检查第一个的结构
    if context.draw_calls:
        dc = context.draw_calls[0]
        print(f"\n--- First Draw Call ---")
        print(f"  Event ID: {dc.event_id}")
        print(f"  Type: {dc.type}")
        print(f"  Index Count: {dc.index_count}")
        print(f"  Vertex Count: {dc.vertex_count}")
        print(f"  Instance Count: {dc.instance_count}")
        print(f"  VS ID: {dc.vs_id}")
        print(f"  PS ID: {dc.ps_id}")
        print(f"  RT IDs: {dc.rt_ids}")
        print(f"  DS ID: {dc.ds_id}")
        print(f"  Blend Enabled: {dc.blend_enabled}")
        print(f"  Depth Test: {dc.depth_test}")
        print(f"  Depth Write: {dc.depth_write}")
    
    # 如果有纹理，检查第一个
    if context.textures:
        tex = context.textures[0]
        print(f"\n--- First Texture ---")
        print(f"  Resource ID: {tex.resource_id}")
        print(f"  Name: {tex.name}")
        print(f"  Dimensions: {tex.width}x{tex.height}x{tex.depth}")
        print(f"  Format: {tex.format}")
        print(f"  Format Category: {tex.format_category}")
        print(f"  Mip Levels: {tex.mip_levels}")
        print(f"  Memory Size: {tex.memory_size:,} bytes")
    
    print("\n[PASS] test_real_xml_file")
    # Test passed - no return value needed


def test_with_analyzer():
    """测试与 PerformanceAnalyzer 的集成"""
    xml_file = _project_root / "g145_capture.xml"
    
    if not xml_file.exists():
        pytest.skip(f"Test file not found: {xml_file}")
    
    try:
        from rdc_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
    except ImportError as e:
        pytest.skip(f"Cannot import PerformanceAnalyzer: {e}")
    
    # 解析和转换
    xml_data = parse_rdc_xml(str(xml_file))
    context = XMLToContextBridge.convert(xml_data, str(xml_file))
    
    # 创建分析器并运行
    analyzer = PerformanceAnalyzer(context)
    analyzer.analyze()
    
    # 检查性能报告
    report = context.performance_report
    print(f"\n--- Performance Report ---")
    print(f"  Issues: {len(report.issues)}")
    print(f"  Warnings: {report.warning_count}")
    print(f"  Suggestions: {len(report.recommendations)}")
    
    if report.issues:
        print(f"\n  Sample Issues:")
        for issue in report.issues[:3]:
            print(f"    - {issue}")
    
    print("\n[PASS] test_with_analyzer")
    # Test passed - no return value needed


def run_all():
    """运行所有集成测试"""
    print("=" * 60)
    print("XMLToContextBridge Integration Tests")
    print("=" * 60)
    
    tests = [
        test_real_xml_file,
        test_with_analyzer,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Integration Tests: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)
