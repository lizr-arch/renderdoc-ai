#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 二进制 IO 工具类

提供低级别的二进制读取方法，用于解析 RDC 文件格式。
从 rdc_parser.py 的 RDCParser 类中提取。
"""

import struct
from typing import BinaryIO, Optional


class BinaryReader:
    """二进制文件读取器
    
    提供便捷的二进制数据读取方法，支持：
    - 各种整数类型读取 (u8, u16, u32, u64, i32)
    - 浮点数读取 (f32, f64)
    - 定长字符串读取
    - 位置控制和对齐
    
    Usage:
        with open('file.rdc', 'rb') as f:
            reader = BinaryReader(f)
            magic = reader.read(4)
            version = reader.read_u32()
    """
    
    def __init__(self, file: BinaryIO):
        """
        Args:
            file: 已打开的二进制文件对象
        """
        self._file = file
    
    @property
    def file(self) -> BinaryIO:
        """获取底层文件对象"""
        return self._file
    
    def read(self, size: int) -> bytes:
        """读取指定字节数
        
        Args:
            size: 要读取的字节数
            
        Returns:
            读取的字节数据
            
        Raises:
            EOFError: 如果读取的字节数不足
        """
        data = self._file.read(size)
        if len(data) != size:
            raise EOFError(f"Expected {size} bytes, got {len(data)}")
        return data
    
    def read_or_none(self, size: int) -> Optional[bytes]:
        """读取指定字节数，不足时返回 None 而非抛出异常"""
        data = self._file.read(size)
        if len(data) != size:
            return None
        return data
    
    def read_u8(self) -> int:
        """读取无符号 8 位整数"""
        return struct.unpack('<B', self.read(1))[0]
    
    def read_u16(self) -> int:
        """读取无符号 16 位整数 (little-endian)"""
        return struct.unpack('<H', self.read(2))[0]
    
    def read_u32(self) -> int:
        """读取无符号 32 位整数 (little-endian)"""
        return struct.unpack('<I', self.read(4))[0]
    
    def read_u64(self) -> int:
        """读取无符号 64 位整数 (little-endian)"""
        return struct.unpack('<Q', self.read(8))[0]
    
    def read_i32(self) -> int:
        """读取有符号 32 位整数 (little-endian)"""
        return struct.unpack('<i', self.read(4))[0]
    
    def read_i64(self) -> int:
        """读取有符号 64 位整数 (little-endian)"""
        return struct.unpack('<q', self.read(8))[0]
    
    def read_f32(self) -> float:
        """读取 32 位浮点数 (little-endian)"""
        return struct.unpack('<f', self.read(4))[0]
    
    def read_f64(self) -> float:
        """读取 64 位浮点数 (little-endian)"""
        return struct.unpack('<d', self.read(8))[0]
    
    def read_string(self, length: int) -> str:
        """读取固定长度字符串
        
        Args:
            length: 要读取的字节数
            
        Returns:
            解码后的字符串（去除 null 终止符）
        """
        data = self.read(length)
        # 去除 null 终止符
        null_idx = data.find(b'\x00')
        if null_idx >= 0:
            data = data[:null_idx]
        return data.decode('utf-8', errors='replace')
    
    def read_cstring(self, max_length: int = 4096) -> str:
        """读取 null 终止的 C 风格字符串
        
        Args:
            max_length: 最大读取长度，防止无限读取
            
        Returns:
            解码后的字符串
        """
        chars = []
        for _ in range(max_length):
            b = self.read(1)
            if b == b'\x00':
                break
            chars.append(b)
        return b''.join(chars).decode('utf-8', errors='replace')
    
    def tell(self) -> int:
        """获取当前文件位置"""
        return self._file.tell()
    
    def seek(self, offset: int, whence: int = 0):
        """设置文件位置
        
        Args:
            offset: 偏移量
            whence: 参考位置 (0=开头, 1=当前, 2=末尾)
        """
        self._file.seek(offset, whence)
    
    def skip(self, count: int):
        """跳过指定字节数"""
        self.seek(count, 1)
    
    def align_to(self, alignment: int):
        """对齐到指定边界
        
        Args:
            alignment: 对齐边界（如 4, 8, 64）
        """
        pos = self.tell()
        aligned = (pos + alignment - 1) & ~(alignment - 1)
        if aligned > pos:
            self.seek(aligned)
    
    def remaining(self) -> int:
        """获取剩余可读字节数"""
        current = self.tell()
        self.seek(0, 2)  # 移动到文件末尾
        end = self.tell()
        self.seek(current)  # 恢复位置
        return end - current
    
    def peek(self, size: int) -> bytes:
        """预览指定字节数，不移动文件指针
        
        Args:
            size: 要预览的字节数
            
        Returns:
            预览的字节数据
        """
        pos = self.tell()
        data = self.read(size)
        self.seek(pos)
        return data


# ============================================================================
# 静态工具函数（用于直接操作 bytes 数据）
# ============================================================================

def read_u8_from_bytes(data: bytes, offset: int) -> int:
    """从 bytes 中读取 u8"""
    return struct.unpack_from('<B', data, offset)[0]


def read_u16_from_bytes(data: bytes, offset: int) -> int:
    """从 bytes 中读取 u16"""
    return struct.unpack_from('<H', data, offset)[0]


def read_u32_from_bytes(data: bytes, offset: int) -> int:
    """从 bytes 中读取 u32"""
    return struct.unpack_from('<I', data, offset)[0]


def read_u64_from_bytes(data: bytes, offset: int) -> int:
    """从 bytes 中读取 u64"""
    return struct.unpack_from('<Q', data, offset)[0]


def read_i32_from_bytes(data: bytes, offset: int) -> int:
    """从 bytes 中读取 i32"""
    return struct.unpack_from('<i', data, offset)[0]


def read_f32_from_bytes(data: bytes, offset: int) -> float:
    """从 bytes 中读取 f32"""
    return struct.unpack_from('<f', data, offset)[0]


def read_f64_from_bytes(data: bytes, offset: int) -> float:
    """从 bytes 中读取 f64"""
    return struct.unpack_from('<d', data, offset)[0]


def read_string_from_bytes(data: bytes, offset: int, length: int) -> str:
    """从 bytes 中读取固定长度字符串"""
    chunk = data[offset:offset + length]
    null_idx = chunk.find(b'\x00')
    if null_idx >= 0:
        chunk = chunk[:null_idx]
    return chunk.decode('utf-8', errors='replace')


def align_offset(offset: int, alignment: int) -> int:
    """计算对齐后的偏移量"""
    return (offset + alignment - 1) & ~(alignment - 1)


__all__ = [
    'BinaryReader',
    'read_u8_from_bytes',
    'read_u16_from_bytes',
    'read_u32_from_bytes',
    'read_u64_from_bytes',
    'read_i32_from_bytes',
    'read_f32_from_bytes',
    'read_f64_from_bytes',
    'read_string_from_bytes',
    'align_offset',
]
