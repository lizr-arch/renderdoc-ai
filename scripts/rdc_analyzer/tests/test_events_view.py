"""
Events 视图测试
================
验证 Events 视图渲染器的层级树结构生成
"""

import unittest
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_ui import render_events_view


class TestEventsViewBasic(unittest.TestCase):
    """Events 视图基础测试"""
    
    def test_empty_events_shows_placeholder(self):
        """空事件列表显示占位符"""
        html = render_events_view([])
        self.assertIn("no events", html.lower())
    
    def test_returns_html_string(self):
        """返回 HTML 字符串"""
        html = render_events_view([])
        self.assertIsInstance(html, str)
        self.assertIn("<div", html)


class TestEventsTreeStructure(unittest.TestCase):
    """Events 树形结构测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.sample_events = [
            {
                'eid': 1,
                'name': 'BeginFrame',
                'type': 'marker',
                'children': []
            },
            {
                'eid': 10,
                'name': 'ShadowPass',
                'type': 'pass',
                'children': [
                    {'eid': 11, 'name': 'DrawCall_01', 'type': 'draw', 'children': []},
                    {'eid': 12, 'name': 'DrawCall_02', 'type': 'draw', 'children': []},
                ]
            },
            {
                'eid': 20,
                'name': 'MainPass',
                'type': 'pass',
                'children': [
                    {'eid': 21, 'name': 'DrawCall_03', 'type': 'draw', 'children': []},
                ]
            },
            {
                'eid': 100,
                'name': 'EndFrame',
                'type': 'marker',
                'children': []
            }
        ]
    
    def test_renders_pass_names(self):
        """渲染 Pass 名称"""
        html = render_events_view(self.sample_events)
        self.assertIn("ShadowPass", html)
        self.assertIn("MainPass", html)
    
    def test_renders_draw_calls(self):
        """渲染 DrawCall"""
        html = render_events_view(self.sample_events)
        self.assertIn("DrawCall_01", html)
        self.assertIn("DrawCall_02", html)
        self.assertIn("DrawCall_03", html)
    
    def test_renders_event_ids(self):
        """渲染事件 ID"""
        html = render_events_view(self.sample_events)
        # EID 应该以某种形式显示
        self.assertIn("10", html)  # ShadowPass EID
        self.assertIn("20", html)  # MainPass EID
    
    def test_tree_has_expandable_structure(self):
        """树形结构有可展开标记"""
        html = render_events_view(self.sample_events)
        # 应该有某种展开/折叠的 CSS 类或元素
        self.assertTrue(
            "tree" in html.lower() or 
            "expand" in html.lower() or 
            "collapse" in html.lower() or
            "children" in html.lower()
        )
    
    def test_nested_children_in_dom(self):
        """子节点嵌套在父节点 DOM 中"""
        html = render_events_view(self.sample_events)
        # ShadowPass 应该包含其子 DrawCall
        shadow_idx = html.find("ShadowPass")
        draw01_idx = html.find("DrawCall_01")
        draw02_idx = html.find("DrawCall_02")
        
        # DrawCall 应该在 ShadowPass 之后出现
        self.assertGreater(draw01_idx, shadow_idx)
        self.assertGreater(draw02_idx, shadow_idx)


class TestEventsViewStyling(unittest.TestCase):
    """Events 视图样式测试"""
    
    def test_has_tree_css_classes(self):
        """包含树形 CSS 类"""
        events = [{'eid': 1, 'name': 'Test', 'type': 'pass', 'children': []}]
        html = render_events_view(events)
        self.assertIn("class=", html)
    
    def test_different_types_have_different_styles(self):
        """不同类型有不同样式"""
        events = [
            {'eid': 1, 'name': 'Marker', 'type': 'marker', 'children': []},
            {'eid': 2, 'name': 'Pass', 'type': 'pass', 'children': []},
            {'eid': 3, 'name': 'Draw', 'type': 'draw', 'children': []},
        ]
        html = render_events_view(events)
        # 应该有类型相关的 class 或 data 属性
        self.assertTrue(
            "marker" in html.lower() or 
            "pass" in html.lower() or 
            "draw" in html.lower() or
            "type" in html.lower()
        )


if __name__ == '__main__':
    unittest.main()
