"""
内存估算工具函数
================

纹理和缓冲区的内存占用估算。
"""

from typing import Optional
from .format_utils import get_format_bpp


def estimate_texture_memory(
    width: int,
    height: int,
    fmt: str,
    mip_count: int = 1,
    array_size: int = 1,
    depth: int = 1,
) -> float:
    """
    估算纹理内存占用 (MB)
    
    Args:
        width: 纹理宽度
        height: 纹理高度
        fmt: 格式字符串
        mip_count: Mipmap 级数
        array_size: 纹理数组大小
        depth: 3D 纹理深度
        
    Returns:
        估算内存占用 (MB)
    """
    bpp = get_format_bpp(fmt)
    
    # 计算基础尺寸 (考虑 Mipmap)
    total_pixels = 0
    w, h = width, height
    for _ in range(mip_count):
        total_pixels += w * h
        w = max(1, w // 2)
        h = max(1, h // 2)
    
    # 考虑数组/3D 深度
    total_pixels *= max(array_size, 1) * max(depth, 1)
    
    # 转换为 MB
    total_bytes = total_pixels * bpp / 8
    return total_bytes / (1024 * 1024)


def estimate_buffer_memory(size_bytes: int) -> float:
    """
    估算缓冲区内存占用 (MB)
    
    Args:
        size_bytes: 缓冲区字节数
        
    Returns:
        内存占用 (MB)
    """
    return size_bytes / (1024 * 1024)


def format_memory_size(size_mb: float) -> str:
    """
    格式化内存大小显示
    
    Args:
        size_mb: MB 为单位的大小
        
    Returns:
        人类可读的字符串 (如 "1.5 GB", "256 MB", "512 KB")
    """
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    elif size_mb >= 1:
        return f"{size_mb:.2f} MB"
    elif size_mb >= 0.001:
        return f"{size_mb * 1024:.2f} KB"
    else:
        return f"{size_mb * 1024 * 1024:.0f} B"
