#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Chunk Parser - Parse FrameCapture chunks.

This module handles the parsing of individual Chunks within the FrameCapture section.
Chunks represent API calls recorded during frame capture.

Chunk structure (from renderdoc/serialise/serialiser.h):
- uint32: chunk_id (lower 16 bits) + flags (upper 16 bits)
- [optional] uint32 callstack_count + uint64[] callstack
- [optional] uint64 thread_id
- [optional] int64 duration_micro
- [optional] uint64 timestamp_micro
- uint32 or uint64: length (depends on CHUNK_64BIT_SIZE flag)
- bytes[length]: chunk data

Extracted from rdc_parser.py for better modularity.
"""

import struct
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .constants import (
    CHUNK_64BIT_SIZE,
    CHUNK_ALIGNMENT,
    CHUNK_CALLSTACK,
    CHUNK_DURATION,
    CHUNK_INDEX_MASK,
    CHUNK_THREAD_ID,
    CHUNK_TIMESTAMP,
)
from .enums import VulkanChunk
from .models import ChunkInfo


class ChunkParser:
    """
    RDC Chunk 解析器。
    
    负责解析 FrameCapture 数据中的 Chunk 结构。
    每个 Chunk 代表一次 API 调用（如 vkCreateImage, vkCmdDraw 等）。
    
    Usage:
        fc_data = section_parser.get_frame_capture_data()
        parser = ChunkParser()
        chunks = parser.parse_chunks(fc_data)
        
        for chunk in chunks:
            print(f"Chunk {chunk.chunk_id} at offset {chunk.data_offset}")
    """
    
    def __init__(self, max_invalid_skip: int = 100):
        """
        初始化 ChunkParser。
        
        Args:
            max_invalid_skip: 允许连续跳过的无效填充次数
        """
        self._max_invalid_skip = max_invalid_skip
    
    def parse_chunks(self, data: bytes) -> List[ChunkInfo]:
        """
        解析 FrameCapture 中的所有 Chunks。
        
        Args:
            data: FrameCapture 解压后的二进制数据
            
        Returns:
            List[ChunkInfo]: 解析出的 Chunk 列表
        """
        chunks = []
        offset = 0
        invalid_count = 0
        
        while offset < len(data) - 4:
            # 跳过对齐填充（全零）
            while offset < len(data) - 4:
                test = struct.unpack_from('<I', data, offset)[0]
                if test != 0:
                    break
                offset += 4
                invalid_count += 1
                if invalid_count > self._max_invalid_skip:
                    # 达到大块零填充区域，尝试对齐跳过
                    offset = ((offset + CHUNK_ALIGNMENT - 1) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
                    invalid_count = 0
            
            if offset >= len(data) - 4:
                break
            
            chunk, new_offset = self._parse_chunk_header(data, offset)
            if chunk is None:
                # 跳到下一个对齐边界重试
                offset = ((offset + CHUNK_ALIGNMENT) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
                invalid_count += 1
                if invalid_count > self._max_invalid_skip:
                    break
                continue
            
            invalid_count = 0
            chunks.append(chunk)
            
            # 移动到下一个 chunk：数据结束后对齐到 64 字节
            next_offset = chunk.data_offset + chunk.length
            offset = ((next_offset + CHUNK_ALIGNMENT - 1) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
        
        return chunks
    
    def _parse_chunk_header(self, data: bytes, offset: int) -> Tuple[Optional[ChunkInfo], int]:
        """
        解析单个 Chunk Header。
        
        Args:
            data: 二进制数据
            offset: 当前偏移量
            
        Returns:
            Tuple[Optional[ChunkInfo], int]: (Chunk 信息, 新偏移量)
        """
        if offset + 4 > len(data):
            return None, offset
        
        # 读取 chunk type + flags
        c = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        if c == 0:  # Chunk 0 是无效的
            return None, offset
        
        chunk_id = c & CHUNK_INDEX_MASK
        flags = c & ~CHUNK_INDEX_MASK
        
        # 可选字段
        callstack = None
        thread_id = None
        duration_micro = None
        timestamp_micro = None
        
        if flags & CHUNK_CALLSTACK:
            if offset + 4 > len(data):
                return None, offset
            num_frames = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if num_frames < 4096:  # 合理性检查
                if offset + num_frames * 8 <= len(data):
                    callstack = list(struct.unpack_from(f'<{num_frames}Q', data, offset))
                offset += num_frames * 8
            else:
                offset += num_frames * 8  # 跳过
        
        if flags & CHUNK_THREAD_ID:
            if offset + 8 > len(data):
                return None, offset
            thread_id = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        
        if flags & CHUNK_DURATION:
            if offset + 8 > len(data):
                return None, offset
            duration_micro = struct.unpack_from('<q', data, offset)[0]
            offset += 8
        
        if flags & CHUNK_TIMESTAMP:
            if offset + 8 > len(data):
                return None, offset
            timestamp_micro = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        
        # Chunk 长度
        if flags & CHUNK_64BIT_SIZE:
            if offset + 8 > len(data):
                return None, offset
            length = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        else:
            if offset + 4 > len(data):
                return None, offset
            length = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        
        chunk = ChunkInfo(
            chunk_id=chunk_id,
            flags=flags,
            length=length,
            data_offset=offset,
            thread_id=thread_id,
            duration_micro=duration_micro,
            timestamp_micro=timestamp_micro,
            callstack=callstack
        )
        
        return chunk, offset
    
    def get_chunk_data(self, data: bytes, chunk: ChunkInfo) -> bytes:
        """
        获取指定 Chunk 的数据部分。
        
        Args:
            data: FrameCapture 二进制数据
            chunk: Chunk 信息
            
        Returns:
            bytes: Chunk 数据
        """
        return data[chunk.data_offset:chunk.data_offset + chunk.length]
    
    def count_vulkan_chunks(self, chunks: List[ChunkInfo]) -> Dict[str, int]:
        """
        统计 Vulkan 关键资源相关的 chunk 数量。
        
        Args:
            chunks: Chunk 列表
            
        Returns:
            Dict[str, int]: chunk 类型名称 -> 数量
        """
        counts = Counter(chunk.chunk_id for chunk in chunks)
        
        return {
            "vkCreateShaderModule": counts.get(VulkanChunk.vkCreateShaderModule, 0),
            "vkCreateShadersEXT": counts.get(VulkanChunk.vkCreateShadersEXT, 0),
            "vkCreateImage": counts.get(VulkanChunk.vkCreateImage, 0),
        }
    
    def filter_chunks_by_type(self, chunks: List[ChunkInfo], chunk_types: List[int]) -> List[ChunkInfo]:
        """
        按类型过滤 Chunks。
        
        Args:
            chunks: Chunk 列表
            chunk_types: 要筛选的 Chunk 类型 ID 列表
            
        Returns:
            List[ChunkInfo]: 过滤后的 Chunk 列表
        """
        type_set = set(chunk_types)
        return [c for c in chunks if c.chunk_id in type_set]


def parse_frame_chunks(data: bytes) -> List[ChunkInfo]:
    """
    便捷函数：解析 FrameCapture 数据中的所有 Chunks。
    
    Args:
        data: FrameCapture 解压后的二进制数据
        
    Returns:
        List[ChunkInfo]: Chunk 列表
    """
    parser = ChunkParser()
    return parser.parse_chunks(data)
