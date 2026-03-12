"""
Renderers - Report output renderers

提供将 ReportDataContract 渲染为各种输出格式的渲染器。

Available Renderers:
    - HtmlRenderer: 生成完整 HTML 报告
    - JsonRenderer: 生成 JSON 格式输出
"""
from .html_renderer import HtmlRenderer
from .json_renderer import (
    JsonRenderer,
    render_contract_to_json,
    contract_to_dict,
)

__all__ = [
    # HTML
    "HtmlRenderer",
    # JSON
    "JsonRenderer",
    "render_contract_to_json",
    "contract_to_dict",
]