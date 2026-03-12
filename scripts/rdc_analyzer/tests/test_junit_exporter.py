"""
JUnit XML 导出器测试
===================

P5-04: CI 集成支持
"""

import pytest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import tempfile

from rdc_analyzer.diff.junit_exporter import JUnitXMLExporter, export_junit_xml
from rdc_analyzer.diff.diff_types import (
    DiffResult,
    SummaryDiff,
    MetricDiff,
    DiffStatus,
)
from rdc_analyzer.diff.regression_types import (
    RegressionReport,
    RegressionResult,
    RegressionRuleId,
    RegressionSeverity,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_diff_result():
    """创建一个示例 DiffResult
    
    注意: MetricDiff 的签名为 (name, baseline, target)
    delta 和 delta_percent 是计算属性，无需传入
    """
    return DiffResult(
        baseline_file="baseline.json",
        target_file="target.json",
        api_type="D3D12",
        summary=SummaryDiff(
            draw_calls=MetricDiff("draw_calls", baseline=100, target=120),
            triangles=MetricDiff("triangles", baseline=50000, target=55000),
            vertices=MetricDiff("vertices", baseline=150000, target=165000),
            texture_memory=MetricDiff("texture_memory", baseline=100*1024*1024, target=110*1024*1024),
            buffer_memory=MetricDiff("buffer_memory", baseline=50*1024*1024, target=55*1024*1024),
            texture_count=MetricDiff("texture_count", baseline=50, target=55),
            buffer_count=MetricDiff("buffer_count", baseline=30, target=33),
            shader_count=MetricDiff("shader_count", baseline=20, target=22),
        ),
        texture_diffs=[],
        shader_diffs=[],
        buffer_diffs=[],
        draw_call_diffs=[],
    )


@pytest.fixture
def sample_regression_report_clean():
    """创建一个无回归的 RegressionReport"""
    return RegressionReport(
        results=[],
        has_warning=False,
        has_critical=False,
    )


@pytest.fixture
def sample_regression_report_warning():
    """创建一个有警告级回归的 RegressionReport"""
    return RegressionReport(
        results=[
            RegressionResult(
                rule_id=RegressionRuleId.REG001,
                severity=RegressionSeverity.MEDIUM,
                category="DrawCalls",
                metric_name="draw_call_count",
                baseline_value=100,
                target_value=120,
                delta_percent=20.0,
                threshold_percent=10.0,
                message="Draw Call 增加 20%，超过阈值 10%",
                details="Draw Call 数量从 100 增加到 120",
            ),
        ],
        has_warning=True,
        has_critical=False,
    )


@pytest.fixture
def sample_regression_report_critical():
    """创建一个有严重回归的 RegressionReport"""
    return RegressionReport(
        results=[
            RegressionResult(
                rule_id=RegressionRuleId.REG001,
                severity=RegressionSeverity.CRITICAL,
                category="DrawCalls",
                metric_name="draw_call_count",
                baseline_value=100,
                target_value=200,
                delta_percent=100.0,
                threshold_percent=10.0,
                message="Draw Call 翻倍，严重回归",
                details="Draw Call 数量从 100 增加到 200",
            ),
            RegressionResult(
                rule_id=RegressionRuleId.REG005,
                severity=RegressionSeverity.HIGH,
                category="Triangles",
                metric_name="triangle_count",
                baseline_value=50000,
                target_value=80000,
                delta_percent=60.0,
                threshold_percent=20.0,
                message="三角形增加 60%，高级别回归",
                details="三角形数量从 50K 增加到 80K",
            ),
        ],
        has_warning=True,
        has_critical=True,
    )


# ============================================================
# Test: JUnitXMLExporter Initialization
# ============================================================

class TestJUnitXMLExporterInit:
    """测试导出器初始化"""
    
    def test_default_init(self):
        """测试默认初始化"""
        exporter = JUnitXMLExporter()
        assert exporter.suite_name == "RDC Regression Tests"
        assert exporter.include_unchanged is False
    
    def test_custom_init(self):
        """测试自定义初始化"""
        exporter = JUnitXMLExporter(
            suite_name="My Tests",
            include_unchanged=True
        )
        assert exporter.suite_name == "My Tests"
        assert exporter.include_unchanged is True


# ============================================================
# Test: XML Export
# ============================================================

class TestJUnitXMLExport:
    """测试 XML 导出"""
    
    def test_export_basic_structure(self, sample_diff_result, sample_regression_report_clean):
        """测试基本 XML 结构"""
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, sample_regression_report_clean)
        
        # 验证是有效的 XML
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        assert root.tag == "testsuite"
        assert "name" in root.attrib
        assert "tests" in root.attrib
        assert "failures" in root.attrib
        assert "errors" in root.attrib
    
    def test_export_clean_report(self, sample_diff_result, sample_regression_report_clean):
        """测试无回归报告"""
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, sample_regression_report_clean)
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        # 无回归时 failures 应为 0
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        assert failures == 0
        assert errors == 0
    
    def test_export_warning_report(self, sample_diff_result, sample_regression_report_warning):
        """测试有警告的报告"""
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, sample_regression_report_warning)
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        # 应有 failure 元素
        failures = int(root.attrib.get("failures", 0))
        assert failures > 0
        
        # 查找 failure 元素
        failure_elements = root.findall(".//failure")
        assert len(failure_elements) >= 1
    
    def test_export_critical_report(self, sample_diff_result, sample_regression_report_critical):
        """测试严重回归报告"""
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, sample_regression_report_critical)
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        # 应有 error 元素（CRITICAL 级别）
        errors = int(root.attrib.get("errors", 0))
        assert errors >= 1
        
        # 查找 error 元素
        error_elements = root.findall(".//error")
        assert len(error_elements) >= 1
    
    def test_export_properties(self, sample_diff_result, sample_regression_report_clean):
        """测试 properties 元素"""
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, sample_regression_report_clean)
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        # 查找 properties
        properties = root.find("properties")
        assert properties is not None
        
        # 验证属性
        props = {p.attrib["name"]: p.attrib["value"] for p in properties.findall("property")}
        assert "baseline_file" in props
        assert "target_file" in props
        assert "api_type" in props
        assert props["api_type"] == "D3D12"
    
    def test_export_timestamp(self, sample_diff_result, sample_regression_report_clean):
        """测试时间戳"""
        exporter = JUnitXMLExporter()
        
        fixed_time = datetime(2025, 1, 21, 14, 30, 0)
        xml_content = exporter.export(
            sample_diff_result,
            sample_regression_report_clean,
            timestamp=fixed_time
        )
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        timestamp = root.attrib.get("timestamp", "")
        assert "2025-01-21" in timestamp


