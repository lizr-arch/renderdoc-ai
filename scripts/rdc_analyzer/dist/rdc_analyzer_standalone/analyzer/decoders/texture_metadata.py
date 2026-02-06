"""
Texture Metadata - 纹理解码元数据

记录纹理解码过程中的所有关键信息，使大模型能够完整理解和恢复纹理。

设计目标:
1. 完整记录解码前后的格式转换
2. 记录颜色空间和坐标系统信息
3. 记录各通道的语义含义
4. 提供恢复/重编码所需的信息
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Literal
from enum import Enum
import json


class GammaSpace(Enum):
    """颜色空间 Gamma 类型"""
    SRGB = "sRGB"
    LINEAR = "Linear"


class AlphaMode(Enum):
    """Alpha 通道模式"""
    STRAIGHT = "straight"          # 直接 Alpha
    PREMULTIPLIED = "premultiplied"  # 预乘 Alpha
    NONE = "none"                  # 无 Alpha


class CoordinateOrigin(Enum):
    """坐标原点位置"""
    TOP_LEFT = "top-left"          # 图像标准 (PNG, JPEG)
    BOTTOM_LEFT = "bottom-left"    # OpenGL 标准


@dataclass
class Dimensions:
    """纹理尺寸信息"""
    width: int
    height: int
    mip_level: int = 0
    array_slice: int = 0
    depth: int = 1  # 3D 纹理深度


@dataclass
class FormatInfo:
    """格式信息"""
    source: str                    # 原始格式 (如 VK_FORMAT_BC7_SRGB_BLOCK)
    source_normalized: str         # 标准化格式 (如 BC7)
    decoded: str = "RGBA8"         # 解码后格式 (固定为 RGBA8)
    bits_per_channel: int = 8      # 每通道位深
    block_size_bytes: int = 0      # 压缩块字节数 (0 表示未压缩)
    is_compressed: bool = True     # 是否为压缩格式


@dataclass
class ColorSpace:
    """颜色空间信息"""
    gamma: GammaSpace = GammaSpace.SRGB
    transfer_applied: bool = False  # 是否已应用 gamma 转换到 linear
    
    # sRGB 格式说明:
    # - transfer_applied=False: 输出保持 sRGB，PNG 查看器会正确显示
    # - transfer_applied=True: 输出已转为 Linear，适合进一步处理


@dataclass
class CoordinateSystem:
    """坐标系统信息"""
    origin: CoordinateOrigin = CoordinateOrigin.TOP_LEFT
    y_flipped_from_source: bool = False
    
    # GPU 纹理通常是 bottom-left 原点
    # PNG 图像是 top-left 原点
    # 如果 y_flipped_from_source=True，表示已从源坐标系翻转


@dataclass
class ChannelSemantics:
    """通道语义信息"""
    R: str = "Red"
    G: str = "Green"
    B: str = "Blue"
    A: str = "Alpha"
    alpha_mode: AlphaMode = AlphaMode.STRAIGHT
    
    # 特殊格式的通道语义示例:
    # BC4: R="Grayscale", G="Grayscale", B="Grayscale", A="Opaque(255)"
    # BC5: R="Normal.X", G="Normal.Y", B="Unused(0)", A="Opaque(255)"


@dataclass
class RecoveryInfo:
    """恢复/重编码信息"""
    lossless_reencode_possible: bool = False
    original_data_hash: str = ""   # 原始压缩数据的 hash (可选)
    notes: str = ""                # 恢复说明
    
    # 量化损失说明:
    # BC1/BC3: 有损压缩，无法无损恢复
    # BC4/BC5: 8-bit 量化，理论上可无损重编码
    # BC7: 有损压缩，但质量很高


@dataclass
class TextureMetadata:
    """
    纹理元数据 - 完整记录解码信息
    
    使用示例:
    ```python
    metadata = TextureMetadata(
        dimensions=Dimensions(1024, 1024),
        format=FormatInfo("VK_FORMAT_BC7_SRGB_BLOCK", "BC7", block_size_bytes=16),
        color_space=ColorSpace(GammaSpace.SRGB),
        coordinate_system=CoordinateSystem(CoordinateOrigin.TOP_LEFT),
        channel_semantics=ChannelSemantics(),
        recovery_info=RecoveryInfo(notes="Lossy BC7 compression")
    )
    
    # 保存为 JSON
    metadata.save_json("texture_meta.json")
    ```
    """
    dimensions: Dimensions
    format: FormatInfo
    color_space: ColorSpace = field(default_factory=ColorSpace)
    coordinate_system: CoordinateSystem = field(default_factory=CoordinateSystem)
    channel_semantics: ChannelSemantics = field(default_factory=ChannelSemantics)
    recovery_info: RecoveryInfo = field(default_factory=RecoveryInfo)
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (用于 JSON 序列化)"""
        def convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, '__dataclass_fields__'):
                return {k: convert(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj
        
        return {
            "version": self.version,
            "dimensions": convert(self.dimensions),
            "format": convert(self.format),
            "color_space": convert(self.color_space),
            "coordinate_system": convert(self.coordinate_system),
            "channel_semantics": convert(self.channel_semantics),
            "recovery_info": convert(self.recovery_info)
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def save_json(self, path: str) -> None:
        """保存为 JSON 文件"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextureMetadata':
        """从字典创建 (用于 JSON 反序列化)"""
        return cls(
            dimensions=Dimensions(**data.get('dimensions', {})),
            format=FormatInfo(**data.get('format', {})),
            color_space=ColorSpace(
                gamma=GammaSpace(data.get('color_space', {}).get('gamma', 'sRGB')),
                transfer_applied=data.get('color_space', {}).get('transfer_applied', False)
            ),
            coordinate_system=CoordinateSystem(
                origin=CoordinateOrigin(data.get('coordinate_system', {}).get('origin', 'top-left')),
                y_flipped_from_source=data.get('coordinate_system', {}).get('y_flipped_from_source', False)
            ),
            channel_semantics=ChannelSemantics(
                R=data.get('channel_semantics', {}).get('R', 'Red'),
                G=data.get('channel_semantics', {}).get('G', 'Green'),
                B=data.get('channel_semantics', {}).get('B', 'Blue'),
                A=data.get('channel_semantics', {}).get('A', 'Alpha'),
                alpha_mode=AlphaMode(data.get('channel_semantics', {}).get('alpha_mode', 'straight'))
            ),
            recovery_info=RecoveryInfo(**data.get('recovery_info', {})),
            version=data.get('version', '1.0')
        )
    
    @classmethod
    def load_json(cls, path: str) -> 'TextureMetadata':
        """从 JSON 文件加载"""
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# ============================================================================
# 预设元数据工厂函数 - 为常见格式创建标准元数据
# ============================================================================

def create_bc1_metadata(width: int, height: int, source_format: str) -> TextureMetadata:
    """创建 BC1 (DXT1) 纹理元数据"""
    is_srgb = 'SRGB' in source_format.upper()
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized="BC1",
            block_size_bytes=8,
            is_compressed=True
        ),
        color_space=ColorSpace(
            gamma=GammaSpace.SRGB if is_srgb else GammaSpace.LINEAR,
            transfer_applied=False
        ),
        channel_semantics=ChannelSemantics(
            R="Red", G="Green", B="Blue",
            A="Alpha (1-bit: 0 or 255)",
            alpha_mode=AlphaMode.STRAIGHT
        ),
        recovery_info=RecoveryInfo(
            lossless_reencode_possible=False,
            notes="BC1 is lossy. RGB565 color endpoints with 2-bit indices."
        )
    )


def create_bc3_metadata(width: int, height: int, source_format: str) -> TextureMetadata:
    """创建 BC3 (DXT5) 纹理元数据"""
    is_srgb = 'SRGB' in source_format.upper()
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized="BC3",
            block_size_bytes=16,
            is_compressed=True
        ),
        color_space=ColorSpace(
            gamma=GammaSpace.SRGB if is_srgb else GammaSpace.LINEAR,
            transfer_applied=False
        ),
        channel_semantics=ChannelSemantics(
            R="Red", G="Green", B="Blue",
            A="Alpha (8-bit interpolated)",
            alpha_mode=AlphaMode.STRAIGHT
        ),
        recovery_info=RecoveryInfo(
            lossless_reencode_possible=False,
            notes="BC3 is lossy. BC1 color + interpolated alpha block."
        )
    )


def create_bc4_metadata(width: int, height: int, source_format: str) -> TextureMetadata:
    """创建 BC4 纹理元数据 (单通道)"""
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized="BC4",
            block_size_bytes=8,
            is_compressed=True
        ),
        color_space=ColorSpace(
            gamma=GammaSpace.LINEAR,  # BC4 通常用于数据纹理
            transfer_applied=False
        ),
        channel_semantics=ChannelSemantics(
            R="Grayscale/Height (0-255)",
            G="Grayscale/Height (duplicate of R)",
            B="Grayscale/Height (duplicate of R)",
            A="Opaque (always 255)",
            alpha_mode=AlphaMode.NONE
        ),
        recovery_info=RecoveryInfo(
            lossless_reencode_possible=True,
            notes="BC4 uses 8-bit quantization. R channel contains the original data."
        )
    )


def create_bc5_metadata(width: int, height: int, source_format: str) -> TextureMetadata:
    """创建 BC5 纹理元数据 (双通道/法线贴图)"""
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized="BC5",
            block_size_bytes=16,
            is_compressed=True
        ),
        color_space=ColorSpace(
            gamma=GammaSpace.LINEAR,  # 法线贴图是 linear
            transfer_applied=False
        ),
        channel_semantics=ChannelSemantics(
            R="Normal.X (0-255 maps to -1.0 to 1.0: X = R/127.5 - 1)",
            G="Normal.Y (0-255 maps to -1.0 to 1.0: Y = G/127.5 - 1)",
            B="Unused (always 0)",
            A="Opaque (always 255)",
            alpha_mode=AlphaMode.NONE
        ),
        recovery_info=RecoveryInfo(
            lossless_reencode_possible=True,
            notes="Normal.Z can be reconstructed: Z = sqrt(1 - X² - Y²). "
                  "R and G channels contain the original tangent-space normal XY."
        )
    )


def create_bc7_metadata(width: int, height: int, source_format: str) -> TextureMetadata:
    """创建 BC7 (BPTC) 纹理元数据"""
    is_srgb = 'SRGB' in source_format.upper()
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized="BC7",
            block_size_bytes=16,
            is_compressed=True
        ),
        color_space=ColorSpace(
            gamma=GammaSpace.SRGB if is_srgb else GammaSpace.LINEAR,
            transfer_applied=False
        ),
        channel_semantics=ChannelSemantics(
            R="Red", G="Green", B="Blue", A="Alpha",
            alpha_mode=AlphaMode.STRAIGHT
        ),
        recovery_info=RecoveryInfo(
            lossless_reencode_possible=False,
            notes="BC7 is lossy but high quality. Uses 8 modes with variable precision."
        )
    )


# 格式名到工厂函数的映射
METADATA_FACTORIES = {
    'BC1': create_bc1_metadata,
    'BC3': create_bc3_metadata,
    'BC4': create_bc4_metadata,
    'BC5': create_bc5_metadata,
    'BC7': create_bc7_metadata,
}


def create_metadata_for_format(
    width: int,
    height: int,
    source_format: str,
    normalized_format: str
) -> TextureMetadata:
    """
    根据格式创建对应的元数据
    
    Args:
        width: 纹理宽度
        height: 纹理高度
        source_format: 原始格式字符串 (如 VK_FORMAT_BC7_SRGB_BLOCK)
        normalized_format: 标准化格式 (如 BC7)
    
    Returns:
        TextureMetadata 实例
    """
    factory = METADATA_FACTORIES.get(normalized_format.upper())
    if factory:
        return factory(width, height, source_format)
    
    # 默认元数据
    return TextureMetadata(
        dimensions=Dimensions(width, height),
        format=FormatInfo(
            source=source_format,
            source_normalized=normalized_format,
            is_compressed=False
        )
    )


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing TextureMetadata...")
    
    # 创建 BC7 元数据
    meta = create_bc7_metadata(1024, 1024, "VK_FORMAT_BC7_SRGB_BLOCK")
    print("\nBC7 Metadata:")
    print(meta.to_json())
    
    # 创建 BC5 法线贴图元数据
    normal_meta = create_bc5_metadata(512, 512, "VK_FORMAT_BC5_UNORM_BLOCK")
    print("\nBC5 Normal Map Metadata:")
    print(normal_meta.to_json())
    
    # 测试序列化/反序列化
    json_str = meta.to_json()
    restored = TextureMetadata.from_dict(json.loads(json_str))
    assert restored.dimensions.width == 1024
    assert restored.format.source_normalized == "BC7"
    print("\n✓ Serialization/deserialization test passed")
