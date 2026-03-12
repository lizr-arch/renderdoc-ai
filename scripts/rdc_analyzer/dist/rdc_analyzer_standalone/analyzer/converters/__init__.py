"""
Shader 格式转换器模块
=====================

提供 Shader 格式检测和转换功能，支持：
- HLSL -> GLSL
- DXBC -> GLSL (via stub generation)
- SPIR-V -> GLSL (via spirv-cross)
"""

from .shader_converter import (
    ShaderConverter,
    ShaderFormat,
    ShaderStage,
    ConversionResult,
    get_converter,
    convert_to_glsl,
)

__all__ = [
    'ShaderConverter',
    'ShaderFormat',
    'ShaderStage',
    'ConversionResult',
    'get_converter',
    'convert_to_glsl',
]
