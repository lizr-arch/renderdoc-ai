"""
Texture Decoder - 统一入口

提供纹理解码的统一接口，支持多种压缩格式。
"""

from typing import Tuple, Optional, Dict, Callable, List
from pathlib import Path
import struct


class TextureDecodeError(Exception):
    """纹理解码错误"""
    pass


# 格式解码器注册表
_DECODERS: Dict[str, Callable] = {}


def register_decoder(format_name: str):
    """装饰器：注册格式解码器"""
    def decorator(func: Callable):
        _DECODERS[format_name.upper()] = func
        return func
    return decorator


def get_supported_formats() -> List[str]:
    """获取支持的格式列表"""
    return list(_DECODERS.keys())


def check_mobile_support() -> Tuple[bool, str]:
    """
    检查移动端格式支持状态
    
    Returns:
        (is_available, message)
        - (True, "...") if texture2ddecoder is installed
        - (False, "pip install ...") if not installed
    """
    try:
        import texture2ddecoder
        return True, f"texture2ddecoder v{getattr(texture2ddecoder, '__version__', 'unknown')} installed"
    except ImportError:
        return False, "Mobile formats (ASTC/ETC2) unavailable. Run: pip install texture2ddecoder"


def get_format_categories() -> Dict[str, List[str]]:
    """
    按类别分组返回支持的格式
    
    Returns:
        {
            'bcn': ['BC1', 'BC2', ...],      # 无依赖
            'astc': ['ASTC_4x4', ...],       # 需要 texture2ddecoder
            'etc': ['ETC1', 'ETC2_RGB', ...],
            'other': ['UNCOMPRESSED', ...]
        }
    """
    all_formats = get_supported_formats()
    
    categories = {
        'bcn': [],       # Desktop (纯 Python)
        'astc': [],      # ASTC (texture2ddecoder)
        'etc': [],       # ETC/EAC (texture2ddecoder)
        'pvrtc_atc': [], # PVRTC/ATC (texture2ddecoder)
        'other': [],     # 未压缩等
    }
    
    for fmt in all_formats:
        if fmt.startswith('BC'):
            categories['bcn'].append(fmt)
        elif fmt.startswith('ASTC'):
            categories['astc'].append(fmt)
        elif fmt.startswith('ETC') or fmt.startswith('EAC'):
            categories['etc'].append(fmt)
        elif fmt.startswith('PVRTC') or fmt.startswith('ATC'):
            categories['pvrtc_atc'].append(fmt)
        else:
            categories['other'].append(fmt)
    
    return categories


