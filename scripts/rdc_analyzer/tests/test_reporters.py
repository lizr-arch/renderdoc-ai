"""
报告器测试
==========

测试所有报告生成器。
"""

import json
import pytest
from datetime import datetime

from rdc_analyzer.reporters.base import ReportData, BaseReporter
from rdc_analyzer.reporters.json_reporter import JSONReporter
from rdc_analyzer.reporters.csv_reporter import CSVReporter
from rdc_analyzer.reporters.html_reporter import HTMLReporter
from rdc_analyzer.reporters.console_reporter import ConsoleReporter
from rdc_analyzer.reporters import get_reporter, REPORTERS
from rdc_analyzer.core.types import Issue, FrameSummary
from rdc_analyzer.core.enums import Severity, Category


class TestReportData:
    """测试 ReportData 数据容器"""
    
    @pytest.fixture
    def sample_issues(self):
        """创建示例问题列表"""
        return [
            Issue(
                code="RD_DC_001",
                severity=Severity.ERROR,
                category=Category.DRAW_CALL,
                message="Draw call count too high: 5000",
                location_path="Frame/Scene/Objects"
            ),
            Issue(
                code="RD_TEX_001",
                severity=Severity.WARNING,
                category=Category.TEXTURE,
                message="Large texture detected: 4096x4096",
                suggestion="Consider using mipmaps"
            ),
            Issue(
                code="RD_BUF_001",
                severity=Severity.INFO,
                category=Category.BUFFER,
                message="Buffer usage is optimal"
            ),
        ]
    
    @pytest.fixture
    def sample_report_data(self, sample_issues):
        """创建示例报告数据"""
        return ReportData(
            file_path="test_capture.rdc",
            platform="pc",
            api="D3D11",
            frame_summary=FrameSummary(
                draw_call_count=5000,
                vertex_count=1000000,
                primitive_count=333333,
                texture_count=50,
                total_texture_memory=256*1024*1024,
                buffer_count=100,
                total_buffer_memory=64*1024*1024,
            ),
            issues=sample_issues,
        )
    
    def test_error_count(self, sample_report_data):
        """验证错误计数"""
        assert sample_report_data.error_count == 1
    
    def test_warning_count(self, sample_report_data):
        """验证警告计数"""
        assert sample_report_data.warning_count == 1
    
    def test_info_count(self, sample_report_data):
        """验证信息计数"""
        assert sample_report_data.info_count == 1
    
    def test_has_issues(self, sample_report_data):
        """验证问题存在检测"""
        assert sample_report_data.has_issues is True
        
        empty_data = ReportData()
        assert empty_data.has_issues is False
    
    def test_to_dict(self, sample_report_data):
        """验证字典转换"""
        data_dict = sample_report_data.to_dict()
        
        assert "metadata" in data_dict
        assert "summary" in data_dict
        assert "frame_summary" in data_dict
        assert "issues" in data_dict
        
        assert data_dict["metadata"]["platform"] == "pc"
        assert data_dict["summary"]["total_issues"] == 3
        assert len(data_dict["issues"]) == 3


class TestJSONReporter:
    """测试 JSON 报告器"""
    
    @pytest.fixture
    def json_reporter(self, sample_report_data):
        """创建 JSON 报告器"""
        return JSONReporter(sample_report_data)
    
    @pytest.fixture
    def sample_report_data(self):
        """创建示例报告数据"""
        return ReportData(
            file_path="test.rdc",
            platform="pc",
            api="D3D11",
            issues=[
                Issue(
                    code="RD_TEST_001",
                    severity=Severity.WARNING,
                    category=Category.DRAW_CALL,
                    message="Test issue"
                )
            ]
        )
    
    def test_generate_valid_json(self, json_reporter):
        """验证生成有效 JSON"""
        output = json_reporter.generate()
        
        # 应该能解析为 JSON
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
    
    def test_json_structure(self, json_reporter):
        """验证 JSON 结构"""
        output = json_reporter.generate()
        parsed = json.loads(output)
        
        assert "metadata" in parsed
        assert "summary" in parsed
        assert "issues" in parsed
    
    def test_generate_minimal(self, json_reporter):
        """验证最小化 JSON"""
        minimal = json_reporter.generate_minimal()
        
        # 不应包含换行
        assert "\n" not in minimal
        
        # 仍是有效 JSON
        parsed = json.loads(minimal)
        assert isinstance(parsed, dict)
    
    def test_file_extension(self, json_reporter):
        """验证文件扩展名"""
        assert json_reporter.file_extension == ".json"


