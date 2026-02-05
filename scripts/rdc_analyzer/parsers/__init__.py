#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Analyzer Parsers - Parse various RenderDoc export formats.

from .rdc_xml_parser import (
    RdcXmlParser,
    RdcXmlData,
    D3D11DrawCall,
    D3D11Resource,
    D3D11PipelineState,
    parse_rdc_xml,
)

__all__ = [
    "RdcXmlParser",
    "RdcXmlData",
    "D3D11DrawCall",
    "D3D11Resource",
    "D3D11PipelineState",
    "parse_rdc_xml",
]
"""

# 常量
from .constants import (
    RDC_MAGIC_BYTES,
    RDC_VERSION_1_0,
    RDC_VERSION_1_1,
    RDC_VERSION_1_2,
    FIRST_DRIVER_CHUNK,
    CHUNK_ALIGNMENT,
    CHUNK_64BIT_SIZE,
    CHUNK_INDEX_MASK,
    CHUNK_CALLSTACK,
    CHUNK_THREAD_ID,
    CHUNK_DURATION,
    CHUNK_TIMESTAMP,
    SPIRV_MAGIC,
    SPIRV_OP_NAME,
    SPIRV_OP_ENTRY_POINT,
    SPIRV_EXEC_MODEL_NAMES,
)

# 枚举
from .enums import (
    RDCDriver,
    SectionType,
    SectionFlags,
    VulkanChunk,
    VK_FORMAT_NAMES,
)

# 数据模型
from .models import (
    FileHeader,
    Thumbnail,
    CaptureMetaData,
    TimeBase,
    SectionInfo,
    ChunkInfo,
    DrawEventContext,
    PipelineInfo,
    ShaderResource,
    SPIRVEntryPoint,
    ShaderInfo,
    TextureInfo,
    RDCFileInfo,
)

# IO 工具
from .io_utils import (
    BinaryReader,
    read_u8_from_bytes,
    read_u16_from_bytes,
    read_u32_from_bytes,
    read_u64_from_bytes,
    read_i32_from_bytes,
    read_f32_from_bytes,
    read_f64_from_bytes,
    read_string_from_bytes,
    align_offset,
)

# Section 解析器
from .section_parser import SectionParser, parse_rdc_file

# Chunk 解析器
from .chunk_parser import ChunkParser, parse_frame_chunks

# Shader 提取器
from .shader_extractor import ShaderExtractor, extract_vulkan_shaders

# Texture 提取器
from .texture_extractor import TextureExtractor, extract_vulkan_textures

# Draw Event 解析器
from .draw_event_parser import (
    DrawEventParser,
    extract_draw_events,
    MARKER_BEGIN_CHUNK_IDS,
    MARKER_END_CHUNK_IDS,
    DRAW_CHUNK_IDS,
    DISPATCH_CHUNK_IDS,
)

# 解析器类 (延迟导入，因依赖 core 模块)
# 使用 lazy import 避免在独立使用 parsers 包时产生循环导入
def _get_api_parser():
    from .api_parser import APIParser
    return APIParser

def _get_binary_parser():
    from .binary_parser import BinaryParser
    return BinaryParser

# 为向后兼容提供直接访问（实际使用时才导入）
try:
    from .api_parser import APIParser
    from .binary_parser import BinaryParser
except ImportError:
    # 独立使用 parsers 包时，跳过依赖 core 的模块
    APIParser = None
    BinaryParser = None
from .rdc_xml_parser import (
    RdcXmlParser,
    RdcXmlData,
    D3D11DrawCall,
    D3D11Resource,
    D3D11PipelineState,
    parse_rdc_xml,
)

__all__ = [
    # constants
    'RDC_MAGIC_BYTES',
    'RDC_VERSION_1_0',
    'RDC_VERSION_1_1',
    'RDC_VERSION_1_2',
    'FIRST_DRIVER_CHUNK',
    'CHUNK_ALIGNMENT',
    'CHUNK_64BIT_SIZE',
    'SPIRV_MAGIC',
    'SPIRV_OP_NAME',
    'SPIRV_OP_ENTRY_POINT',
    'SPIRV_EXEC_MODEL_NAMES',
    # enums
    'RDCDriver',
    'SectionType',
    'SectionFlags',
    'VulkanChunk',
    'VK_FORMAT_NAMES',
    # models
    'FileHeader',
    'Thumbnail',
    'CaptureMetaData',
    'TimeBase',
    'SectionInfo',
    'ChunkInfo',
    'DrawEventContext',
    'PipelineInfo',
    'ShaderResource',
    'SPIRVEntryPoint',
    'ShaderInfo',
    'TextureInfo',
    'RDCFileInfo',
    # io_utils
    'BinaryReader',
    'read_u8_from_bytes',
    'read_u16_from_bytes',
    'read_u32_from_bytes',
    'read_u64_from_bytes',
    'read_i32_from_bytes',
    'read_f32_from_bytes',
    'read_f64_from_bytes',
    'read_string_from_bytes',
    'align_offset',
    # section_parser
    'SectionParser',
    'parse_rdc_file',
    # chunk_parser
    'ChunkParser',
    'parse_frame_chunks',
    # shader_extractor
    'ShaderExtractor',
    'extract_vulkan_shaders',
    # texture_extractor
    'TextureExtractor',
    'extract_vulkan_textures',
    # draw_event_parser
    'DrawEventParser',
    'extract_draw_events',
    'MARKER_BEGIN_CHUNK_IDS',
    'MARKER_END_CHUNK_IDS',
    'DRAW_CHUNK_IDS',
    'DISPATCH_CHUNK_IDS',
    # parsers
    'APIParser',
    'BinaryParser',
    # RDC XML parser
    'RdcXmlParser',
    'RdcXmlData',
    'D3D11DrawCall',
    'D3D11Resource',
    'D3D11PipelineState',
    'parse_rdc_xml',
]
