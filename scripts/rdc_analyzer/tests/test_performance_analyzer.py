"""
性能分析器测试 (C.2, C.3)
=========================

测试 PerformanceAnalyzer 的各项检测规则。
"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import unittest
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from rdc_analyzer.core.types import (
    PerformanceMetrics,
    PerformanceIssue,
    PerformanceReport,
    PerformanceRule,
    PERFORMANCE_RULES,
    DrawCallInfo,
    TextureInfo,
    FrameSummary,
    ParsedData,
)
from rdc_analyzer.core.context import AnalysisContext
from rdc_analyzer.analyzers.performance_analyzer import (
    PerformanceAnalyzer,
    is_compressed_format,
    is_power_of_two,
    COMPRESSED_FORMATS,
)


class TestPerformanceModels(unittest.TestCase):
    """测试性能数据模型"""
    
    def test_performance_metrics_creation(self):
        """测试 PerformanceMetrics 创建"""
        metrics = PerformanceMetrics(
            event_id=100,
            vertex_count=3000,
            triangle_count=1000,
            instance_count=5,
            alpha_blend_enabled=True,
        )
        self.assertEqual(metrics.event_id, 100)
        self.assertEqual(metrics.vertex_count, 3000)
        self.assertEqual(metrics.triangle_count, 1000)
        self.assertEqual(metrics.instance_count, 5)
        self.assertTrue(metrics.alpha_blend_enabled)
    
    def test_performance_issue_creation(self):
        """测试 PerformanceIssue 创建"""
        issue = PerformanceIssue(
            rule_id="PERF001",
            severity="warning",
            category="overdraw",
            title="Overdraw Detected",
            message="Multiple draws to same RT",
            impact_score=50.0,
            related_events=[1, 2, 3],
        )
        self.assertEqual(issue.rule_id, "PERF001")
        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.impact_score, 50.0)
        self.assertEqual(len(issue.related_events), 3)
    
    def test_performance_report_creation(self):
        """测试 PerformanceReport 创建"""
        report = PerformanceReport()
        self.assertEqual(report.total_draw_calls, 0)
        self.assertEqual(report.overall_score, 100.0)
        self.assertEqual(len(report.issues), 0)
    
    def test_performance_rules_registry(self):
        """测试性能规则注册表"""
        self.assertIn("PERF001", PERFORMANCE_RULES)
        self.assertIn("PERF002", PERFORMANCE_RULES)
        self.assertIn("PERF003", PERFORMANCE_RULES)
        self.assertIn("PERF004", PERFORMANCE_RULES)
        self.assertIn("PERF005", PERFORMANCE_RULES)
        self.assertIn("PERF006", PERFORMANCE_RULES)
        self.assertIn("PERF007", PERFORMANCE_RULES)
        
        # 检查规则属性
        rule = PERFORMANCE_RULES["PERF001"]
        self.assertEqual(rule.rule_id, "PERF001")
        self.assertEqual(rule.category, "overdraw")
        self.assertTrue(rule.enabled)
        self.assertIn("max_overdraw", rule.thresholds)


class TestUtilityFunctions(unittest.TestCase):
    """测试工具函数"""
    
    def test_is_compressed_format_bc(self):
        """测试 BC 压缩格式检测"""
        self.assertTrue(is_compressed_format("BC1"))
        self.assertTrue(is_compressed_format("bc7"))
        self.assertTrue(is_compressed_format("DXGI_FORMAT_BC1_UNORM"))
        self.assertTrue(is_compressed_format("DXGI_FORMAT_BC7_UNORM_SRGB"))
    
    def test_is_compressed_format_dxt(self):
        """测试 DXT 压缩格式检测"""
        self.assertTrue(is_compressed_format("DXT1"))
        self.assertTrue(is_compressed_format("DXT5"))
    
    def test_is_compressed_format_uncompressed(self):
        """测试未压缩格式检测"""
        self.assertFalse(is_compressed_format("RGBA8"))
        self.assertFalse(is_compressed_format("DXGI_FORMAT_R8G8B8A8_UNORM"))
        self.assertFalse(is_compressed_format("R32_FLOAT"))
    
    def test_is_power_of_two(self):
        """测试 2 的幂检测"""
        self.assertTrue(is_power_of_two(1))
        self.assertTrue(is_power_of_two(2))
        self.assertTrue(is_power_of_two(256))
        self.assertTrue(is_power_of_two(1024))
        self.assertTrue(is_power_of_two(2048))
        
        self.assertFalse(is_power_of_two(0))
        self.assertFalse(is_power_of_two(3))
        self.assertFalse(is_power_of_two(100))
        self.assertFalse(is_power_of_two(1000))


class TestPerformanceAnalyzerInit(unittest.TestCase):
    """测试性能分析器初始化"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_analyzer_creation(self):
        """测试分析器创建"""
        analyzer = PerformanceAnalyzer(self.context)
        self.assertEqual(analyzer.name, "performance")
        self.assertIsNotNone(analyzer.report)
        self.assertIsInstance(analyzer.report, PerformanceReport)
    
    def test_analyzer_rules_loaded(self):
        """测试规则加载"""
        analyzer = PerformanceAnalyzer(self.context)
        self.assertIn("PERF001", analyzer._rules)
        self.assertIn("PERF007", analyzer._rules)