def normalize_format_name(format_name: str) -> str:
    """
    标准化格式名称
    
    Examples:
        "VK_FORMAT_BC7_UNORM_BLOCK" -> "BC7"
        "DXGI_FORMAT_BC1_UNORM" -> "BC1"
        "BC7_SRGB" -> "BC7"
        "VK_FORMAT_ASTC_4x4_UNORM_BLOCK" -> "ASTC_4x4"
        "VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK" -> "ETC2_RGB"
        "DXGI_FORMAT_R16G16_FLOAT" -> "RG16F"
        "DXGI_FORMAT_D32_FLOAT_S8X24_UINT" -> "D32S8"
    """
    fmt = format_name.upper()
    
    # ASTC 格式: 提取块大小
    import re
    astc_match = re.search(r'ASTC[_\s]*(\d+)[Xx](\d+)', fmt)
    if astc_match:
        bw, bh = astc_match.groups()
        return f'ASTC_{bw}x{bh}'
    
    # ETC2/EAC 格式
    if 'ETC2' in fmt:
        if 'R8G8B8A8' in fmt or 'RGBA8' in fmt:
            return 'ETC2_RGBA8'
        elif 'R8G8B8A1' in fmt or 'RGBA1' in fmt:
            return 'ETC2_RGBA1'
        else:
            return 'ETC2_RGB'
    
    if 'ETC1' in fmt:
        return 'ETC1'
    
    if 'EAC' in fmt:
        if 'R11G11' in fmt or 'RG11' in fmt:
            if 'SIGNED' in fmt or 'SNORM' in fmt:
                return 'EAC_RG11_SIGNED'
            return 'EAC_RG11'
        else:
            if 'SIGNED' in fmt or 'SNORM' in fmt:
                return 'EAC_R11_SIGNED'
            return 'EAC_R11'
    
    # PVRTC 格式
    if 'PVRTC' in fmt:
        if '2BPP' in fmt or '2_BPP' in fmt:
            return 'PVRTC_2BPP'
        return 'PVRTC_4BPP'
    
    # ATC 格式
    if 'ATC' in fmt:
        if 'RGBA' in fmt:
            return 'ATC_RGBA'
        return 'ATC_RGB'
    
    # ========== Vulkan 特有格式 ==========
    
    # B10G11R11_UFLOAT_PACK32 (与 R11G11B10F 通道顺序相反)
    if 'B10G11R11' in fmt:
        return 'B10G11R11F'
    
    # A2R10G10B10 / A2B10G10R10 格式
    if 'A2R10G10B10' in fmt:
        return 'A2R10G10B10'
    if 'A2B10G10R10' in fmt:
        return 'A2B10G10R10'
    
    # A8B8G8R8 格式 (Vulkan 专用)
    if 'A8B8G8R8' in fmt:
        return 'A8B8G8R8'
    
    # R16_UNORM / D16_UNORM
    if 'R16_UNORM' in fmt:
        return 'R16_UNORM'
    if 'R16G16_UNORM' in fmt:
        return 'R16G16_UNORM'
    if 'D16_UNORM' in fmt:
        return 'D16_UNORM'
    
    # S8_UINT (纯模板)
    if 'S8_UINT' in fmt and 'D32' not in fmt and 'D24' not in fmt:
        return 'S8_UINT'
    
    # ========== Vulkan 第二批格式 (v1.6.0) ==========
    
    # SNORM 格式 (有符号归一化)
    if 'R8_SNORM' in fmt:
        return 'R8_SNORM'
    if 'R16_SNORM' in fmt:
        return 'R16_SNORM'
    if 'R8G8_SNORM' in fmt:
        return 'R8G8_SNORM'
    if 'R16G16_SNORM' in fmt:
        return 'R16G16_SNORM'
    
    # SFLOAT 格式 (有符号浮点) - 注意：需要在通用 FLOAT 之前匹配
    if 'R16_SFLOAT' in fmt:
        return 'R16_SFLOAT'
    if 'R32_SFLOAT' in fmt and 'D32' not in fmt:
        return 'R32_SFLOAT'
    
    # Vulkan 深度+模板格式 (完整名称)
    if 'D24_UNORM_S8_UINT' in fmt:
        return 'D24_UNORM_S8_UINT'
    if 'D32_SFLOAT_S8_UINT' in fmt:
        return 'D32_SFLOAT_S8_UINT'
    
    # 提取 BC 格式编号
    for bc in ['BC7', 'BC6H', 'BC5', 'BC4', 'BC3', 'BC2', 'BC1']:
        if bc in fmt:
            return bc
    
    # ========== DXGI 特殊格式 ==========
    
    # 深度+模板格式
    if 'D32_FLOAT_S8X24' in fmt or 'D32_S8X24' in fmt:
        return 'D32S8'
    if 'R32G8X24_TYPELESS' in fmt:
        return 'D32S8'  # 通常用作深度模板
    if 'D24_UNORM_S8' in fmt or 'D24S8' in fmt:
        return 'D24S8'
    if 'D32_FLOAT' in fmt or 'D32_SFLOAT' in fmt:
        return 'D32F'
    if 'D16_UNORM' in fmt:
        return 'R16F'  # 作为灰度处理
    
    # R11G11B10 浮点
    if 'R11G11B10' in fmt:
        return 'R11G11B10F'
    
    # RGBA 浮点格式
    if 'R16G16B16A16' in fmt and 'FLOAT' in fmt:
        return 'RGBA16F'
    if 'R32G32B32A32' in fmt and 'FLOAT' in fmt:
        return 'RGBA32F'
    
    # RG 浮点格式
    if 'R16G16' in fmt and 'FLOAT' in fmt:
        return 'RG16F'
    if 'R32G32' in fmt and 'FLOAT' in fmt:
        return 'RG32F'
    
    # R 单通道浮点
    if 'R16' in fmt and 'FLOAT' in fmt:
        return 'R16F'
    if 'R32' in fmt and 'FLOAT' in fmt:
        return 'R32F'
    
    # RGBA8/BGRA8 格式
    if 'R8G8B8A8' in fmt:
        return 'RGBA8'
    if 'B8G8R8A8' in fmt or 'B8G8R8X8' in fmt:
        return 'BGRA8'
    
    # RG8 格式
    if 'R8G8' in fmt and 'B8' not in fmt:
        return 'RG8'
    
    # R8 单通道 (例如 DXGI_FORMAT_R8_UNORM)
    if 'R8_UNORM' in fmt or 'R8_SNORM' in fmt or 'R8_UINT' in fmt or 'R8_SINT' in fmt:
        return 'R8'
    
    # 仅 R8（需要排除 R8G8 等）
    if re.search(r'_R8$', fmt) or fmt == 'R8':
        return 'R8'
    
    # 检查是否是未压缩格式 (兜底)
    uncompressed = ['R8G8B8A8', 'B8G8R8A8']
    for uc in uncompressed:
        if uc in fmt:
            return 'UNCOMPRESSED'
    
    return fmt


