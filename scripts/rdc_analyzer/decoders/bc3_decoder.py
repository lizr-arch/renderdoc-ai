"""
BC3 (DXT5) Texture Decoder

BC3 压缩格式解码器，用于解压 DXT5 纹理。

格式规格:
- 4x4 像素块 = 16 字节
- 8 字节 Alpha 块:
  - 2 个 8-bit alpha 端点 (2 字节)
  - 16 个 3-bit 索引 (6 字节)
- 8 字节颜色块 (同 BC1):
  - 2 个 RGB565 颜色端点 (4 字节)
  - 16 个 2-bit 索引 (4 字节)
- 4:1 压缩比

参考:
- https://www.khronos.org/opengl/wiki/S3_Texture_Compression#DXT5
- https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc3
"""

import struct
from typing import List, Tuple

from .texture_decoder import register_decoder
from .bc1_decoder import unpack_rgb565, interpolate_color


def decode_alpha_block(block: bytes) -> List[int]:
    """
    解码 BC3 Alpha 块 (8 bytes -> 16 alpha values)
    
    Args:
        block: 8 字节的 Alpha 块数据
    
    Returns:
        16 个 alpha 值 (0-255) 的列表
    """
    if len(block) < 8:
        return [255] * 16
    
    # 读取两个 8-bit alpha 端点
    alpha0 = block[0]
    alpha1 = block[1]
    
    # 构建 8 级 alpha 调色板
    if alpha0 > alpha1:
        # 8 级插值模式
        palette = [
            alpha0,
            alpha1,
            (6 * alpha0 + 1 * alpha1) // 7,
            (5 * alpha0 + 2 * alpha1) // 7,
            (4 * alpha0 + 3 * alpha1) // 7,
            (3 * alpha0 + 4 * alpha1) // 7,
            (2 * alpha0 + 5 * alpha1) // 7,
            (1 * alpha0 + 6 * alpha1) // 7,
        ]
    else:
        # 6 级插值 + 透明/不透明
        palette = [
            alpha0,
            alpha1,
            (4 * alpha0 + 1 * alpha1) // 5,
            (3 * alpha0 + 2 * alpha1) // 5,
            (2 * alpha0 + 3 * alpha1) // 5,
            (1 * alpha0 + 4 * alpha1) // 5,
            0,    # 完全透明
            255,  # 完全不透明
        ]
    
    # 读取 16 个 3-bit 索引 (6 字节)
    # 索引存储方式: 每 3 字节包含 8 个索引
    indices_bytes = block[2:8]
    
    # 将 6 字节展开为 48 bit，提取 16 个 3-bit 索引
    indices_value = int.from_bytes(indices_bytes, 'little')
    
    alphas = []
    for i in range(16):
        idx = (indices_value >> (i * 3)) & 0x7
        alphas.append(palette[idx])
    
    return alphas


def decode_bc3_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC3 块 (16 bytes -> 16 RGBA pixels)
    
    Args:
        block: 16 字节的 BC3 块数据
    
    Returns:
        16 个 RGBA 元组的列表
    """
    if len(block) < 16:
        return [(0, 0, 0, 255)] * 16
    
    # 前 8 字节: Alpha 块
    alpha_block = block[:8]
    alphas = decode_alpha_block(alpha_block)
    
    # 后 8 字节: 颜色块 (BC1 格式，但始终使用 4 色模式)
    color_block = block[8:16]
    
    # 解码颜色部分
    color0, color1 = struct.unpack('<HH', color_block[:4])
    c0 = unpack_rgb565(color0)
    c1 = unpack_rgb565(color1)
    
    # BC3 颜色块始终使用 4 色模式（忽略 color0 > color1 条件）
    palette = [
        c0,
        c1,
        interpolate_color(c0, c1, 1/3),
        interpolate_color(c0, c1, 2/3),
    ]
    
    # 读取颜色索引
    indices = struct.unpack('<I', color_block[4:8])[0]
    
    # 组合颜色和 alpha
    pixels = []
    for i in range(16):
        color_idx = (indices >> (i * 2)) & 0x3
        r, g, b = palette[color_idx]
        a = alphas[i]
        pixels.append((r, g, b, a))
    
    return pixels


def decode_bc3_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC3 纹理为 RGBA
    
    Args:
        data: BC3 压缩数据
        width: 纹理宽度
        height: 纹理高度
    
    Returns:
        RGBA 像素数据 (width * height * 4 bytes)
    """
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    
    result = bytearray(width * height * 4)
    
    block_idx = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block_offset = block_idx * 16  # BC3 块是 16 字节
            if block_offset + 16 <= len(data):
                block_data = data[block_offset:block_offset + 16]
            else:
                block_data = b'\x00' * 16
            
            pixels = decode_bc3_block(block_data)
            
            for py in range(4):
                for px in range(4):
                    gx = bx * 4 + px
                    gy = by * 4 + py
                    
                    if gx < width and gy < height:
                        pixel_idx = py * 4 + px
                        r, g, b, a = pixels[pixel_idx]
                        
                        out_idx = (gy * width + gx) * 4
                        result[out_idx] = r
                        result[out_idx + 1] = g
                        result[out_idx + 2] = b
                        result[out_idx + 3] = a
            
            block_idx += 1
    
    return bytes(result)


# 注册解码器
@register_decoder('BC3')
def decode_bc3(data: bytes, width: int, height: int) -> bytes:
    """BC3 解码器入口"""
    return decode_bc3_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC3 decoder...")
    
    # 测试 Alpha 块解码
    # alpha0 = 255, alpha1 = 0, 所有索引 = 0 (使用 alpha0)
    alpha_block = bytes([255, 0, 0, 0, 0, 0, 0, 0])
    alphas = decode_alpha_block(alpha_block)
    assert alphas[0] == 255, f"Expected 255, got {alphas[0]}"
    print("✓ Alpha block test passed")
    
    # 测试完整 BC3 块
    # Alpha 块: 全不透明
    # 颜色块: 纯红色 (同 BC1)
    test_block = (
        bytes([255, 255, 0, 0, 0, 0, 0, 0]) +  # Alpha: alpha0=alpha1=255
        struct.pack('<HHI', 0xF800, 0x0000, 0x00000000)  # Color: 红色
    )
    
    pixels = decode_bc3_block(test_block)
    assert pixels[0] == (248, 0, 0, 255), f"Expected red, got {pixels[0]}"
    print("✓ BC3 block decode test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc3_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    print(f"✓ BC3 texture decode test passed ({width}x{height})")
