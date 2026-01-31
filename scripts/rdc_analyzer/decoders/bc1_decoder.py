"""
BC1 (DXT1) Texture Decoder

BC1 压缩格式解码器，用于解压 DXT1 纹理。

格式规格:
- 4x4 像素块 = 8 字节
- 2 个 RGB565 颜色端点 (4 字节)
- 16 个 2-bit 索引 (4 字节)
- 4:1 压缩比 (64 pixels * 4 bytes = 256 -> 8 bytes)

参考:
- https://www.khronos.org/opengl/wiki/S3_Texture_Compression
- https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc1
"""

import struct
from typing import List, Tuple

# 从父模块导入注册器
from .texture_decoder import register_decoder


def unpack_rgb565(color: int) -> Tuple[int, int, int]:
    """
    解包 RGB565 颜色为 RGB888
    
    RGB565 布局: RRRRR GGGGGG BBBBB (16-bit)
    """
    r = (color >> 11) & 0x1F  # 5 bits
    g = (color >> 5) & 0x3F   # 6 bits
    b = color & 0x1F          # 5 bits
    
    # 扩展到 8-bit (复制高位到低位)
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    
    return (r, g, b)


def interpolate_color(c0: Tuple[int, int, int], c1: Tuple[int, int, int], 
                      t: float) -> Tuple[int, int, int]:
    """线性插值两个颜色"""
    return (
        int(c0[0] + (c1[0] - c0[0]) * t),
        int(c0[1] + (c1[1] - c0[1]) * t),
        int(c0[2] + (c1[2] - c0[2]) * t),
    )


def decode_bc1_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC1 块 (8 bytes -> 16 RGBA pixels)
    
    Args:
        block: 8 字节的 BC1 块数据
    
    Returns:
        16 个 RGBA 元组的列表，按行主序排列 (4x4)
    """
    if len(block) < 8:
        # 数据不足，返回黑色块
        return [(0, 0, 0, 255)] * 16
    
    # 读取两个 RGB565 颜色端点
    color0, color1 = struct.unpack('<HH', block[:4])
    
    # 解包为 RGB888
    c0 = unpack_rgb565(color0)
    c1 = unpack_rgb565(color1)
    
    # 构建 4 色调色板
    if color0 > color1:
        # 4 色模式 (不透明)
        palette = [
            (*c0, 255),                                    # color_0
            (*c1, 255),                                    # color_1
            (*interpolate_color(c0, c1, 1/3), 255),        # 2/3 * c0 + 1/3 * c1
            (*interpolate_color(c0, c1, 2/3), 255),        # 1/3 * c0 + 2/3 * c1
        ]
    else:
        # 3 色模式 + 透明 (1-bit alpha)
        palette = [
            (*c0, 255),                                    # color_0
            (*c1, 255),                                    # color_1
            (*interpolate_color(c0, c1, 0.5), 255),        # 1/2 * c0 + 1/2 * c1
            (0, 0, 0, 0),                                  # 透明黑
        ]
    
    # 读取 16 个 2-bit 索引 (4 字节，低位在前)
    indices = struct.unpack('<I', block[4:8])[0]
    
    # 解码 16 个像素
    pixels = []
    for i in range(16):
        idx = (indices >> (i * 2)) & 0x3
        pixels.append(palette[idx])
    
    return pixels


def decode_bc1_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC1 纹理为 RGBA
    
    Args:
        data: BC1 压缩数据
        width: 纹理宽度
        height: 纹理高度
    
    Returns:
        RGBA 像素数据 (width * height * 4 bytes)
    """
    # 计算块数量（向上取整到 4 的倍数）
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    
    # 分配输出缓冲区
    result = bytearray(width * height * 4)
    
    # 遍历所有块
    block_idx = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            # 读取块数据
            block_offset = block_idx * 8
            if block_offset + 8 <= len(data):
                block_data = data[block_offset:block_offset + 8]
            else:
                # 数据不足，使用零填充
                block_data = b'\x00' * 8
            
            # 解码块
            pixels = decode_bc1_block(block_data)
            
            # 写入输出缓冲区
            for py in range(4):
                for px in range(4):
                    # 计算全局坐标
                    gx = bx * 4 + px
                    gy = by * 4 + py
                    
                    # 边界检查
                    if gx < width and gy < height:
                        pixel_idx = py * 4 + px
                        r, g, b, a = pixels[pixel_idx]
                        
                        # 写入 RGBA
                        out_idx = (gy * width + gx) * 4
                        result[out_idx] = r
                        result[out_idx + 1] = g
                        result[out_idx + 2] = b
                        result[out_idx + 3] = a
            
            block_idx += 1
    
    return bytes(result)


# 注册解码器
@register_decoder('BC1')
def decode_bc1(data: bytes, width: int, height: int) -> bytes:
    """BC1 解码器入口"""
    return decode_bc1_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    # 简单测试: 创建一个纯色 BC1 块并解码
    print("Testing BC1 decoder...")
    
    # 创建测试数据: 纯红色块
    # color0 = 0xF800 (红色 RGB565), color1 = 0x0000 (黑色)
    # 所有索引 = 0 (使用 color0)
    test_block = struct.pack('<HHI', 0xF800, 0x0000, 0x00000000)
    
    pixels = decode_bc1_block(test_block)
    print(f"Block pixels: {pixels[:4]}...")  # 前 4 个像素
    
    # 验证: 应该都是红色
    expected = (248, 0, 0, 255)  # RGB565 红色扩展到 RGB888
    assert pixels[0][:3] == expected[:3], f"Expected {expected}, got {pixels[0]}"
    
    print("✓ BC1 block decode test passed")
    
    # 测试完整纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc1_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    print(f"✓ BC1 texture decode test passed ({width}x{height})")
