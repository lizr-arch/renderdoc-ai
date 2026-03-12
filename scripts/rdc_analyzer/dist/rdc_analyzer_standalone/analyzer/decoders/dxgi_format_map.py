#!/usr/bin/env python3
"""
dxgi_format_map.py - DXGI 格式到解码器的映射

用于 D3D11/D3D12 纹理提取时的格式转换。

使用方法:
    from decoders.dxgi_format_map import get_decoder_info, get_bytes_per_pixel
"""

from typing import Tuple, Optional

# DXGI 格式到解码器的映射
# 格式: (解码器名称, 每像素字节数)
# 压缩格式的字节数表示每 4x4 块的平均字节数 / 16
DXGI_FORMAT_MAP = {
    # ========== 未压缩 RGBA 格式 ==========
    "DXGI_FORMAT_R8G8B8A8_UNORM": ("RGBA8", 4),
    "DXGI_FORMAT_R8G8B8A8_UNORM_SRGB": ("RGBA8", 4),
    "DXGI_FORMAT_R8G8B8A8_SNORM": ("RGBA8", 4),
    "DXGI_FORMAT_R8G8B8A8_UINT": ("RGBA8", 4),
    "DXGI_FORMAT_R8G8B8A8_SINT": ("RGBA8", 4),
    
    "DXGI_FORMAT_B8G8R8A8_UNORM": ("BGRA8", 4),
    "DXGI_FORMAT_B8G8R8A8_UNORM_SRGB": ("BGRA8", 4),
    "DXGI_FORMAT_B8G8R8X8_UNORM": ("BGRX8", 4),
    "DXGI_FORMAT_B8G8R8X8_UNORM_SRGB": ("BGRX8", 4),
    
    # ========== 未压缩 RGB 格式 ==========
    "DXGI_FORMAT_R8G8_UNORM": ("RG8", 2),
    "DXGI_FORMAT_R8G8_SNORM": ("RG8", 2),
    "DXGI_FORMAT_R8G8_UINT": ("RG8", 2),
    "DXGI_FORMAT_R8G8_SINT": ("RG8", 2),
    
    "DXGI_FORMAT_R8_UNORM": ("R8", 1),
    "DXGI_FORMAT_R8_SNORM": ("R8", 1),
    "DXGI_FORMAT_R8_UINT": ("R8", 1),
    "DXGI_FORMAT_R8_SINT": ("R8", 1),
    "DXGI_FORMAT_A8_UNORM": ("A8", 1),
    
    # ========== 16位格式 ==========
    "DXGI_FORMAT_R16G16B16A16_FLOAT": ("RGBA16F", 8),
    "DXGI_FORMAT_R16G16B16A16_UNORM": ("RGBA16", 8),
    "DXGI_FORMAT_R16G16B16A16_UINT": ("RGBA16", 8),
    "DXGI_FORMAT_R16G16B16A16_SNORM": ("RGBA16", 8),
    "DXGI_FORMAT_R16G16B16A16_SINT": ("RGBA16", 8),
    
    "DXGI_FORMAT_R16G16_FLOAT": ("RG16F", 4),
    "DXGI_FORMAT_R16G16_UNORM": ("RG16", 4),
    "DXGI_FORMAT_R16G16_UINT": ("RG16", 4),
    "DXGI_FORMAT_R16G16_SNORM": ("RG16", 4),
    "DXGI_FORMAT_R16G16_SINT": ("RG16", 4),
    
    "DXGI_FORMAT_R16_FLOAT": ("R16F", 2),
    "DXGI_FORMAT_R16_UNORM": ("R16", 2),
    "DXGI_FORMAT_R16_UINT": ("R16", 2),
    "DXGI_FORMAT_R16_SNORM": ("R16", 2),
    "DXGI_FORMAT_R16_SINT": ("R16", 2),
    
    # ========== 32位格式 ==========
    "DXGI_FORMAT_R32G32B32A32_FLOAT": ("RGBA32F", 16),
    "DXGI_FORMAT_R32G32B32A32_UINT": ("RGBA32", 16),
    "DXGI_FORMAT_R32G32B32A32_SINT": ("RGBA32", 16),
    
    "DXGI_FORMAT_R32G32B32_FLOAT": ("RGB32F", 12),
    "DXGI_FORMAT_R32G32B32_UINT": ("RGB32", 12),
    "DXGI_FORMAT_R32G32B32_SINT": ("RGB32", 12),
    
    "DXGI_FORMAT_R32G32_FLOAT": ("RG32F", 8),
    "DXGI_FORMAT_R32G32_UINT": ("RG32", 8),
    "DXGI_FORMAT_R32G32_SINT": ("RG32", 8),
    
    "DXGI_FORMAT_R32_FLOAT": ("R32F", 4),
    "DXGI_FORMAT_R32_UINT": ("R32", 4),
    "DXGI_FORMAT_R32_SINT": ("R32", 4),
    
    # ========== 深度/模板格式 ==========
    "DXGI_FORMAT_D32_FLOAT": ("D32F", 4),
    "DXGI_FORMAT_D24_UNORM_S8_UINT": ("D24S8", 4),
    "DXGI_FORMAT_D16_UNORM": ("D16", 2),
    "DXGI_FORMAT_D32_FLOAT_S8X24_UINT": ("D32S8", 8),
    
    # ========== BC 压缩格式 ==========
    # BC1 (DXT1): 8 bytes per 4x4 block = 0.5 bytes/pixel
    "DXGI_FORMAT_BC1_UNORM": ("BC1", 0.5),
    "DXGI_FORMAT_BC1_UNORM_SRGB": ("BC1", 0.5),
    
    # BC2 (DXT3): 16 bytes per 4x4 block = 1 byte/pixel
    "DXGI_FORMAT_BC2_UNORM": ("BC2", 1),
    "DXGI_FORMAT_BC2_UNORM_SRGB": ("BC2", 1),
    
    # BC3 (DXT5): 16 bytes per 4x4 block = 1 byte/pixel
    "DXGI_FORMAT_BC3_UNORM": ("BC3", 1),
    "DXGI_FORMAT_BC3_UNORM_SRGB": ("BC3", 1),
    
    # BC4 (ATI1/3Dc+): 8 bytes per 4x4 block = 0.5 bytes/pixel
    "DXGI_FORMAT_BC4_UNORM": ("BC4", 0.5),
    "DXGI_FORMAT_BC4_SNORM": ("BC4", 0.5),
    
    # BC5 (ATI2/3Dc): 16 bytes per 4x4 block = 1 byte/pixel
    "DXGI_FORMAT_BC5_UNORM": ("BC5", 1),
    "DXGI_FORMAT_BC5_SNORM": ("BC5", 1),
    
    # BC6H (HDR): 16 bytes per 4x4 block = 1 byte/pixel
    "DXGI_FORMAT_BC6H_UF16": ("BC6H", 1),
    "DXGI_FORMAT_BC6H_SF16": ("BC6H", 1),
    
    # BC7: 16 bytes per 4x4 block = 1 byte/pixel
    "DXGI_FORMAT_BC7_UNORM": ("BC7", 1),
    "DXGI_FORMAT_BC7_UNORM_SRGB": ("BC7", 1),
    
    # ========== 特殊格式 ==========
    "DXGI_FORMAT_R10G10B10A2_UNORM": ("RGB10A2", 4),
    "DXGI_FORMAT_R10G10B10A2_UINT": ("RGB10A2", 4),
    "DXGI_FORMAT_R11G11B10_FLOAT": ("R11G11B10F", 4),
    "DXGI_FORMAT_R9G9B9E5_SHAREDEXP": ("RGB9E5", 4),
}

