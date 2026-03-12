#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JUnit XML Reporter for RDC Analyzer
====================================

将多帧统计对比结果输出为 JUnit XML 格式，供 CI 系统（Jenkins/GitLab）使用。

格式参考: https://llg.cubic.org/docs/junit/

使用场景:
    - Jenkins Pipeline 集成
    - GitLab CI/CD 测试报告
    - 自动化回归检测 (fail-on-regression)

示例输出:
    <?xml version="1.0" encoding="UTF-8"?>
    <testsuite name="RDC Performance Regression" tests="8" failures="3" errors="0" time="1.234">
        <testcase name="draw_calls" classname="metrics.rendering" time="0.001">
            <failure message="Regression: +15.0% (Z=21.18, p<0.01)" type="HIGH">
                Baseline: 1202.0 (±5.0)
                Target: 1382.0 (±12.5)
                Change: +180.0 (+15.0%)
                Z-score: 21.18 (HIGH significance)
                Effect size: d=17.29 (Large)
            </failure>
        </testcase>
        <testcase name="vertices" classname="metrics.rendering" time="0.001"/>
    </testsuite>

作者: RDC Analyzer Team
版本: 1.0.0
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class JUnitReporter:
    """
    JUnit XML 报告生成器
    
    将 StatisticalSummary 结果转换为标准 JUnit XML 格式。
    
    映射规则:
        - testsuite.name = "RDC Performance Regression"
        - testcase.name = 指标名称 (draw_calls, vertices, etc.)
        - testcase.classname = 指标分类 (metrics.rendering, metrics.memory, etc.)
        - failure = 检测到显著回归
        - pass = 无显著回归或改进
    """
    
    # 指标分类映射
    METRIC_CLASSNAME_MAP = {
        'draw_calls': 'metrics.rendering',
        'vertices': 'metrics.rendering',
        'triangles': 'metrics.rendering',
        'texture_count': 'metrics.memory',
        'texture_memory': 'metrics.memory',
        'buffer_count': 'metrics.memory',
        'buffer_memory': 'metrics.memory',
        'shader_count': 'metrics.shaders',
        'state_changes': 'metrics.rendering',
        'overdraw': 'metrics.rendering',
    }
    
    # 显著性级别映射
    SIGNIFICANCE_THRESHOLDS = {
        'critical': 0.001,  # p < 0.001
        'high': 0.01,       # p < 0.01
        'medium': 0.05,     # p < 0.05
        'low': 0.10,        # p < 0.10
    }
    
    def __init__(
        self,
        suite_name: str = "RDC Performance Regression",
        fail_threshold: str = "medium",
        confidence_level: float = 0.95
    ):
        """
        初始化 JUnit 报告生成器
        
        Args:
            suite_name: 测试套件名称
            fail_threshold: 触发失败的最低回归级别 (low/medium/high/critical)
            confidence_level: 置信水平 (0.90/0.95/0.99)
        """
        self.suite_name = suite_name
        self.fail_threshold = fail_threshold
        self.confidence_level = confidence_level
        self.timestamp = datetime.now().isoformat()
    
    def generate(
        self,
        comparison_result: Dict[str, Any],
        execution_time: float = 0.0
    ) -> str:
        """
        生成 JUnit XML 报告
        
        Args:
            comparison_result: StatisticalSummary 输出的比较结果
            execution_time: 执行时间（秒）
        
        Returns:
            格式化的 JUnit XML 字符串
        """
        # 解析比较结果
        metrics = comparison_result.get('metrics', {})
        significance = comparison_result.get('significance', {})
        baseline_stats = comparison_result.get('baseline', {})
        target_stats = comparison_result.get('target', {})
        
        # 创建根元素
        testsuite = ET.Element('testsuite')
        testsuite.set('name', self.suite_name)
        testsuite.set('timestamp', self.timestamp)
        testsuite.set('time', f"{execution_time:.3f}")
        
        # 统计计数
        total_tests = 0
        failures = 0
        errors = 0
        
        # 添加属性节点
        properties = ET.SubElement(testsuite, 'properties')
        self._add_property(properties, 'confidence_level', str(self.confidence_level))
        self._add_property(properties, 'fail_threshold', self.fail_threshold)
        self._add_property(properties, 'baseline_samples', str(comparison_result.get('baseline_count', 'N/A')))
        self._add_property(properties, 'target_samples', str(comparison_result.get('target_count', 'N/A')))
        
        # 为每个指标创建 testcase
        for metric_name, metric_data in metrics.items():
            total_tests += 1
            testcase = ET.SubElement(testsuite, 'testcase')
            testcase.set('name', metric_name)
            testcase.set('classname', self._get_classname(metric_name))
            testcase.set('time', '0.001')  # 单个指标计算时间可忽略
            
            # 获取显著性信息
            sig_info = significance.get(metric_name, {})
            sig_level = sig_info.get('level', 'none')
            z_score = sig_info.get('z_score', 0.0)
            p_value = sig_info.get('p_value', 1.0)
            effect_size = sig_info.get('effect_size', 0.0)
            
            # 判断是否为回归（且达到失败阈值）
            is_regression = self._is_regression(metric_data)
            is_significant = self._meets_threshold(sig_level)
            
            if is_regression and is_significant:
                failures += 1
                failure = ET.SubElement(testcase, 'failure')
                failure.set('message', self._format_failure_message(
                    metric_name, metric_data, sig_level, z_score, p_value
                ))
                failure.set('type', sig_level.upper())
                failure.text = self._format_failure_details(
                    metric_name, metric_data, sig_info,
                    baseline_stats.get(metric_name, {}),
                    target_stats.get(metric_name, {})
                )
        
        # 设置统计属性
        testsuite.set('tests', str(total_tests))
        testsuite.set('failures', str(failures))
        testsuite.set('errors', str(errors))
        testsuite.set('skipped', '0')
        
        # 格式化输出
        return self._prettify(testsuite)
    
    def save(
        self,
        comparison_result: Dict[str, Any],
        output_path: str,
        execution_time: float = 0.0
    ) -> Path:
        """
        生成并保存 JUnit XML 报告
        
        Args:
            comparison_result: 比较结果
            output_path: 输出文件路径
            execution_time: 执行时间
        
        Returns:
            输出文件的 Path 对象
        """
        xml_content = self.generate(comparison_result, execution_time)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(xml_content, encoding='utf-8')
        return output_file
    
    def _get_classname(self, metric_name: str) -> str:
        """获取指标的 classname 分类"""
        return self.METRIC_CLASSNAME_MAP.get(metric_name, 'metrics.other')
    
    def _is_regression(self, metric_data: Dict) -> bool:
        """判断是否为性能回归（数值增加）"""
        change_pct = metric_data.get('change_pct', 0)
        # 对于 draw_calls/triangles/memory 等，增加表示回归
        return change_pct > 0
    
    def _meets_threshold(self, sig_level: str) -> bool:
        """判断显著性级别是否达到失败阈值"""
        level_order = ['none', 'low', 'medium', 'high', 'critical']
        if sig_level not in level_order:
            return False
        threshold_idx = level_order.index(self.fail_threshold)
        actual_idx = level_order.index(sig_level)
        return actual_idx >= threshold_idx
    
    def _format_failure_message(
        self,
        metric_name: str,
        metric_data: Dict,
        sig_level: str,
        z_score: float,
        p_value: float
    ) -> str:
        """格式化失败消息（简短）"""
        change_pct = metric_data.get('change_pct', 0)
        p_str = f"p<{p_value:.3f}" if p_value < 1 else "p=N/A"
        return f"Regression: {change_pct:+.1f}% (Z={z_score:.2f}, {p_str})"
    
    def _format_failure_details(
        self,
        metric_name: str,
        metric_data: Dict,
        sig_info: Dict,
        baseline_stat: Dict,
        target_stat: Dict
    ) -> str:
        """格式化失败详情（详细）"""
        lines = []
        
        # 基准值
        baseline_mean = baseline_stat.get('mean', metric_data.get('baseline', 'N/A'))
        baseline_std = baseline_stat.get('std', 0)
        lines.append(f"Baseline: {baseline_mean:.1f} (±{baseline_std:.1f})")
        
        # 目标值
        target_mean = target_stat.get('mean', metric_data.get('target', 'N/A'))
        target_std = target_stat.get('std', 0)
        lines.append(f"Target: {target_mean:.1f} (±{target_std:.1f})")
        
        # 变化
        change = metric_data.get('change', 0)
        change_pct = metric_data.get('change_pct', 0)
        lines.append(f"Change: {change:+.1f} ({change_pct:+.1f}%)")
        
        # 统计显著性
        z_score = sig_info.get('z_score', 0)
        sig_level = sig_info.get('level', 'none')
        lines.append(f"Z-score: {z_score:.2f} ({sig_level.upper()} significance)")
        
        # 效应大小
        effect_size = sig_info.get('effect_size', 0)
        effect_label = self._effect_size_label(effect_size)
        lines.append(f"Effect size: d={effect_size:.2f} ({effect_label})")
        
        return '\n'.join(lines)
    
    def _effect_size_label(self, d: float) -> str:
        """Cohen's d 效应大小标签"""
        d_abs = abs(d)
        if d_abs < 0.2:
            return "Negligible"
        elif d_abs < 0.5:
            return "Small"
        elif d_abs < 0.8:
            return "Medium"
        else:
            return "Large"
    
    def _add_property(self, parent: ET.Element, name: str, value: str) -> None:
        """添加 property 元素"""
        prop = ET.SubElement(parent, 'property')
        prop.set('name', name)
        prop.set('value', value)
    
    def _prettify(self, elem: ET.Element) -> str:
        """格式化 XML 输出"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding=None)


def generate_junit_report(
    comparison_result: Dict[str, Any],
    output_path: str,
    fail_threshold: str = "medium",
    confidence_level: float = 0.95,
    execution_time: float = 0.0
) -> Path:
    """
    便捷函数：生成 JUnit XML 报告
    
    Args:
        comparison_result: StatisticalSummary 输出
        output_path: 输出路径
        fail_threshold: 失败阈值
        confidence_level: 置信水平
        execution_time: 执行时间
    
    Returns:
        输出文件路径
    """
    reporter = JUnitReporter(
        fail_threshold=fail_threshold,
        confidence_level=confidence_level
    )
    return reporter.save(comparison_result, output_path, execution_time)


# 测试代码
if __name__ == '__main__':
    # 模拟比较结果
    mock_result = {
        'baseline_count': 3,
        'target_count': 3,
        'metrics': {
            'draw_calls': {
                'baseline': 1202,
                'target': 1382,
                'change': 180,
                'change_pct': 15.0
            },
            'vertices': {
                'baseline': 450000,
                'target': 521000,
                'change': 71000,
                'change_pct': 15.8
            },
            'triangles': {
                'baseline': 150000,
                'target': 173333,
                'change': 23333,
                'change_pct': 15.6
            }
        },
        'significance': {
            'draw_calls': {
                'level': 'high',
                'z_score': 21.18,
                'p_value': 0.001,
                'effect_size': 17.29
            },
            'vertices': {
                'level': 'high',
                'z_score': 29.83,
                'p_value': 0.001,
                'effect_size': 24.35
            },
            'triangles': {
                'level': 'high',
                'z_score': 22.14,
                'p_value': 0.001,
                'effect_size': 18.07
            }
        },
        'baseline': {
            'draw_calls': {'mean': 1202, 'std': 5},
            'vertices': {'mean': 450000, 'std': 2000},
            'triangles': {'mean': 150000, 'std': 1000}
        },
        'target': {
            'draw_calls': {'mean': 1382, 'std': 12.5},
            'vertices': {'mean': 521000, 'std': 3500},
            'triangles': {'mean': 173333, 'std': 1500}
        }
    }
    
    # 生成报告
    reporter = JUnitReporter(fail_threshold='medium')
    xml_output = reporter.generate(mock_result, execution_time=1.234)
    print(xml_output)