# ============================================================
# Test: File Save
# ============================================================

class TestJUnitXMLSave:
    """测试文件保存"""
    
    def test_save_to_file(self, sample_diff_result, sample_regression_report_clean):
        """测试保存到文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "junit-report.xml"
            
            exporter = JUnitXMLExporter()
            saved_path = exporter.save(
                str(output_path),
                sample_diff_result,
                sample_regression_report_clean
            )
            
            assert Path(saved_path).exists()
            
            # 验证文件内容是有效 XML
            content = Path(saved_path).read_text(encoding="utf-8")
            assert "<?xml" in content
            assert "<testsuite" in content
    
    def test_save_creates_parent_dirs(self, sample_diff_result, sample_regression_report_clean):
        """测试自动创建父目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "deep" / "junit-report.xml"
            
            exporter = JUnitXMLExporter()
            saved_path = exporter.save(
                str(output_path),
                sample_diff_result,
                sample_regression_report_clean
            )
            
            assert Path(saved_path).exists()


# ============================================================
# Test: Exit Codes
# ============================================================

class TestJUnitXMLExitCodes:
    """测试退出码"""
    
    def test_exit_success(self, sample_regression_report_clean):
        """测试成功退出码"""
        exporter = JUnitXMLExporter()
        exit_code = exporter.get_exit_code(sample_regression_report_clean)
        assert exit_code == JUnitXMLExporter.EXIT_SUCCESS
        assert exit_code == 0
    
    def test_exit_warning(self, sample_regression_report_warning):
        """测试警告退出码"""
        exporter = JUnitXMLExporter()
        exit_code = exporter.get_exit_code(sample_regression_report_warning)
        assert exit_code == JUnitXMLExporter.EXIT_WARNING
        assert exit_code == 1
    
    def test_exit_critical(self, sample_regression_report_critical):
        """测试严重错误退出码"""
        exporter = JUnitXMLExporter()
        exit_code = exporter.get_exit_code(sample_regression_report_critical)
        assert exit_code == JUnitXMLExporter.EXIT_CRITICAL
        assert exit_code == 2


