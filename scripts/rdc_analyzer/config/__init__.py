"""
配置模块
========

包含:
- thresholds: 检测阈值配置
- platforms: 平台特定配置 (PC/Mobile)
"""

from .thresholds import get_thresholds, DEFAULT_THRESHOLDS, MOBILE_THRESHOLDS
from .platforms import PlatformConfig, get_platform_config

__all__ = [
    "get_thresholds",
    "DEFAULT_THRESHOLDS",
    "MOBILE_THRESHOLDS",
    "PlatformConfig",
    "get_platform_config",
]