def is_srgb_format(format_name: str) -> bool:
    """检查是否是 SRGB 格式"""
    fmt = format_name.upper()
    return 'SRGB' in fmt


def decode_texture(
    data: bytes,
    width: int,
    height: int,
    format_name: str,
    apply_srgb: bool = True
) -> bytes:
    """
    解码压缩纹理为 RGBA 像素数据
    
    Args:
        data: 压缩纹理数据
        width: 纹理宽度
        height: 纹理高度
        format_name: 格式名称 (如 "VK_FORMAT_BC7_UNORM_BLOCK")
        apply_srgb: 是否应用 SRGB 转换 (仅对 SRGB 格式)
    
    Returns:
        RGBA 像素数据 (width * height * 4 bytes)
    
    Raises:
        TextureDecodeError: 解码失败或格式不支持
    """
    # 标准化格式名
    normalized = normalize_format_name(format_name)
    
    # 查找解码器
    if normalized not in _DECODERS:
        raise TextureDecodeError(
            f"Unsupported format: {format_name} (normalized: {normalized}). "
            f"Supported: {', '.join(get_supported_formats())}"
        )
    
    decoder = _DECODERS[normalized]
    
    try:
        rgba_data = decoder(data, width, height)
    except Exception as e:
        raise TextureDecodeError(f"Decode failed for {format_name}: {e}") from e
    
    # 应用 SRGB 转换
    if apply_srgb and is_srgb_format(format_name):
        rgba_data = apply_srgb_to_linear(rgba_data)
    
    return rgba_data


def apply_srgb_to_linear(data: bytes) -> bytes:
    """
    SRGB -> 线性颜色空间转换
    
    注意: 对于 PNG 输出，通常不需要转换，因为 PNG 查看器会处理
    """
    # 目前直接返回，PNG 查看器会正确显示 SRGB
    return data


def save_as_png(
    rgba_data: bytes,
    width: int,
    height: int,
    output_path: Path,
    flip_vertical: bool = False
) -> Path:
    """
    将 RGBA 像素数据保存为 PNG 文件
    
    Args:
        rgba_data: RGBA 像素数据
        width: 图像宽度
        height: 图像高度
        output_path: 输出文件路径
        flip_vertical: 是否垂直翻转（某些 API 需要）
    
    Returns:
        保存的文件路径
    """
    try:
        from PIL import Image
    except ImportError:
        raise TextureDecodeError(
            "PIL not installed. Run: pip install Pillow"
        )
    
    # 确保数据大小正确
    expected_size = width * height * 4
    if len(rgba_data) != expected_size:
        raise TextureDecodeError(
            f"RGBA data size mismatch: got {len(rgba_data)}, "
            f"expected {expected_size} ({width}x{height}x4)"
        )
    
    # 创建 PIL Image
    img = Image.frombytes('RGBA', (width, height), rgba_data)
    
    # 垂直翻转（如果需要）
    if flip_vertical:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    
    # 确保输出目录存在
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存 PNG
    img.save(output_path, 'PNG')
    
    return output_path


def calculate_compressed_size(width: int, height: int, format_name: str) -> int:
    """
    计算压缩纹理的字节大小
    
    Args:
        width: 纹理宽度
        height: 纹理高度
        format_name: 格式名称
    
    Returns:
        压缩数据大小（字节）
    """
    normalized = normalize_format_name(format_name)
    
    # 块数量（向上取整到 4 的倍数）
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    num_blocks = blocks_x * blocks_y
    
    # 每块字节数
    bytes_per_block = {
        'BC1': 8,
        'BC2': 16,
        'BC3': 16,
        'BC4': 8,
        'BC5': 16,
        'BC6H': 16,
        'BC7': 16,
    }
    
    if normalized in bytes_per_block:
        return num_blocks * bytes_per_block[normalized]
    
    # 未压缩格式
    bpp = {
        'R8_UNORM': 1,
        'R8G8_UNORM': 2,
        'R8G8B8A8': 4,
        'B8G8R8A8': 4,
    }
    
    for fmt, bytes_pp in bpp.items():
        if fmt in format_name.upper():
            return width * height * bytes_pp
    
    raise TextureDecodeError(f"Cannot calculate size for format: {format_name}")


# ============================================================================
# 未压缩格式解码器
# ============================================================================