# ============================================================
# Test: Convenience Function
# ============================================================

class TestExportJunitXmlFunction:
    """测试便捷函数"""
    
    def test_export_junit_xml(self, sample_diff_result, sample_regression_report_warning):
        """测试 export_junit_xml 便捷函数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.xml"
            
            saved_path = export_junit_xml(
                sample_diff_result,
                sample_regression_report_warning,
                str(output_path)
            )
            
            assert Path(saved_path).exists()
            
            content = Path(saved_path).read_text(encoding="utf-8")
            assert "<testsuite" in content
            assert "RDC Regression Tests" in content
    
    def test_export_junit_xml_custom_suite(self, sample_diff_result, sample_regression_report_clean):
        """测试自定义 suite 名称"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.xml"
            
            saved_path = export_junit_xml(
                sample_diff_result,
                sample_regression_report_clean,
                str(output_path),
                suite_name="Custom Suite Name"
            )
            
            content = Path(saved_path).read_text(encoding="utf-8")
            assert "Custom Suite Name" in content


# ============================================================
# Test: Edge Cases
# ============================================================

class TestJUnitXMLEdgeCases:
    """测试边界情况"""
    
    def test_empty_regression_list(self, sample_diff_result):
        """测试空回归列表"""
        report = RegressionReport(results=[], has_warning=False, has_critical=False)
        
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, report)
        
        # 应该可以正常生成
        assert "<testsuite" in xml_content
    
    def test_multiple_regressions(self, sample_diff_result):
        """测试多个回归"""
        report = RegressionReport(
            results=[
                RegressionResult(
                    rule_id=RegressionRuleId.REG001,
                    severity=RegressionSeverity.LOW,
                    category="Test",
                    metric_name="metric1",
                    baseline_value=1,
                    target_value=2,
                    delta_percent=100.0,
                    threshold_percent=10.0,
                    message="Regression 1",
                ),
                RegressionResult(
                    rule_id=RegressionRuleId.REG002,
                    severity=RegressionSeverity.MEDIUM,
                    category="Test",
                    metric_name="metric2",
                    baseline_value=10,
                    target_value=15,
                    delta_percent=50.0,
                    threshold_percent=20.0,
                    message="Regression 2",
                ),
                RegressionResult(
                    rule_id=RegressionRuleId.REG003,
                    severity=RegressionSeverity.HIGH,
                    category="Test",
                    metric_name="metric3",
                    baseline_value=100,
                    target_value=200,
                    delta_percent=100.0,
                    threshold_percent=30.0,
                    message="Regression 3",
                ),
            ],
            has_warning=True,
            has_critical=False,
        )
        
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(sample_diff_result, report)
        
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        
        # 应有多个 testcase
        testcases = root.findall(".//testcase")
        # 5 metrics + 3 regression = 至少 8 个
        assert len(testcases) >= 3
    
    def test_special_characters_in_message(self, sample_diff_result):
        """测试消息中的特殊字符"""
        report = RegressionReport(
            results=[
                RegressionResult(
                    rule_id=RegressionRuleId.REG001,
                    severity=RegressionSeverity.MEDIUM,
                    category="Test",
                    metric_name="metric",
                    baseline_value=1,
                    target_value=2,
                    delta_percent=100.0,
                    threshold_percent=10.0,
                    message='Message with <special> & "characters"',
                    details='Details: 100% > 10%',
                ),
            ],
            has_warning=True,
            has_critical=False,
        )
        
        exporter = JUnitXMLExporter()
        
        # 不应抛出异常
        xml_content = exporter.export(sample_diff_result, report)
        
        # XML 应该是有效的
        root = ET.fromstring(xml_content.strip().replace('<?xml version="1.0" ?>\n', ''))
        assert root is not None
