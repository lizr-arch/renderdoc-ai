"""
BC6H (BPTC_FLOAT) HDR Texture Decoder

BC6H 压缩格式解码器，用于解压 HDR 纹理。

格式规格:
- 4x4 像素块 = 16 字节
- 14 种模式 (由块首 2-5 位确定)
- 每种模式有不同的:
  - 端点精度 (10-16 bits per component)
  - 分区表 (0-31，5 bits)
  - 是否有符号 (BC6H_SF16 vs BC6H_UF16)
- 输出为 RGB Half-Float，本解码器会进行 HDR→LDR 色调映射

参考:
- https://learn.microsoft.com/en-us/windows/win32/direct3d11/bc6h-format
- https://registry.khronos.org/DataFormat/specs/1.3/dataformat.1.3.html#BPTC
"""

import struct
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .texture_decoder import register_decoder


# ============================================================================
# BC6H 模式配置表
# ============================================================================
# BC6H 有 14 种模式，每种模式的位布局完全不同
# 格式: (mode_bits, num_subsets, partition_bits, 
#        r_bits, g_bits, b_bits, delta_bits,
#        transformed)  # 是否使用 delta 编码

@dataclass
class BC6HModeConfig:
    """BC6H 模式配置"""
    mode_id: int
    mode_bits: int          # 模式位数
    num_subsets: int        # 子集数量 (1 或 2)
    partition_bits: int     # 分区位数 (0 或 5)
    endpoint_bits: Tuple[int, int, int]  # R, G, B 端点位数
    delta_bits: Tuple[int, int, int]     # R, G, B delta 位数 (0 表示无 delta)
    transformed: bool       # 是否使用 delta 编码


# 模式配置表
# 模式由前导位确定: 2-bit 模式 (00, 01, 10) 或 5-bit 模式 (11xxx)
BC6H_MODE_CONFIGS = {
    # 2 子集模式
    0:  BC6HModeConfig(0,  2, 2, 5, (10,10,10), (5,5,5), True),
    1:  BC6HModeConfig(1,  2, 2, 5, (7,7,7),    (6,6,6), True),
    2:  BC6HModeConfig(2,  5, 2, 5, (11,11,11), (5,4,4), True),
    6:  BC6HModeConfig(6,  5, 2, 5, (11,11,11), (4,5,4), True),
    10: BC6HModeConfig(10, 5, 2, 5, (11,11,11), (4,4,5), True),
    14: BC6HModeConfig(14, 5, 2, 5, (9,9,9),    (5,5,5), True),
    18: BC6HModeConfig(18, 5, 2, 5, (8,8,8),    (6,5,5), True),
    22: BC6HModeConfig(22, 5, 2, 5, (8,8,8),    (5,6,5), True),
    26: BC6HModeConfig(26, 5, 2, 5, (8,8,8),    (5,5,6), True),
    30: BC6HModeConfig(30, 5, 2, 5, (6,6,6),    (6,6,6), False),
    # 1 子集模式
    3:  BC6HModeConfig(3,  5, 1, 0, (10,10,10), (10,10,10), False),
    7:  BC6HModeConfig(7,  5, 1, 0, (11,11,11), (9,9,9), True),
    11: BC6HModeConfig(11, 5, 1, 0, (12,12,12), (8,8,8), True),
    15: BC6HModeConfig(15, 5, 1, 0, (16,16,16), (4,4,4), True),
}

