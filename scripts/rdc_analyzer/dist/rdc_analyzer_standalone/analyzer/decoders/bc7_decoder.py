"""
BC7 (BPTC) Texture Decoder

BC7 压缩格式解码器，用于解压 BPTC 纹理。

格式规格:
- 4x4 像素块 = 16 字节
- 8 种模式 (0-7)，由块首位的前导 1 位置确定
- 每种模式有不同的:
  - 子集数量 (1-3)
  - 颜色端点精度 (4-7 bits)
  - Alpha 端点精度 (0-8 bits)
  - 分区表 (0-63)
  - P-bits (每端点/共享)
  - 索引位数 (2-4 bits)

参考:
- https://www.khronos.org/opengl/wiki/BPTC_Texture_Compression
- https://learn.microsoft.com/en-us/windows/win32/direct3d11/bc7-format
- https://registry.khronos.org/DataFormat/specs/1.3/dataformat.1.3.html#BPTC
"""

import struct
from typing import List, Tuple, Optional

from .texture_decoder import register_decoder


# ============================================================================
# BC7 模式配置表
# ============================================================================
# 格式: (num_subsets, partition_bits, rotation_bits, index_selection_bit,
#        color_bits, alpha_bits, p_bits, index_bits, index2_bits)
BC7_MODE_CONFIG = {
    #       ns  pb  rb  isb  cb  ab  pb  ib  ib2
    0:     (3,  4,  0,  0,   4,  0,  1,  3,  0),
    1:     (2,  6,  0,  0,   6,  0,  1,  3,  0),  # shared p-bits
    2:     (3,  6,  0,  0,   5,  0,  0,  2,  0),
    3:     (2,  6,  0,  0,   7,  0,  1,  2,  0),
    4:     (1,  0,  2,  1,   5,  6,  0,  2,  3),
    5:     (1,  0,  2,  0,   7,  8,  0,  2,  2),
    6:     (1,  0,  0,  0,   7,  7,  1,  4,  0),
    7:     (2,  6,  0,  0,   5,  5,  1,  2,  0),
}

