"""
Report Engine - RDC 报告生成引擎 v2.2

提供模块化的报告生成功能，支持从不同数据源生成统一格式的 HTML/JSON 报告。

Architecture:
    DataSource (RDC/XML/JSON) 
        → Adapter (RdcAdapter/XmlAdapter)
        → ReportDataContract 
        → Renderer (HtmlRenderer/JsonRenderer)
        → Report (HTML/JSON)

Quick Start:
    from report_engine import ReportDataContract, HtmlRenderer, JsonRenderer
    
    contract = ReportDataContract(
        textures=[...],
        optimization_data={...}
    )
    
    # HTML 输出
    html_renderer = HtmlRenderer()
    html = html_renderer.render(contract, "my_capture.rdc")
    
    # JSON 输出
    json_renderer = JsonRenderer()
    json_str = json_renderer.render(contract)

Modules:
    - contract: 数据契约定义 (ReportDataContract, MetaData)
    - schemas: 字段结构定义 (ShaderSchema, PipelineStateSchema, etc.)
    - adapters: 数据适配器 (RdcAdapter, XmlAdapter, JsonAdapter)
    - renderers: 渲染器 (HtmlRenderer, JsonRenderer)
    - sections: HTML Section 生成器
    - assets: 静态资源 (CSS, JS 模板)
"""

from .contract import ReportDataContract, MetaData
from .renderers import HtmlRenderer, JsonRenderer, render_contract_to_json
from .adapters import XmlAdapter, load_xml_to_contract

# Schema imports (optional, for type hints and validation)
from .schemas import (
    ShaderSchema,
    PipelineStateSchema,
    TextureSchema,
    EventSchema,
    ShaderStage,
    TextureType,
    FillMode,
    CullMode,
    CompareFunc,
    validate_shader_dict,
    validate_pipeline_state_dict,
    validate_texture_dict,
    validate_event_dict,
)

__all__ = [
    # Core
    "ReportDataContract",
    "MetaData",
    
    # Renderers
    "HtmlRenderer",
    "JsonRenderer",
    "render_contract_to_json",
    
    # Adapters
    "XmlAdapter",
    "load_xml_to_contract",
    
    # Schemas
    "ShaderSchema",
    "PipelineStateSchema",
    "TextureSchema",
    "EventSchema",
    
    # Enums
    "ShaderStage",
    "TextureType",
    "FillMode",
    "CullMode",
    "CompareFunc",
    
    # Validators
    "validate_shader_dict",
    "validate_pipeline_state_dict",
    "validate_texture_dict",
    "validate_event_dict",
]