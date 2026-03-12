"""
RDC 数据模型包
==============

从 rdc_parser.py 提取的数据类，按功能分类为：
- base: 文件头、Section、Chunk 等基础结构
- shader: SPIR-V Shader 相关
- texture: 纹理资源相关
- rdc_file: RDC 文件整体信息聚合

使用示例::

    from rdc_analyzer.parsers.models import (
        FileHeader, ShaderInfo, TextureInfo, RDCFileInfo
    )
"""

# 基础模型
from .base import (
    FileHeader,
    Thumbnail,
    CaptureMetaData,
    TimeBase,
    SectionInfo,
    ChunkInfo,
    DrawEventContext,
    PipelineInfo,
)

# Shader 模型
from .shader import (
    ShaderResource,
    SPIRVEntryPoint,
    ShaderInfo,
)

# 纹理模型
from .texture import (
    TextureInfo,
)

# RDC 文件聚合模型
from .rdc_file import (
    RDCFileInfo,
)

__all__ = [
    # base
    'FileHeader',
    'Thumbnail',
    'CaptureMetaData',
    'TimeBase',
    'SectionInfo',
    'ChunkInfo',
    'DrawEventContext',
    'PipelineInfo',
    # shader
    'ShaderResource',
    'SPIRVEntryPoint',
    'ShaderInfo',
    # texture
    'TextureInfo',
    # rdc_file
    'RDCFileInfo',
]