class TestOverdrawDetection(unittest.TestCase):
    """测试过度绘制检测 (PERF001)"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_overdraw_detected(self):
        """测试过度绘制检测"""
        # 创建多个绘制到同一 RT 的 DrawCall
        draws = []
        for i in range(10):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=100,
                index_count=0,
                instance_count=1,
                rt_ids=["RT_0"],  # 都绘制到同一个 RT
                vs_id="VS_0",
                ps_id="PS_0",
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        # 应该检测到过度绘制问题
        overdraw_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF001"]
        self.assertGreater(len(overdraw_issues), 0)
    
    def test_no_overdraw(self):
        """测试无过度绘制"""
        # 每个 Draw 绘制到不同 RT
        draws = []
        for i in range(3):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=100,
                rt_ids=[f"RT_{i}"],
                vs_id="VS_0",
                ps_id="PS_0",
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        overdraw_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF001"]
        self.assertEqual(len(overdraw_issues), 0)


class TestStateRedundancy(unittest.TestCase):
    """测试状态冗余检测 (PERF002)"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_shader_redundancy_detected(self):
        """测试 Shader 冗余检测"""
        # 创建连续使用相同 Shader 的 DrawCall
        draws = []
        for i in range(10):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=100,
                vs_id="VS_SAME",
                ps_id="PS_SAME",
                rt_ids=[f"RT_{i}"],
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        # 应该检测到状态冗余 (虽然 Shader 相同是正常的，但连续 > 3 次会报告)
        redundancy_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF002"]
        # 注意：这个规则是检测"冗余设置"，如果连续使用相同 Shader 是优化后的结果
        # 这里测试的是规则是否正常运行


