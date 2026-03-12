"""
ETC/ETC2/EAC Texture Decoder

ETC (Ericsson Texture Compression) 系列解码器封装。
使用 texture2ddecoder 库进行解码。

支持格式:
- ETC1: RGB (OpenGL ES 2.0)
- ETC2_RGB: RGB (OpenGL ES 3.0)
- ETC2_RGBA1: RGB + 1-bit Alpha (punch-through)
- ETC2_RGBA8: RGB + 8-bit Alpha
- EAC_R11: 单通道 11-bit
- EAC_RG11: 双通道 11-bit

参考:
- https://www.khronos.org/registry/OpenGL/extensions/OES/OES_compressed_ETC1_RGB8_texture.txt
- https://www.khronos.org/registry/OpenGL/specs/es/3.0/es_spec_3.0.pdf (Appendix C)
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


def _check_t2d():
    """检查 texture2ddecoder 是否可用"""
    if not HAS_T2D:
        raise TextureDecodeError(
            "texture2ddecoder not installed. "
            "Run: pip install texture2ddecoder"
        )


# ============================================================================
# ETC1 解码器
# ============================================================================

@register_decoder('ETC1')
def decode_etc1(data: bytes, width: int, height: int) -> bytes:
    """
    解码 ETC1 纹理为 RGBA
    
    ETC1 只有 RGB，Alpha 设为 255
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_etc1(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ETC1 decode failed: {e}") from e
    
    return bytes(output)


# ============================================================================
# ETC2 解码器
# ============================================================================

@register_decoder('ETC2')
@register_decoder('ETC2_RGB')
@register_decoder('ETC2_RGB8')
def decode_etc2_rgb(data: bytes, width: int, height: int) -> bytes:
    """
    解码 ETC2 RGB 纹理为 RGBA
    
    ETC2 RGB 只有 RGB，Alpha 设为 255
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_etc2(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ETC2 RGB decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('ETC2_RGBA1')
@register_decoder('ETC2_RGB_A1')
@register_decoder('ETC2_PUNCHTHROUGH')
def decode_etc2_rgba1(data: bytes, width: int, height: int) -> bytes:
    """
    解码 ETC2 RGB + 1-bit Alpha (punch-through) 纹理为 RGBA
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_etc2a1(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ETC2 RGBA1 decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('ETC2_RGBA')
@register_decoder('ETC2_RGBA8')
def decode_etc2_rgba(data: bytes, width: int, height: int) -> bytes:
    """
    解码 ETC2 RGBA 纹理为 RGBA
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_etc2a8(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ETC2 RGBA decode failed: {e}") from e
    
    return bytes(output)


# ============================================================================
# EAC 解码器 (单/双通道)
# ============================================================================

@register_decoder('EAC_R11')
@register_decoder('EAC_R')
def decode_eac_r11(data: bytes, width: int, height: int) -> bytes:
    """
    解码 EAC R11 单通道纹理为 RGBA
    
    输出: (R, R, R, 255) 灰度格式
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_eacr(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"EAC R11 decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('EAC_R11_SIGNED')
def decode_eac_r11_signed(data: bytes, width: int, height: int) -> bytes:
    """
    解码 EAC R11 有符号单通道纹理为 RGBA
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_eacr_signed(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"EAC R11 signed decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('EAC_RG11')
@register_decoder('EAC_RG')
def decode_eac_rg11(data: bytes, width: int, height: int) -> bytes:
    """
    解码 EAC RG11 双通道纹理为 RGBA
    
    输出: (R, G, 0, 255) 双通道格式 (常用于法线贴图)
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_eacrg(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"EAC RG11 decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('EAC_RG11_SIGNED')
def decode_eac_rg11_signed(data: bytes, width: int, height: int) -> bytes:
    """
    解码 EAC RG11 有符号双通道纹理为 RGBA
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_eacrg_signed(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"EAC RG11 signed decode failed: {e}") from e
    
    return bytes(output)


# ============================================================================
# PVRTC 解码器 (iOS)
# ============================================================================

def decode_pvrtc_texture(
    data: bytes,
    width: int,
    height: int,
    is_2bpp: bool = False
) -> bytes:
    """
    解码 PVRTC 纹理为 RGBA
    
    Args:
        data: 压缩数据
        width: 纹理宽度
        height: 纹理高度
        is_2bpp: True=2bpp, False=4bpp
    
    Returns:
        RGBA8 字节数据
    """
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_pvrtc(data, width, height, output, is_2bpp)
    except Exception as e:
        raise TextureDecodeError(f"PVRTC decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('PVRTC_4BPP')
@register_decoder('PVRTC1_4BPP')
def decode_pvrtc_4bpp(data: bytes, width: int, height: int) -> bytes:
    """解码 PVRTC 4bpp"""
    return decode_pvrtc_texture(data, width, height, is_2bpp=False)


@register_decoder('PVRTC_2BPP')
@register_decoder('PVRTC1_2BPP')
def decode_pvrtc_2bpp(data: bytes, width: int, height: int) -> bytes:
    """解码 PVRTC 2bpp"""
    return decode_pvrtc_texture(data, width, height, is_2bpp=True)


# ============================================================================
# ATC 解码器 (Qualcomm Adreno)
# ============================================================================

@register_decoder('ATC_RGB')
def decode_atc_rgb(data: bytes, width: int, height: int) -> bytes:
    """解码 ATC RGB"""
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_atc_rgb4(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ATC RGB decode failed: {e}") from e
    
    return bytes(output)


@register_decoder('ATC_RGBA')
@register_decoder('ATC_RGBA8')
def decode_atc_rgba(data: bytes, width: int, height: int) -> bytes:
    """解码 ATC RGBA"""
    _check_t2d()
    
    output = bytearray(width * height * 4)
    
    try:
        t2d.decode_atc_rgba8(data, width, height, output)
    except Exception as e:
        raise TextureDecodeError(f"ATC RGBA decode failed: {e}") from e
    
    return bytes(output)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing ETC/ETC2/EAC decoders...")
    
    if not HAS_T2D:
        print("✗ texture2ddecoder not installed")
        exit(1)
    
    # 测试空数据 (验证不崩溃)
    width, height = 8, 8
    blocks = ((width + 3) // 4) * ((height + 3) // 4)
    
    # ETC1/ETC2 每块 8 字节
    test_data_8 = bytes([0] * (blocks * 8))
    # ETC2 RGBA / EAC RG 每块 16 字节
    test_data_16 = bytes([0] * (blocks * 16))
    
    tests = [
        ("ETC1", decode_etc1, test_data_8),
        ("ETC2_RGB", decode_etc2_rgb, test_data_8),
        ("ETC2_RGBA1", decode_etc2_rgba1, test_data_8),
        ("ETC2_RGBA", decode_etc2_rgba, test_data_16),
        ("EAC_R11", decode_eac_r11, test_data_8),
        ("EAC_RG11", decode_eac_rg11, test_data_16),
    ]
    
    for name, func, data in tests:
        try:
            rgba = func(data, width, height)
            assert len(rgba) == width * height * 4
            print(f"✓ {name} decode test passed")
        except Exception as e:
            print(f"✗ {name} decode failed: {e}")
