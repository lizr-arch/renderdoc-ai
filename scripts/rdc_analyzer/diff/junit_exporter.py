"""
JUnit XML 输出器
================

将 RDC 对比结果输出为 JUnit XML 格式，供 CI 系统（如 GitHub Actions、Jenkins）使用。

P5-04: CI 集成支持
Created: 2026-01-21
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .diff_types import DiffResult, DiffStatus
from .regression_types import RegressionReport, RegressionResult, RegressionSeverity


class JUnitXMLExporter:
    """
    JUnit XML 导出器
    
    将回归检测结果转换为 JUnit XML 格式，CI 系统可识别：
    - 每个回归项生成一个 testcase
    - 回归严重程度映射为 failure/error
    - 输出 testsuite 级别的统计
    
    使用示例:
        exporter = JUnitXMLExporter()
        xml_content = exporter.export(diff_result, regression_report)
        exporter.save("junit-report.xml", diff_result, regression_report)
    """
    
    # 退出码定义
    EXIT_SUCCESS = 0           # 无回归
    EXIT_WARNING = 1           # 有警告级别回归
    EXIT_CRITICAL = 2          # 有严重级别回归
    EXIT_ERROR = 3             # 执行错误
    
    def __init__(
        self,
        suite_name: str = "RDC Regression Tests",
        include_unchanged: bool = False
    ):
        """
        初始化导出器
        
        Args:
            suite_name: 测试套件名称
            include_unchanged: 是否包含未变化的项（通过的测试）
        """
        self.suite_name = suite_name
        self.include_unchanged = include_unchanged
    
    def export(
        self,
        diff_result: DiffResult,
        regression_report: RegressionReport,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        导出为 JUnit XML 字符串
        
        Args:
            diff_result: 差异对比结果
            regression_report: 回归检测报告
            timestamp: 时间戳（默认当前时间）
            
        Returns:
            JUnit XML 格式的字符串
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # 创建 testsuite 根元素
        testsuite = ET.Element("testsuite")
        testsuite.set("name", self.suite_name)
        testsuite.set("timestamp", timestamp.isoformat())
        
        # 统计计数
        tests = 0
        failures = 0
        errors = 0
        skipped = 0
        time_total = 0.0
        
        # 1. 帧级指标测试
        metrics_tests, metrics_failures = self._add_metrics_tests(
            testsuite, diff_result, regression_report
        )
        tests += metrics_tests
        failures += metrics_failures
        
        # 2. 回归规则测试
        for result in regression_report.results:
            tests += 1
            testcase = self._create_regression_testcase(result)
            testsuite.append(testcase)
            
            if result.severity == RegressionSeverity.CRITICAL:
                errors += 1
            elif result.severity in (
                RegressionSeverity.HIGH,
                RegressionSeverity.MEDIUM,
                RegressionSeverity.WARNING,
            ):
                failures += 1
        
        # 3. 资源变化测试（可选）
        if self.include_unchanged:
            resource_tests = self._add_resource_tests(testsuite, diff_result)
            tests += resource_tests
        
        # 设置统计属性
        testsuite.set("tests", str(tests))
        testsuite.set("failures", str(failures))
        testsuite.set("errors", str(errors))
        testsuite.set("skipped", str(skipped))
        testsuite.set("time", f"{time_total:.3f}")
        
        # 添加 properties（元信息）
        properties = ET.SubElement(testsuite, "properties")
        self._add_property(properties, "baseline_file", diff_result.baseline_file)
        self._add_property(properties, "target_file", diff_result.target_file)
        self._add_property(properties, "api_type", diff_result.api_type)
        self._add_property(properties, "has_changes", str(diff_result.has_changes))
        self._add_property(properties, "regression_count", str(len(regression_report.results)))
        
        # 格式化输出
        rough_string = ET.tostring(testsuite, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def save(
        self,
        output_path: str,
        diff_result: DiffResult,
        regression_report: RegressionReport,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        导出并保存为文件
        
        Args:
            output_path: 输出文件路径
            diff_result: 差异对比结果
            regression_report: 回归检测报告
            timestamp: 时间戳
            
        Returns:
            保存的文件路径
        """
        xml_content = self.export(diff_result, regression_report, timestamp)
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(xml_content, encoding="utf-8")
        
        return str(output_file)
    
    def get_exit_code(self, regression_report: RegressionReport) -> int:
        """
        根据回归报告确定退出码
        
        Args:
            regression_report: 回归检测报告
            
        Returns:
            退出码:
            - 0: 成功（无回归）
            - 1: 警告（有中低级别回归）
            - 2: 失败（有严重回归）
        """
        if regression_report.has_critical:
            return self.EXIT_CRITICAL
        elif regression_report.has_warning:
            return self.EXIT_WARNING
        else:
            return self.EXIT_SUCCESS
    
    def _add_metrics_tests(
        self,
        testsuite: ET.Element,
        diff_result: DiffResult,
        regression_report: RegressionReport
    ) -> tuple:
        """添加帧级指标测试"""
        tests = 0
        failures = 0
        
        # 关键指标列表
        key_metrics = [
            ("draw_calls", diff_result.summary.draw_calls, "Draw Call 数量"),
            ("triangles", diff_result.summary.triangles, "三角形数量"),
            ("vertices", diff_result.summary.vertices, "顶点数量"),
            ("texture_memory", diff_result.summary.texture_memory, "纹理内存"),
            ("buffer_memory", diff_result.summary.buffer_memory, "Buffer 内存"),
        ]
        
        for metric_name, metric_diff, description in key_metrics:
            tests += 1
            
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("classname", "RDCRegression.Metrics")
            testcase.set("name", f"metric_{metric_name}")
            testcase.set("time", "0.001")
            
            # 检查是否有相关回归
            is_regression = False
            regression_msg = ""
            
            for result in regression_report.results:
                result_metric = str(result.metric_name or "").lower()
                normalized_metric = {
                    "draw_call_count": "draw_calls",
                    "triangle_count": "triangles",
                }.get(result_metric, result_metric)
                if normalized_metric == metric_name.lower():
                    is_regression = True
                    regression_msg = result.message
                    break
            
            if is_regression:
                failures += 1
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", regression_msg)
                failure.set("type", "RegressionDetected")
                failure.text = (
                    f"Metric: {description}\n"
                    f"Baseline: {metric_diff.baseline}\n"
                    f"Target: {metric_diff.target}\n"
                    f"Delta: {metric_diff.delta:+} ({metric_diff.delta_percent:+.2f}%)"
                )
            else:
                # 添加系统输出信息
                system_out = ET.SubElement(testcase, "system-out")
                system_out.text = (
                    f"{description}: {metric_diff.baseline} → {metric_diff.target} "
                    f"({metric_diff.delta_percent:+.2f}%)"
                )
        
        return tests, failures
    
    def _create_regression_testcase(self, result: RegressionResult) -> ET.Element:
        """为单个回归结果创建 testcase"""
        testcase = ET.Element("testcase")
        testcase.set("classname", f"RDCRegression.{result.category}")
        testcase.set("name", f"regression_{result.rule_id.value}")
        testcase.set("time", "0.001")
        
        # 根据严重程度添加失败信息
        if result.severity == RegressionSeverity.CRITICAL:
            error = ET.SubElement(testcase, "error")
            error.set("message", result.message)
            error.set("type", "CriticalRegression")
            error.text = self._format_regression_details(result)
        elif result.severity in (
            RegressionSeverity.HIGH,
            RegressionSeverity.MEDIUM,
            RegressionSeverity.WARNING,
        ):
            failure = ET.SubElement(testcase, "failure")
            failure.set("message", result.message)
            failure.set("type", f"{result.severity.value}Regression")
            failure.text = self._format_regression_details(result)
        elif result.severity == RegressionSeverity.LOW:
            # 低级别作为通过但有警告
            system_out = ET.SubElement(testcase, "system-out")
            system_out.text = f"[WARNING] {result.message}\n{self._format_regression_details(result)}"
        
        return testcase
    
    def _format_regression_details(self, result: RegressionResult) -> str:
        """格式化回归详情"""
        lines = [
            f"Rule: {result.rule_id.value}",
            f"Category: {result.category}",
            f"Severity: {result.severity.value}",
            f"Metric: {result.metric_name}",
            f"Baseline: {result.baseline_value}",
            f"Target: {result.target_value}",
            f"Delta: {result.delta_percent:+.2f}%",
            f"Threshold: {result.threshold_percent}%",
        ]
        
        if result.details:
            lines.append(f"Details: {result.details}")
        
        return "\n".join(lines)
    
    def _add_resource_tests(
        self,
        testsuite: ET.Element,
        diff_result: DiffResult
    ) -> int:
        """添加资源变化测试（可选，用于详细报告）"""
        tests = 0
        
        # Texture 变化
        for tex_diff in diff_result.texture_diffs:
            tests += 1
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("classname", "RDCRegression.Resources.Textures")
            testcase.set("name", f"texture_{tex_diff.resource_id}")
            testcase.set("time", "0.001")
            
            if tex_diff.status == DiffStatus.ADDED:
                system_out = ET.SubElement(testcase, "system-out")
                system_out.text = f"[ADDED] {tex_diff.name or tex_diff.resource_id}"
            elif tex_diff.status == DiffStatus.REMOVED:
                system_out = ET.SubElement(testcase, "system-out")
                system_out.text = f"[REMOVED] {tex_diff.name or tex_diff.resource_id}"
            elif tex_diff.status == DiffStatus.MODIFIED:
                system_out = ET.SubElement(testcase, "system-out")
                changes_str = ", ".join(f"{k}: {v[0]} → {v[1]}" for k, v in tex_diff.changes.items())
                system_out.text = f"[MODIFIED] {tex_diff.name or tex_diff.resource_id}: {changes_str}"
        
        # Shader 变化
        for shader_diff in diff_result.shader_diffs:
            tests += 1
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("classname", "RDCRegression.Resources.Shaders")
            testcase.set("name", f"shader_{shader_diff.resource_id}")
            testcase.set("time", "0.001")
            
            system_out = ET.SubElement(testcase, "system-out")
            system_out.text = f"[{shader_diff.status.value.upper()}] {shader_diff.shader_type}: {shader_diff.name or shader_diff.resource_id}"
        
        return tests
    
    def _add_property(self, properties: ET.Element, name: str, value: str):
        """添加属性元素"""
        prop = ET.SubElement(properties, "property")
        prop.set("name", name)
        prop.set("value", value)


def export_junit_xml(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str,
    suite_name: str = "RDC Regression Tests"
) -> str:
    """
    便捷函数：导出 JUnit XML
    
    Args:
        diff_result: 差异对比结果
        regression_report: 回归检测报告
        output_path: 输出文件路径
        suite_name: 测试套件名称
        
    Returns:
        保存的文件路径
    """
    exporter = JUnitXMLExporter(suite_name=suite_name)
    return exporter.save(output_path, diff_result, regression_report)
