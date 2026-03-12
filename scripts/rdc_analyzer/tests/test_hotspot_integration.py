"""
热点分析集成测试
================

测试 HotspotAnalyzer 与报告生成的完整集成。
"""

import sys
from pathlib import Path
import tempfile
import os

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from rdc_analyzer.core.hotspot_analyzer import (
    HotspotAnalyzer,
    analyze_hotspots,
)
from rdc_analyzer.components.hotspot_component import (
    generate_hotspot_css,
    generate_hotspot_js,
    generate_hotspot_html,
    convert_report_to_js_data,
)


class TestHotspotComponentGeneration(unittest.TestCase):
    """测试热点组件生成"""
    
    def test_css_generation(self):
        """测试 CSS 生成"""
        css = generate_hotspot_css()
        
        self.assertIn('.hotspot-panel', css)
        self.assertIn('.hotspot-toggle-btn', css)
        self.assertIn('.hotspot-item.critical', css)
        self.assertIn('.hotspot-indicator', css)
        self.assertIn('event-row.hotspot-critical', css)
    
    def test_js_generation(self):
        """测试 JS 生成"""
        js = generate_hotspot_js()
        
        self.assertIn('HotspotModule', js)
        self.assertIn('createToggleButton', js)
        self.assertIn('renderHotspotList', js)
        self.assertIn('highlightEvents', js)
        self.assertIn('showSuggestion', js)
    
    def test_html_generation_with_data(self):
        """测试带数据的 HTML 生成"""
        data = {
            "total_draws": 100,
            "hotspots": [
                {"event_id": 1, "name": "Draw", "score": 1000, "level": "critical"}
            ]
        }
        html = generate_hotspot_html(data)
        
        self.assertIn('HotspotModule.init', html)
        self.assertIn('"total_draws": 100', html)
    
    def test_html_generation_no_data(self):
        """测试无数据时的 HTML 生成"""
        html = generate_hotspot_html(None)
        self.assertIn('not available', html)


class TestReportConversion(unittest.TestCase):
    """测试报告格式转换"""
    
    def test_convert_report_to_js_data(self):
        """测试报告转换为 JS 数据"""
        # 创建分析器并添加数据
        analyzer = HotspotAnalyzer()
        
        draws = [
            {"eid": 1, "name": "DrawA", "numIndices": 30000},
            {"eid": 2, "name": "DrawB", "numIndices": 3000},
            {"eid": 3, "name": "DrawC", "numIndices": 300},
        ]
        for d in draws:
            analyzer.add_draw(d)
        
        report = analyzer.analyze()
        js_data = convert_report_to_js_data(report)
        
        # 验证结构
        self.assertEqual(js_data["total_draws"], 3)
        self.assertTrue(js_data["total_score"] > 0)
        self.assertTrue(len(js_data["hotspots"]) > 0)
        
        # 验证热点数据格式
        first_hs = js_data["hotspots"][0]
        self.assertIn("event_id", first_hs)
        self.assertIn("score", first_hs)
        self.assertIn("level", first_hs)


class TestIntegrationWithReportGenerator(unittest.TestCase):
    """测试与报告生成器的集成"""
    
    def test_import_in_report_generator(self):
        """测试报告生成器能成功导入热点模块"""
        try:
            # 切换到 rdc_analyzer 目录
            rdc_analyzer_path = Path(__file__).parent.parent
            sys.path.insert(0, str(rdc_analyzer_path))
            
            from components.hotspot_component import (
                generate_hotspot_css,
                generate_hotspot_js,
                generate_hotspot_html,
            )
            
            # 验证导入成功
            self.assertTrue(callable(generate_hotspot_css))
            self.assertTrue(callable(generate_hotspot_js))
            self.assertTrue(callable(generate_hotspot_html))
            
        except ImportError as e:
            self.fail(f"Failed to import hotspot component: {e}")


class TestEndToEndHotspotFlow(unittest.TestCase):
    """端到端热点分析流程测试"""
    
    def test_full_flow(self):
        """测试完整流程: 分析 -> 转换 -> 生成组件"""
        # 1. 创建模拟 draw call 数据
        draws = []
        for i in range(50):
            draws.append({
                "eid": i + 1,
                "name": f"DrawIndexed_{i}",
                "numIndices": (i + 1) * 600,  # 200 ~ 10000 triangles
                "numInstances": 1 if i < 40 else 10,
                "outputs": ["rt0"] if i < 30 else ["rt0", "rt1", "rt2"],
            })
        
        # 2. 运行分析
        report = analyze_hotspots(draws, top_n=10)
        
        # 3. 验证分析结果
        self.assertEqual(report.total_draws, 50)
        self.assertTrue(len(report.hotspots) <= 10)
        self.assertTrue(report.hotspots[0].weighted_score > report.hotspots[-1].weighted_score)
        
        # 4. 转换为 JS 数据
        js_data = convert_report_to_js_data(report)
        
        # 5. 生成组件
        css = generate_hotspot_css()
        js = generate_hotspot_js()
        html = generate_hotspot_html(js_data)
        
        # 6. 验证组件包含关键内容
        self.assertIn('.hotspot-panel', css)
        self.assertIn('HotspotModule', js)
        self.assertIn('"total_draws": 50', html)
        
        # 7. 验证热点级别分配
        levels = [h["level"] for h in js_data["hotspots"]]
        self.assertIn("critical", levels)  # Top 热点应该是 critical


class TestHotspotSuggestions(unittest.TestCase):
    """测试优化建议生成"""
    
    def test_high_polygon_suggestion(self):
        """测试高多边形建议"""
        analyzer = HotspotAnalyzer()
        
        # 添加一个超高多边形的 draw
        draw = {
            "eid": 1,
            "name": "HeavyMesh",
            "numIndices": 600000,  # 200k triangles
        }
        analyzer.add_draw(draw)
        report = analyzer.analyze()
        
        # 验证建议包含 LOD 提示
        self.assertTrue(len(report.suggestions) > 0)
        sugg = report.suggestions[0]
        self.assertIn("LOD", str(sugg.get("recommendations", [])))
    
    def test_heavy_instancing_suggestion(self):
        """测试大量实例建议"""
        analyzer = HotspotAnalyzer()
        
        draw = {
            "eid": 1,
            "name": "ManyInstances",
            "numIndices": 3000,
            "numInstances": 500,
        }
        analyzer.add_draw(draw)
        report = analyzer.analyze()
        
        self.assertTrue(len(report.suggestions) > 0)
        sugg = report.suggestions[0]
        reasons_str = str(sugg.get("reasons", []))
        self.assertIn("实例", reasons_str)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print(f"[OK] All {result.testsRun} tests passed!")
    else:
        print(f"[FAIL] {len(result.failures)} failures, {len(result.errors)} errors")
    
    sys.exit(0 if result.wasSuccessful() else 1)
