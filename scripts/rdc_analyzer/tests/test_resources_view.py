"""
Resources 视图测试
==================
验证 Resources 视图渲染器的纹理/Shader 展示功能
"""

import unittest
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_contract import ReportDataContract
from report_ui import render_resources_view


class TestResourcesViewBasic(unittest.TestCase):
    """Resources 视图基础测试"""
    
    def test_empty_resources_shows_placeholder(self):
        """空资源显示占位符"""
        contract = ReportDataContract()
        html = render_resources_view(contract)
        self.assertIn("no resources", html.lower())
    
    def test_returns_html_string(self):
        """返回 HTML 字符串"""
        contract = ReportDataContract()
        html = render_resources_view(contract)
        self.assertIsInstance(html, str)
        self.assertIn("<div", html)


class TestTexturesList(unittest.TestCase):
    """纹理列表测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.textures = [
            {
                'resource_id': 'tex_001',
                'name': 'Albedo_Diffuse',
                'width': 2048,
                'height': 2048,
                'format': 'BC7_UNORM',
                'mips': 11,
                'thumbnail': 'data:image/png;base64,ABC123'
            },
            {
                'resource_id': 'tex_002',
                'name': 'Normal_Map',
                'width': 1024,
                'height': 1024,
                'format': 'BC5_UNORM',
                'mips': 10
            },
            {
                'resource_id': 'tex_003',
                'name': 'Shadow_Depth',
                'width': 4096,
                'height': 4096,
                'format': 'D32_FLOAT',
                'mips': 1
            }
        ]
        self.contract = ReportDataContract(textures=self.textures)
    
    def test_renders_texture_names(self):
        """渲染纹理名称"""
        html = render_resources_view(self.contract)
        self.assertIn("Albedo_Diffuse", html)
        self.assertIn("Normal_Map", html)
        self.assertIn("Shadow_Depth", html)
    
    def test_renders_texture_dimensions(self):
        """渲染纹理尺寸"""
        html = render_resources_view(self.contract)
        self.assertIn("2048", html)
        self.assertIn("1024", html)
        self.assertIn("4096", html)
    
    def test_renders_texture_format(self):
        """渲染纹理格式"""
        html = render_resources_view(self.contract)
        self.assertIn("BC7", html.upper() if "bc7" in html.lower() else html)
    
    def test_texture_section_exists(self):
        """纹理分区存在"""
        html = render_resources_view(self.contract)
        self.assertTrue(
            "texture" in html.lower() and 
            ("section" in html.lower() or "list" in html.lower() or "grid" in html.lower())
        )


class TestShadersList(unittest.TestCase):
    """Shader 列表测试"""
    
    def setUp(self):
        """准备测试数据"""
        self.shaders = [
            {
                'resource_id': 'shader_001',
                'name': 'PBR_Standard_VS',
                'type': 'vertex',
                'entry_point': 'main'
            },
            {
                'resource_id': 'shader_002',
                'name': 'PBR_Standard_PS',
                'type': 'pixel',
                'entry_point': 'main'
            },
            {
                'resource_id': 'shader_003',
                'name': 'Shadow_CS',
                'type': 'compute',
                'entry_point': 'CSMain'
            }
        ]
        self.contract = ReportDataContract(shaders=self.shaders)
    
    def test_renders_shader_names(self):
        """渲染 Shader 名称"""
        html = render_resources_view(self.contract)
        self.assertIn("PBR_Standard_VS", html)
        self.assertIn("PBR_Standard_PS", html)
        self.assertIn("Shadow_CS", html)
    
    def test_renders_shader_types(self):
        """渲染 Shader 类型"""
        html = render_resources_view(self.contract)
        # 至少显示类型信息
        self.assertTrue(
            "vertex" in html.lower() or 
            "pixel" in html.lower() or 
            "compute" in html.lower() or
            "vs" in html.lower() or
            "ps" in html.lower() or
            "cs" in html.lower()
        )
    
    def test_shader_section_exists(self):
        """Shader 分区存在"""
        html = render_resources_view(self.contract)
        self.assertIn("shader", html.lower())


class TestResourcesTabs(unittest.TestCase):
    """资源类型切换测试"""
    
    def setUp(self):
        """准备混合资源数据"""
        self.contract = ReportDataContract(
            textures=[{'resource_id': 'tex_001', 'name': 'Test_Texture', 'width': 512, 'height': 512, 'format': 'RGBA8'}],
            shaders=[{'resource_id': 'shader_001', 'name': 'Test_Shader', 'type': 'vertex'}]
        )
    
    def test_has_resource_type_tabs_or_sections(self):
        """有资源类型分隔"""
        html = render_resources_view(self.contract)
        # 应该有某种分隔结构
        has_tabs = "tab" in html.lower()
        has_sections = html.lower().count("section") >= 2 or html.lower().count("heading") >= 2
        has_categories = "texture" in html.lower() and "shader" in html.lower()
        self.assertTrue(has_tabs or has_sections or has_categories)
    
    def test_both_types_rendered(self):
        """同时渲染纹理和 Shader"""
        html = render_resources_view(self.contract)
        self.assertIn("Test_Texture", html)
        self.assertIn("Test_Shader", html)


if __name__ == '__main__':
    unittest.main()
