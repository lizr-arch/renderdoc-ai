"""
Texture Decoders Module

提供多种压缩纹理格式的 CPU 解码功能。

支持格式:
- BC1~BC7: Desktop BCn 全系列 (D3D/Vulkan)
- ASTC: Adaptive Scalable (移动端通用, 14 种块大小)
- ETC1/ETC2/EAC: OpenGL ES 标准 (Android)
- PVRTC: PowerVR (iOS)
- ATC: Adreno (Qualcomm 芯片)

依赖:
- 移动端格式需要 texture2ddecoder 库: pip install texture2ddecoder
- BCn 格式使用纯 Python 实现，无额外依赖
"""

from .texture_decoder import (
    decode_texture,
    save_as_png,
    get_supported_formats,
    check_mobile_support,
    get_format_categories,
    TextureDecodeError,
    register_decoder,
)

# 导入具体解码器（触发注册）
# BCn 系列 (纯 Python，无依赖)
from . import bc1_decoder
from . import bc2_decoder
from . import bc3_decoder
from . import bc4_decoder
from . import bc5_decoder
from . import bc6h_decoder
from . import bc7_decoder

# 移动端格式 (需要 texture2ddecoder)
try:
    from . import astc_decoder
    from . import etc_decoder
except ImportError:
    pass  # texture2ddecoder 未安装，移动端格式不可用

__all__ = [
    'decode_texture',
    'save_as_png',
    'get_supported_formats',
    'check_mobile_support',
    'get_format_categories',
    'TextureDecodeError',
]

__version__ = '1.3.0'
