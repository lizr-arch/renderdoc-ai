#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Shader Extractor - Extract SPIR-V shaders from Vulkan captures.

This module handles the extraction of SPIR-V shader modules from RDC files.
It parses vkCreateShaderModule and vkCreateShadersEXT chunks.

Shader data structure in vkCreateShaderModule chunk:
- offset 0x00-0x07: ResourceId (device)
- offset 0x08-0x0F: flags/other data
- offset 0x10-0x17: codeSize (uint64_t)
- offset 0x18-0x1F: duplicate codeSize
- offset 0x20-0x5F: padding (zeros)
- offset 0x60+: SPIR-V data (64-byte aligned)

Extracted from rdc_parser.py for better modularity.
"""

import hashlib
import struct
from typing import List, Optional

from .constants import CHUNK_ALIGNMENT, SPIRV_MAGIC
from .enums import VulkanChunk
from .models import ChunkInfo, ShaderInfo


class ShaderExtractor:
    """
    SPIR-V Shader 提取器。
    
    从 Vulkan 捕获的 FrameCapture 数据中提取 SPIR-V shader 模块。
    
    Usage:
        fc_data = section_parser.get_frame_capture_data()
        chunks = chunk_parser.parse_chunks(fc_data)
        
        extractor = ShaderExtractor()
        shaders = extractor.extract_from_chunks(fc_data, chunks)
        
        for shader in shaders:
            print(f"Shader {shader.resource_id}: {shader.stage_name}")
    """
    
    def __init__(self, deduplicate: bool = True):
        """
        初始化 ShaderExtractor。
        
        Args:
            deduplicate: 是否对提取的 shader 去重（基于内容哈希）
        """
        self._deduplicate = deduplicate
    
    def extract_from_chunks(self, data: bytes, chunks: List[ChunkInfo]) -> List[ShaderInfo]:
        """
        从 Chunk 列表中提取所有 SPIR-V shaders。
        
        Args:
            data: FrameCapture 二进制数据
            chunks: 已解析的 Chunk 列表
            
        Returns:
            List[ShaderInfo]: 提取的 Shader 列表
        """
        shaders = []
        create_shaders_ext = getattr(VulkanChunk, "vkCreateShadersEXT", None)

        for chunk in chunks:
            if chunk.chunk_id == VulkanChunk.vkCreateShaderModule:
                shader = self._extract_from_shader_module(data, chunk)
                if shader and shader.is_valid_spirv:
                    shaders.append(shader)
            elif create_shaders_ext is not None and chunk.chunk_id == create_shaders_ext:
                shaders.extend(self._extract_spirv_blobs(data, chunk))
        
        if self._deduplicate:
            return self._deduplicate_shaders(shaders)
        
        return shaders
    
    def _deduplicate_shaders(self, shaders: List[ShaderInfo]) -> List[ShaderInfo]:
        """根据内容哈希去重 Shaders"""
        deduped = []
        seen = set()
        
        for shader in shaders:
            if not shader or not shader.is_valid_spirv:
                continue
            digest = hashlib.sha1(shader.spirv_data).digest()
            if digest in seen:
                continue
            seen.add(digest)
            deduped.append(shader)
        
        return deduped
    
    def _extract_from_shader_module(self, data: bytes, chunk: ChunkInfo) -> Optional[ShaderInfo]:
        """
        从 vkCreateShaderModule chunk 中提取 Shader。
        
        数据结构 (基于调试分析):
        - offset 0x00-0x07: ResourceId (device)
        - offset 0x08-0x0F: 标志或其他数据
        - offset 0x10-0x17: codeSize (uint64_t)
        - offset 0x18-0x1F: 重复的 codeSize
        - offset 0x20-0x5F: 填充 (全零)
        - offset 0x60+: SPIR-V 数据 (64字节对齐)
        """
        try:
            offset = chunk.data_offset
            chunk_end = offset + chunk.length
            
            if chunk.length < 0x64:  # 最小有效长度
                return None
            
            # 读取 ResourceId (偏移 0x00)
            resource_id = struct.unpack_from('<Q', data, offset)[0]
            
            # 读取 codeSize (偏移 0x10)
            code_size = struct.unpack_from('<Q', data, offset + 0x10)[0]
            
            # 验证 codeSize
            if code_size == 0 or code_size > chunk.length or code_size % 4 != 0:
                # 尝试备用方法：直接搜索 SPIR-V magic
                spirv_offset = self._find_spirv_in_chunk(data, offset, chunk_end)
                if spirv_offset < 0:
                    return None
                spirv_data = self._extract_spirv_blob(data, spirv_offset, chunk_end)
                if spirv_data:
                    return ShaderInfo(
                        resource_id=resource_id,
                        spirv_data=spirv_data,
                        code_size=len(spirv_data),
                        chunk_offset=chunk.data_offset
                    )
                return None
            
            # SPIR-V 数据在 0x60 偏移处 (64字节对齐)
            spirv_offset = offset + 0x60
            
            # 验证 SPIR-V magic
            if spirv_offset + 4 > chunk_end:
                return None
            
            magic = struct.unpack_from('<I', data, spirv_offset)[0]
            if magic != SPIRV_MAGIC:
                # Magic 不在预期位置，搜索
                spirv_offset = self._find_spirv_in_chunk(data, offset, chunk_end)
                if spirv_offset < 0:
                    return None
            
            # 提取 SPIR-V 数据
            spirv_end = spirv_offset + code_size
            if spirv_end > chunk_end:
                # codeSize 超出 chunk 范围，使用 chunk 剩余长度
                spirv_end = chunk_end
                code_size = spirv_end - spirv_offset
            
            spirv_data = data[spirv_offset:spirv_end]
            
            # 验证提取的数据
            if len(spirv_data) < 20:  # SPIR-V header 最小 20 字节
                return None
            
            # 确保 magic 正确
            extracted_magic = struct.unpack_from('<I', spirv_data, 0)[0]
            if extracted_magic != SPIRV_MAGIC:
                return None
            
            return ShaderInfo(
                resource_id=resource_id,
                spirv_data=spirv_data,
                code_size=code_size,
                chunk_offset=chunk.data_offset
            )
            
        except Exception as e:
            print(f"Warning: Failed to extract shader from chunk at {chunk.data_offset}: {e}")
            return None
    
    def _extract_spirv_blobs(self, data: bytes, chunk: ChunkInfo) -> List[ShaderInfo]:
        """
        在 chunk 范围内扫描所有 SPIR-V blob（用于 vkCreateShadersEXT）。
        
        Args:
            data: 二进制数据
            chunk: Chunk 信息
            
        Returns:
            List[ShaderInfo]: 找到的 Shader 列表
        """
        try:
            start = chunk.data_offset
            end = start + chunk.length
            magic_bytes = struct.pack('<I', SPIRV_MAGIC)
            pos = data.find(magic_bytes, start, end)
            shaders = []
            
            while pos != -1 and pos < end - 4:
                spirv_data = self._extract_spirv_blob(data, pos, end)
                if spirv_data:
                    shaders.append(ShaderInfo(
                        resource_id=0,
                        spirv_data=spirv_data,
                        code_size=len(spirv_data),
                        chunk_offset=chunk.data_offset
                    ))
                    pos = data.find(magic_bytes, pos + len(spirv_data), end)
                else:
                    pos = data.find(magic_bytes, pos + 4, end)
            
            return shaders
        except Exception as e:
            print(f"Warning: Failed to scan SPIR-V in chunk at {chunk.data_offset}: {e}")
            return []
    
    def _find_spirv_in_chunk(self, data: bytes, start: int, end: int) -> int:
        """
        在 chunk 数据中搜索 SPIR-V magic。
        
        优先在 64 字节对齐位置搜索，然后尝试任意位置。
        
        Args:
            data: 二进制数据
            start: 搜索起始位置
            end: 搜索结束位置
            
        Returns:
            int: SPIR-V magic 的位置，未找到返回 -1
        """
        magic_bytes = struct.pack('<I', SPIRV_MAGIC)
        
        # 只在 64 字节对齐的位置搜索
        aligned_start = (start + CHUNK_ALIGNMENT - 1) & ~(CHUNK_ALIGNMENT - 1)
        
        pos = aligned_start
        while pos < end - 4:
            if data[pos:pos + 4] == magic_bytes:
                return pos
            pos += CHUNK_ALIGNMENT
        
        # 如果对齐搜索失败，尝试任意位置
        idx = data.find(magic_bytes, start, end)
        return idx
    
    def _extract_spirv_blob(self, data: bytes, start: int, max_end: int) -> Optional[bytes]:
        """
        提取 SPIR-V blob，基于 SPIR-V 结构解析。
        
        Args:
            data: 二进制数据
            start: SPIR-V magic 位置
            max_end: 最大结束位置
            
        Returns:
            bytes: SPIR-V 数据，无效返回 None
        """
        if start + 20 > max_end:
            return None
        
        # SPIR-V header: magic(4) + version(4) + generator(4) + bound(4) + reserved(4)
        magic, version, generator, bound, reserved = struct.unpack_from('<5I', data, start)
        
        if magic != SPIRV_MAGIC:
            return None
        
        # SPIR-V 是 word (4 bytes) 为单位
        # 扫描直到遇到无效指令或超出范围
        offset = start + 20  # 跳过 header
        
        while offset < max_end - 4:
            word = struct.unpack_from('<I', data, offset)[0]
            word_count = word >> 16
            opcode = word & 0xFFFF
            
            if word_count == 0:
                break
            
            if opcode == 0 and word_count == 0:
                break
            
            offset += word_count * 4
        
        # 返回 SPIR-V 数据
        size = offset - start
        if size > 0 and size % 4 == 0:
            return data[start:offset]
        
        return None


def extract_vulkan_shaders(data: bytes, chunks: List[ChunkInfo], deduplicate: bool = True) -> List[ShaderInfo]:
    """
    便捷函数：从 FrameCapture 数据中提取所有 Vulkan shaders。
    
    Args:
        data: FrameCapture 二进制数据
        chunks: 已解析的 Chunk 列表
        deduplicate: 是否去重
        
    Returns:
        List[ShaderInfo]: Shader 列表
    """
    extractor = ShaderExtractor(deduplicate=deduplicate)
    return extractor.extract_from_chunks(data, chunks)