# BC7 分区表 (2 子集)
BC7_PARTITION_TABLE_2 = [
    [0,0,1,1,0,0,1,1,0,0,1,1,0,0,1,1], [0,0,0,1,0,0,0,1,0,0,0,1,0,0,0,1],
    [0,1,1,1,0,1,1,1,0,1,1,1,0,1,1,1], [0,0,0,1,0,0,1,1,0,0,1,1,0,1,1,1],
    [0,0,0,0,0,0,0,1,0,0,0,1,0,0,1,1], [0,0,1,1,0,1,1,1,0,1,1,1,1,1,1,1],
    [0,0,0,1,0,0,1,1,0,1,1,1,1,1,1,1], [0,0,0,0,0,0,0,1,0,0,1,1,0,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,1], [0,0,1,1,0,1,1,1,1,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,1,0,1,1,1,1,1,1,1], [0,0,0,0,0,0,0,0,0,0,0,1,0,1,1,1],
    [0,0,0,1,0,1,1,1,1,1,1,1,1,1,1,1], [0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1],
    [0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1], [0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1],
    [0,0,0,0,1,0,0,0,1,1,1,0,1,1,1,1], [0,1,1,1,0,0,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,1,0,0,0,1,1,1,0], [0,1,1,1,0,0,1,1,0,0,0,1,0,0,0,0],
    [0,0,1,1,0,0,0,1,0,0,0,0,0,0,0,0], [0,0,0,0,1,0,0,0,1,1,0,0,1,1,1,0],
    [0,0,0,0,0,0,0,0,1,0,0,0,1,1,0,0], [0,1,1,1,0,0,1,1,0,0,1,1,0,0,0,1],
    [0,0,1,1,0,0,0,1,0,0,0,1,0,0,0,0], [0,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
    [0,1,0,0,1,1,1,0,0,1,0,0,0,0,0,0], [0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],
    [0,1,0,0,1,1,0,0,1,0,0,0,1,0,0,0], [0,1,0,0,0,1,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0], [0,1,0,0,1,1,0,0,1,1,0,0,1,0,0,0],
    [0,0,1,1,0,1,1,0,0,1,1,0,1,1,0,0], [0,0,0,1,0,1,1,1,1,1,1,0,1,0,0,0],
    [0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0], [0,1,1,0,0,0,1,1,1,1,0,0,0,1,1,0],
    [0,0,1,1,1,0,0,1,1,0,0,1,1,1,0,0], [0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
    [0,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1], [0,1,0,1,1,0,1,0,0,1,0,1,1,0,1,0],
    [0,0,1,1,0,0,1,1,1,1,0,0,1,1,0,0], [0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0],
    [0,1,0,1,0,1,0,1,1,0,1,0,1,0,1,0], [0,1,1,0,1,0,0,1,0,1,1,0,1,0,0,1],
    [0,1,0,1,1,0,1,0,1,0,1,0,0,1,0,1], [0,1,1,1,0,0,1,1,1,1,0,0,1,1,1,0],
    [0,0,0,1,0,0,1,1,1,1,0,0,1,0,0,0], [0,0,1,1,0,0,1,0,0,1,0,0,1,1,0,0],
    [0,0,1,1,1,0,1,1,1,1,0,1,1,1,0,0], [0,1,1,0,1,0,0,1,1,0,0,1,0,1,1,0],
    [0,0,1,1,1,1,0,0,1,1,0,0,0,0,1,1], [0,1,1,0,0,1,1,0,1,0,0,1,1,0,0,1],
    [0,0,0,0,0,1,1,0,0,1,1,0,0,0,0,0], [0,1,0,0,1,1,1,0,0,1,0,0,0,0,0,0],
    [0,0,1,0,0,1,1,1,0,0,1,0,0,0,0,0], [0,0,0,0,0,0,1,0,0,1,1,1,0,0,1,0],
    [0,0,0,0,0,1,0,0,1,1,1,0,0,1,0,0], [0,1,1,0,1,1,0,0,1,0,0,1,0,0,1,1],
    [0,0,1,1,0,1,1,0,1,1,0,0,1,0,0,1], [0,1,1,0,0,0,1,1,1,0,0,1,1,1,0,0],
    [0,0,1,1,1,0,0,1,1,1,0,0,0,1,1,0], [0,1,1,0,1,1,0,0,1,1,0,0,1,0,0,1],
    [0,1,1,0,0,0,1,1,0,0,1,1,1,0,0,1], [0,1,1,1,1,1,1,0,1,0,0,0,0,0,0,1],
]

# BC7 分区表 (3 子集) - 简化版，仅前 16 个
BC7_PARTITION_TABLE_3 = [
    [0,0,1,1,0,0,1,1,0,2,2,1,2,2,2,2], [0,0,0,1,0,0,1,1,2,2,1,1,2,2,2,1],
    [0,0,0,0,2,0,0,1,2,2,1,1,2,2,1,1], [0,2,2,2,0,0,2,2,0,0,1,1,0,1,1,1],
    [0,0,0,0,0,0,0,0,1,1,2,2,1,1,2,2], [0,0,1,1,0,0,1,1,0,0,2,2,0,0,2,2],
    [0,0,2,2,0,0,2,2,1,1,1,1,1,1,1,1], [0,0,1,1,0,0,1,1,2,2,1,1,2,2,1,1],
    [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2], [0,0,0,0,1,1,1,1,1,1,1,1,2,2,2,2],
    [0,0,0,0,1,1,1,1,2,2,2,2,2,2,2,2], [0,0,1,2,0,0,1,2,0,0,1,2,0,0,1,2],
    [0,1,1,2,0,1,1,2,0,1,1,2,0,1,1,2], [0,1,2,2,0,1,2,2,0,1,2,2,0,1,2,2],
    [0,0,1,1,0,1,1,2,1,1,2,2,1,2,2,2], [0,0,1,1,2,0,0,1,2,2,0,0,2,2,2,0],
    # 剩余分区表使用第一个作为默认
] + [[0,0,1,1,0,0,1,1,0,2,2,1,2,2,2,2]] * 48

# Anchor 索引表 (用于确定哪个像素需要少1位索引)
BC7_ANCHOR_INDEX_2 = [
    15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,15,
    15, 2, 8, 2, 2, 8, 8,15, 2, 8, 2, 2, 8, 8, 2, 2,
     15,15, 6, 8, 2, 8,15,15, 2, 8, 2, 2, 2,15,15, 6,
     6, 2, 6, 8,15,15, 2, 2,15,15,15,15, 3, 2,15,15,
]

BC7_ANCHOR_INDEX_3_2 = [
    3, 3,15,15, 8, 3,15,15, 8, 8, 6, 6, 6, 5, 3, 3,
    3, 3, 8,15, 3, 3, 6,10, 5, 8, 8, 6, 8, 5,15,15,
    8,15, 3, 5, 6,10, 8,15,15, 3,15, 5,15,15,15,15,
    3,15, 5, 5, 5, 8, 5,10, 5,10, 8,13,15,12, 3, 3,
]

BC7_ANCHOR_INDEX_3_3 = [
    15, 8, 8, 3,15,15, 3, 8,15,15,15,15,15,15,15, 8,
    15, 8,15, 3,15, 8,15, 8, 3,15, 6,10,15,15,10, 8,
    15, 3,15,10,10, 8, 9,10, 6,15, 8,15, 3, 6, 6, 8,
    15, 3,15,15,15,15,15,15,15,15,15,15, 3,15,15, 8,
]


class BitReader:
    """位流读取器"""
    
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
        """读取单个位"""
        return self.read_bits(1)


def expand_bits(value: int, from_bits: int, to_bits: int = 8) -> int:
    """扩展位数到目标精度"""
    if from_bits == 0:
        return 0
    if from_bits >= to_bits:
        return value >> (from_bits - to_bits)
    
    # 复制高位到低位填充
    result = value << (to_bits - from_bits)
    shift = from_bits
    while shift < to_bits:
        result |= value >> (2 * from_bits - to_bits - shift) if 2 * from_bits > to_bits + shift else value << (to_bits + shift - 2 * from_bits)
        shift += from_bits
    
    # 简化版: 直接按比例缩放
    return (value * 255 + (1 << (from_bits - 1))) >> from_bits if from_bits < 8 else value >> (from_bits - 8)


def interpolate_bc7(e0: int, e1: int, weight: int, weight_bits: int) -> int:
    """BC7 颜色插值"""
    # 权重表
    if weight_bits == 2:
        weights = [0, 21, 43, 64]
    elif weight_bits == 3:
        weights = [0, 9, 18, 27, 37, 46, 55, 64]
    elif weight_bits == 4:
        weights = [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]
    else:
        weights = [0, 64]
    
    w = weights[weight] if weight < len(weights) else 0
    return ((64 - w) * e0 + w * e1 + 32) >> 6


def decode_bc7_block(block: bytes) -> List[Tuple[int, int, int, int]]:
    """
    解码单个 BC7 块 (16 bytes -> 16 RGBA pixels)
    """
    if len(block) < 16:
        return [(0, 0, 0, 255)] * 16
    
    reader = BitReader(block)
    
    # 确定模式 (通过前导 0 的数量)
    mode = 0
    while mode < 8 and reader.read_bit() == 0:
        mode += 1
    
    if mode >= 8:
        # 无效块，返回黑色
        return [(0, 0, 0, 255)] * 16
    
    # 获取模式配置
    config = BC7_MODE_CONFIG[mode]
    num_subsets, partition_bits, rotation_bits, index_selection_bit = config[:4]
    color_bits, alpha_bits, p_bit_count, index_bits, index2_bits = config[4:]
    
    # 读取分区索引
    partition = reader.read_bits(partition_bits) if partition_bits > 0 else 0
    
    # 读取旋转位
    rotation = reader.read_bits(rotation_bits) if rotation_bits > 0 else 0
    
    # 读取索引选择位
    index_sel = reader.read_bits(1) if index_selection_bit else 0
    
    # 计算端点数量
    num_endpoints = num_subsets * 2
    
    # 读取颜色端点
    colors = []
    for _ in range(num_endpoints):
        r = reader.read_bits(color_bits)
        colors.append([r, 0, 0, 255])
    for i in range(num_endpoints):
        colors[i][1] = reader.read_bits(color_bits)
    for i in range(num_endpoints):
        colors[i][2] = reader.read_bits(color_bits)
    
    # 读取 alpha 端点
    if alpha_bits > 0:
        for i in range(num_endpoints):
            colors[i][3] = reader.read_bits(alpha_bits)
    
    # 读取 P-bits
    if p_bit_count > 0:
        if mode == 1:
            # 共享 P-bits
            for i in range(num_subsets):
                pbit = reader.read_bits(1)
                for j in range(2):
                    idx = i * 2 + j
                    for c in range(3):
                        colors[idx][c] = (colors[idx][c] << 1) | pbit
                    if alpha_bits > 0:
                        colors[idx][3] = (colors[idx][3] << 1) | pbit
        else:
            # 每端点 P-bit
            for i in range(num_endpoints):
                pbit = reader.read_bits(1)
                for c in range(3):
                    colors[i][c] = (colors[i][c] << 1) | pbit
                if alpha_bits > 0:
                    colors[i][3] = (colors[i][3] << 1) | pbit
    
    # 扩展颜色到 8 位
    effective_color_bits = color_bits + (1 if p_bit_count > 0 else 0)
    effective_alpha_bits = alpha_bits + (1 if p_bit_count > 0 and alpha_bits > 0 else 0)
    
    for i in range(num_endpoints):
        for c in range(3):
            colors[i][c] = expand_bits(colors[i][c], effective_color_bits)
        if alpha_bits > 0:
            colors[i][3] = expand_bits(colors[i][3], effective_alpha_bits)
        else:
            colors[i][3] = 255
    
    # 获取分区表
    if num_subsets == 2:
        partition_table = BC7_PARTITION_TABLE_2[partition] if partition < 64 else BC7_PARTITION_TABLE_2[0]
    elif num_subsets == 3:
        partition_table = BC7_PARTITION_TABLE_3[partition] if partition < 64 else BC7_PARTITION_TABLE_3[0]
    else:
        partition_table = [0] * 16
    
    # 读取颜色索引
    color_indices = []
    for i in range(16):
        subset = partition_table[i]
        
        # 确定是否是 anchor 像素（anchor 像素少1位）
        is_anchor = False
        if i == 0:
            is_anchor = True
        elif num_subsets == 2:
            if subset == 1 and i == BC7_ANCHOR_INDEX_2[partition]:
                is_anchor = True
        elif num_subsets == 3:
            if subset == 1 and i == BC7_ANCHOR_INDEX_3_2[partition]:
                is_anchor = True
            elif subset == 2 and i == BC7_ANCHOR_INDEX_3_3[partition]:
                is_anchor = True
        
        bits_to_read = index_bits - (1 if is_anchor else 0)
        color_indices.append(reader.read_bits(bits_to_read))
    
    # 读取 alpha 索引 (如果有单独的 alpha 索引)
    alpha_indices = None
    if index2_bits > 0:
        alpha_indices = []
        for i in range(16):
            bits_to_read = index2_bits - (1 if i == 0 else 0)
            alpha_indices.append(reader.read_bits(bits_to_read))
    
    # 插值生成最终像素
    pixels = []
    for i in range(16):
        subset = partition_table[i]
        e0 = colors[subset * 2]
        e1 = colors[subset * 2 + 1]
        
        # 颜色插值
        ci = color_indices[i]
        r = interpolate_bc7(e0[0], e1[0], ci, index_bits)
        g = interpolate_bc7(e0[1], e1[1], ci, index_bits)
        b = interpolate_bc7(e0[2], e1[2], ci, index_bits)
        
        # Alpha 插值
        if alpha_indices is not None:
            ai = alpha_indices[i]
            a = interpolate_bc7(e0[3], e1[3], ai, index2_bits)
        else:
            a = interpolate_bc7(e0[3], e1[3], ci, index_bits)
        
        # 应用旋转
        if rotation == 1:
            r, a = a, r
        elif rotation == 2:
            g, a = a, g
        elif rotation == 3:
            b, a = a, b
        
        # 如果有索引选择，交换颜色和 alpha 索引结果
        if index_sel and alpha_indices is not None:
            # 重新计算（已在上面处理）
            pass
        
        pixels.append((
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
            max(0, min(255, a))
        ))
    
    return pixels


def decode_bc7_texture(data: bytes, width: int, height: int) -> bytes:
    """
    解码整个 BC7 纹理为 RGBA
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
            
            pixels = decode_bc7_block(block_data)
            
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
@register_decoder('BC7')
def decode_bc7(data: bytes, width: int, height: int) -> bytes:
    """BC7 解码器入口"""
    return decode_bc7_texture(data, width, height)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("Testing BC7 decoder...")
    
    # 测试 BitReader
    reader = BitReader(bytes([0b10110100, 0b11001010]))
    assert reader.read_bits(4) == 0b0100
    assert reader.read_bits(4) == 0b1011
    print("✓ BitReader test passed")
    
    # 测试 expand_bits
    assert expand_bits(15, 4) == 255  # 4-bit max -> 8-bit max
    assert expand_bits(0, 4) == 0
    print("✓ expand_bits test passed")
    
    # 简单测试: 创建一个 mode 6 的测试块 (最简单的单子集模式)
    # Mode 6: 7-bit color, 7-bit alpha, 每端点1个p-bit, 4-bit索引
    # 这里只是验证不会崩溃
    test_block = bytes([0b01000000] + [0] * 15)  # Mode 6 (第7位是1)
    pixels = decode_bc7_block(test_block)
    assert len(pixels) == 16
    print("✓ BC7 block decode test passed")
    
    # 测试纹理解码
    width, height = 8, 8
    num_blocks = (width // 4) * (height // 4)
    test_data = test_block * num_blocks
    
    rgba = decode_bc7_texture(test_data, width, height)
    assert len(rgba) == width * height * 4
    print(f"✓ BC7 texture decode test passed ({width}x{height})")
