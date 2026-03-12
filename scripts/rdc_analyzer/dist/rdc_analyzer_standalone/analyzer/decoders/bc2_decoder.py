"""
BC2 (DXT3) Texture Decoder

BC2 压缩格式解码器，用于解压带显式 Alpha 的纹理。

格式规格:
- 4x4 像素块 = 16 字节
- 8 字节 Alpha 数据:
  - 每像素 4-bit 显式 Alpha (16 × 4-bit = 64-bit)
  - 直接存储，无插值（与 BC3 不同！）
- 8 字节颜色数据 (同 BC1):
  - 2 个 RGB565 颜色端点 (4 字节)
  - 16 个 2-bit 索引 (4 字节)
- 4:1 压缩比

与 BC3 的区别:
- BC2: 4-bit 显式 Alpha，适合锐利边缘
- BC3: 8-bit 插值 Alpha，适合平滑渐变

参考:
- https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc2
- https://www.khronos.org/opengl/wiki/S3_Texture_Compression#DXT3

Vulkan 格式:
- VK_FORMAT_BC2_UNORM_BLOCK
- VK_FORMAT_BC2_SRGB_BLOCK

DXGI 格式:
- DXGI_FORMAT_BC2_UNORM
- DXGI_FORMAT_BC2_UNORM_SRGB
"""

import struct
from typing import List, Tuple

from .texture_decoder import register_decoder
from .bc1_decoder import unpack_rgb565, interpolate_color


def decode_explicit_alpha_block(block: bytes) -> List[int]:
    """
    解码 BC2 显式 Alpha 块 (8 bytes -> 16 alpha values)
    
    BC2 Alpha 存储方式:
    - 每像素 4-bit (0-15)
    - 扩展到 8-bit: alpha8 = alpha4 * 17 (或 alpha4 << 4 | alpha4)
    - 像素按行优先顺序存储
    
    Args:
        block: 8 字节的 Alpha 块数据
    
    Returns:
        16 个 alpha 值 (0-255) 的列表
    """
    if len(block) < 8:
        return [255] * 16
    
    alphas = []
    
    # 8 字节 = 64 bits = 16 × 4-bit Alpha 值
    # 每 2 字节包含 4 个像素的 Alpha (一行)
    for row in range(4):
        # 读取一行的 2 字节 (4 个 4-bit Alpha)
        row_data = struct.unpack('<H', block[row * 2:row * 2 + 2])[0]
        
        for col in range(4):
            # 提取 4-bit Alpha
            alpha4 = (row_data >> (col * 4)) & 0xF
            # 扩展到 8-bit: 0->0, 15->255
            alpha8 = (alpha4 << 4) | alpha4  # 等价于 alpha4 * 17
            alphas.append(alpha8)
    
    return alphas


def decode_bc2_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC2 块 (16 bytes -> 16 RGBA pixels)
    
    Args:
        block: 16 字节的 BC2 块数据
    
    Returns:
        16 个 RGBA 元组的列表
    """
    if len(block) < 16:
        return [(0, 0, 0, 255)] * 16
    
    # 前 8 字节: 显式 Alpha 块
    alpha_block = block[:8]
    alphas = decode_explicit_alpha_block(alpha_block)
    
    # 后 8 字节: 颜色块 (BC1 格式，但始终使用 4 色模式)
    color_block = block[8:16]
    
    # 解码颜色部分
    color0, color1 = struct.unpack('<HH', color_block[:4])
    c0 = unpack_rgb565(color0)
    c1 = unpack_rgb565(color1)
    
    # BC2 颜色块始终使用 4 色模式（与 BC3 相同）
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


def decode_bc2_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC2 纹理为 RGBA
    
    Args:
        data: BC2 压缩数据
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
            block_offset = block_idx * 16  # BC2 块是 16 字节
            if block_offset + 16 <= len(data):
                block_data = data[block_offset:block_offset + 16]
            else:
                block_data = b'\x00' * 16
            
            pixels = decode_bc2_block(block_data)
            
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
@register_decoder('BC2')
def decode_bc2(data: bytes, width: int, height: int) -> bytes:
    """BC2 解码器入口"""
    return decode_bc2_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC2 decoder...")
    
    # 测试显式 Alpha 块解码
    # 所有 4-bit Alpha = 15 (0xFF) -> 扩展为 255
    alpha_block = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    alphas = decode_explicit_alpha_block(alpha_block)
    assert alphas[0] == 255, f"Expected 255, got {alphas[0]}"
    print("✓ Explicit alpha (all 255) test passed")
    
    # 测试 4-bit Alpha = 8 (中值) -> 扩展为 136
    # 0x88 = 每个像素 Alpha = 8
    alpha_block_mid = bytes([0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88])
    alphas_mid = decode_explicit_alpha_block(alpha_block_mid)
    assert alphas_mid[0] == 136, f"Expected 136, got {alphas_mid[0]}"
    print("✓ Explicit alpha (mid value) test passed")
    
    # 测试完整 BC2 块
    # Alpha: 全不透明
    # 颜色: 纯红色 (同 BC1)
    test_block = (
        bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]) +  # Alpha: all 255
        struct.pack('<HHI', 0xF800, 0x0000, 0x00000000)  # Color: 红色
    )
    
    pixels = decode_bc2_block(test_block)
    assert pixels[0] == (248, 0, 0, 255), f"Expected red with alpha, got {pixels[0]}"
    print("✓ BC2 block decode test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc2_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    print(f"✓ BC2 texture decode test passed ({width}x{height})")
