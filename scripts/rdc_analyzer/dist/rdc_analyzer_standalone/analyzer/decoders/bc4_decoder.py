"""
BC4 Texture Decoder

BC4 压缩格式解码器，用于解压单通道纹理（高度图、灰度遮罩等）。

格式规格:
- 4x4 像素块 = 8 字节
- 与 BC3 的 Alpha 块编码完全相同:
  - 2 个 8-bit 端点 (2 字节)
  - 16 个 3-bit 索引 (6 字节)
- 输出: 单通道 R，映射为 (R, R, R, 255) 灰度

参考:
- https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc4
- https://www.khronos.org/opengl/wiki/S3_Texture_Compression#BC4/BC5

Vulkan 格式:
- VK_FORMAT_BC4_UNORM_BLOCK
- VK_FORMAT_BC4_SNORM_BLOCK

DXGI 格式:
- DXGI_FORMAT_BC4_UNORM
- DXGI_FORMAT_BC4_SNORM
"""

from typing import List, Tuple

from .texture_decoder import register_decoder
from .bc3_decoder import decode_alpha_block


def decode_bc4_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC4 块 (8 bytes -> 16 灰度 RGBA pixels)
    
    Args:
        block: 8 字节的 BC4 块数据
    
    Returns:
        16 个 RGBA 元组的列表，格式为 (R, R, R, 255)
    """
    # BC4 块与 BC3 Alpha 块完全相同
    red_values = decode_alpha_block(block)
    
    # 将单通道 R 值映射为灰度 RGBA
    pixels = []
    for r in red_values:
        pixels.append((r, r, r, 255))
    
    return pixels


def decode_bc4_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC4 纹理为 RGBA
    
    Args:
        data: BC4 压缩数据
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
            block_offset = block_idx * 8  # BC4 块是 8 字节
            if block_offset + 8 <= len(data):
                block_data = data[block_offset:block_offset + 8]
            else:
                block_data = b'\x00' * 8
            
            pixels = decode_bc4_block(block_data)
            
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
@register_decoder('BC4')
def decode_bc4(data: bytes, width: int, height: int) -> bytes:
    """BC4 解码器入口"""
    return decode_bc4_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC4 decoder...")
    
    # 测试 BC4 块解码
    # red0 = 255, red1 = 0, 所有索引 = 0 (使用 red0 = 255)
    test_block = bytes([255, 0, 0, 0, 0, 0, 0, 0])
    pixels = decode_bc4_block(test_block)
    assert pixels[0] == (255, 255, 255, 255), f"Expected white, got {pixels[0]}"
    print("✓ BC4 block decode test passed")
    
    # 测试灰度中值
    # red0 = 200, red1 = 100, 索引 = 0 使用 red0
    test_block2 = bytes([200, 100, 0, 0, 0, 0, 0, 0])
    pixels2 = decode_bc4_block(test_block2)
    assert pixels2[0] == (200, 200, 200, 255), f"Expected gray 200, got {pixels2[0]}"
    print("✓ BC4 gray value test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc4_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    assert rgba[0] == 255  # R
    assert rgba[1] == 255  # G
    assert rgba[2] == 255  # B
    assert rgba[3] == 255  # A
    print(f"✓ BC4 texture decode test passed ({width}x{height})")
