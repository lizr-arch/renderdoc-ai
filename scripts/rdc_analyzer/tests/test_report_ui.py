"""
Report UI Shell 单元测试
测试四视图骨架布局生成
"""
import unittest
from scripts.rdc_analyzer.report_ui import (
    render_report_shell,
    render_issues_view,
    render_manifest_bar,
    ReportUIConfig,
)


class TestReportUIConfig(unittest.TestCase):
    """测试 UI 配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = ReportUIConfig()
        self.assertEqual(config.theme, "dark")
        self.assertTrue(config.show_manifest_bar)
        self.assertEqual(config.default_view, "issues")

    def test_custom_config(self):
        """测试自定义配置"""
        config = ReportUIConfig(theme="light", default_view="events")
        self.assertEqual(config.theme, "light")
        self.assertEqual(config.default_view, "events")


class TestRenderReportShell(unittest.TestCase):
    """测试主报告骨架渲染"""

    def test_returns_html_string(self):
        """测试返回 HTML 字符串"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract(
            meta={"title": "Test Report", "api": "D3D11"}
        )
        html = render_report_shell(contract)
        
        self.assertIsInstance(html, str)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)

    def test_contains_four_view_tabs(self):
        """测试包含四视图标签"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract()
        html = render_report_shell(contract)
        
        # 四个主视图标签
        self.assertIn("Issues", html)
        self.assertIn("Events", html)
        self.assertIn("Resources", html)
        self.assertIn("Performance", html)

    def test_contains_manifest_bar(self):
        """测试包含 Manifest 状态栏"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract(
            meta={"title": "Test"},
            textures=[{"name": "tex1", "width": 512, "height": 512}]
        )
        html = render_report_shell(contract)
        
        # Manifest 栏应显示覆盖率和计数
        self.assertIn("coverage", html.lower())

    def test_dark_theme_css(self):
        """测试深色主题 CSS"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract()
        config = ReportUIConfig(theme="dark")
        html = render_report_shell(contract, config)
        
        # 深色主题背景色
        self.assertIn("#1e1e1e", html)  # VS Code dark background


class TestIssuesView(unittest.TestCase):
    """测试 Issues 视图渲染"""

    def test_empty_issues(self):
        """测试无问题时显示"""
        html = render_issues_view([])
        self.assertIn("no issues", html.lower())

    def test_issues_grouped_by_severity(self):
        """测试问题按严重性分组"""
        from scripts.rdc_analyzer.core.issue_detector import Issue, Severity, Category
        
        issues = [
            Issue(Severity.CRITICAL, Category.TEXTURE, "Critical Bug", "desc"),
            Issue(Severity.WARNING, Category.SHADER, "Warning", "desc"),
            Issue(Severity.INFO, Category.BUFFER, "Info", "desc"),
        ]
        html = render_issues_view(issues)
        
        # 应有严重性分组标题
        self.assertIn("critical", html.lower())
        self.assertIn("warning", html.lower())


class TestManifestBar(unittest.TestCase):
    """测试 Manifest 状态栏"""

    def test_coverage_display(self):
        """测试覆盖率显示"""
        manifest = {
            "coverage_percent": 85.5,
            "counts": {"textures": 10, "events": 100},
        }
        html = render_manifest_bar(manifest)
        
        self.assertIn("85", html)  # 显示覆盖率
        self.assertIn("10", html)  # 显示纹理数量

    def test_low_coverage_warning(self):
        """测试低覆盖率警告"""
        manifest = {
            "coverage_percent": 50.0,
            "counts": {"textures": 0, "events": 0},
        }
        html = render_manifest_bar(manifest)
        
        # 低覆盖率应有视觉警告
        self.assertIn("warning", html.lower())


if __name__ == "__main__":
    unittest.main()
