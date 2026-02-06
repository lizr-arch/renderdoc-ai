"""
平台配置
========

定义不同平台的特定配置和优化建议。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class PlatformConfig:
    """平台配置"""
    name: str
    display_name: str
    
    # 渲染架构
    gpu_architecture: str  # "IMR" (PC) 或 "TBDR" (移动端)
    
    # 推荐格式
    preferred_texture_formats: List[str] = field(default_factory=list)
    preferred_compression: List[str] = field(default_factory=list)
    
    # 硬件限制
    max_texture_size: int = 8192
    max_render_targets: int = 8
    max_vertex_attribs: int = 16
    
    # 性能特征
    bandwidth_sensitive: bool = False
    prefer_compute: bool = False
    
    # 额外规则
    extra_rules: List[str] = field(default_factory=list)
    disabled_rules: List[str] = field(default_factory=list)
    
    # 阈值覆盖
    threshold_overrides: Dict[str, Any] = field(default_factory=dict)


# PC 配置
PC_CONFIG = PlatformConfig(
    name="pc",
    display_name="PC (Desktop)",
    gpu_architecture="IMR",
    preferred_texture_formats=["BC7", "BC5", "BC3", "BC1"],
    preferred_compression=["BC7_UNORM", "BC5_UNORM", "BC3_UNORM"],
    max_texture_size=16384,
    max_render_targets=8,
    bandwidth_sensitive=False,
    prefer_compute=True,
)

# 移动端 Android 配置
ANDROID_CONFIG = PlatformConfig(
    name="android",
    display_name="Android (Mobile)",
    gpu_architecture="TBDR",
    preferred_texture_formats=["ASTC_6x6", "ASTC_4x4", "ETC2"],
    preferred_compression=["ASTC_6x6_UNORM", "ETC2_RGBA"],
    max_texture_size=4096,
    max_render_targets=4,
    bandwidth_sensitive=True,
    prefer_compute=False,
    extra_rules=[
        "RD_MOBILE_001",  # TBDR 优化
        "RD_MOBILE_002",  # 半精度建议
    ],
    threshold_overrides={
        "max_draw_calls": 500,
        "large_texture_threshold_mb": 4.0,
    },
)

# 移动端 iOS 配置
IOS_CONFIG = PlatformConfig(
    name="ios",
    display_name="iOS (Mobile)",
    gpu_architecture="TBDR",
    preferred_texture_formats=["ASTC_6x6", "ASTC_4x4", "PVRTC1_4"],
    preferred_compression=["ASTC_6x6_UNORM", "ASTC_4x4_SRGB"],
    max_texture_size=8192,
    max_render_targets=4,
    bandwidth_sensitive=True,
    prefer_compute=False,
    extra_rules=[
        "RD_MOBILE_001",
        "RD_MOBILE_002",
    ],
    threshold_overrides={
        "max_draw_calls": 500,
        "large_texture_threshold_mb": 4.0,
    },
)

# 主机配置
CONSOLE_CONFIG = PlatformConfig(
    name="console",
    display_name="Console (PS/Xbox)",
    gpu_architecture="IMR",
    preferred_texture_formats=["BC7", "BC5", "BC3"],
    preferred_compression=["BC7_UNORM", "BC5_UNORM"],
    max_texture_size=16384,
    max_render_targets=8,
    bandwidth_sensitive=False,
    prefer_compute=True,
)

# 平台注册表
_PLATFORM_REGISTRY: Dict[str, PlatformConfig] = {
    "pc": PC_CONFIG,
    "desktop": PC_CONFIG,
    "windows": PC_CONFIG,
    "android": ANDROID_CONFIG,
    "ios": IOS_CONFIG,
    "mobile": ANDROID_CONFIG,  # 默认移动端使用 Android
    "console": CONSOLE_CONFIG,
    "ps4": CONSOLE_CONFIG,
    "ps5": CONSOLE_CONFIG,
    "xbox": CONSOLE_CONFIG,
}


def get_platform_config(platform: str) -> PlatformConfig:
    """
    获取平台配置
    
    Args:
        platform: 平台名称
        
    Returns:
        平台配置对象
    """
    return _PLATFORM_REGISTRY.get(platform.lower(), PC_CONFIG)


def list_platforms() -> List[str]:
    """
    列出所有支持的平台
    
    Returns:
        平台名称列表
    """
    return list(set(cfg.name for cfg in _PLATFORM_REGISTRY.values()))