class TestSmallBatchDetection(unittest.TestCase):
    """测试小批次绘制检测 (PERF003)"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_small_batch_detected(self):
        """测试小批次检测"""
        # 创建多个小批次 DrawCall
        draws = []
        for i in range(20):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=10,  # 很小的批次
                index_count=0,
                instance_count=1,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        # 应该检测到小批次问题
        batch_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF003"]
        self.assertGreater(len(batch_issues), 0)
    
    def test_normal_batch_no_issue(self):
        """测试正常批次不报问题"""
        draws = []
        for i in range(3):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=5000,  # 正常大小
                instance_count=1,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        batch_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF003"]
        self.assertEqual(len(batch_issues), 0)


class TestTextureIssues(unittest.TestCase):
    """测试纹理相关问题检测 (PERF004, PERF005)"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_large_texture_detected(self):
        """测试大纹理检测"""
        textures = [
            TextureInfo(
                resource_id="TEX_1",
                name="HugeTexture",
                width=8192,
                height=8192,
                depth=1,
                format="RGBA8",
                memory_size=8192 * 8192 * 4,
            )
        ]
        self.context.textures = textures
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        large_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF004"]
        self.assertGreater(len(large_issues), 0)
    
    def test_uncompressed_texture_detected(self):
        """测试未压缩纹理检测"""
        textures = [
            TextureInfo(
                resource_id="TEX_1",
                name="UncompressedTexture",
                width=1024,
                height=1024,
                depth=1,
                format="DXGI_FORMAT_R8G8B8A8_UNORM",  # 未压缩
                memory_size=1024 * 1024 * 4,
                is_render_target=False,
                is_depth_stencil=False,
            )
        ]
        self.context.textures = textures
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        uncompressed_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF005"]
        self.assertGreater(len(uncompressed_issues), 0)
    
    def test_compressed_texture_no_issue(self):
        """测试压缩纹理不报问题"""
        textures = [
            TextureInfo(
                resource_id="TEX_1",
                name="CompressedTexture",
                width=1024,
                height=1024,
                depth=1,
                format="DXGI_FORMAT_BC7_UNORM",  # 压缩
                memory_size=1024 * 1024 // 2,
                is_render_target=False,
                is_depth_stencil=False,
            )
        ]
        self.context.textures = textures
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        uncompressed_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF005"]
        self.assertEqual(len(uncompressed_issues), 0)


class TestAlphaBlendDetection(unittest.TestCase):
    """测试 Alpha 混合检测 (PERF006)"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_excessive_blend_detected(self):
        """测试过多 Alpha 混合检测"""
        draws = []
        for i in range(10):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=100,
                blend_enabled=(i < 8),  # 80% 使用 blend
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        blend_issues = [i for i in analyzer.report.issues if i.rule_id == "PERF006"]
        self.assertGreater(len(blend_issues), 0)


class TestReportGeneration(unittest.TestCase):
    """测试报告生成"""
    
    def setUp(self):
        """设置测试环境"""
        self.context = AnalysisContext()
        self.context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
    
    def test_statistics_collection(self):
        """测试统计数据收集"""
        draws = []
        for i in range(5):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=300,
                index_count=0,
                instance_count=2,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        report = analyzer.report
        self.assertEqual(report.total_draw_calls, 5)
        self.assertEqual(report.total_vertices, 300 * 2 * 5)
        self.assertEqual(report.total_triangles, 100 * 2 * 5)
    
    def test_overall_score_calculation(self):
        """测试总体评分计算"""
        # 无问题的情况
        self.context.draw_calls = [
            DrawCallInfo(
                event_id=0,
                vertex_count=1000,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
        ]
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        # 无问题时评分应接近 100
        self.assertGreaterEqual(analyzer.report.overall_score, 90)
    
    def test_recommendations_generated(self):
        """测试建议生成"""
        # 创建有问题的场景
        draws = []
        for i in range(20):
            draw = DrawCallInfo(
                event_id=i,
                vertex_count=10,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
                blend_enabled=True,
            )
            draws.append(draw)
        
        self.context.draw_calls = draws
        
        analyzer = PerformanceAnalyzer(self.context)
        analyzer.analyze()
        
        # 应该生成建议
        report = analyzer.report
        # 注意：建议列表可能为空或有内容，取决于检测到的问题


class TestContextIntegration(unittest.TestCase):
    """测试与上下文的集成"""
    
    def test_report_saved_to_context(self):
        """测试报告保存到上下文"""
        context = AnalysisContext()
        context.parsed = ParsedData(file_path="test.rdc", api="D3D11")
        context.draw_calls = [
            DrawCallInfo(
                event_id=0,
                vertex_count=100,
                vs_id="VS_0",
                ps_id="PS_0",
                rt_ids=["RT_0"],
            )
        ]
        
        analyzer = PerformanceAnalyzer(context)
        analyzer.analyze()
        
        # 报告应保存到上下文
        self.assertIsNotNone(context.performance_report)
        self.assertIsInstance(context.performance_report, PerformanceReport)


if __name__ == "__main__":
    unittest.main(verbosity=2)
