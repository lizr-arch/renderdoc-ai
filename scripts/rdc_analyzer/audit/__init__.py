"""
资产审计模块
============

单帧资源分析模式，检测资源的绝对问题（无需对比基准）。

使用方式:
    from rdc_analyzer.audit import AuditEngine, AuditReport
    
    engine = AuditEngine(platform="mobile")
    report = engine.audit(capture_data)
    print(report.summary())
"""

from .engine import AuditEngine
from .report import AuditReport, AuditSummary, AssetCategory

__all__ = [
    "AuditEngine",
    "AuditReport",
    "AuditSummary",
    "AssetCategory",
]
