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

# 解析器类
from .api_parser import APIParser
from .binary_parser import BinaryParser
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
