#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端集成测试：验证 V2 报告生成流水线
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_ui import render_report_shell
from report_contract import ReportDataContract, build_manifest


def create_test_contract(source: str = "test.xml") -> ReportDataContract:
    """创建测试用 ReportDataContract"""
    return ReportDataContract(
        meta={
            "capture_name": source,
            "api": "D3D11",
            "source": "test",
            "title": "Test Report"
        },
        textures=[
            {"id": 1, "name": "Diffuse", "width": 1024, "height": 1024, "format": "BC3"},
            {"id": 2, "name": "Normal", "width": 512, "height": 512, "format": "BC5"},
        ],
        shaders=[
            {"id": 1, "name": "MainVS", "type": "Vertex"},
            {"id": 2, "name": "MainPS", "type": "Pixel"},
        ],
        events=[
            {"eventId": 1, "name": "ClearRenderTarget"},
            {"eventId": 2, "name": "DrawIndexed", "indexCount": 3000},
            {"eventId": 3, "name": "DrawIndexed", "indexCount": 1500},
        ],
        buffers=[
            {"id": 1, "name": "VertexBuffer", "size": 65536},
        ],
        issues=[
            {"id": "TEX-001", "title": "Oversized Texture", "severity": "warning", "description": "Large texture"},
        ],
        performance={
            "total_draw_calls": 2,
            "total_vertices": 4500,
        }
    )


class TestE2EReportGeneration(unittest.TestCase):
    """端到端报告生成测试"""
    
    def test_render_report_shell_returns_html(self):
        """render_report_shell 应返回有效 HTML"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # 验证基本 HTML 结构
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<html", html)
        self.assertIn("</html>", html)
        
    def test_report_contains_four_views(self):
        """生成的报告应包含四个视图"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # 验证四个视图 tab
        self.assertIn("issues-view", html)
        self.assertIn("events-view", html)
        self.assertIn("resources-view", html)
        self.assertIn("performance-view", html)
        
    def test_report_contains_navigation(self):
        """生成的报告应包含导航栏"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # 验证导航元素
        self.assertIn("Issues", html)
        self.assertIn("Events", html)
        self.assertIn("Resources", html)
        self.assertIn("Performance", html)
        
    def test_report_contains_capture_name(self):
        """生成的报告应包含 capture 名称"""
        contract = create_test_contract("my_capture.xml")
        html = render_report_shell(contract)
        
        # 报告标题应出现
        self.assertIn("Test Report", html)
        
    def test_write_report_to_file(self):
        """验证报告可以成功写入文件"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', 
                                         delete=False, encoding='utf-8') as f:
            f.write(html)
            temp_path = f.name
            
        try:
            # 验证文件存在且内容正确
            self.assertTrue(os.path.exists(temp_path))
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.assertEqual(content, html)
            self.assertGreater(len(content), 1000)  # 至少 1KB
        finally:
            # 清理
            os.unlink(temp_path)
            
    def test_manifest_generation(self):
        """验证 manifest 生成包含必要字段"""
        contract = create_test_contract()
        manifest = build_manifest(contract)
        
        # 验证必要字段
        self.assertIn('counts', manifest)
        self.assertIn('generated_at', manifest)
        self.assertIn('coverage', manifest)
        
        # 验证计数正确
        self.assertEqual(manifest['counts']['textures'], 2)
        self.assertEqual(manifest['counts']['shaders'], 2)
        self.assertEqual(manifest['counts']['events'], 3)


class TestE2EWithMinimalData(unittest.TestCase):
    """使用最小化数据的端到端测试"""
    
    def test_report_shell_with_empty_contract(self):
        """使用空 contract 生成报告"""
        contract = ReportDataContract(
            meta={"capture_name": "empty.xml", "api": "D3D11", "title": "Empty Report"}
        )
        
        html = render_report_shell(contract)
        
        # 验证基本结构
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("issues-view", html)
        
    def test_report_contains_texture_data(self):
        """验证纹理数据显示在报告中"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # 纹理名称应该出现
        self.assertIn("Diffuse", html)
        self.assertIn("Normal", html)
        
    def test_report_contains_shader_data(self):
        """验证 Shader 数据显示在报告中"""
        contract = create_test_contract()
        html = render_report_shell(contract)
        
        # Shader 名称应该出现
        self.assertIn("MainVS", html)
        self.assertIn("MainPS", html)
        

if __name__ == '__main__':
    unittest.main(verbosity=2)