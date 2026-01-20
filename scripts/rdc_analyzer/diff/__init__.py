"""
RDC 差异对比模块
===============

提供两个 RDC 捕获文件的差异分析功能。

核心组件:
- DiffEngine: 差异对比引擎
- RegressionDetector: 性能回归检测器
- DiffResult: 差异结果数据结构
"""

from .diff_types import (
    DiffResult,
    SummaryDiff,
    MetricDiff,
    ResourceDiff,
    DrawCallDiff,
    TextureDiff,
    ShaderDiff,
    BufferDiff,
    StateDiff,
    DiffStatus,
)
from .diff_engine import DiffEngine
from .regression_types import (
    RegressionRule,
    RegressionRuleId,
    RegressionSeverity,
    RegressionIssue,
    RegressionReport,
    EvidenceAnchor,
    DEFAULT_RULES,
)
from .regression_detector import RegressionDetector
from .diff_html_exporter import DiffHTMLExporter, DiffHTMLConfig

__all__ = [
    # 核心类
    'DiffEngine',
    'RegressionDetector',
    # Diff 数据类型
    'DiffResult',
    'SummaryDiff',
    'MetricDiff',
    'ResourceDiff',
    'DrawCallDiff',
    'TextureDiff',
    'ShaderDiff',
    'BufferDiff',
    'StateDiff',
    'DiffStatus',
    # Regression 数据类型
    'RegressionRule',
    'RegressionRuleId',
    'RegressionSeverity',
    'RegressionIssue',
    'RegressionReport',
    'EvidenceAnchor',
    'DEFAULT_RULES',
    # HTML 导出
    'DiffHTMLExporter',
    'DiffHTMLConfig',
]
