"""
Issues 视图测试
================
验证 Issues 视图渲染器的问题卡片展示功能
"""

import unittest
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_ui import render_issues_view


class TestIssuesViewBasic(unittest.TestCase):
    """Issues 视图基础测试"""
    
    def test_empty_issues_shows_placeholder(self):
        """空问题列表显示占位符"""
        html = render_issues_view([])
        self.assertIn("no issues", html.lower())
    
    def test_returns_html_string(self):
        """返回 HTML 字符串"""
        html = render_issues_view([])
        self.assertIsInstance(html, str)
        self.assertIn("<div", html)


class TestIssueCard(unittest.TestCase):
    """问题卡片测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.issues = [
            {
                'id': 'TEX-001',
                'title': '纹理尺寸超标',
                'severity': 'high',
                'category': 'texture',
                'description': '发现 5 个纹理超过 2048x2048',
                'details': '建议使用 mipmap 或降低分辨率',
                'affected_resources': ['Texture_Diffuse', 'Texture_Normal']
            },
            {
                'id': 'PERF-002',
                'title': 'DrawCall 数量过高',
                'severity': 'medium',
                'category': 'performance',
                'description': '单帧 DrawCall 达到 2500+',
                'details': '考虑合批或 GPU Instancing'
            }
        ]
    
    def test_renders_issue_title(self):
        """渲染问题标题"""
        html = render_issues_view(self.issues)
        self.assertIn("纹理尺寸超标", html)
        self.assertIn("DrawCall 数量过高", html)
    
    def test_renders_severity_badge(self):
        """渲染严重程度徽章"""
        html = render_issues_view(self.issues)
        # 应该有 high 和 medium 标记
        self.assertTrue(
            "high" in html.lower() or 
            "严重" in html or 
            "danger" in html.lower()
        )
        self.assertTrue(
            "medium" in html.lower() or 
            "中等" in html or 
            "warning" in html.lower()
        )
    
    def test_renders_category_tag(self):
        """渲染分类标签"""
        html = render_issues_view(self.issues)
        self.assertTrue(
            "texture" in html.lower() or 
            "纹理" in html
        )
        self.assertTrue(
            "performance" in html.lower() or 
            "性能" in html
        )
    
    def test_renders_description(self):
        """渲染问题描述"""
        html = render_issues_view(self.issues)
        self.assertIn("5 个纹理", html)
    
    def test_has_card_structure(self):
        """有卡片结构"""
        html = render_issues_view(self.issues)
        self.assertTrue(
            "issue-card" in html.lower() or 
            "card" in html.lower()
        )


class TestSeveritySorting(unittest.TestCase):
    """严重程度排序测试"""
    
    def setUp(self):
        """准备乱序数据"""
        self.issues = [
            {'id': '1', 'title': 'Low Issue', 'severity': 'low', 'category': 'other', 'description': '...'},
            {'id': '2', 'title': 'Critical Issue', 'severity': 'critical', 'category': 'other', 'description': '...'},
            {'id': '3', 'title': 'Medium Issue', 'severity': 'medium', 'category': 'other', 'description': '...'},
            {'id': '4', 'title': 'High Issue', 'severity': 'high', 'category': 'other', 'description': '...'},
        ]
    
    def test_critical_appears_before_low(self):
        """Critical 问题在 Low 之前显示"""
        html = render_issues_view(self.issues)
        critical_pos = html.find("Critical Issue")
        low_pos = html.find("Low Issue")
        self.assertLess(critical_pos, low_pos, "Critical 应该在 Low 之前")
    
    def test_high_appears_before_medium(self):
        """High 问题在 Medium 之前显示"""
        html = render_issues_view(self.issues)
        high_pos = html.find("High Issue")
        medium_pos = html.find("Medium Issue")
        self.assertLess(high_pos, medium_pos, "High 应该在 Medium 之前")


class TestCollapsibleDetails(unittest.TestCase):
    """可折叠详情测试"""
    
    def setUp(self):
        """准备带详情的问题"""
        self.issues = [
            {
                'id': 'TEX-001',
                'title': '纹理问题',
                'severity': 'high',
                'category': 'texture',
                'description': '纹理超标',
                'details': '这是详细建议内容：使用压缩格式如 BC7',
                'affected_resources': ['Tex1', 'Tex2', 'Tex3']
            }
        ]
    
    def test_details_section_exists(self):
        """详情区域存在"""
        html = render_issues_view(self.issues)
        self.assertTrue(
            "details" in html.lower() or 
            "collapse" in html.lower() or
            "expand" in html.lower() or
            "详情" in html or
            "建议" in html
        )
    
    def test_affected_resources_shown(self):
        """受影响资源显示"""
        html = render_issues_view(self.issues)
        self.assertTrue(
            "Tex1" in html or 
            "affected" in html.lower() or
            "资源" in html
        )


class TestSeverityIcons(unittest.TestCase):
    """严重程度图标测试"""
    
    def test_severity_has_visual_indicator(self):
        """严重程度有视觉指示"""
        issues = [
            {'id': '1', 'title': 'Test', 'severity': 'critical', 'category': 'test', 'description': '...'}
        ]
        html = render_issues_view(issues)
        # 应该有颜色类或图标
        self.assertTrue(
            "🔴" in html or 
            "critical" in html.lower() or
            "#" in html or  # 颜色代码
            "color" in html.lower()
        )


if __name__ == '__main__':
    unittest.main()