@register_decoder('UNCOMPRESSED')
def decode_uncompressed(data: bytes, width: int, height: int) -> bytes:
    """直接返回 RGBA 数据（假设已经是 RGBA 格式）"""
    expected = width * height * 4
    if len(data) >= expected:
        return data[:expected]
    
    # 如果数据不足，填充为黑色
    result = bytearray(expected)
    result[:len(data)] = data
    return bytes(result)


@register_decoder('R8_UNORM')
@register_decoder('R8')
def decode_r8_unorm(data: bytes, width: int, height: int) -> bytes:
    """解码单通道灰度图为 RGBA"""
    expected = width * height
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data), expected)):
        gray = data[i]
        idx = i * 4
        result[idx] = gray      # R
        result[idx + 1] = gray  # G
        result[idx + 2] = gray  # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


@register_decoder('RG8')
def decode_rg8(data: bytes, width: int, height: int) -> bytes:
    """解码双通道 RG8 为 RGBA"""
    expected = width * height * 2
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        r = data[i * 2]
        g = data[i * 2 + 1]
        idx = i * 4
        result[idx] = r        # R
        result[idx + 1] = g    # G
        result[idx + 2] = 0    # B
        result[idx + 3] = 255  # A
    
    return bytes(result)


@register_decoder('RGBA8')
def decode_rgba8(data: bytes, width: int, height: int) -> bytes:
    """RGBA8 直接拷贝"""
    expected = width * height * 4
    if len(data) >= expected:
        return data[:expected]
    result = bytearray(expected)
    result[:len(data)] = data
    return bytes(result)


@register_decoder('BGRA8')
@register_decoder('BGRX8')
def decode_bgra8(data: bytes, width: int, height: int) -> bytes:
    """BGRA8 转换为 RGBA"""
    expected = width * height * 4
    result = bytearray(expected)
    
    for i in range(min(len(data) // 4, width * height)):
        src = i * 4
        dst = i * 4
        if src + 3 < len(data):
            result[dst] = data[src + 2]      # R <- B
            result[dst + 1] = data[src + 1]  # G
            result[dst + 2] = data[src]      # B <- R
            result[dst + 3] = data[src + 3]  # A
    
    return bytes(result)


@register_decoder('R16F')
def decode_r16f(data: bytes, width: int, height: int) -> bytes:
    """解码 R16F (half float) 为 RGBA"""
    expected = width * height * 2
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        # 读取 16 位 half float
        half_val = struct.unpack('<H', data[i*2:i*2+2])[0]
        # 转换为 float 再映射到 0-255
        f = _half_to_float(half_val)
        gray = int(max(0, min(255, f * 255)))
        
        idx = i * 4
        result[idx] = gray      # R
        result[idx + 1] = gray  # G
        result[idx + 2] = gray  # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


@register_decoder('RG16F')
def decode_rg16f(data: bytes, width: int, height: int) -> bytes:
    """解码 RG16F (dual half float) 为 RGBA"""
    expected = width * height * 4
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        # 读取两个 16 位 half float
        r_half = struct.unpack('<H', data[i*4:i*4+2])[0]
        g_half = struct.unpack('<H', data[i*4+2:i*4+4])[0]
        
        r = int(max(0, min(255, _half_to_float(r_half) * 255)))
        g = int(max(0, min(255, _half_to_float(g_half) * 255)))
        
        idx = i * 4
        result[idx] = r        # R
        result[idx + 1] = g    # G
        result[idx + 2] = 0    # B
        result[idx + 3] = 255  # A
    
    return bytes(result)


@register_decoder('RGBA16F')
def decode_rgba16f(data: bytes, width: int, height: int) -> bytes:
    """解码 RGBA16F (four half floats) 为 RGBA"""
    expected = width * height * 8
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 8, width * height)):
        offset = i * 8
        r_half = struct.unpack('<H', data[offset:offset+2])[0]
        g_half = struct.unpack('<H', data[offset+2:offset+4])[0]
        b_half = struct.unpack('<H', data[offset+4:offset+6])[0]
        a_half = struct.unpack('<H', data[offset+6:offset+8])[0]
        
        r = int(max(0, min(255, _half_to_float(r_half) * 255)))
        g = int(max(0, min(255, _half_to_float(g_half) * 255)))
        b = int(max(0, min(255, _half_to_float(b_half) * 255)))
        a = int(max(0, min(255, _half_to_float(a_half) * 255)))
        
        idx = i * 4
        result[idx] = r
        result[idx + 1] = g
        result[idx + 2] = b
        result[idx + 3] = a
    
    return bytes(result)


