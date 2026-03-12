"""
Performance 视图测试
====================
验证 Performance 视图渲染器的指标展示功能
"""

import unittest
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_ui import render_performance_view


class TestPerformanceViewBasic(unittest.TestCase):
    """Performance 视图基础测试"""
    
    def test_empty_performance_shows_placeholder(self):
        """空性能数据显示占位符"""
        html = render_performance_view({})
        self.assertIn("no performance", html.lower())
    
    def test_returns_html_string(self):
        """返回 HTML 字符串"""
        html = render_performance_view({})
        self.assertIsInstance(html, str)
        self.assertIn("<div", html)


class TestMetricCards(unittest.TestCase):
    """指标卡片测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.perf_data = {
            'frame_time_ms': 16.7,
            'draw_call_count': 1500,
            'triangle_count': 2500000,
            'texture_memory_mb': 512.5,
            'buffer_memory_mb': 128.0,
            'render_target_count': 8
        }
    
    def test_renders_frame_time(self):
        """渲染帧时间"""
        html = render_performance_view(self.perf_data)
        self.assertIn("16.7", html)
    
    def test_renders_draw_call_count(self):
        """渲染 DrawCall 数量"""
        html = render_performance_view(self.perf_data)
        # 1500 可能被格式化为 1,500
        self.assertTrue("1500" in html or "1,500" in html)
    
    def test_renders_triangle_count(self):
        """渲染三角形数量"""
        html = render_performance_view(self.perf_data)
        # 可以是 2500000 或 2.5M 格式
        self.assertTrue("2500000" in html or "2.5" in html)
    
    def test_has_metric_card_structure(self):
        """有指标卡片结构"""
        html = render_performance_view(self.perf_data)
        self.assertTrue(
            "metric" in html.lower() or 
            "card" in html.lower() or 
            "stat" in html.lower()
        )


class TestPerformanceSummary(unittest.TestCase):
    """性能摘要测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.perf_data = {
            'frame_time_ms': 33.3,  # 30 FPS - 可能有性能问题
            'draw_call_count': 5000,  # 较高
            'passes': [
                {'name': 'ShadowPass', 'duration_ms': 5.0},
                {'name': 'MainPass', 'duration_ms': 20.0},
                {'name': 'PostProcess', 'duration_ms': 8.0}
            ]
        }
    
    def test_renders_pass_breakdown(self):
        """渲染 Pass 耗时分解"""
        html = render_performance_view(self.perf_data)
        # 至少应该有 Pass 名称
        self.assertTrue(
            "ShadowPass" in html or 
            "MainPass" in html or 
            "shadow" in html.lower() or
            "main" in html.lower()
        )
    
    def test_has_performance_section(self):
        """有性能分区"""
        html = render_performance_view(self.perf_data)
        self.assertTrue(
            "performance" in html.lower() or 
            "dashboard" in html.lower() or 
            "metrics" in html.lower()
        )


class TestTimelineChart(unittest.TestCase):
    """时序图占位测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.perf_data = {
            'timeline': [
                {'eid': 10, 'name': 'ShadowPass', 'start_ms': 0, 'end_ms': 5},
                {'eid': 20, 'name': 'MainPass', 'start_ms': 5, 'end_ms': 25},
            ]
        }
    
    def test_timeline_section_exists(self):
        """时序图分区存在"""
        html = render_performance_view(self.perf_data)
        self.assertTrue(
            "timeline" in html.lower() or 
            "chart" in html.lower() or 
            "graph" in html.lower() or
            "coming soon" in html.lower()
        )


if __name__ == '__main__':
    unittest.main()
