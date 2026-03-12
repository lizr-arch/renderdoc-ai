"""
RDC Analyzer
============

RenderDoc Capture 文件分析工具包。

自动检测图形渲染性能问题，支持:
- 36 条内置检测规则
- RenderDoc API 和 二进制解析 双模式
- JSON 和 Markdown 报告输出
- PC 和 Mobile 平台优化建议

快速开始:
    from rdc_analyzer import analyze_rdc
    
    result = analyze_rdc("capture.rdc", platform="pc")
    print(f"发现 {len(result.issues)} 个问题")

命令行使用:
    python -m rdc_analyzer capture.rdc --output report.json

版本: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "Graphics Consultant"

# 核心类型
from .core.types import (
    Issue,
    TextureInfo,
    BufferInfo,
    PassInfo,
    FrameSummary,
    ParsedData,
)
from .core.result import AnalysisResult
from .core.context import AnalysisContext
from .core.enums import Severity, Category

# 管线
from .pipeline import AnalysisPipeline, analyze_rdc

# 规则
from .rules import BaseRule, RuleRegistry, RuleRunner, register_all_rules

# 报告
from .reporters import (
    BaseReporter,
    ReportData,
    JSONReporter,
    CSVReporter,
    HTMLReporter,
    ConsoleReporter,
    get_reporter,
)


__all__ = [
    # 版本
    "__version__",
    
    # 核心类型
    "Issue",
    "TextureInfo",
    "BufferInfo",
    "PassInfo",
    "FrameSummary",
    "ParsedData",
    "AnalysisResult",
    "AnalysisContext",
    "Severity",
    "Category",
    
    # 管线
    "AnalysisPipeline",
    "analyze_rdc",
    
    # 规则
    "BaseRule",
    "RuleRegistry",
    "RuleRunner",
    "register_all_rules",
    
    # 报告
    "BaseReporter",
    "ReportData",
    "JSONReporter",
    "CSVReporter",
    "HTMLReporter",
    "ConsoleReporter",
    "get_reporter",
]
