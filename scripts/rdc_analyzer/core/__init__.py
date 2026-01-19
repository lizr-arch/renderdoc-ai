"""
核心模块
========

包含:
- enums: 枚举类型 (Severity, Category)
- types: 数据类型 (TextureInfo, DrawCallInfo 等)
- result: 分析结果 (AnalysisResult)
- context: 分析上下文 (AnalysisContext)
"""

from .enums import Severity, Category
from .types import (
    TextureInfo,
    BufferInfo,
    ShaderInfo,
    PassInfo,
    RenderPassInfo,
    DrawCallInfo,
    Issue,
    FrameSummary,
    ParsedData,
    # C.1: 性能分析类型
    PerformanceMetrics,
    PerformanceIssue,
    PerformanceReport,
    PerformanceRule,
    PERFORMANCE_RULES,
    OverdrawInfo,
    StateRedundancy,
    BatchAnalysis,
    TextureAnalysis,
)
from .result import AnalysisResult
from .context import AnalysisContext

__all__ = [
    # Enums
    "Severity",
    "Category",
    # Types
    "TextureInfo",
    "BufferInfo",
    "ShaderInfo",
    "PassInfo",
    "RenderPassInfo",
    "DrawCallInfo",
    "Issue",
    "FrameSummary",
    "ParsedData",
    # C.1: Performance Types
    "PerformanceMetrics",
    "PerformanceIssue",
    "PerformanceReport",
    "PerformanceRule",
    "PERFORMANCE_RULES",
    "OverdrawInfo",
    "StateRedundancy",
    "BatchAnalysis",
    "TextureAnalysis",
    # Result
    "AnalysisResult",
    # Context
    "AnalysisContext",
]
