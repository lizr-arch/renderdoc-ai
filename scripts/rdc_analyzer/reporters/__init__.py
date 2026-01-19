"""
报告导出模块
============

支持多种格式的分析报告导出。
"""

from .base import BaseReporter, ReportData
from .json_reporter import JSONReporter
from .csv_reporter import CSVReporter
from .html_reporter import HTMLReporter
from .console_reporter import ConsoleReporter

__all__ = [
    "BaseReporter",
    "ReportData",
    "JSONReporter",
    "CSVReporter", 
    "HTMLReporter",
    "ConsoleReporter",
]

# 报告器注册表
REPORTERS = {
    "json": JSONReporter,
    "csv": CSVReporter,
    "html": HTMLReporter,
    "console": ConsoleReporter,
}


def get_reporter(format_name: str) -> type:
    """获取指定格式的报告器类"""
    if format_name not in REPORTERS:
        raise ValueError(f"Unknown format: {format_name}. Available: {list(REPORTERS.keys())}")
    return REPORTERS[format_name]