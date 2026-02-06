"""
BC5 Texture Decoder

BC5 压缩格式解码器，用于解压双通道纹理（法线贴图等）。

格式规格:
- 4x4 像素块 = 16 字节
- 2 个独立的 BC4 块:
  - 第一个 8 字节: R 通道
  - 第二个 8 字节: G 通道
- 输出: 双通道 RG，映射为 (R, G, 0, 255)

法线贴图应用:
- R 通道存储法线的 X 分量
- G 通道存储法线的 Y 分量
- Z 分量可由 Z = sqrt(1 - X² - Y²) 计算得出

参考:
- https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc5
- https://www.khronos.org/opengl/wiki/S3_Texture_Compression#BC4/BC5

Vulkan 格式:
- VK_FORMAT_BC5_UNORM_BLOCK
- VK_FORMAT_BC5_SNORM_BLOCK

DXGI 格式:
- DXGI_FORMAT_BC5_UNORM
- DXGI_FORMAT_BC5_SNORM
"""

from typing import List, Tuple

from .texture_decoder import register_decoder
from .bc3_decoder import decode_alpha_block


def decode_bc5_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC5 块 (16 bytes -> 16 RG RGBA pixels)
    
    Args:
        block: 16 字节的 BC5 块数据
    
    Returns:
        16 个 RGBA 元组的列表，格式为 (R, G, 0, 255)
    """
    if len(block) < 16:
        return [(0, 0, 0, 255)] * 16
    
    # 前 8 字节: R 通道 (BC4 格式)
    red_block = block[:8]
    red_values = decode_alpha_block(red_block)
    
    # 后 8 字节: G 通道 (BC4 格式)
    green_block = block[8:16]
    green_values = decode_alpha_block(green_block)
    
    # 组合为 RGBA，B=0, A=255
    pixels = []
    for i in range(16):
        r = red_values[i]
        g = green_values[i]
        pixels.append((r, g, 0, 255))
    
    return pixels


def decode_bc5_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC5 纹理为 RGBA
    
    Args:
        data: BC5 压缩数据
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
            block_offset = block_idx * 16  # BC5 块是 16 字节
            if block_offset + 16 <= len(data):
                block_data = data[block_offset:block_offset + 16]
            else:
                block_data = b'\x00' * 16
            
            pixels = decode_bc5_block(block_data)
            
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
@register_decoder('BC5')
def decode_bc5(data: bytes, width: int, height: int) -> bytes:
    """BC5 解码器入口"""
    return decode_bc5_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC5 decoder...")
    
    # 测试 BC5 块解码
    # R 通道: red0=255, red1=0, 索引=0 -> R=255
    # G 通道: green0=128, green1=0, 索引=0 -> G=128
    test_block = (
        bytes([255, 0, 0, 0, 0, 0, 0, 0]) +  # R 通道
        bytes([128, 0, 0, 0, 0, 0, 0, 0])     # G 通道
    )
    
    pixels = decode_bc5_block(test_block)
    assert pixels[0] == (255, 128, 0, 255), f"Expected (255, 128, 0, 255), got {pixels[0]}"
    print("✓ BC5 block decode test passed")
    
    # 测试法线贴图典型值 (X=0.5, Y=0.5 -> R=128, G=128)
    normal_block = (
        bytes([128, 128, 0, 0, 0, 0, 0, 0]) +  # R = 128 (X=0)
        bytes([128, 128, 0, 0, 0, 0, 0, 0])     # G = 128 (Y=0)
    )
    
    normal_pixels = decode_bc5_block(normal_block)
    assert normal_pixels[0] == (128, 128, 0, 255), f"Expected (128, 128, 0, 255), got {normal_pixels[0]}"
    print("✓ BC5 normal map value test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc5_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    assert rgba[0] == 255  # R
    assert rgba[1] == 128  # G
    assert rgba[2] == 0    # B
    assert rgba[3] == 255  # A
    print(f"✓ BC5 texture decode test passed ({width}x{height})")