@register_decoder('R32F')
@register_decoder('D32F')
def decode_r32f(data: bytes, width: int, height: int) -> bytes:
    """解码 R32F / D32F (32-bit float) 为灰度 RGBA"""
    expected = width * height * 4
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        f = struct.unpack('<f', data[i*4:i*4+4])[0]
        # 深度值通常在 0-1 范围，映射到 0-255
        gray = int(max(0, min(255, f * 255)))
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('D32S8')
@register_decoder('D32_S8X24')
def decode_d32s8(data: bytes, width: int, height: int) -> bytes:
    """
    解码 D32_FLOAT_S8X24_UINT 格式为 RGBA
    
    布局: 32-bit float depth + 8-bit stencil + 24-bit padding = 8 bytes/pixel
    输出: R=深度可视化, G=模板值, B=0, A=255
    """
    expected = width * height * 8
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 8, width * height)):
        offset = i * 8
        depth = struct.unpack('<f', data[offset:offset+4])[0]
        stencil = data[offset + 4] if offset + 4 < len(data) else 0
        
        # 深度映射到灰度
        gray = int(max(0, min(255, depth * 255)))
        
        idx = i * 4
        result[idx] = gray      # R = 深度
        result[idx + 1] = stencil  # G = 模板
        result[idx + 2] = 0     # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


@register_decoder('D24S8')
def decode_d24s8(data: bytes, width: int, height: int) -> bytes:
    """
    解码 D24_UNORM_S8_UINT 格式为 RGBA
    
    布局: 24-bit depth + 8-bit stencil = 4 bytes/pixel
    """
    expected = width * height * 4
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        offset = i * 4
        # D24: 低 24 位是深度 (UNORM)
        depth_raw = struct.unpack('<I', data[offset:offset+4])[0] & 0xFFFFFF
        stencil = data[offset + 3] if offset + 3 < len(data) else 0
        
        # 24位深度归一化到 0-255
        gray = int((depth_raw / 0xFFFFFF) * 255)
        
        idx = i * 4
        result[idx] = gray      # R = 深度
        result[idx + 1] = stencil  # G = 模板
        result[idx + 2] = 0     # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


