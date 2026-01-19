#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 解析器包
============

提供 RDC 文件解析的核心组件。

子模块:
- constants: 魔数、版本号等常量
- enums: 枚举类型（VulkanChunk, SectionType 等）
- models: 数据模型（FileHeader, ShaderInfo, TextureInfo 等）

使用示例::

    from rdc_analyzer.parsers import (
        RDC_MAGIC_BYTES, SPIRV_MAGIC,
        VulkanChunk, SectionType,
        FileHeader, ShaderInfo, TextureInfo, RDCFileInfo,
    )
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
]