# 分区表 (2 子集, 32 种)
BC6H_PARTITION_TABLE = [
    [0,0,1,1,0,0,1,1,0,0,1,1,0,0,1,1],
    [0,0,0,1,0,0,0,1,0,0,0,1,0,0,0,1],
    [0,1,1,1,0,1,1,1,0,1,1,1,0,1,1,1],
    [0,0,0,1,0,0,1,1,0,0,1,1,0,1,1,1],
    [0,0,0,0,0,0,0,1,0,0,0,1,0,0,1,1],
    [0,0,1,1,0,1,1,1,0,1,1,1,1,1,1,1],
    [0,0,0,1,0,0,1,1,0,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,1,0,0,1,1,0,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,1],
    [0,0,1,1,0,1,1,1,1,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,1,0,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,0,1,0,1,1,1],
    [0,0,0,1,0,1,1,1,1,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1],
    [0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1],
    [0,0,0,0,1,0,0,0,1,1,1,0,1,1,1,1],
    [0,1,1,1,0,0,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,1,0,0,0,1,1,1,0],
    [0,1,1,1,0,0,1,1,0,0,0,1,0,0,0,0],
    [0,0,1,1,0,0,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,0,0,0,1,1,0,0,1,1,1,0],
    [0,0,0,0,0,0,0,0,1,0,0,0,1,1,0,0],
    [0,1,1,1,0,0,1,1,0,0,1,1,0,0,0,1],
    [0,0,1,1,0,0,0,1,0,0,0,1,0,0,0,0],
    [0,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
    [0,1,0,0,1,1,1,0,0,1,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],
    [0,1,0,0,1,1,0,0,1,0,0,0,1,0,0,0],
    [0,1,0,0,0,1,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0],
    [0,1,0,0,1,1,0,0,1,1,0,0,1,0,0,0],
]

# Anchor 索引 (2 子集的第二个 anchor)
BC6H_ANCHOR_INDEX_2 = [
    15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,
    15, 2, 8, 2, 2, 8, 8,15, 2, 8, 2, 2, 8, 8, 2, 2,
]

# 索引权重表 (3-bit 和 4-bit)
BC6H_WEIGHTS_3 = [0, 9, 18, 27, 37, 46, 55, 64]
BC6H_WEIGHTS_4 = [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]


class BitReader:
    """位流读取器 (LSB优先)"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.bit_pos = 0
    
    def read_bits(self, count: int) -> int:
        """读取指定数量的位"""
        if count == 0:
            return 0
        
        result = 0
        for i in range(count):
            byte_idx = self.bit_pos // 8
            bit_idx = self.bit_pos % 8
            
            if byte_idx < len(self.data):
                bit = (self.data[byte_idx] >> bit_idx) & 1
                result |= (bit << i)
            
            self.bit_pos += 1
        
        return result
    
    def read_bit(self) -> int:
        return self.read_bits(1)
    
    def get_position(self) -> int:
        return self.bit_pos
    
    def set_position(self, pos: int):
        self.bit_pos = pos


def sign_extend(value: int, bits: int) -> int:
    """符号扩展"""
    if bits <= 0:
        return 0
    sign_bit = 1 << (bits - 1)
    if value & sign_bit:
        value |= ~((1 << bits) - 1)
    return value


def unquantize_endpoint(value: int, bits: int, signed: bool) -> int:
    """
    反量化端点值到半精度浮点范围
    返回 16-bit half-float 的整数表示
    """
    if bits >= 15:
        # 16-bit: 直接返回
        return value
    
    if signed:
        # 有符号模式
        if bits < 16:
            sign = 0
            if value < 0:
                sign = 0x8000
                value = -value
            
            if value == 0:
                return 0
            elif value >= ((1 << (bits - 1)) - 1):
                return 0x7BFF | sign  # 最大正值
            else:
                # 缩放到 [0, 0x7BFF] 范围
                value = ((value << 15) + 0x4000) >> (bits - 1)
                return value | sign
    else:
        # 无符号模式
        if value == 0:
            return 0
        elif value >= ((1 << bits) - 1):
            return 0xFFFF  # 最大值
        else:
            # 缩放到 [0, 0xFFFF] 范围
            return ((value << 16) + 0x8000) >> bits
    
    return value


def half_to_float(h: int) -> float:
    """将半精度浮点转换为单精度浮点"""
    sign = (h >> 15) & 1
    exponent = (h >> 10) & 0x1F
    mantissa = h & 0x3FF
    
    if exponent == 0:
        if mantissa == 0:
            return -0.0 if sign else 0.0
        # 次正规数
        while (mantissa & 0x400) == 0:
            mantissa <<= 1
            exponent -= 1
        exponent += 1
        mantissa &= 0x3FF
    elif exponent == 31:
        if mantissa == 0:
            return float('-inf') if sign else float('inf')
        return float('nan')
    
    exponent = exponent - 15 + 127
    result = (sign << 31) | (exponent << 23) | (mantissa << 13)
    return struct.unpack('f', struct.pack('I', result))[0]


def interpolate_half(e0: int, e1: int, weight: int) -> int:
    """
    在半精度浮点空间中插值
    """
    # 将 half 转换为 float 进行插值
    f0 = half_to_float(e0)
    f1 = half_to_float(e1)
    
    # 线性插值
    w = weight / 64.0
    result = f0 * (1 - w) + f1 * w
    
    # 转换回 half (简化: 使用 struct)
    return float_to_half(result)


def float_to_half(f: float) -> int:
    """将单精度浮点转换为半精度浮点"""
    # 处理特殊情况
    if f != f:  # NaN
        return 0x7E00
    
    # 打包为 int32
    bits = struct.unpack('I', struct.pack('f', f))[0]
    sign = (bits >> 31) & 1
    exponent = (bits >> 23) & 0xFF
    mantissa = bits & 0x7FFFFF
    
    if exponent == 0:
        # 零或次正规数
        return sign << 15
    elif exponent == 255:
        # Inf 或 NaN
        if mantissa == 0:
            return (sign << 15) | 0x7C00
        return (sign << 15) | 0x7E00
    
    # 调整指数
    exponent = exponent - 127 + 15
    
    if exponent >= 31:
        # 溢出，返回 Inf
        return (sign << 15) | 0x7C00
    elif exponent <= 0:
        # 下溢，返回 0 或次正规数
        if exponent < -10:
            return sign << 15
        # 次正规数
        mantissa = (mantissa | 0x800000) >> (1 - exponent)
        return (sign << 15) | (mantissa >> 13)
    
    return (sign << 15) | (exponent << 10) | (mantissa >> 13)


def tonemap_reinhard(r: float, g: float, b: float, exposure: float = 1.0) -> Tuple[int, int, int]:
    """
    Reinhard 色调映射: HDR -> LDR
    返回 [0, 255] 范围的 RGB
    """
    # 应用曝光
    r *= exposure
    g *= exposure
    b *= exposure
    
    # Reinhard 映射: x / (1 + x)
    r = r / (1.0 + r)
    g = g / (1.0 + g)
    b = b / (1.0 + b)
    
    # 可选: Gamma 校正 (线性 -> sRGB)
    # r = pow(r, 1/2.2)
    # g = pow(g, 1/2.2)
    # b = pow(b, 1/2.2)
    
    # 转换到 [0, 255]
    return (
        max(0, min(255, int(r * 255 + 0.5))),
        max(0, min(255, int(g * 255 + 0.5))),
        max(0, min(255, int(b * 255 + 0.5)))
    )


def decode_bc6h_mode(reader: BitReader) -> Optional[BC6HModeConfig]:
    """解析 BC6H 模式"""
    # 读取前 2 位
    mode_bits = reader.read_bits(2)
    
    if mode_bits < 2:
        # 2-bit 模式 (0 或 1)
        return BC6H_MODE_CONFIGS.get(mode_bits)
    else:
        # 5-bit 模式 (11xxx)
        # 已读取的 2 位是 "11"，再读取 3 位
        extra = reader.read_bits(3)
        mode = (extra << 2) | mode_bits  # 组合为 5-bit 值
        return BC6H_MODE_CONFIGS.get(mode)


def decode_bc6h_block(block: bytes, signed: bool = False) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC6H 块 (16 bytes -> 16 RGBA pixels)
    
    Args:
        block: 16 字节数据
        signed: True=BC6H_SF16(有符号), False=BC6H_UF16(无符号)
    
    Returns:
        16 个 (R, G, B, A) 元组，A 始终为 255
    """
    if len(block) < 16:
        return [(0, 0, 0, 255)] * 16
    
    reader = BitReader(block)
    
    # 解析模式
    mode_config = decode_bc6h_mode(reader)
    
    if mode_config is None:
        # 未知模式，返回品红色
        return [(255, 0, 255, 255)] * 16
    
    # 简化实现: 对于复杂的 BC6H 格式，使用简化解码
    # 完整实现需要按模式逐位解析端点和索引
    
    # 读取分区索引 (如果有)
    partition = 0
    if mode_config.num_subsets == 2:
        partition = reader.read_bits(5)
    
    # 计算端点数量
    num_endpoints = mode_config.num_subsets * 2
    
    # 简化: 读取端点数据 (每个端点 RGB 各若干位)
    # 实际的 BC6H 格式有非常复杂的位打包，这里使用简化处理
    endpoints = []
    eb = mode_config.endpoint_bits
    db = mode_config.delta_bits
    
    for i in range(num_endpoints):
        if i == 0 or not mode_config.transformed:
            # 绝对值
            r = reader.read_bits(eb[0])
            g = reader.read_bits(eb[1])
            b = reader.read_bits(eb[2])
        else:
            # Delta 值 (相对于端点 0)
            r = sign_extend(reader.read_bits(db[0]), db[0])
            g = sign_extend(reader.read_bits(db[1]), db[1])
            b = sign_extend(reader.read_bits(db[2]), db[2])
            # 应用 delta
            r = (endpoints[0][0] + r) & ((1 << eb[0]) - 1)
            g = (endpoints[0][1] + g) & ((1 << eb[1]) - 1)
            b = (endpoints[0][2] + b) & ((1 << eb[2]) - 1)
        
        endpoints.append((r, g, b))
    
    # 反量化端点到半精度
    unquantized = []
    for ep in endpoints:
        r = unquantize_endpoint(ep[0], eb[0], signed)
        g = unquantize_endpoint(ep[1], eb[1], signed)
        b = unquantize_endpoint(ep[2], eb[2], signed)
        unquantized.append((r, g, b))
    
    # 获取分区表
    if mode_config.num_subsets == 2:
        partition_table = BC6H_PARTITION_TABLE[partition % 32]
    else:
        partition_table = [0] * 16
    
    # 读取索引 (3-bit 或 4-bit)
    index_bits = 3 if mode_config.num_subsets == 2 else 4
    weights = BC6H_WEIGHTS_3 if index_bits == 3 else BC6H_WEIGHTS_4
    
    indices = []
    for i in range(16):
        # Anchor 像素少 1 位
        is_anchor = (i == 0)
        if mode_config.num_subsets == 2:
            subset = partition_table[i]
            if subset == 1 and i == BC6H_ANCHOR_INDEX_2[partition % 32]:
                is_anchor = True
        
        bits = index_bits - (1 if is_anchor else 0)
        indices.append(reader.read_bits(bits))
    
    # 插值并色调映射
    pixels = []
    for i in range(16):
        subset = partition_table[i]
        e0 = unquantized[subset * 2]
        e1 = unquantized[subset * 2 + 1]
        
        w = weights[indices[i]] if indices[i] < len(weights) else 0
        
        # 在半精度空间插值
        r_half = interpolate_half(e0[0], e1[0], w)
        g_half = interpolate_half(e0[1], e1[1], w)
        b_half = interpolate_half(e0[2], e1[2], w)
        
        # 转换为浮点
        r_float = max(0.0, half_to_float(r_half))
        g_float = max(0.0, half_to_float(g_half))
        b_float = max(0.0, half_to_float(b_half))
        
        # 色调映射到 LDR
        r_ldr, g_ldr, b_ldr = tonemap_reinhard(r_float, g_float, b_float)
        
        pixels.append((r_ldr, g_ldr, b_ldr, 255))
    
    return pixels


def decode_bc6h_texture(data: bytes, width: int, height: int, signed: bool = False) -> bytes:
    """
    解码整个 BC6H 纹理为 RGBA
    
    Args:
        data: 压缩数据
        width: 纹理宽度
        height: 纹理高度
        signed: True=BC6H_SF16, False=BC6H_UF16
    
    Returns:
        RGBA8 字节数据
    """
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    
    result = bytearray(width * height * 4)
    
    block_idx = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block_offset = block_idx * 16
            if block_offset + 16 <= len(data):
                block_data = data[block_offset:block_offset + 16]
            else:
                block_data = b'\x00' * 16
            
            pixels = decode_bc6h_block(block_data, signed)
            
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
@register_decoder('BC6H_UF16')
def decode_bc6h_uf16(data: bytes, width: int, height: int) -> bytes:
    """BC6H 无符号浮点解码器"""
    return decode_bc6h_texture(data, width, height, signed=False)


@register_decoder('BC6H_SF16')
def decode_bc6h_sf16(data: bytes, width: int, height: int) -> bytes:
    """BC6H 有符号浮点解码器"""
    return decode_bc6h_texture(data, width, height, signed=True)


# 别名
@register_decoder('BC6H')
def decode_bc6h(data: bytes, width: int, height: int) -> bytes:
    """BC6H 解码器 (默认无符号)"""
    return decode_bc6h_texture(data, width, height, signed=False)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC6H decoder...")
    
    # 测试 BitReader
    reader = BitReader(bytes([0b10110100, 0b11001010]))
    assert reader.read_bits(4) == 0b0100
    assert reader.read_bits(4) == 0b1011
    print("✓ BitReader test passed")
    
    # 测试半精度转换
    assert abs(half_to_float(0x3C00) - 1.0) < 0.001  # 1.0
    assert abs(half_to_float(0x4000) - 2.0) < 0.001  # 2.0
    print("✓ half_to_float test passed")
    
    # 测试色调映射
    r, g, b = tonemap_reinhard(1.0, 1.0, 1.0)
    assert 120 < r < 140  # 约 127 (0.5 * 255)
    print(f"✓ tonemap test passed: RGB({r},{g},{b})")
    
    # 简单测试: 不会崩溃
    test_block = bytes([0] * 16)
    pixels = decode_bc6h_block(test_block, signed=False)
    assert len(pixels) == 16
    print("✓ BC6H block decode test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = bytes([0] * 16) * num_blocks
    
    rgba = decode_bc6h_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    print(f"✓ BC6H texture decode test passed ({width}x{height})")
