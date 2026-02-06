#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tile-Based GPU 内存模型
======================

提供 Tile GPU 的基础配置与 Tile 内存估算逻辑。
该模型用于启发式分析，并非精确硬件测量。
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TileMemoryConfig:
    """Tile GPU 基础配置"""
    name: str
    tile_width: int
    tile_height: int
    gmem_kb: int
    bytes_per_pixel: int = 4
    description: str = ""

    @property
    def tile_pixels(self) -> int:
        return self.tile_width * self.tile_height

    @property
    def tile_bytes(self) -> int:
        return self.tile_pixels * self.bytes_per_pixel

    @property
    def gmem_bytes(self) -> int:
        return self.gmem_kb * 1024


@dataclass(frozen=True)
class TileMemoryEstimate:
    """Tile 内存估算结果"""
    estimated_bytes: int
    color_attachments: int
    depth_enabled: bool
    bytes_per_pixel: int
    sample_count: int
    estimated: bool = True
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[object]]:
        return {
            "estimated_bytes": self.estimated_bytes,
            "color_attachments": self.color_attachments,
            "depth_enabled": self.depth_enabled,
            "bytes_per_pixel": self.bytes_per_pixel,
            "sample_count": self.sample_count,
            "estimated": self.estimated,
            "reason": self.reason,
        }


# 预设配置（启发式）
_TILE_GPU_PRESETS: Dict[str, TileMemoryConfig] = {
    "generic": TileMemoryConfig(
        name="Generic-Tile",
        tile_width=32,
        tile_height=32,
        gmem_kb=512,
        bytes_per_pixel=4,
        description="通用 Tile 估算配置",
    ),
    "adreno": TileMemoryConfig(
        name="Adreno",
        tile_width=32,
        tile_height=32,
        gmem_kb=1024,
        bytes_per_pixel=4,
        description="Adreno 系列默认估算配置",
    ),
    "mali": TileMemoryConfig(
        name="Mali",
        tile_width=16,
        tile_height=16,
        gmem_kb=256,
        bytes_per_pixel=4,
        description="Mali 系列默认估算配置",
    ),
    "powervr": TileMemoryConfig(
        name="PowerVR",
        tile_width=32,
        tile_height=32,
        gmem_kb=512,
        bytes_per_pixel=4,
        description="PowerVR 系列默认估算配置",
    ),
}

# 指定型号覆盖
_TILE_GPU_OVERRIDES: Dict[str, TileMemoryConfig] = {
    "adreno-730": TileMemoryConfig("Adreno-730", 32, 32, 1024, 4, "Snapdragon 8 Gen 1"),
    "adreno-740": TileMemoryConfig("Adreno-740", 32, 32, 1024, 4, "Snapdragon 8 Gen 2"),
    "mali-g78": TileMemoryConfig("Mali-G78", 16, 16, 256, 4, "Valhall 主流型号"),
    "mali-g710": TileMemoryConfig("Mali-G710", 16, 16, 256, 4, "Valhall 2021"),
}


def get_tile_memory_config(gpu_name: str) -> TileMemoryConfig:
    """根据 GPU 名称返回 Tile 配置（模糊匹配）"""
    if not gpu_name:
        return _TILE_GPU_PRESETS["generic"]

    key = gpu_name.lower()
    for override_key, config in _TILE_GPU_OVERRIDES.items():
        if override_key in key:
            return config

    if "adreno" in key:
        return _TILE_GPU_PRESETS["adreno"]
    if "mali" in key:
        return _TILE_GPU_PRESETS["mali"]
    if "powervr" in key or "pvr" in key:
        return _TILE_GPU_PRESETS["powervr"]

    return _TILE_GPU_PRESETS["generic"]


def estimate_tile_memory(
    config: TileMemoryConfig,
    color_attachments: int,
    depth_enabled: bool,
    bytes_per_pixel: int = 4,
    sample_count: int = 1,
    estimated: bool = True,
    reason: Optional[str] = None,
) -> TileMemoryEstimate:
    """估算单个 Tile 的内存开销（字节）"""
    safe_samples = max(sample_count, 1)
    color_bytes = config.tile_pixels * bytes_per_pixel * max(color_attachments, 0) * safe_samples
    depth_bytes = config.tile_pixels * bytes_per_pixel * safe_samples if depth_enabled else 0
    total = color_bytes + depth_bytes

    return TileMemoryEstimate(
        estimated_bytes=total,
        color_attachments=max(color_attachments, 0),
        depth_enabled=depth_enabled,
        bytes_per_pixel=bytes_per_pixel,
        sample_count=safe_samples,
        estimated=estimated,
        reason=reason,
    )