# 简化格式名映射（去掉 DXGI_FORMAT_ 前缀）
SIMPLIFIED_FORMAT_MAP = {
    k.replace("DXGI_FORMAT_", ""): v 
    for k, v in DXGI_FORMAT_MAP.items()
}


def get_decoder_info(dxgi_format: str) -> Optional[Tuple[str, float]]:
    """
    获取 DXGI 格式对应的解码器信息
    
    Args:
        dxgi_format: DXGI 格式名称 (如 "DXGI_FORMAT_BC7_UNORM" 或 "BC7_UNORM")
    
    Returns:
        (decoder_name, bytes_per_pixel) 或 None
    """
    # 尝试完整格式名
    if dxgi_format in DXGI_FORMAT_MAP:
        return DXGI_FORMAT_MAP[dxgi_format]
    
    # 尝试简化格式名
    simplified = dxgi_format.replace("DXGI_FORMAT_", "")
    if simplified in SIMPLIFIED_FORMAT_MAP:
        return SIMPLIFIED_FORMAT_MAP[simplified]
    
    return None


def get_bytes_per_pixel(dxgi_format: str) -> float:
    """
    获取格式的每像素字节数
    
    Args:
        dxgi_format: DXGI 格式名称
    
    Returns:
        每像素字节数，未知格式返回 4.0
    """
    info = get_decoder_info(dxgi_format)
    return info[1] if info else 4.0