@register_decoder('R11G11B10F')
def decode_r11g11b10f(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R11G11B10_FLOAT 格式为 RGBA
    
    布局 (32 bits): R (11 bits) | G (11 bits) | B (10 bits)
    每个通道是无符号浮点: mantissa + exponent (无符号数)
    """
    expected = width * height * 4
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        val = struct.unpack('<I', data[i*4:i*4+4])[0]
        
        # 解包各通道
        r_raw = val & 0x7FF          # bits 0-10
        g_raw = (val >> 11) & 0x7FF  # bits 11-21
        b_raw = (val >> 22) & 0x3FF  # bits 22-31
        
        # R11/G11: 6-bit mantissa + 5-bit exponent
        r = _decode_float11(r_raw)
        g = _decode_float11(g_raw)
        # B10: 5-bit mantissa + 5-bit exponent
        b = _decode_float10(b_raw)
        
        # HDR 值映射到 0-255 (简单 tonemap)
        idx = i * 4
        result[idx] = int(max(0, min(255, r * 255)))
        result[idx + 1] = int(max(0, min(255, g * 255)))
        result[idx + 2] = int(max(0, min(255, b * 255)))
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('RGBA32F')
def decode_rgba32f(data: bytes, width: int, height: int) -> bytes:
    """解码 RGBA32F (four 32-bit floats) 为 RGBA"""
    expected = width * height * 16
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 16, width * height)):
        offset = i * 16
        r = struct.unpack('<f', data[offset:offset+4])[0]
        g = struct.unpack('<f', data[offset+4:offset+8])[0]
        b = struct.unpack('<f', data[offset+8:offset+12])[0]
        a = struct.unpack('<f', data[offset+12:offset+16])[0]
        
        idx = i * 4
        result[idx] = int(max(0, min(255, r * 255)))
        result[idx + 1] = int(max(0, min(255, g * 255)))
        result[idx + 2] = int(max(0, min(255, b * 255)))
        result[idx + 3] = int(max(0, min(255, a * 255)))
    
    return bytes(result)


@register_decoder('RG32F')
def decode_rg32f(data: bytes, width: int, height: int) -> bytes:
    """解码 RG32F (two 32-bit floats) 为 RGBA"""
    expected = width * height * 8
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 8, width * height)):
        offset = i * 8
        r = struct.unpack('<f', data[offset:offset+4])[0]
        g = struct.unpack('<f', data[offset+4:offset+8])[0]
        
        idx = i * 4
        result[idx] = int(max(0, min(255, r * 255)))
        result[idx + 1] = int(max(0, min(255, g * 255)))
        result[idx + 2] = 0
        result[idx + 3] = 255
    
    return bytes(result)


# ============================================================================
# Vulkan 特有格式解码器 (v1.5.0)
# ============================================================================

@register_decoder('B10G11R11F')
def decode_b10g11r11f(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_B10G11R11_UFLOAT_PACK32 为 RGBA
    
    布局 (32 bits): B (10 bits) | G (11 bits) | R (11 bits)
    注意: 与 R11G11B10F 的通道顺序相反
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        val = struct.unpack('<I', data[i*4:i*4+4])[0]
        
        # 解包各通道 (注意顺序: B-G-R)
        b_raw = val & 0x3FF           # bits 0-9 (10 bits)
        g_raw = (val >> 10) & 0x7FF   # bits 10-20 (11 bits)
        r_raw = (val >> 21) & 0x7FF   # bits 21-31 (11 bits)
        
        # B10: 5-bit mantissa + 5-bit exponent
        b = _decode_float10(b_raw)
        # G11/R11: 6-bit mantissa + 5-bit exponent
        g = _decode_float11(g_raw)
        r = _decode_float11(r_raw)
        
        idx = i * 4
        result[idx] = int(max(0, min(255, r * 255)))
        result[idx + 1] = int(max(0, min(255, g * 255)))
        result[idx + 2] = int(max(0, min(255, b * 255)))
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('A2R10G10B10')
def decode_a2r10g10b10(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_A2R10G10B10_UNORM_PACK32 为 RGBA
    
    布局 (32 bits): A (2 bits) | R (10 bits) | G (10 bits) | B (10 bits)
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        val = struct.unpack('<I', data[i*4:i*4+4])[0]
        
        # 解包各通道
        b = val & 0x3FF               # bits 0-9
        g = (val >> 10) & 0x3FF       # bits 10-19
        r = (val >> 20) & 0x3FF       # bits 20-29
        a = (val >> 30) & 0x3         # bits 30-31
        
        idx = i * 4
        result[idx] = (r * 255) // 1023      # 10-bit -> 8-bit
        result[idx + 1] = (g * 255) // 1023
        result[idx + 2] = (b * 255) // 1023
        result[idx + 3] = (a * 255) // 3     # 2-bit -> 8-bit
    
    return bytes(result)


@register_decoder('A2B10G10R10')
def decode_a2b10g10r10(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_A2B10G10R10_UNORM_PACK32 为 RGBA
    
    布局 (32 bits): A (2 bits) | B (10 bits) | G (10 bits) | R (10 bits)
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        val = struct.unpack('<I', data[i*4:i*4+4])[0]
        
        # 解包各通道 (注意顺序: R-G-B-A)
        r = val & 0x3FF               # bits 0-9
        g = (val >> 10) & 0x3FF       # bits 10-19
        b = (val >> 20) & 0x3FF       # bits 20-29
        a = (val >> 30) & 0x3         # bits 30-31
        
        idx = i * 4
        result[idx] = (r * 255) // 1023
        result[idx + 1] = (g * 255) // 1023
        result[idx + 2] = (b * 255) // 1023
        result[idx + 3] = (a * 255) // 3
    
    return bytes(result)


@register_decoder('A8B8G8R8')
def decode_a8b8g8r8(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_A8B8G8R8_UNORM_PACK32 为 RGBA
    
    布局: A (8) | B (8) | G (8) | R (8) = 32 bits
    注意: 内存中是 R-G-B-A 顺序 (little-endian)
    """
    expected = width * height * 4
    result = bytearray(expected)
    
    for i in range(min(len(data) // 4, width * height)):
        src = i * 4
        dst = i * 4
        if src + 3 < len(data):
            # Little-endian: 内存顺序 R, G, B, A
            result[dst] = data[src]        # R
            result[dst + 1] = data[src + 1]  # G
            result[dst + 2] = data[src + 2]  # B
            result[dst + 3] = data[src + 3]  # A
    
    return bytes(result)


@register_decoder('R16_UNORM')
@register_decoder('R16U')
def decode_r16_unorm(data: bytes, width: int, height: int) -> bytes:
    """解码 R16_UNORM (16-bit UNORM) 为灰度 RGBA"""
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        val = struct.unpack('<H', data[i*2:i*2+2])[0]
        gray = (val * 255) // 65535  # 16-bit -> 8-bit
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R16G16_UNORM')
@register_decoder('RG16U')
def decode_rg16_unorm(data: bytes, width: int, height: int) -> bytes:
    """解码 R16G16_UNORM (双通道 16-bit UNORM) 为 RGBA"""
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        r = struct.unpack('<H', data[i*4:i*4+2])[0]
        g = struct.unpack('<H', data[i*4+2:i*4+4])[0]
        
        idx = i * 4
        result[idx] = (r * 255) // 65535
        result[idx + 1] = (g * 255) // 65535
        result[idx + 2] = 0
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('D16_UNORM')
@register_decoder('D16')
def decode_d16_unorm(data: bytes, width: int, height: int) -> bytes:
    """解码 D16_UNORM (16-bit 深度) 为灰度 RGBA"""
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        val = struct.unpack('<H', data[i*2:i*2+2])[0]
        gray = (val * 255) // 65535
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('S8_UINT')
@register_decoder('S8')
def decode_s8_uint(data: bytes, width: int, height: int) -> bytes:
    """解码 S8_UINT (8-bit 纯模板) 为灰度 RGBA"""
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data), width * height)):
        stencil = data[i]
        
        idx = i * 4
        result[idx] = stencil        # R = 模板值
        result[idx + 1] = stencil    # G
        result[idx + 2] = stencil    # B
        result[idx + 3] = 255
    
    return bytes(result)


