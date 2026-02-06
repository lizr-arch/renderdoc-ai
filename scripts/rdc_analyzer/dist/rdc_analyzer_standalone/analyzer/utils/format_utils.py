"""
格式工具函数
============

纹理格式分类、压缩检测、尺寸验证等工具函数。
"""

from typing import Tuple

# 压缩纹理格式列表
COMPRESSED_FORMATS = {
    # BC 格式 (DirectX)
    "BC1", "BC1_UNORM", "BC1_UNORM_SRGB",
    "BC2", "BC2_UNORM", "BC2_UNORM_SRGB",
    "BC3", "BC3_UNORM", "BC3_UNORM_SRGB",
    "BC4", "BC4_UNORM", "BC4_SNORM",
    "BC5", "BC5_UNORM", "BC5_SNORM",
    "BC6H", "BC6H_UF16", "BC6H_SF16",
    "BC7", "BC7_UNORM", "BC7_UNORM_SRGB",
    # ASTC 格式 (移动端)
    "ASTC_4x4", "ASTC_5x5", "ASTC_6x6", "ASTC_8x8", "ASTC_10x10", "ASTC_12x12",
    "ASTC_4x4_UNORM", "ASTC_5x5_UNORM", "ASTC_6x6_UNORM",
    "ASTC_8x8_UNORM", "ASTC_10x10_UNORM", "ASTC_12x12_UNORM",
    "ASTC_4x4_SRGB", "ASTC_5x5_SRGB", "ASTC_6x6_SRGB",
    "ASTC_8x8_SRGB", "ASTC_10x10_SRGB", "ASTC_12x12_SRGB",
    # ETC 格式 (移动端)
    "ETC1", "ETC2", "ETC2_RGB", "ETC2_RGBA", "ETC2_EAC",
    # PVRTC 格式 (iOS)
    "PVRTC1_2", "PVRTC1_4", "PVRTC2_2", "PVRTC2_4",
}

# 深度/模板格式列表
DEPTH_FORMATS = {
    "D16_UNORM", "D24_UNORM", "D32_FLOAT",
    "D24_UNORM_S8_UINT", "D32_FLOAT_S8X24_UINT",
    "R16_UNORM", "R24_UNORM_X8_TYPELESS", "R32_FLOAT",
}

# HDR 格式列表
HDR_FORMATS = {
    "R16G16B16A16_FLOAT", "R32G32B32A32_FLOAT",
    "R16G16_FLOAT", "R32G32_FLOAT",
    "R16_FLOAT", "R32_FLOAT",
    "R11G11B10_FLOAT",
    "BC6H", "BC6H_UF16", "BC6H_SF16",
}


def classify_format(fmt: str) -> str:
    """
    分类纹理格式
    
    Args:
        fmt: 格式字符串 (如 "R8G8B8A8_UNORM")
        
    Returns:
        格式类别: "compressed" | "depth" | "hdr" | "uncompressed"
    """
    fmt_upper = fmt.upper()
    
    # 检查压缩格式
    for cf in COMPRESSED_FORMATS:
        if cf in fmt_upper:
            return "compressed"
    
    # 检查深度格式
    for df in DEPTH_FORMATS:
        if df in fmt_upper:
            return "depth"
    
    # 检查 HDR 格式
    for hf in HDR_FORMATS:
        if hf in fmt_upper:
            return "hdr"
    
    return "uncompressed"


def is_power_of_two(n: int) -> bool:
    """检查是否为 2 的幂"""
    return n > 0 and (n & (n - 1)) == 0


def get_format_bpp(fmt: str) -> float:
    """
    获取格式的 Bits Per Pixel (BPP)
    
    Args:
        fmt: 格式字符串
        
    Returns:
        每像素位数 (float, 支持压缩格式的小数位)
    """
    fmt_upper = fmt.upper()
    
    # 压缩格式 BPP (按 4x4 block 计算)
    if "BC1" in fmt_upper or "BC4" in fmt_upper:
        return 4.0  # 64 bits / 16 pixels
    if "BC2" in fmt_upper or "BC3" in fmt_upper or "BC5" in fmt_upper:
        return 8.0  # 128 bits / 16 pixels
    if "BC6H" in fmt_upper or "BC7" in fmt_upper:
        return 8.0
    
    # ASTC 格式
    if "ASTC_4x4" in fmt_upper:
        return 8.0  # 128 bits / 16 pixels
    if "ASTC_5x5" in fmt_upper:
        return 5.12  # 128 / 25
    if "ASTC_6x6" in fmt_upper:
        return 3.56  # 128 / 36
    if "ASTC_8x8" in fmt_upper:
        return 2.0  # 128 / 64
    
    # ETC 格式
    if "ETC" in fmt_upper:
        return 4.0
    
    # 非压缩格式
    if "R32G32B32A32" in fmt_upper:
        return 128.0
    if "R16G16B16A16" in fmt_upper:
        return 64.0
    if "R32G32B32" in fmt_upper:
        return 96.0
    if "R32G32" in fmt_upper:
        return 64.0
    if "R16G16B16" in fmt_upper:
        return 48.0
    if "R16G16" in fmt_upper:
        return 32.0
    if "R8G8B8A8" in fmt_upper or "B8G8R8A8" in fmt_upper:
        return 32.0
    if "R10G10B10A2" in fmt_upper:
        return 32.0
    if "R11G11B10" in fmt_upper:
        return 32.0
    if "R8G8B8" in fmt_upper or "B8G8R8" in fmt_upper:
        return 24.0
    if "R16" in fmt_upper:
        return 16.0
    if "R8G8" in fmt_upper:
        return 16.0
    if "R8" in fmt_upper:
        return 8.0
    if "R32" in fmt_upper:
        return 32.0
    
    # 深度格式
    if "D32_FLOAT_S8" in fmt_upper:
        return 64.0
    if "D32" in fmt_upper:
        return 32.0
    if "D24" in fmt_upper:
        return 32.0
    if "D16" in fmt_upper:
        return 16.0
    
    # 默认假设 32bpp
    return 32.0


def calculate_mip_levels(width: int, height: int) -> int:
    """
    计算完整的 Mipmap 级数
    
    Args:
        width: 纹理宽度
        height: 纹理高度
        
    Returns:
        完整 Mipmap 链的级数
    """
    import math
    return int(math.log2(max(width, height))) + 1


def is_mipmap_complete(width: int, height: int, mip_count: int) -> bool:
    """
    检查 Mipmap 是否完整
    
    Args:
        width: 纹理宽度
        height: 纹理高度
        mip_count: 实际 Mipmap 级数
        
    Returns:
        True 如果 Mipmap 完整
    """
    expected = calculate_mip_levels(width, height)
    # 允许少 1 级 (最后 1x1 有时省略)
    return mip_count >= expected - 1
