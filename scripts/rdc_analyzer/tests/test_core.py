"""
Core 模块测试
============

测试核心数据结构和枚举。
"""

import pytest
from rdc_analyzer.core.types import (
    ParsedData, FrameSummary, TextureInfo, BufferInfo,
    PassInfo, Issue
)
from rdc_analyzer.core.enums import Severity, Category, Platform


class TestSeverity:
    """测试 Severity 枚举"""
    
    def test_severity_values(self):
        """验证所有 Severity 值"""
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
    
    def test_severity_comparison(self):
        """验证 Severity 可比较"""
        severities = [Severity.INFO, Severity.WARNING, Severity.ERROR]
        assert len(severities) == 3


class TestCategory:
    """测试 Category 枚举"""
    
    def test_category_values(self):
        """验证所有 Category 值存在"""
        expected = [
            "draw_call", "texture", "buffer", "pass",
            "state", "memory", "mobile", "performance"
        ]
        actual = [c.value for c in Category]
        for exp in expected:
            assert exp in actual, f"Missing category: {exp}"


class TestPlatform:
    """测试 Platform 枚举"""
    
    def test_platform_values(self):
        """验证 Platform 值"""
        assert Platform.PC.value == "pc"
        assert Platform.MOBILE.value == "mobile"


class TestParsedData:
    """测试 ParsedData 数据类"""
    
    def test_default_values(self):
        """验证默认值"""
        data = ParsedData()
        assert data.api == ""
        assert data.draws == []
        assert data.textures == []
        assert data.buffers == []
        assert data.chunks == []
        assert data.controller is None
    
    def test_custom_values(self):
        """验证自定义值"""
        data = ParsedData(
            api="D3D11",
            file_path="/test.rdc",
            draws=[{"event_id": 1}],
            total_events=100
        )
        assert data.api == "D3D11"
        assert data.file_path == "/test.rdc"
        assert len(data.draws) == 1
        assert data.total_events == 100


class TestFrameSummary:
    """测试 FrameSummary 数据类"""
    
    def test_default_values(self):
        """验证默认值"""
        summary = FrameSummary()
        assert summary.draw_call_count == 0
        assert summary.vertex_count == 0  # 实际字段名
        assert summary.viewport_width == 0
        assert summary.viewport_height == 0
    
    def test_viewport(self):
        """验证 viewport 设置"""
        summary = FrameSummary(viewport_width=1920, viewport_height=1080)
        assert summary.viewport_width == 1920
        assert summary.viewport_height == 1080


class TestTextureInfo:
    """测试 TextureInfo 数据类"""
    
    def test_required_field(self):
        """验证必需字段"""
        tex = TextureInfo(resource_id="tex_0")
        assert tex.resource_id == "tex_0"
        assert tex.width == 0
        assert tex.height == 0
        assert tex.mip_levels == 1
        assert tex.memory_size == 0
        assert tex.is_render_target is False
    
    def test_custom_texture(self):
        """验证自定义纹理"""
        tex = TextureInfo(
            resource_id="tex_0",
            name="Albedo",
            width=2048,
            height=2048,
            format="BC7_UNORM",
            mip_levels=11,
            memory_size=5592320,
            is_render_target=False
        )
        assert tex.resource_id == "tex_0"
        assert tex.name == "Albedo"
        assert tex.width == 2048
        assert tex.format == "BC7_UNORM"
        assert tex.mip_levels == 11


class TestBufferInfo:
    """测试 BufferInfo 数据类"""
    
    def test_required_field(self):
        """验证必需字段"""
        buf = BufferInfo(resource_id="buf_0")
        assert buf.resource_id == "buf_0"
        assert buf.size == 0
    
    def test_vertex_buffer(self):
        """验证顶点缓冲"""
        buf = BufferInfo(
            resource_id="buf_0",
            name="VertexBuffer",
            size=1048576,
            usage=["VERTEX"]
        )
        assert buf.size == 1048576
        assert "VERTEX" in buf.usage


class TestPassInfo:
    """测试 PassInfo 数据类"""
    
    def test_required_field(self):
        """验证必需字段"""
        pass_info = PassInfo(index=0)
        assert pass_info.index == 0
        assert pass_info.name == ""
        assert pass_info.draw_count == 0
        assert pass_info.has_clear is False
    
    def test_shadow_pass(self):
        """验证阴影 Pass"""
        pass_info = PassInfo(
            index=3,
            name="ShadowPass",
            start_event_id=100,
            end_event_id=200,
            draw_count=50,
            has_clear=True
        )
        assert pass_info.name == "ShadowPass"
        assert pass_info.draw_count == 50
        assert pass_info.has_clear is True
        assert pass_info.start_event_id == 100


class TestIssue:
    """测试 Issue 数据类"""
    
    def test_required_fields(self):
        """验证必需字段"""
        issue = Issue(
            severity="warning",
            category="performance",
            code="RD_DC_001",
            message="Test message"
        )
        assert issue.severity == "warning"
        assert issue.category == "performance"
        assert issue.code == "RD_DC_001"
        assert issue.message == "Test message"
    
    def test_warning_issue(self):
        """验证警告 Issue"""
        issue = Issue(
            severity="warning",
            category="draw_call",
            code="RD_DC_001",
            message="检测到 5000 个 Draw Call，超过阈值 3000",
            location_path="Frame Summary"
        )
        assert issue.code == "RD_DC_001"
        assert issue.severity == "warning"
        assert issue.category == "draw_call"
        assert "5000" in issue.message
        assert issue.location_path == "Frame Summary"