# ============================================================================
# Vulkan 第二批格式 (v1.6.0) - SNORM / SFLOAT / 深度模板
# ============================================================================

@register_decoder('R8_SNORM')
def decode_r8_snorm(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R8_SNORM (有符号归一化) 为灰度 RGBA
    
    值域: -128~127 → -1.0~1.0 → 显示为 0~255 (映射 -1→0, 0→128, 1→255)
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data), width * height)):
        # 读取有符号字节
        val = data[i]
        if val > 127:
            val = val - 256  # 转为有符号 (-128 ~ 127)
        
        # 映射 -128~127 → 0~255
        gray = int((val + 128) * 255 / 255)  # 等同于 val + 128
        gray = max(0, min(255, gray))
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R16_SNORM')
def decode_r16_snorm(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R16_SNORM (16-bit 有符号归一化) 为灰度 RGBA
    
    值域: -32768~32767 → -1.0~1.0 → 显示为 0~255
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        # 读取有符号 16-bit
        val = struct.unpack('<h', data[i*2:i*2+2])[0]  # 'h' = signed short
        
        # 映射 -32768~32767 → 0~255
        gray = int((val + 32768) * 255 / 65535)
        gray = max(0, min(255, gray))
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R16_SFLOAT')
@register_decoder('R16SF')
def decode_r16_sfloat(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R16_SFLOAT (半精度有符号浮点) 为灰度 RGBA
    
    使用 IEEE 754 half-float，支持负值
    显示时: 将 [-1,1] 映射到 [0,255]
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        half_val = struct.unpack('<H', data[i*2:i*2+2])[0]
        f = _half_to_float(half_val)
        
        # 映射 [-1,1] → [0,255]，超出范围的值会被钳制
        gray = int((f + 1.0) * 0.5 * 255)
        gray = max(0, min(255, gray))
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R32_SFLOAT')
@register_decoder('R32SF')
def decode_r32_sfloat(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R32_SFLOAT (单精度有符号浮点) 为灰度 RGBA
    
    显示时: 将 [-1,1] 映射到 [0,255]
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        f = struct.unpack('<f', data[i*4:i*4+4])[0]
        
        # 映射 [-1,1] → [0,255]
        gray = int((f + 1.0) * 0.5 * 255)
        gray = max(0, min(255, gray))
        
        idx = i * 4
        result[idx] = gray
        result[idx + 1] = gray
        result[idx + 2] = gray
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R8G8_SNORM')
@register_decoder('RG8S')
def decode_rg8_snorm(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R8G8_SNORM (双通道有符号归一化) 为 RGBA
    
    常用于法线贴图 (存储 X/Y 分量)
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 2, width * height)):
        # 读取两个有符号字节
        r_val = data[i * 2]
        g_val = data[i * 2 + 1]
        
        # 转为有符号
        if r_val > 127:
            r_val = r_val - 256
        if g_val > 127:
            g_val = g_val - 256
        
        # 映射 -128~127 → 0~255
        r = max(0, min(255, r_val + 128))
        g = max(0, min(255, g_val + 128))
        
        idx = i * 4
        result[idx] = r
        result[idx + 1] = g
        result[idx + 2] = 128  # B = 中间值 (法线 Z 通常推导)
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('R16G16_SNORM')
@register_decoder('RG16S')
def decode_rg16_snorm(data: bytes, width: int, height: int) -> bytes:
    """
    解码 R16G16_SNORM (双通道 16-bit 有符号归一化) 为 RGBA
    
    高精度法线贴图常用
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        # 读取两个有符号 16-bit
        r_val = struct.unpack('<h', data[i*4:i*4+2])[0]
        g_val = struct.unpack('<h', data[i*4+2:i*4+4])[0]
        
        # 映射 -32768~32767 → 0~255
        r = int((r_val + 32768) * 255 / 65535)
        g = int((g_val + 32768) * 255 / 65535)
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        
        idx = i * 4
        result[idx] = r
        result[idx + 1] = g
        result[idx + 2] = 128
        result[idx + 3] = 255
    
    return bytes(result)


@register_decoder('D24_UNORM_S8_UINT')
def decode_d24_unorm_s8_uint(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_D24_UNORM_S8_UINT 为 RGBA
    
    布局: 24-bit depth (UNORM) + 8-bit stencil = 4 bytes/pixel
    与 D24S8 相同，提供 Vulkan 命名别名
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 4, width * height)):
        offset = i * 4
        # D24: 低 24 位是深度 (UNORM)
        depth_raw = struct.unpack('<I', data[offset:offset+4])[0] & 0xFFFFFF
        stencil = data[offset + 3] if offset + 3 < len(data) else 0
        
        # 24位深度归一化到 0-255
        gray = int((depth_raw / 0xFFFFFF) * 255)
        
        idx = i * 4
        result[idx] = gray      # R = 深度
        result[idx + 1] = stencil  # G = 模板
        result[idx + 2] = 0     # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


@register_decoder('D32_SFLOAT_S8_UINT')
def decode_d32_sfloat_s8_uint(data: bytes, width: int, height: int) -> bytes:
    """
    解码 VK_FORMAT_D32_SFLOAT_S8_UINT 为 RGBA
    
    布局: 32-bit float depth + 8-bit stencil + 24-bit padding = 8 bytes/pixel
    与 D32S8 相同，提供 Vulkan 命名别名
    """
    result = bytearray(width * height * 4)
    
    for i in range(min(len(data) // 8, width * height)):
        offset = i * 8
        depth = struct.unpack('<f', data[offset:offset+4])[0]
        stencil = data[offset + 4] if offset + 4 < len(data) else 0
        
        # 深度映射到灰度 (假设 0-1 范围)
        gray = int(max(0, min(255, depth * 255)))
        
        idx = i * 4
        result[idx] = gray      # R = 深度
        result[idx + 1] = stencil  # G = 模板
        result[idx + 2] = 0     # B
        result[idx + 3] = 255   # A
    
    return bytes(result)


# ============================================================================
# 浮点数转换辅助函数
# ============================================================================

def _half_to_float(h: int) -> float:
    """IEEE 754 half precision (16-bit) 转 float"""
    sign = (h >> 15) & 1
    exp = (h >> 10) & 0x1F
    mantissa = h & 0x3FF
    
    if exp == 0:
        # 非规格化数或零
        if mantissa == 0:
            return -0.0 if sign else 0.0
        # 非规格化数
        return ((-1) ** sign) * (mantissa / 1024.0) * (2 ** -14)
    elif exp == 31:
        # Inf 或 NaN
        if mantissa == 0:
            return float('-inf') if sign else float('inf')
        return float('nan')
    else:
        # 规格化数
        return ((-1) ** sign) * (1 + mantissa / 1024.0) * (2 ** (exp - 15))


def _decode_float11(val: int) -> float:
    """解码 11-bit 无符号浮点 (6-bit mantissa, 5-bit exponent)"""
    exp = (val >> 6) & 0x1F
    mantissa = val & 0x3F
    
    if exp == 0:
        return (mantissa / 64.0) * (2 ** -14)
    elif exp == 31:
        return float('inf') if mantissa == 0 else float('nan')
    else:
        return (1 + mantissa / 64.0) * (2 ** (exp - 15))


def _decode_float10(val: int) -> float:
    """解码 10-bit 无符号浮点 (5-bit mantissa, 5-bit exponent)"""
    exp = (val >> 5) & 0x1F
    mantissa = val & 0x1F
    
    if exp == 0:
        return (mantissa / 32.0) * (2 ** -14)
    elif exp == 31:
        return float('inf') if mantissa == 0 else float('nan')
    else:
        return (1 + mantissa / 32.0) * (2 ** (exp - 15))


# BC1/BC3/BC7 解码器将在单独的模块中实现，并在此导入注册
# 导入顺序很重要，必须在 register_decoder 定义之后

def _register_all_decoders():
    """延迟导入并注册所有解码器"""
    try:
        from . import bc1_decoder
    except ImportError:
        pass
    
    try:
        from . import bc2_decoder
    except ImportError:
        pass
    
    try:
        from . import bc3_decoder
    except ImportError:
        pass
    
    try:
        from . import bc4_decoder
    except ImportError:
        pass
    
    try:
        from . import bc5_decoder
    except ImportError:
        pass
    
    try:
        from . import bc6h_decoder
    except ImportError:
        pass
    
    try:
        from . import bc7_decoder
    except ImportError:
        pass


# 模块加载时注册解码器
_register_all_decoders()
