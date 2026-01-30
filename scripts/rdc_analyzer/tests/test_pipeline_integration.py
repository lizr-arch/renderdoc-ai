#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 集成测试
=================

测试完整的分析管线流程。

注意：完整测试需要在 RenderDoc GUI 的 Python Shell 中运行，
      因为需要访问真实的 renderdoc 模块和 ReplayController。

独立运行时仅验证模块导入和配置解析。
"""

import sys
import os
import unittest
from pathlib import Path
from dataclasses import asdict

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAnalysisOptions(unittest.TestCase):
    """测试 AnalysisOptions 配置类"""
    
    def test_default_options(self):
        """测试默认配置"""
        from rdc_analyzer.main import AnalysisOptions
        
        opts = AnalysisOptions()
        
        self.assertTrue(opts.sample_textures)
        self.assertTrue(opts.sample_buffers)
        self.assertEqual(opts.max_texture_size, 256)
        self.assertEqual(opts.platform, "pc")
        self.assertEqual(opts.log_level, "INFO")
        self.assertIn("html", opts.output_formats)
        
    def test_custom_options(self):
        """测试自定义配置"""
        from rdc_analyzer.main import AnalysisOptions
        
        opts = AnalysisOptions(
            sample_textures=False,
            sample_buffers=True,
            max_texture_size=128,
            event_range=(100, 500),
            platform="mobile",
            output_formats=["html", "json"],
            verbose=True
        )
        
        self.assertFalse(opts.sample_textures)
        self.assertTrue(opts.sample_buffers)
        self.assertEqual(opts.max_texture_size, 128)
        self.assertEqual(opts.event_range, (100, 500))
        self.assertEqual(opts.platform, "mobile")
        self.assertIn("json", opts.output_formats)
        
    def test_options_serialization(self):
        """测试配置序列化"""
        from rdc_analyzer.main import AnalysisOptions
        
        opts = AnalysisOptions(output_dir="/tmp/test")
        d = asdict(opts)
        
        self.assertIn("output_dir", d)
        self.assertEqual(d["output_dir"], "/tmp/test")


class TestAnalysisSummary(unittest.TestCase):
    """测试 AnalysisSummary 结果类"""
    
    def test_empty_summary(self):
        """测试空结果"""
        from rdc_analyzer.main import AnalysisSummary
        
        summary = AnalysisSummary(
            rdc_path="test.rdc",
            api="D3D11",
            timestamp="2025-01-16T14:00:00",
            duration_seconds=0.0,
            total_events=0,
            draw_call_count=0,
            total_vertices=0,
            total_triangles=0,
            texture_count=0,
            buffer_count=0,
            shader_count=0,
            error_count=0,
            warning_count=0,
            info_count=0
        )
        
        self.assertEqual(summary.draw_call_count, 0)
        self.assertEqual(summary.total_vertices, 0)
        self.assertEqual(summary.warning_count, 0)
        self.assertEqual(summary.error_count, 0)
        self.assertEqual(summary.output_files, [])
        
    def test_summary_with_data(self):
        """测试带数据的结果"""
        from rdc_analyzer.main import AnalysisSummary
        
        summary = AnalysisSummary(
            rdc_path="capture.rdc",
            api="D3D12",
            timestamp="2025-01-16T14:00:00",
            duration_seconds=2.5,
            total_events=500,
            draw_call_count=150,
            total_vertices=1000000,
            total_triangles=333333,
            texture_count=25,
            buffer_count=50,
            shader_count=10,
            error_count=0,
            warning_count=3,
            info_count=5,
            output_files=["output/report.html"]
        )
        
        self.assertEqual(summary.draw_call_count, 150)
        self.assertEqual(summary.total_vertices, 1000000)
        self.assertEqual(summary.texture_count, 25)
        self.assertEqual(len(summary.output_files), 1)


class TestCLIInterface(unittest.TestCase):
    """测试 CLI 接口"""
    
    def test_cli_import(self):
        """测试 CLI 模块导入"""
        from rdc_analyzer.__main__ import main, cmd_analyze, cmd_list_rules
        
        self.assertTrue(callable(main))
        self.assertTrue(callable(cmd_analyze))
        self.assertTrue(callable(cmd_list_rules))
        
    def test_rules_registration(self):
        """测试规则注册"""
        from rdc_analyzer.rules import RuleRegistry, register_all_rules
        
        register_all_rules()
        rules = RuleRegistry.all()
        
        # 应该有多条规则
        self.assertGreater(len(rules), 20)
        
        # 检查关键规则存在
        rule_ids = list(rules.keys())
        self.assertTrue(any("DC" in r for r in rule_ids))  # Draw Call 规则
        self.assertTrue(any("TEX" in r for r in rule_ids))  # Texture 规则
        self.assertTrue(any("BUF" in r for r in rule_ids))  # Buffer 规则


class TestPipelineStructure(unittest.TestCase):
    """测试 Pipeline 结构"""
    
    def test_pipeline_class_exists(self):
        """测试 Pipeline 类存在"""
        from rdc_analyzer.main import AnalysisPipeline
        
        # 验证必要的方法存在
        self.assertTrue(hasattr(AnalysisPipeline, 'run'))
        self.assertTrue(hasattr(AnalysisPipeline, '_open_capture'))
        self.assertTrue(hasattr(AnalysisPipeline, '_parse_events'))
        
    def test_pipeline_init_without_rdc(self):
        """测试 Pipeline 初始化（无实际文件）"""
        from rdc_analyzer.main import AnalysisPipeline, AnalysisOptions
        
        opts = AnalysisOptions(output_dir="./test_output")
        
        # 应该能初始化，即使文件不存在
        pipeline = AnalysisPipeline("nonexistent.rdc", opts)
        
        self.assertEqual(pipeline.rdc_path, "nonexistent.rdc")
        self.assertEqual(pipeline.options.output_dir, "./test_output")


class TestHTMLExporterIntegration(unittest.TestCase):
    """测试 HTML 导出器集成"""
    
    def test_exporter_import(self):
        """测试导出器导入"""
        from rdc_analyzer.exporters.html_exporter import HTMLExporter
        
        self.assertTrue(callable(HTMLExporter))
        
    def test_exporter_methods(self):
        """测试导出器方法"""
        from rdc_analyzer.exporters.html_exporter import HTMLExporter
        
        exporter = HTMLExporter()
        
        self.assertTrue(hasattr(exporter, 'export'))
        self.assertTrue(hasattr(exporter, 'export_to_file'))


class TestMockPipelineRun(unittest.TestCase):
    """测试 Mock 模式的 Pipeline 运行"""
    
    def test_analyze_function_exists(self):
        """测试 analyze 便捷函数存在"""
        from rdc_analyzer.main import analyze
        
        self.assertTrue(callable(analyze))
        
    def test_mock_run_returns_summary(self):
        """测试 Mock 运行返回摘要"""
        from rdc_analyzer.main import AnalysisPipeline, AnalysisOptions, AnalysisSummary
        
        # 这个测试在没有真实 RDC 文件时会失败
        # 但可以验证类型签名正确
        opts = AnalysisOptions()
        pipeline = AnalysisPipeline("fake.rdc", opts)
        
        # 验证返回类型注解
        import inspect
        sig = inspect.signature(pipeline.run)
        # run() 应该返回 AnalysisSummary
        self.assertIn('AnalysisSummary', str(sig.return_annotation))


class TestEventRange(unittest.TestCase):
    """测试事件范围过滤"""
    
    def test_event_range_parsing(self):
        """测试事件范围解析"""
        from rdc_analyzer.main import AnalysisOptions
        
        # 正常范围
        opts = AnalysisOptions(event_range=(100, 500))
        self.assertEqual(opts.event_range[0], 100)
        self.assertEqual(opts.event_range[1], 500)
        
        # 空范围
        opts2 = AnalysisOptions()
        self.assertIsNone(opts2.event_range)
        
    def test_event_range_filter_logic(self):
        """测试事件范围过滤逻辑"""
        from rdc_analyzer.main import AnalysisOptions
        
        opts = AnalysisOptions(event_range=(100, 200))
        
        # 模拟事件过滤
        events = [50, 100, 150, 200, 250]
        filtered = [e for e in events if opts.event_range[0] <= e <= opts.event_range[1]]
        
        self.assertEqual(filtered, [100, 150, 200])


# =============================================================================
# 需要真实 RDC 文件的测试（仅在 RenderDoc GUI 中运行）
# =============================================================================

class TestRealRDCAnalysis(unittest.TestCase):
    """
    真实 RDC 文件分析测试
    
    这些测试需要在 RenderDoc GUI 的 Python Shell 中运行，
    因为需要访问 renderdoc 模块的 ReplayController。
    """
    
    @classmethod
    def setUpClass(cls):
        """检查是否在 RenderDoc 环境中"""
        try:
            import renderdoc as rd
            cls.has_renderdoc = True
        except ImportError:
            cls.has_renderdoc = False
            
        # 检查测试文件
        cls.test_rdc = Path(__file__).parent.parent.parent / "test_data" / "g145.rdc"
        if not cls.test_rdc.exists():
            cls.test_rdc = None
    
    def test_real_file_analysis(self):
        """测试真实文件分析"""
        if self.test_rdc is None:
            self.skipTest("测试 RDC 文件不存在")
            
        from rdc_analyzer.main import analyze, AnalysisOptions
        
        opts = AnalysisOptions(
            sample_textures=True,
            sample_buffers=True,
            output_formats=["html"],
            output_dir="./test_output"
        )
        
        result = analyze(str(self.test_rdc), opts)
        
        self.assertTrue(result.success)
        self.assertGreater(result.draw_call_count, 0)


def run_standalone_tests():
    """运行独立测试（不需要 RenderDoc）"""
    suite = unittest.TestSuite()
    
    # 添加不需要 RenderDoc 的测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnalysisOptions))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnalysisSummary))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCLIInterface))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPipelineStructure))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHTMLExporterIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEventRange))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    print("=" * 60)
    print("RDC Analyzer Pipeline 集成测试")
    print("=" * 60)
    print()
    print("独立模式：验证模块导入和配置解析")
    print("完整模式：需要在 RenderDoc GUI Python Shell 中运行")
    print()
    
    result = run_standalone_tests()
    
    # 返回适当的退出码
    sys.exit(0 if result.wasSuccessful() else 1)
