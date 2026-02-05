#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Draw Event Parser - Vulkan Draw/Dispatch event extraction

从 FrameCapture 中提取所有 Draw/Dispatch 事件及其上下文信息，
包括 Debug Marker 层级和 Pipeline 绑定状态。

Author: Codex RDC Analyzer Team
License: MIT
"""

import struct
from typing import Optional, List, Dict, Tuple, Set

from .models import ChunkInfo, DrawEventContext, PipelineInfo
from .enums import VulkanChunk


# ============================================================================
# Vulkan Chunk ID 集合
# ============================================================================

# Debug Marker 开始 Chunk IDs
MARKER_BEGIN_CHUNK_IDS: Set[int] = {
    VulkanChunk.vkCmdBeginDebugUtilsLabelEXT,
    VulkanChunk.vkCmdDebugMarkerBeginEXT,
}

# Debug Marker 结束 Chunk IDs
MARKER_END_CHUNK_IDS: Set[int] = {
    VulkanChunk.vkCmdEndDebugUtilsLabelEXT,
    VulkanChunk.vkCmdDebugMarkerEndEXT,
}

# Draw 调用 Chunk IDs
DRAW_CHUNK_IDS: Set[int] = {
    VulkanChunk.vkCmdDraw,
    VulkanChunk.vkCmdDrawIndirect,
    VulkanChunk.vkCmdDrawIndexed,
    VulkanChunk.vkCmdDrawIndexedIndirect,
}

# Dispatch 调用 Chunk IDs
DISPATCH_CHUNK_IDS: Set[int] = {
    VulkanChunk.vkCmdDispatch,
    VulkanChunk.vkCmdDispatchIndirect,
}

# Draw 事件类型映射
DRAW_TYPE_MAP: Dict[int, str] = {
    VulkanChunk.vkCmdDraw: 'draw',
    VulkanChunk.vkCmdDrawIndirect: 'draw_indirect',
    VulkanChunk.vkCmdDrawIndexed: 'draw_indexed',
    VulkanChunk.vkCmdDrawIndexedIndirect: 'draw_indexed_indirect',
}


class DrawEventParser:
    """Vulkan Draw/Dispatch 事件解析器
    
    遍历 FrameCapture 中的所有 Chunk，追踪：
    1. Debug Marker 的 Push/Pop（构建 marker_stack）
    2. vkCmdBindPipeline（追踪当前绑定的 Pipeline）
    3. vkCmdDraw/vkCmdDispatch 等绘制调用
    """
    
    def __init__(self, frame_data: bytes, chunks: List[ChunkInfo]):
        """
        Args:
            frame_data: FrameCapture section 的原始解压数据
            chunks: 已解析的 Chunk 列表
        """
        self._data = frame_data
        self._chunks = chunks
        
        # 缓存 ShaderModule IDs
        self._shader_module_ids: Optional[Dict[int, int]] = None
    
    def extract_all(self) -> Tuple[List[DrawEventContext], Dict[int, PipelineInfo]]:
        """提取所有 Draw/Dispatch 事件及其上下文信息
        
        Returns:
            (draw_events, pipelines) 元组:
            - draw_events: 所有 Draw/Dispatch 事件列表
            - pipelines: ResourceId -> PipelineInfo 映射
        """
        # 第一遍：收集所有 ShaderModule ResourceIds
        shader_module_ids = self._collect_shader_module_ids()
        
        draw_events: List[DrawEventContext] = []
        pipelines: Dict[int, PipelineInfo] = {}
        
        # 状态追踪
        current_marker_stack: List[str] = []
        current_graphics_pipeline: int = 0
        current_compute_pipeline: int = 0
        
        # 第二遍：处理所有事件
        for idx, chunk in enumerate(self._chunks):
            chunk_id = chunk.chunk_id
            
            # 处理 Debug Marker
            if chunk_id in MARKER_BEGIN_CHUNK_IDS:
                marker_name = self._parse_marker_begin(chunk)
                if marker_name:
                    current_marker_stack.append(marker_name)
            
            elif chunk_id in MARKER_END_CHUNK_IDS:
                if current_marker_stack:
                    current_marker_stack.pop()
            
            # 处理 BindPipeline
            elif chunk_id == VulkanChunk.vkCmdBindPipeline:
                bind_point, pipeline_id = self._parse_bind_pipeline(chunk)
                if bind_point == 0:  # VK_PIPELINE_BIND_POINT_GRAPHICS
                    current_graphics_pipeline = pipeline_id
                elif bind_point == 1:  # VK_PIPELINE_BIND_POINT_COMPUTE
                    current_compute_pipeline = pipeline_id
            
            # 处理 Draw 调用
            elif chunk_id in DRAW_CHUNK_IDS:
                event_type = DRAW_TYPE_MAP.get(chunk_id, 'draw')
                event = DrawEventContext(
                    chunk_index=idx,
                    chunk_id=chunk_id,
                    event_type=event_type,
                    pipeline_resource_id=current_graphics_pipeline,
                    marker_stack=list(current_marker_stack)
                )
                draw_events.append(event)
            
            # 处理 Dispatch 调用
            elif chunk_id in DISPATCH_CHUNK_IDS:
                event_type = 'dispatch' if chunk_id == VulkanChunk.vkCmdDispatch else 'dispatch_indirect'
                event = DrawEventContext(
                    chunk_index=idx,
                    chunk_id=chunk_id,
                    event_type=event_type,
                    pipeline_resource_id=current_compute_pipeline,
                    marker_stack=list(current_marker_stack)
                )
                draw_events.append(event)
            
            # 处理 Pipeline 创建
            elif chunk_id == VulkanChunk.vkCreateGraphicsPipelines:
                pipeline_info = self._parse_graphics_pipeline(chunk, shader_module_ids)
                if pipeline_info:
                    pipelines[pipeline_info.resource_id] = pipeline_info
            
            elif chunk_id == VulkanChunk.vkCreateComputePipelines:
                pipeline_info = self._parse_compute_pipeline(chunk, shader_module_ids)
                if pipeline_info:
                    pipelines[pipeline_info.resource_id] = pipeline_info
        
        return draw_events, pipelines
    
    def _collect_shader_module_ids(self) -> Dict[int, int]:
        """收集所有 ShaderModule ResourceIds
        
        Returns:
            resource_id -> chunk_index 映射
        """
        if self._shader_module_ids is not None:
            return self._shader_module_ids
        
        shader_module_ids: Dict[int, int] = {}
        for idx, chunk in enumerate(self._chunks):
            if chunk.chunk_id == VulkanChunk.vkCreateShaderModule:
                chunk_end = chunk.data_offset + chunk.length
                if chunk.length >= 8:
                    rid = struct.unpack_from('<Q', self._data, chunk_end - 8)[0]
                    if 0 < rid < (1 << 48):
                        shader_module_ids[rid] = idx
        
        self._shader_module_ids = shader_module_ids
        return shader_module_ids
    
    def _parse_marker_begin(self, chunk: ChunkInfo) -> Optional[str]:
        """解析 vkCmdBeginDebugUtilsLabelEXT，提取 marker 名称
        
        序列化格式:
        1. commandBuffer: ResourceId (8 bytes)
        2. Label.sType: uint32 (4 bytes)
        3. Label.pNext: 通常为 NULL
        4. Label.pLabelName: 字符串（int32 长度 + 字符数据）
        5. Label.color[4]: float[4] (16 bytes)
        """
        try:
            chunk_end = chunk.data_offset + chunk.length
            
            if chunk.length < 12:
                return None
            
            # 搜索字符串长度字段（偏移 8-40 字节内）
            for str_offset in range(8, min(40, chunk.length - 4)):
                pos = chunk.data_offset + str_offset
                strlen = struct.unpack_from('<i', self._data, pos)[0]
                
                # 合理的字符串长度: 1-256
                if 1 <= strlen <= 256 and pos + 4 + strlen <= chunk_end:
                    try:
                        label_bytes = self._data[pos + 4:pos + 4 + strlen]
                        label = label_bytes.decode('utf-8', errors='replace')
                        # 验证是否像是有意义的 marker 名称
                        if label and any(c.isalnum() for c in label):
                            return label
                    except:
                        continue
            
            return None
            
        except Exception:
            return None
    
    def _parse_bind_pipeline(self, chunk: ChunkInfo) -> Tuple[int, int]:
        """解析 vkCmdBindPipeline，提取 bind point 和 pipeline ResourceId
        
        序列化格式:
        1. commandBuffer: ResourceId (8 bytes)
        2. pipelineBindPoint: VkPipelineBindPoint (4 bytes, enum)
        3. pipeline: ResourceId (8 bytes)
        
        Returns:
            (bind_point, pipeline_resource_id)
            bind_point: 0=Graphics, 1=Compute, 2=RayTracing
        """
        try:
            offset = chunk.data_offset
            
            if chunk.length < 20:
                return (-1, 0)
            
            bind_point = struct.unpack_from('<I', self._data, offset + 8)[0]
            pipeline_id = struct.unpack_from('<Q', self._data, offset + 12)[0]
            
            return (bind_point, pipeline_id)
            
        except Exception:
            return (-1, 0)
    
    def _parse_graphics_pipeline(self, chunk: ChunkInfo, 
                                 known_shader_ids: Dict[int, int]) -> Optional[PipelineInfo]:
        """解析 vkCreateGraphicsPipelines，提取 Pipeline 和 Shader 关联
        
        使用启发式搜索：在 Pipeline chunk 中搜索已知的 ShaderModule ResourceIDs。
        """
        try:
            offset = chunk.data_offset
            if chunk.length < 16:
                return None
            
            chunk_end = offset + chunk.length
            pipeline_id = struct.unpack_from('<Q', self._data, chunk_end - 8)[0]
            
            if pipeline_id == 0 or pipeline_id > (1 << 48):
                return None
            
            # 启发式搜索
            shader_stages = self._search_shader_modules_in_chunk(
                chunk, known_shader_ids, is_graphics=True
            )
            
            return PipelineInfo(
                resource_id=pipeline_id,
                pipeline_type='graphics',
                shader_stages=shader_stages
            )
            
        except Exception:
            return None
    
    def _parse_compute_pipeline(self, chunk: ChunkInfo,
                                known_shader_ids: Dict[int, int]) -> Optional[PipelineInfo]:
        """解析 vkCreateComputePipelines，提取 Pipeline 和 Compute Shader 关联"""
        try:
            offset = chunk.data_offset
            if chunk.length < 16:
                return None
            
            chunk_end = offset + chunk.length
            pipeline_id = struct.unpack_from('<Q', self._data, chunk_end - 8)[0]
            
            if pipeline_id == 0 or pipeline_id > (1 << 48):
                return None
            
            # 启发式搜索
            shader_stages = self._search_shader_modules_in_chunk(
                chunk, known_shader_ids, is_graphics=False
            )
            
            return PipelineInfo(
                resource_id=pipeline_id,
                pipeline_type='compute',
                shader_stages=shader_stages
            )
            
        except Exception:
            return None
    
    def _search_shader_modules_in_chunk(self, chunk: ChunkInfo,
                                        known_shader_ids: Dict[int, int],
                                        is_graphics: bool) -> Dict[str, int]:
        """在 Pipeline chunk 中搜索已知的 ShaderModule IDs
        
        这是一个启发式方法：由于 Vulkan 序列化格式复杂且包含 pNext 链，
        直接按偏移解析很容易出错。我们改为：
        1. 遍历 chunk 中所有可能的 8 字节对齐位置
        2. 检查该位置的 uint64 是否匹配已知的 ShaderModule ID
        3. 根据找到 ID 的顺序推断 Shader Stage
        """
        shader_stages: Dict[str, int] = {}
        found_modules: List[Tuple[int, int]] = []  # (offset, module_id)
        
        # 扫描 chunk 中所有 8 字节对齐位置
        start = chunk.data_offset
        end = start + chunk.length - 8
        
        for pos in range(start, end, 8):
            try:
                value = struct.unpack_from('<Q', self._data, pos)[0]
                if value in known_shader_ids:
                    found_modules.append((pos, value))
            except Exception:
                continue
        
        if not found_modules:
            return shader_stages
        
        # 去重
        seen_modules: Set[int] = set()
        unique_modules: List[Tuple[int, int]] = []
        for offset, mid in found_modules:
            if mid not in seen_modules:
                seen_modules.add(mid)
                unique_modules.append((offset, mid))
        
        if is_graphics:
            # Graphics Pipeline 通常按 VS, TCS, TES, GS, FS 顺序
            if len(unique_modules) == 1:
                shader_stages['VS'] = unique_modules[0][1]
            elif len(unique_modules) == 2:
                # 最常见：VS + FS
                shader_stages['VS'] = unique_modules[0][1]
                shader_stages['FS'] = unique_modules[1][1]
            else:
                # 多个 stages
                stage_order = ['VS', 'TCS', 'TES', 'GS', 'FS']
                for i, (_, mid) in enumerate(unique_modules):
                    if i < len(stage_order):
                        shader_stages[stage_order[i]] = mid
                    else:
                        shader_stages[f'STAGE{i}'] = mid
        else:
            # Compute Pipeline 只有一个 CS
            if unique_modules:
                shader_stages['CS'] = unique_modules[0][1]
        
        return shader_stages


# ============================================================================
# 便捷函数
# ============================================================================

def extract_draw_events(frame_data: bytes, chunks: List[ChunkInfo]) -> Tuple[List[DrawEventContext], Dict[int, PipelineInfo]]:
    """从 FrameCapture 数据中提取所有 Draw/Dispatch 事件及上下文
    
    Args:
        frame_data: FrameCapture section 的原始解压数据
        chunks: 已解析的 Chunk 列表
        
    Returns:
        (draw_events, pipelines) 元组
    """
    parser = DrawEventParser(frame_data, chunks)
    return parser.extract_all()