class TestCSVReporter:
    """测试 CSV 报告器"""
    
    @pytest.fixture
    def csv_reporter(self):
        """创建 CSV 报告器"""
        data = ReportData(
            file_path="test.rdc",
            platform="pc",
            api="D3D11",
            issues=[
                Issue(
                    code="RD_TEST_001",
                    severity=Severity.ERROR,
                    category=Category.TEXTURE,
                    message="Test error"
                )
            ]
        )
        return CSVReporter(data)
    
    def test_generate_csv(self, csv_reporter):
        """验证生成 CSV"""
        output = csv_reporter.generate()
        
        assert "RDC Analyzer Report" in output
        assert "RD_TEST_001" in output
        assert "ERROR" in output
    
    def test_csv_columns(self, csv_reporter):
        """验证 CSV 列"""
        output = csv_reporter.generate()
        
        for col in CSVReporter.ISSUE_COLUMNS:
            assert col in output
    
    def test_bom_included(self, csv_reporter):
        """验证 UTF-8 BOM"""
        output = csv_reporter.generate()
        assert output.startswith('\ufeff')
    
    def test_no_bom(self):
        """验证无 BOM 选项"""
        data = ReportData(file_path="test.rdc")
        reporter = CSVReporter(data, include_bom=False)
        output = reporter.generate()
        
        assert not output.startswith('\ufeff')
    
    def test_file_extension(self, csv_reporter):
        """验证文件扩展名"""
        assert csv_reporter.file_extension == ".csv"


class TestHTMLReporter:
    """测试 HTML 报告器"""
    
    @pytest.fixture
    def html_reporter(self):
        """创建 HTML 报告器"""
        data = ReportData(
            file_path="test.rdc",
            platform="pc",
            api="D3D11",
            frame_summary=FrameSummary(
                draw_call_count=1000,
                vertex_count=100000,
            ),
            issues=[
                Issue(
                    code="RD_TEST_001",
                    severity=Severity.WARNING,
                    category=Category.DRAW_CALL,
                    message="Test warning",
                    suggestion="Fix it"
                )
            ]
        )
        return HTMLReporter(data)
    
    def test_generate_valid_html(self, html_reporter):
        """验证生成有效 HTML"""
        output = html_reporter.generate()
        
        assert output.startswith("<!DOCTYPE html>")
        assert "<html" in output
        assert "</html>" in output
    
    def test_html_contains_styles(self, html_reporter):
        """验证包含样式"""
        output = html_reporter.generate()
        assert "<style>" in output
        assert "</style>" in output
    
    def test_html_contains_scripts(self, html_reporter):
        """验证包含脚本"""
        output = html_reporter.generate()
        assert "<script>" in output
        assert "</script>" in output
    
    def test_html_contains_issues(self, html_reporter):
        """验证包含问题"""
        output = html_reporter.generate()
        assert "RD_TEST_001" in output
        assert "Test warning" in output
    
    def test_html_contains_stats(self, html_reporter):
        """验证包含统计"""
        output = html_reporter.generate()
        assert "1,000" in output  # draw calls
    
    def test_file_extension(self, html_reporter):
        """验证文件扩展名"""
        assert html_reporter.file_extension == ".html"


class TestConsoleReporter:
    """测试控制台报告器"""
    
    @pytest.fixture
    def console_reporter(self):
        """创建控制台报告器"""
        data = ReportData(
            file_path="test.rdc",
            platform="mobile",
            api="GLES",
            issues=[
                Issue(
                    code="RD_MOB_001",
                    severity=Severity.ERROR,
                    category=Category.MOBILE,
                    message="TBDR flush detected"
                )
            ]
        )
        return ConsoleReporter(data, use_colors=False)
    
    def test_generate_text(self, console_reporter):
        """验证生成文本"""
        output = console_reporter.generate()
        
        assert "RDC 性能分析报告" in output
        assert "RD_MOB_001" in output
    
    def test_contains_metadata(self, console_reporter):
        """验证包含元数据"""
        output = console_reporter.generate()
        
        assert "test.rdc" in output
        assert "MOBILE" in output
        assert "GLES" in output
    
    def test_generate_brief(self, console_reporter):
        """验证简短摘要"""
        brief = console_reporter.generate_brief()
        
        assert "FAIL" in brief  # 有错误
        assert "1 errors" in brief
    
    def test_no_colors(self, console_reporter):
        """验证无颜色模式"""
        output = console_reporter.generate()
        
        # 不应包含 ANSI 转义序列
        assert "\033[" not in output
    
    def test_with_colors(self):
        """验证彩色模式"""
        data = ReportData(file_path="test.rdc")
        reporter = ConsoleReporter(data, use_colors=True)
        output = reporter.generate()
        
        # 应包含 ANSI 转义序列
        assert "\033[" in output
    
    def test_file_extension(self, console_reporter):
        """验证文件扩展名"""
        assert console_reporter.file_extension == ".txt"


class TestReporterRegistry:
    """测试报告器注册表"""
    
    def test_all_formats_registered(self):
        """验证所有格式已注册"""
        expected = ["json", "csv", "html", "console"]
        for fmt in expected:
            assert fmt in REPORTERS
    
    def test_get_reporter(self):
        """验证获取报告器"""
        assert get_reporter("json") == JSONReporter
        assert get_reporter("csv") == CSVReporter
        assert get_reporter("html") == HTMLReporter
        assert get_reporter("console") == ConsoleReporter
    
    def test_get_unknown_reporter(self):
        """验证获取未知报告器抛出异常"""
        with pytest.raises(ValueError):
            get_reporter("unknown_format")
