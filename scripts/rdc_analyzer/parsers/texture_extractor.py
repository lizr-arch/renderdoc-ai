#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Texture Extractor - Vulkan texture metadata extraction

从 vkCreateImage Chunks 中提取 VkImageCreateInfo 结构体信息。

支持的格式:
- Format A: 标准对齐格式
- Format B: 短格式 (106 bytes)，带 1 字节 padding
- Format C: 长格式 (136 bytes)，带 pNext 扩展链

Author: Codex RDC Analyzer Team
License: MIT
"""

import struct
from typing import Optional, List, Dict, Tuple, TYPE_CHECKING

from .models import TextureInfo, ChunkInfo
from .enums import VulkanChunk, VK_FORMAT_NAMES

if TYPE_CHECKING:
    pass


class TextureExtractor:
    """Vulkan 纹理元数据提取器
    
    解析 vkCreateImage chunk 获取 VkImageCreateInfo 信息。
    注意：这只提取元数据，不提取实际像素数据（需要 GPU 回放）。
    """
    
    def __init__(self, frame_data: bytes, chunks: List[ChunkInfo]):
        """
        Args:
            frame_data: FrameCapture section 的原始解压数据
            chunks: 已解析的 Chunk 列表
        """
        self._data = frame_data
        self._chunks = chunks
    
    def extract_all(self) -> List[TextureInfo]:
        """提取所有 Vulkan 纹理元数据
        
        Returns:
            TextureInfo 列表
        """
        textures = []
        for chunk in self._chunks:
            if chunk.chunk_id == VulkanChunk.vkCreateImage:
                texture = self._extract_texture_from_chunk(chunk)
                if texture:
                    textures.append(texture)
        return textures
    
    def _extract_texture_from_chunk(self, chunk: ChunkInfo) -> Optional[TextureInfo]:
        """从 vkCreateImage chunk 中提取纹理元数据
        
        基于实际 RDC 数据分析的布局:
        
        短格式 (106 bytes):
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: 标记 = 14 (0x0E)
        - 0x0C-0x0F: flags (uint32)
        - 0x10: 额外字节 (0x00)
        - 0x11-0x14: imageType (注意: 偏移了1字节!)
        - ...
        
        长格式 (136 bytes, 包含 pNext 链):
        - 包含额外的扩展信息
        """
        try:
            offset = chunk.data_offset
            chunk_end = offset + chunk.length
            
            if chunk.length < 64:
                return None
            
            # 从偏移 0x08 开始搜索数据
            search_start = offset + 8
            
            # 读取标记
            marker = struct.unpack_from('<I', self._data, search_start)[0]
            
            if marker == 14:  # 简单格式
                # 方式 1: 假设在 0x0C 是 flags，然后每 4 字节
                texture = self._parse_format_a(offset, chunk_end)
                if texture:
                    return texture
                
                # 方式 2: 假设字节对齐问题，从 0x11 开始
                texture = self._parse_format_b(offset, chunk_end)
                if texture:
                    return texture
            else:
                # 长格式，包含 pNext 链
                texture = self._parse_format_c(offset, chunk_end)
                if texture:
                    return texture
            
            # 备用：通用扫描
            return self._try_parse_image_create_info(search_start, chunk_end, offset)
            
        except Exception:
            return None
    
    def _parse_format_a(self, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 A：标准对齐"""
        try:
            offset = chunk_start + 12  # 跳过 device(8) + marker(4)
            
            # 读取 flags (4 bytes)
            flags = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            # 检查是否有额外的 1 字节 padding
            if offset < chunk_end - 1:
                b0 = self._data[offset]
                b1 = self._data[offset + 1] if offset + 1 < chunk_end else 0
                
                if b0 == 0 and b1 in (0, 1, 2):
                    offset += 1
            
            # 现在读取 imageType
            image_type = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if image_type > 2:
                return None
            
            # format
            fmt = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if fmt == 0 or fmt > 300:
                return None
            
            # extent: width, height, depth
            width = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            height = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            depth = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if not self._validate_extent(width, height, depth):
                return None
            
            # mipLevels, arrayLayers, samples, tiling, usage
            mip_levels = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            array_layers = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            samples = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            tiling = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            usage = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if not self._validate_image_params(mip_levels, array_layers, samples, tiling, usage):
                return None
            
            # 读取 Image ResourceId
            resource_id = self._find_resource_id(offset, chunk_end)
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _parse_format_b(self, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 B：短格式 (106 bytes)，带 1 字节 padding
        
        验证通过的布局:
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: Marker = 14 (4 bytes)
        - 0x0C-0x0F: flags (4 bytes)
        - 0x10: padding byte (1 byte, 值为 0x00)
        - 0x11-0x14: imageType (4 bytes)
        - 0x15-0x18: format (4 bytes)
        - ...
        """
        try:
            chunk_len = chunk_end - chunk_start
            if chunk_len != 106:
                return None
            
            # 检查 padding byte
            padding = self._data[chunk_start + 0x10]
            if padding != 0:
                return None
            
            # 从偏移 0x11 开始读取 VkImageCreateInfo 字段
            offset = chunk_start + 0x11
            
            if offset + 40 > chunk_end:
                return None
            
            image_type = struct.unpack_from('<I', self._data, offset)[0]
            if image_type > 2:
                return None
            offset += 4
            
            fmt = struct.unpack_from('<I', self._data, offset)[0]
            if fmt == 0 or fmt > 300:
                return None
            offset += 4
            
            width = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            height = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            depth = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if not self._validate_extent(width, height, depth):
                return None
            
            mip_levels = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            array_layers = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            samples = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            tiling = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            usage = struct.unpack_from('<I', self._data, offset)[0]
            offset += 4
            
            if not self._validate_image_params(mip_levels, array_layers, samples, tiling, usage):
                return None
            
            # 读取 Image ResourceId (在 offset 0x54 附近)
            resource_id = 0
            rid_offset = chunk_start + 0x54
            if rid_offset + 8 <= chunk_end:
                resource_id = struct.unpack_from('<Q', self._data, rid_offset)[0]
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _parse_format_c(self, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 C：带 pNext 扩展的长格式 (136 bytes)
        
        基于 hex 分析的布局（含 pNext 扩展块）:
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: Marker = 14 (4 bytes)
        - 0x0C-0x0F: flags (4 bytes)
        - 0x10: pNext presence marker (1 byte, 值为 0x01)
        - 0x11-0x23: pNext 扩展数据
        - 0x24-0x27: format (4 bytes)
        - ...
        """
        try:
            chunk_len = chunk_end - chunk_start
            if chunk_len < 120 or chunk_len > 160:
                return None
            
            # 检查 pNext 标记
            pnext_marker = self._data[chunk_start + 0x10]
            if pnext_marker != 0x01:
                return None
            
            # 尝试固定偏移解析
            result = self._try_format_c_fixed_offset(chunk_start, chunk_end)
            if result:
                return result
            
            # 尝试扫描查找
            return self._try_format_c_scan(chunk_start, chunk_end)
            
        except (struct.error, IndexError):
            return None
    
    def _try_format_c_fixed_offset(self, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """尝试使用固定偏移解析长格式"""
        offset_candidates = [
            (0x24, "标准 pNext 长格式"),
            (0x23, "无额外 padding"),
            (0x25, "多一字节 padding"),
        ]
        
        for fmt_offset, _ in offset_candidates:
            result = self._parse_at_offset(chunk_start, chunk_end, fmt_offset)
            if result:
                return result
        
        return None
    
    def _parse_at_offset(self, chunk_start: int, chunk_end: int, fmt_offset: int) -> Optional[TextureInfo]:
        """从指定偏移解析 VkImageCreateInfo 结构"""
        try:
            base = chunk_start + fmt_offset
            if base + 40 > chunk_end:
                return None
            
            fmt = struct.unpack_from('<I', self._data, base)[0]
            if fmt == 0 or fmt > 300:
                return None
            
            width = struct.unpack_from('<I', self._data, base + 4)[0]
            height = struct.unpack_from('<I', self._data, base + 8)[0]
            depth = struct.unpack_from('<I', self._data, base + 12)[0]
            
            if not self._validate_extent(width, height, depth):
                return None
            
            mip_levels = struct.unpack_from('<I', self._data, base + 16)[0]
            array_layers = struct.unpack_from('<I', self._data, base + 20)[0]
            samples = struct.unpack_from('<I', self._data, base + 24)[0]
            tiling = struct.unpack_from('<I', self._data, base + 28)[0]
            usage = struct.unpack_from('<I', self._data, base + 32)[0]
            
            if not self._validate_image_params(mip_levels, array_layers, samples, tiling, usage):
                return None
            
            # 尝试读取 imageType
            image_type = 1  # 默认 2D
            for type_offset in [0x20, 0x21, 0x22, 0x23]:
                if chunk_start + type_offset < base:
                    candidate = struct.unpack_from('<I', self._data, chunk_start + type_offset)[0]
                    if candidate <= 2:
                        image_type = candidate
                        break
            
            # 读取 ResourceId
            resource_id = self._find_resource_id_from_end(chunk_end)
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _try_format_c_scan(self, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """通过特征扫描查找长格式中的 format + extent"""
        chunk_len = chunk_end - chunk_start
        best_result = None
        best_score = 0
        
        # 扫描可能的 format 起始位置
        for scan_offset in range(0x20, min(0x50, chunk_len - 36), 1):
            pos = chunk_start + scan_offset
            
            try:
                fmt = struct.unpack_from('<I', self._data, pos)[0]
                if fmt == 0 or fmt > 300:
                    continue
                
                width = struct.unpack_from('<I', self._data, pos + 4)[0]
                height = struct.unpack_from('<I', self._data, pos + 8)[0]
                depth = struct.unpack_from('<I', self._data, pos + 12)[0]
                
                if not self._validate_extent(width, height, depth):
                    continue
                
                # 计算匹配分数
                score = self._calculate_format_score(fmt, width, height, depth)
                
                # 验证后续字段
                mip = struct.unpack_from('<I', self._data, pos + 16)[0]
                layers = struct.unpack_from('<I', self._data, pos + 20)[0]
                samples = struct.unpack_from('<I', self._data, pos + 24)[0]
                
                if not (0 < mip <= 15):
                    continue
                score += 2
                
                if not (0 < layers <= 2048):
                    continue
                score += 2
                
                if samples not in (1, 2, 4, 8, 16, 32, 64):
                    continue
                score += 3
                
                if score > best_score:
                    best_score = score
                    
                    tiling = struct.unpack_from('<I', self._data, pos + 28)[0]
                    usage = struct.unpack_from('<I', self._data, pos + 32)[0]
                    
                    resource_id = self._find_resource_id_from_end(chunk_end)
                    
                    best_result = TextureInfo(
                        resource_id=resource_id,
                        image_type=1,  # 假设 2D
                        format=fmt,
                        width=width,
                        height=height,
                        depth=depth,
                        mip_levels=mip,
                        array_layers=layers,
                        samples=samples,
                        usage=usage if usage <= 0xFFFF else 0,
                        chunk_offset=chunk_start
                    )
                    
            except (struct.error, IndexError):
                continue
        
        return best_result
    
    def _try_parse_image_create_info(self, offset: int, chunk_end: int, chunk_offset: int) -> Optional[TextureInfo]:
        """尝试解析 VkImageCreateInfo 结构（通用扫描）"""
        if offset + 48 > chunk_end:
            return None
        
        best_match = None
        best_score = 0
        
        # 扫描整个 chunk 寻找最佳匹配
        for scan_offset in range(0, min(80, chunk_end - offset - 44), 4):
            pos = offset + scan_offset
            
            try:
                vals = struct.unpack_from('<11I', self._data, pos)
                flags, image_type, fmt, width, height, depth, mip_levels, array_layers, samples, tiling, usage = vals
                
                # 计算匹配分数
                score = 0
                
                if image_type > 2:
                    continue
                score += 10
                
                if fmt == 0 or fmt > 500:
                    continue
                if fmt in VK_FORMAT_NAMES:
                    score += 5
                else:
                    score += 1
                
                if not self._validate_extent(width, height, depth):
                    continue
                
                # 尺寸是 2 的幂次加分
                if width > 0 and (width & (width - 1)) == 0:
                    score += 2
                if height > 0 and (height & (height - 1)) == 0:
                    score += 2
                
                score += 5
                
                if mip_levels == 0 or mip_levels > 15:
                    continue
                if array_layers == 0 or array_layers > 2048:
                    continue
                score += 3
                
                if samples not in (1, 2, 4, 8, 16, 32, 64):
                    continue
                score += 3
                
                if tiling > 1:
                    continue
                score += 2
                
                if usage == 0 or usage > 0xFFFF:
                    continue
                score += 2
                
                # 额外验证
                if image_type == 1 and depth != 1:
                    score -= 5
                if image_type == 0 and (height != 1 or depth != 1):
                    score -= 5
                
                if score > best_score:
                    best_score = score
                    
                    resource_id = self._find_resource_id(pos + 44, chunk_end)
                    
                    best_match = TextureInfo(
                        resource_id=resource_id,
                        image_type=image_type,
                        format=fmt,
                        width=width,
                        height=height,
                        depth=depth,
                        mip_levels=mip_levels,
                        array_layers=array_layers,
                        samples=samples,
                        usage=usage,
                        chunk_offset=chunk_offset
                    )
                    
            except struct.error:
                continue
        
        # 只返回高置信度的匹配
        if best_score >= 20:
            return best_match
        
        return None
    
    # ========================================================================
    # Helper methods
    # ========================================================================
    
    def _validate_extent(self, width: int, height: int, depth: int) -> bool:
        """验证纹理尺寸"""
        if width == 0 or width > 16384:
            return False
        if height == 0 or height > 16384:
            return False
        if depth == 0 or depth > 2048:
            return False
        return True
    
    def _validate_image_params(self, mip_levels: int, array_layers: int, 
                               samples: int, tiling: int, usage: int) -> bool:
        """验证图像参数"""
        if mip_levels == 0 or mip_levels > 15:
            return False
        if array_layers == 0 or array_layers > 2048:
            return False
        if samples not in (1, 2, 4, 8, 16, 32, 64):
            return False
        if tiling > 1:
            return False
        if usage == 0 or usage > 0xFFFF:
            return False
        return True
    
    def _calculate_format_score(self, fmt: int, width: int, height: int, depth: int) -> int:
        """计算格式匹配分数"""
        score = 10
        
        if fmt in VK_FORMAT_NAMES:
            score += 10
        
        if width > 0 and (width & (width - 1)) == 0:
            score += 3
        if height > 0 and (height & (height - 1)) == 0:
            score += 3
        
        return score
    
    def _find_resource_id(self, search_start: int, chunk_end: int) -> int:
        """在指定范围内查找 ResourceId"""
        for skip in range(0, min(32, chunk_end - search_start - 8), 4):
            rid = struct.unpack_from('<Q', self._data, search_start + skip)[0]
            if 0 < rid < (1 << 48):
                return rid
        return 0
    
    def _find_resource_id_from_end(self, chunk_end: int) -> int:
        """从 chunk 尾部向前搜索 ResourceId"""
        for rid_offset in range(-16, -4):
            try:
                rid = struct.unpack_from('<Q', self._data, chunk_end + rid_offset)[0]
                if 0 < rid < 0xFFFFFFFF:
                    return rid
            except:
                pass
        return 0


# ============================================================================
# 便捷函数
# ============================================================================

def extract_vulkan_textures(frame_data: bytes, chunks: List[ChunkInfo]) -> List[TextureInfo]:
    """从 FrameCapture 数据中提取所有 Vulkan 纹理元数据
    
    Args:
        frame_data: FrameCapture section 的原始解压数据
        chunks: 已解析的 Chunk 列表
        
    Returns:
        TextureInfo 列表
    """
    extractor = TextureExtractor(frame_data, chunks)
    return extractor.extract_all()
