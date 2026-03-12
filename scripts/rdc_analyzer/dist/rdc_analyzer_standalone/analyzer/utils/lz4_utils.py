"""
LZ4 解压工具
============

RenderDoc 使用 LZ4 分块压缩，每个块最大 1MB。
本模块提供兼容 RenderDoc 格式的 LZ4 解压功能。
"""

import struct
from typing import Tuple


def decompress_lz4_block(compressed: bytes, uncompressed_size: int) -> bytes:
    """
    解压单个 LZ4 块 (纯 Python 实现)
    
    LZ4 块格式:
    - Token (1 byte): 高 4 位 = literal 长度, 低 4 位 = match 长度
    - 如果长度 == 15, 后续字节累加直到非 255
    - Literal 数据
    - Offset (2 bytes LE): 回溯偏移
    - Match 扩展长度
    
    Args:
        compressed: 压缩数据
        uncompressed_size: 期望的解压后大小
        
    Returns:
        解压后的数据
    """
    output = bytearray()
    pos = 0
    data_len = len(compressed)
    
    while pos < data_len and len(output) < uncompressed_size:
        # 读取 Token
        if pos >= data_len:
            break
        token = compressed[pos]
        pos += 1
        
        # Literal 长度
        literal_len = (token >> 4) & 0x0F
        if literal_len == 15:
            while pos < data_len:
                extra = compressed[pos]
                pos += 1
                literal_len += extra
                if extra != 255:
                    break
        
        # 复制 Literal
        if pos + literal_len > data_len:
            literal_len = data_len - pos
        output.extend(compressed[pos:pos + literal_len])
        pos += literal_len
        
        # 检查是否到达末尾
        if len(output) >= uncompressed_size:
            break
        
        # 读取 Match Offset (2 bytes LE)
        if pos + 2 > data_len:
            break
        offset = compressed[pos] | (compressed[pos + 1] << 8)
        pos += 2
        
        if offset == 0:
            # 非法偏移，结束
            break
        
        # Match 长度 (最小 4)
        match_len = (token & 0x0F) + 4
        if (token & 0x0F) == 15:
            while pos < data_len:
                extra = compressed[pos]
                pos += 1
                match_len += extra
                if extra != 255:
                    break
        
        # 从输出缓冲区复制 (可能重叠)
        match_start = len(output) - offset
        if match_start < 0:
            # 偏移超出范围，用零填充
            output.extend(b'\x00' * match_len)
        else:
            # 逐字节复制 (处理重叠情况)
            for i in range(match_len):
                if match_start + i < len(output):
                    output.append(output[match_start + i])
                else:
                    output.append(0)
    
    return bytes(output[:uncompressed_size])


def decompress_lz4_blocks(data: bytes, start_offset: int, total_uncompressed: int) -> bytes:
    """
    解压 RenderDoc LZ4 分块数据
    
    RenderDoc 使用分块压缩:
    - 每个块前有 4 字节 LE 的压缩大小
    - 解压后每块最大 1MB
    - 块之间使用字典链式解压 (LZ4_decompress_safe_continue)
    
    Args:
        data: 完整的 RDC 文件数据
        start_offset: 压缩数据起始偏移
        total_uncompressed: 期望的总解压大小
        
    Returns:
        完整解压数据
    """
    BLOCK_SIZE = 1024 * 1024  # 1MB per block
    result = bytearray()
    pos = start_offset
    
    # 上一个块的解压数据 (用于字典)
    # 注意: 纯 Python 实现不支持字典模式，这是简化版
    
    while len(result) < total_uncompressed and pos + 4 <= len(data):
        # 读取压缩块大小
        compressed_size = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        if compressed_size == 0:
            break
        
        if pos + compressed_size > len(data):
            break
        
        # 计算期望解压大小
        remaining = total_uncompressed - len(result)
        expected_size = min(BLOCK_SIZE, remaining)
        
        # 解压块
        compressed_block = data[pos:pos + compressed_size]
        decompressed = decompress_lz4_block(compressed_block, expected_size)
        result.extend(decompressed)
        
        pos += compressed_size
    
    return bytes(result[:total_uncompressed])


def try_import_lz4() -> bool:
    """
    尝试导入 lz4 库
    
    Returns:
        True 如果 lz4 库可用
    """
    try:
        import lz4.block
        return True
    except ImportError:
        return False


def decompress_with_lz4_lib(
    data: bytes, 
    start_offset: int, 
    total_uncompressed: int
) -> bytes:
    """
    使用 lz4 库解压 (如果可用)
    
    Args:
        data: 完整的 RDC 文件数据
        start_offset: 压缩数据起始偏移
        total_uncompressed: 期望的总解压大小
        
    Returns:
        完整解压数据
    """
    try:
        import lz4.block
    except ImportError:
        return decompress_lz4_blocks(data, start_offset, total_uncompressed)
    
    BLOCK_SIZE = 1024 * 1024
    result = bytearray()
    pos = start_offset
    
    prev_block = b''  # 字典上下文
    
    while len(result) < total_uncompressed and pos + 4 <= len(data):
        compressed_size = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        if compressed_size == 0:
            break
        
        if pos + compressed_size > len(data):
            break
        
        remaining = total_uncompressed - len(result)
        expected_size = min(BLOCK_SIZE, remaining)
        
        compressed_block = data[pos:pos + compressed_size]
        
        # 使用 lz4 库解压 (带字典)
        try:
            if prev_block:
                decompressed = lz4.block.decompress(
                    compressed_block,
                    uncompressed_size=expected_size,
                    dict=prev_block
                )
            else:
                decompressed = lz4.block.decompress(
                    compressed_block,
                    uncompressed_size=expected_size
                )
            result.extend(decompressed)
            prev_block = decompressed  # 更新字典
        except Exception:
            # 回退到纯 Python 实现
            decompressed = decompress_lz4_block(compressed_block, expected_size)
            result.extend(decompressed)
        
        pos += compressed_size
    
    return bytes(result[:total_uncompressed])
