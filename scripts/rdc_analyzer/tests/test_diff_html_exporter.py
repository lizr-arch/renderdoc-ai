"""
DiffHTMLExporter 单元测试
========================

测试 HTML 对比报告生成功能。
"""

import pytest
from pathlib import Path
import tempfile

from rdc_analyzer.diff import (
    DiffResult,
    SummaryDiff,
    MetricDiff,
    DiffStatus,
    TextureDiff,
    ShaderDiff,
    BufferDiff,
    DrawCallDiff,
    RegressionReport,
    RegressionIssue,
    RegressionSeverity,
    RegressionRuleId,
    DiffHTMLExporter,
    DiffHTMLConfig,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_diff() -> DiffResult:
    """创建示例差异结果"""
    result = DiffResult()
    result.baseline_file = "baseline_v1.json"
    result.target_file = "target_v2.json"
    result.api_type = "D3D12"
    
    # 设置摘要指标
    result.summary = SummaryDiff(
        draw_calls=MetricDiff("draw_calls", 100, 120),
        triangles=MetricDiff("triangles", 50000, 60000),
        vertices=MetricDiff("vertices", 100000, 110000),
        texture_count=MetricDiff("texture_count", 50, 52),
        buffer_count=MetricDiff("buffer_count", 30, 30),
        shader_count=MetricDiff("shader_count", 20, 22),
        texture_memory=MetricDiff("texture_memory", 100*1024*1024, 120*1024*1024),
        buffer_memory=MetricDiff("buffer_memory", 50*1024*1024, 50*1024*1024),
    )
    
    # 添加纹理差异
    result.texture_diffs = [
        TextureDiff(
            resource_id="tex_001",
            name="MainAlbedo",
            status=DiffStatus.ADDED,
            width=1024,
            height=1024,
            format="BC7_UNORM",
            memory_size=1024*1024,
        ),
        TextureDiff(
            resource_id="tex_002",
            name="ShadowMap",
            status=DiffStatus.MODIFIED,
            width=2048,
            height=2048,
            format="R32_FLOAT",
            memory_size=16*1024*1024,
            changes={"width": (1024, 2048), "height": (1024, 2048)},
        ),
    ]
    
    # 添加 Shader 差异
    result.shader_diffs = [
        ShaderDiff(
            resource_id="shader_001",
            name="PBR_PS",
            status=DiffStatus.MODIFIED,
            shader_type="PS",
            hash="abc123def456",
        ),
    ]
    
    # 添加 Buffer 差异
    result.buffer_diffs = [
        BufferDiff(
            resource_id="buf_001",
            name="VertexBuffer",
            status=DiffStatus.MODIFIED,
            size=8*1024*1024,
            usage="vertex",
            changes={"size": (4*1024*1024, 8*1024*1024)},
        ),
    ]
    
    # 添加 Draw Call 差异
    result.draw_call_diffs = [
        DrawCallDiff(
            event_id=100,
            status=DiffStatus.ADDED,
            draw_type="DrawIndexed",
            vertex_count=3000,
            index_count=9000,
        ),
        DrawCallDiff(
            event_id=50,
            status=DiffStatus.MODIFIED,
            matched_event_id=52,
            draw_type="DrawIndexed",
            vertex_count=1500,
            index_count=4500,
        ),
    ]
    
    return result


@pytest.fixture
def sample_regression() -> RegressionReport:
    """创建示例回归报告"""
    report = RegressionReport(
        rules_checked=7,
        rules_triggered=3,
        issues=[
            RegressionIssue(
                rule_id=RegressionRuleId.REG001,
                severity=RegressionSeverity.WARNING,
                message="Draw Call 数量增加 20%",
                details="从 100 增加到 120",
                baseline_value=100,
                target_value=120,
                delta_percent=20.0,
            ),
            RegressionIssue(
                rule_id=RegressionRuleId.REG005,
                severity=RegressionSeverity.CRITICAL,
                message="三角形数量增加 20%",
                details="从 50000 增加到 60000",
                baseline_value=50000,
                target_value=60000,
                delta_percent=20.0,
            ),
            RegressionIssue(
                rule_id=RegressionRuleId.REG003,
                severity=RegressionSeverity.INFO,
                message="检测到 Shader 变更",
                details="1 个 Shader 被修改",
            ),
        ],
    )
    return report


# ============================================================
# Basic Export Tests
# ============================================================

class TestBasicExport:
    """基础导出测试"""
    
    def test_export_returns_html_string(self, sample_diff):
        """测试导出返回 HTML 字符串"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
    
    def test_export_contains_title(self, sample_diff):
        """测试导出包含标题"""
        config = DiffHTMLConfig(title="My Custom Report")
        exporter = DiffHTMLExporter(config)
        html = exporter.export(sample_diff)
        
        assert "My Custom Report" in html
    
    def test_export_contains_file_info(self, sample_diff):
        """测试导出包含文件信息"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "baseline_v1.json" in html
        assert "target_v2.json" in html
        assert "D3D12" in html
    
    def test_export_to_file(self, sample_diff):
        """测试导出到文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            
            exporter = DiffHTMLExporter()
            exporter.export(sample_diff, output_path=output_path)
            
            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content


# ============================================================
# Statistics Tests
# ============================================================

class TestStatistics:
    """统计卡片测试"""
    
    def test_stats_grid_rendered(self, sample_diff):
        """测试统计网格被渲染"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "stats-grid" in html
        assert "stat-card" in html
    
    def test_draw_call_increase_shown(self, sample_diff):
        """测试 Draw Call 增加被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "Draw Calls" in html
        # 120 = target value
        assert "120" in html
    
    def test_memory_formatted(self, sample_diff):
        """测试内存值被格式化"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        # 120 MB texture memory
        assert "120" in html and "MB" in html
    
    def test_stats_can_be_disabled(self, sample_diff):
        """测试统计可以被禁用"""
        config = DiffHTMLConfig(include_summary=False)
        exporter = DiffHTMLExporter(config)
        html = exporter.export(sample_diff)
        
        # CSS 中仍有 .stats-grid 定义，但不应有实际渲染的统计卡片
        assert '<div class="stats-grid">' not in html
        assert "stat-card increase" not in html


# ============================================================
# Regression Panel Tests
# ============================================================

class TestRegressionPanel:
    """回归面板测试"""
    
    def test_critical_banner_shown(self, sample_diff, sample_regression):
        """测试严重回归横幅显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff, regression=sample_regression)
        
        assert "regression-banner" in html
        assert "critical" in html
        assert "严重回归问题" in html
    
    def test_issues_sorted_by_severity(self, sample_diff, sample_regression):
        """测试问题按严重程度排序"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff, regression=sample_regression)
        
        # CRITICAL (REG005) 应该在 WARNING (REG001) 之前
        critical_pos = html.find("REG005")
        warning_pos = html.find("REG001")
        
        assert critical_pos < warning_pos
    
    def test_issue_values_displayed(self, sample_diff, sample_regression):
        """测试问题数值被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff, regression=sample_regression)
        
        assert "50000" in html  # baseline triangles
        assert "60000" in html  # target triangles
        assert "+20" in html    # delta percent
    
    def test_clean_banner_when_no_issues(self, sample_diff):
        """测试无问题时显示通过横幅"""
        report = RegressionReport(rules_checked=7, rules_triggered=0, issues=[])
        
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff, regression=report)
        
        assert "clean" in html or "通过" in html
    
    def test_regression_panel_can_be_disabled(self, sample_diff, sample_regression):
        """测试回归面板可以被禁用"""
        config = DiffHTMLConfig(include_regression_panel=False)
        exporter = DiffHTMLExporter(config)
        html = exporter.export(sample_diff, regression=sample_regression)
        
        # 不应显示回归问题内容
        assert "REG001" not in html


# ============================================================
# Resource Diff Tests
# ============================================================

class TestResourceDiff:
    """资源差异测试"""
    
    def test_tabs_rendered(self, sample_diff):
        """测试标签页被渲染"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "tab-btn" in html
        assert "纹理" in html
        assert "Shader" in html
        assert "缓冲区" in html
    
    def test_texture_diff_shown(self, sample_diff):
        """测试纹理差异被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "MainAlbedo" in html
        assert "ShadowMap" in html
        assert "BC7_UNORM" in html
    
    def test_status_badges_shown(self, sample_diff):
        """测试状态徽章被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "status-badge" in html
        assert "added" in html
        assert "modified" in html
    
    def test_shader_diff_shown(self, sample_diff):
        """测试 Shader 差异被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "PBR_PS" in html
        assert "PS" in html  # shader type
    
    def test_buffer_diff_shown(self, sample_diff):
        """测试缓冲区差异被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "VertexBuffer" in html
        assert "vertex" in html  # usage
    
    def test_drawcall_diff_shown(self, sample_diff):
        """测试 Draw Call 差异被显示"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        assert "DrawIndexed" in html
        # Event ID 100
        assert ">100<" in html or ">100 " in html or "100</" in html


# ============================================================
# Theme Tests
# ============================================================

class TestThemes:
    """主题测试"""
    
    def test_dark_theme_default(self, sample_diff):
        """测试默认使用暗色主题"""
        exporter = DiffHTMLExporter()
        html = exporter.export(sample_diff)
        
        # 暗色主题背景色
        assert "#0d1117" in html
    
    def test_light_theme(self, sample_diff):
        """测试亮色主题"""
        config = DiffHTMLConfig(theme="light")
        exporter = DiffHTMLExporter(config)
        html = exporter.export(sample_diff)
        
        # 亮色主题背景色
        assert "#f6f8fa" in html


# ============================================================
# Empty State Tests
# ============================================================

class TestEmptyStates:
    """空状态测试"""
    
    def test_empty_texture_diff(self):
        """测试空纹理差异显示"""
        diff = DiffResult()
        diff.texture_diffs = []
        
        exporter = DiffHTMLExporter()
        html = exporter.export(diff)
        
        assert "无纹理变化" in html
    
    def test_empty_shader_diff(self):
        """测试空 Shader 差异显示"""
        diff = DiffResult()
        diff.shader_diffs = []
        
        exporter = DiffHTMLExporter()
        html = exporter.export(diff)
        
        assert "无 Shader 变化" in html
    
    def test_no_regression_run(self):
        """测试未运行回归检测显示"""
        diff = DiffResult()
        
        exporter = DiffHTMLExporter()
        html = exporter.export(diff, regression=None)
        
        assert "未运行回归检测" in html


# ============================================================
# Integration Test
# ============================================================

class TestIntegration:
    """集成测试"""
    
    def test_full_pipeline(self, sample_diff, sample_regression):
        """测试完整流水线"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "full_report.html"
            
            config = DiffHTMLConfig(
                title="Integration Test Report",
                theme="dark",
                include_summary=True,
                include_regression_panel=True,
                include_resource_diff=True,
                include_draw_calls=True,
            )
            
            exporter = DiffHTMLExporter(config)
            html = exporter.export(
                sample_diff,
                regression=sample_regression,
                output_path=output_path,
            )
            
            # 验证文件生成
            assert output_path.exists()
            
            # 验证内容完整性
            assert "Integration Test Report" in html
            assert "baseline_v1.json" in html
            assert "REG005" in html  # Critical issue
            assert "MainAlbedo" in html  # Texture
            assert "PBR_PS" in html  # Shader
            assert "VertexBuffer" in html  # Buffer
            assert "DrawIndexed" in html  # Draw call
