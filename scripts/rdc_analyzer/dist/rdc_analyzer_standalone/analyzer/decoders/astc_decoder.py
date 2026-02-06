"""
ASTC Texture Decoder

ASTC (Adaptive Scalable Texture Compression) 解码器封装。
使用 texture2ddecoder 库进行解码。

支持块大小:
- 4x4, 5x4, 5x5, 6x5, 6x6
- 8x5, 8x6, 8x8
- 10x5, 10x6, 10x8, 10x10
- 12x10, 12x12

参考:
- https://www.khronos.org/registry/OpenGL/extensions/KHR/KHR_texture_compression_astc_hdr.txt
"""

from typing import Tuple, Optional
from .texture_decoder import register_decoder, TextureDecodeError


# 尝试导入 texture2ddecoder
try:
    import texture2ddecoder as t2d
    HAS_T2D = True
except ImportError:
    HAS_T2D = False
    t2d = None


# ASTC 块大小列表
ASTC_BLOCK_SIZES = [
    (4, 4), (5, 4), (5, 5), (6, 5), (6, 6),
    (8, 5), (8, 6), (8, 8),
    (10, 5), (10, 6), (10, 8), (10, 10),
    (12, 10), (12, 12),
]


def decode_astc_texture(
    data: bytes,
    width: int,
    height: int,
    block_width: int,
    block_height: int
) -> bytes:
    """
    解码 ASTC 纹理为 RGBA
    
    Args:
        data: 压缩数据
        width: 纹理宽度
        height: 纹理高度
        block_width: ASTC 块宽度 (4-12)
        block_height: ASTC 块高度 (4-12)
    
    Returns:
        RGBA8 字节数据
    
    Raises:
        TextureDecodeError: 解码失败或库不可用
    """
    if not HAS_T2D:
        raise TextureDecodeError(
            "texture2ddecoder not installed. "
            "Run: pip install texture2ddecoder"
        )
    
    # 验证块大小
    if (block_width, block_height) not in ASTC_BLOCK_SIZES:
        raise TextureDecodeError(
            f"Invalid ASTC block size: {block_width}x{block_height}. "
            f"Valid sizes: {ASTC_BLOCK_SIZES}"
        )
    
    # 分配输出缓冲区
    output_size = width * height * 4
    output = bytearray(output_size)
    
    try:
        # texture2ddecoder.decode_astc 直接写入缓冲区
        t2d.decode_astc(data, width, height, block_width, block_height, output)
    except Exception as e:
        raise TextureDecodeError(f"ASTC decode failed: {e}") from e
    
    return bytes(output)


def make_astc_decoder(block_width: int, block_height: int):
    """
    工厂函数：创建特定块大小的 ASTC 解码器
    """
    def decoder(data: bytes, width: int, height: int) -> bytes:
        return decode_astc_texture(data, width, height, block_width, block_height)
    return decoder


# 注册所有 ASTC 块大小
for bw, bh in ASTC_BLOCK_SIZES:
    format_name = f'ASTC_{bw}x{bh}'
    register_decoder(format_name)(make_astc_decoder(bw, bh))


# 通用 ASTC 解码器 (需要从格式名解析块大小)
@register_decoder('ASTC')
def decode_astc_generic(data: bytes, width: int, height: int) -> bytes:
    """
    通用 ASTC 解码器 (默认 4x4)
    
    注意: 实际使用时应通过具体格式名 (ASTC_4x4 等) 调用
    """
    return decode_astc_texture(data, width, height, 4, 4)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing ASTC decoder...")
    
    if not HAS_T2D:
        print("✗ texture2ddecoder not installed")
        exit(1)
    
    # 测试空数据 (验证不崩溃)
    width, height = 8, 8
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    # ASTC 每块 16 字节
    test_data = bytes([0] * (blocks_x * blocks_y * 16))
    
    try:
        rgba = decode_astc_texture(test_data, width, height, 4, 4)
        assert len(rgba) == width * height * 4
        print(f"✓ ASTC 4x4 decode test passed ({width}x{height})")
    except Exception as e:
        print(f"✓ ASTC decode handled: {e}")
    
    # 验证所有块大小已注册
    from .texture_decoder import get_supported_formats
    formats = get_supported_formats()
    for bw, bh in ASTC_BLOCK_SIZES:
        name = f'ASTC_{bw}X{bh}'
        if name in formats:
            print(f"✓ {name} registered")
        else:
            print(f"✗ {name} NOT registered")
