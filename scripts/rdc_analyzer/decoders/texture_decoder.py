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
    
    # 提取 BC 格式编号
    for bc in ['BC7', 'BC6H', 'BC5', 'BC4', 'BC3', 'BC2', 'BC1']:
        if bc in fmt:
            return bc
    
    # 检查是否是未压缩格式
    uncompressed = ['R8G8B8A8', 'B8G8R8A8', 'R8_UNORM', 'R16', 'R32']
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
