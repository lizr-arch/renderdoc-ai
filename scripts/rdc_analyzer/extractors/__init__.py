"""
状态提取器模块
==============

从 RDC 文件中提取 GPU 管线状态信息
"""

from .base import (
    BaseExtractor, 
    ExtractorError, 
    ExtractorRegistry,
    ExtractorConfig,
    EventInfo,
    EventType,
    StateExtractionError,
)
from .event_parser import (
    EventParser,
    parse_events_from_controller,
    flatten_events,
    filter_actionable_events,
    get_events_by_marker,
    count_events_by_type,
)
from .replay_wrapper import (
    ReplayWrapper,
    MockReplayWrapper,
    ReplayError,
    RenderDocNotAvailableError,
    CaptureLoadError,
    CaptureInfo,
    RENDERDOC_AVAILABLE,
)
from .shader_extractor import (
    ShaderExtractor,
    ShaderExtractorResult,
    create_shader_extractor,
    SHADER_STAGE_NAMES,
    SHADER_TYPE_ABBREV,
    SHADER_ENCODING_NAMES,
)

# 导入提取器实现（会自动注册）
from .d3d11_extractor import D3D11Extractor

__all__ = [
    # 基类
    'BaseExtractor',
    'ExtractorError', 
    'ExtractorRegistry',
    'ExtractorConfig',
    'EventInfo',
    'EventType',
    'StateExtractionError',
    # 事件解析
    'EventParser',
    'parse_events_from_controller',
    'flatten_events',
    'filter_actionable_events',
    'get_events_by_marker',
    'count_events_by_type',
    # 回放封装
    'ReplayWrapper',
    'MockReplayWrapper',
    'ReplayError',
    'RenderDocNotAvailableError',
    'CaptureLoadError',
    'CaptureInfo',
    'RENDERDOC_AVAILABLE',
    # 提取器实现
    'D3D11Extractor',
    # Shader 提取
    'ShaderExtractor',
    'ShaderExtractorResult',
    'create_shader_extractor',
    'SHADER_STAGE_NAMES',
    'SHADER_TYPE_ABBREV',
    'SHADER_ENCODING_NAMES',
]