def get_decoder_name(dxgi_format: str) -> str:
    """
    获取格式对应的解码器名称
    
    Args:
        dxgi_format: DXGI 格式名称
    
    Returns:
        解码器名称，未知格式返回 "UNKNOWN"
    """
    info = get_decoder_info(dxgi_format)
    return info[0] if info else "UNKNOWN"


def is_compressed_format(dxgi_format: str) -> bool:
    """
    判断是否为压缩格式
    
    Args:
        dxgi_format: DXGI 格式名称
    
    Returns:
        是否为 BC 压缩格式
    """
    name = get_decoder_name(dxgi_format)
    return name.startswith("BC")


def is_depth_format(dxgi_format: str) -> bool:
    """
    判断是否为深度格式
    
    Args:
        dxgi_format: DXGI 格式名称
    
    Returns:
        是否为深度格式
    """
    name = get_decoder_name(dxgi_format)
    return name.startswith("D") and name[1:2].isdigit()


def calculate_texture_size(width: int, height: int, dxgi_format: str, mip_levels: int = 1) -> int:
    """
    计算纹理占用的字节数
    
    Args:
        width: 宽度
        height: 高度
        dxgi_format: DXGI 格式名称
        mip_levels: Mip 级别数
    
    Returns:
        总字节数
    """
    bpp = get_bytes_per_pixel(dxgi_format)
    is_bc = is_compressed_format(dxgi_format)
    
    total = 0
    w, h = width, height
    
    for _ in range(mip_levels):
        if is_bc:
            # BC 格式按 4x4 块计算
            block_w = (w + 3) // 4
            block_h = (h + 3) // 4
            # bpp 是每像素字节，块大小 = bpp * 16
            block_size = int(bpp * 16)
            total += block_w * block_h * block_size
        else:
            total += int(w * h * bpp)
        
        w = max(1, w // 2)
        h = max(1, h // 2)
    
    return total


# 格式统计信息
def get_format_stats() -> dict:
    """获取支持的格式统计"""
    stats = {
        "total": len(DXGI_FORMAT_MAP),
        "uncompressed": 0,
        "compressed": 0,
        "depth": 0,
    }
    
    for fmt in DXGI_FORMAT_MAP:
        if is_compressed_format(fmt):
            stats["compressed"] += 1
        elif is_depth_format(fmt):
            stats["depth"] += 1
        else:
            stats["uncompressed"] += 1
    
    return stats


if __name__ == "__main__":
    # 测试
    print("DXGI Format Map - Supported Formats")
    print("=" * 50)
    
    stats = get_format_stats()
    print(f"Total formats: {stats['total']}")
    print(f"  Uncompressed: {stats['uncompressed']}")
    print(f"  Compressed: {stats['compressed']}")
    print(f"  Depth: {stats['depth']}")
    
    print("\nExample lookups:")
    for fmt in ["DXGI_FORMAT_BC7_UNORM", "BC1_UNORM", "R8G8B8A8_UNORM"]:
        info = get_decoder_info(fmt)
        print(f"  {fmt}: {info}")
