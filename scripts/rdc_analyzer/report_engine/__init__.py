"""
Report Engine - 模块化 HTML 报告生成引擎

此包提供统一的报告生成接口，将数据提取与渲染解耦。

Architecture:
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Adapters   │────►│  Contract   │────►│  Renderer   │
    │ (数据适配)  │     │ (数据契约)  │     │ (HTML渲染)  │
    └─────────────┘     └─────────────┘     └─────────────┘

Usage:
    from rdc_analyzer.report_engine import ReportDataContract, HtmlRenderer
    
    # 1. 创建数据契约
    contract = ReportDataContract(
        meta={"capture_name": "test.rdc"},
        textures=[...],
        events=[...]
    )
    
    # 2. 渲染 HTML
    renderer = HtmlRenderer(contract)
    html = renderer.render()

Version: 1.0.0
"""

from .contract import ReportDataContract, MetaData, build_manifest

__version__ = "1.0.0"
__all__ = [
    "ReportDataContract",
    "MetaData", 
    "build_manifest",
]
