"""
枚举定义
========

定义规则严重性、分类和平台等枚举类型。
"""

from enum import Enum


class Severity(str, Enum):
    """问题严重性"""
    ERROR = "error"      # 严重问题，必须修复
    WARNING = "warning"  # 潜在问题，建议修复
    INFO = "info"        # 信息性提示


class Category(str, Enum):
    """问题分类"""
    PERFORMANCE = "performance"    # 性能问题
    MEMORY = "memory"              # 内存问题
    CORRECTNESS = "correctness"    # 正确性问题
    COMPATIBILITY = "compatibility" # 兼容性问题
    # 细分类别 (用于规则组织)
    DRAW_CALL = "draw_call"        # DrawCall 相关
    TEXTURE = "texture"            # 纹理相关
    BUFFER = "buffer"              # 缓冲区相关
    PASS = "pass"                  # 渲染 Pass 相关
    STATE = "state"                # 管线状态相关
    MOBILE = "mobile"              # 移动平台特定


class Platform(str, Enum):
    """目标平台"""
    PC = "pc"
    MOBILE = "mobile"
    CONSOLE = "console"


class ResourceType(str, Enum):
    """资源类型"""
    TEXTURE = "texture"
    BUFFER = "buffer"
    SHADER = "shader"
    RENDER_TARGET = "render_target"
    DEPTH_STENCIL = "depth_stencil"
    SAMPLER = "sampler"


class ShaderStage(str, Enum):
    """Shader 阶段"""
    VERTEX = "VS"
    HULL = "HS"
    DOMAIN = "DS"
    GEOMETRY = "GS"
    PIXEL = "PS"
    COMPUTE = "CS"


class FormatCategory(str, Enum):
    """纹理格式分类"""
    COMPRESSED = "compressed"      # BC, ASTC, ETC 等
    UNCOMPRESSED = "uncompressed"  # R8G8B8A8, R16G16 等
    DEPTH = "depth"                # D24S8, D32F 等
