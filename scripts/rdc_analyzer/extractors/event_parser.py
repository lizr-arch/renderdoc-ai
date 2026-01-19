"""
事件解析器
==========

解析 RenderDoc 事件列表，构建层级化的调用树结构

主要功能:
1. 从 ReplayController 获取事件列表
2. 解析标记层级（Push/Pop Marker）
3. 分类事件类型
4. 构建完整的事件树
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable

from .base import EventInfo, EventType


logger = logging.getLogger(__name__)


# =============================================================================
# API 调用名称到事件类型的映射
# =============================================================================

# D3D11 API 调用映射
D3D11_EVENT_MAPPING: Dict[str, EventType] = {
    # Draw 调用
    "Draw": EventType.DRAW,
    "DrawIndexed": EventType.DRAW_INDEXED,
    "DrawInstanced": EventType.DRAW_INSTANCED,
    "DrawIndexedInstanced": EventType.DRAW_INDEXED_INSTANCED,
    "DrawInstancedIndirect": EventType.DRAW_INDIRECT,
    "DrawIndexedInstancedIndirect": EventType.DRAW_INDEXED_INDIRECT,
    "DrawAuto": EventType.DRAW,
    
    # Compute
    "Dispatch": EventType.DISPATCH,
    "DispatchIndirect": EventType.DISPATCH_INDIRECT,
    
    # Clear
    "ClearRenderTargetView": EventType.CLEAR_RTV,
    "ClearDepthStencilView": EventType.CLEAR_DSV,
    "ClearUnorderedAccessViewUint": EventType.CLEAR_UAV,
    "ClearUnorderedAccessViewFloat": EventType.CLEAR_UAV,
    "ClearView": EventType.CLEAR_RTV,
    
    # Copy
    "CopyResource": EventType.COPY_TEXTURE,
    "CopySubresourceRegion": EventType.COPY_TEXTURE,
    "CopyStructureCount": EventType.COPY_BUFFER,
    "UpdateSubresource": EventType.UPDATE_BUFFER,
    "CopyBuffer": EventType.COPY_BUFFER,
    
    # Resolve
    "ResolveSubresource": EventType.RESOLVE,
    
    # Map/Unmap
    "Map": EventType.MAP,
    "Unmap": EventType.UNMAP,
    
    # Present
    "Present": EventType.PRESENT,
    "Present1": EventType.PRESENT,
    
    # Markers
    "PushMarker": EventType.MARKER_PUSH,
    "PopMarker": EventType.MARKER_POP,
    "SetMarker": EventType.MARKER_PUSH,  # 单点标记视为 Push
}

# D3D12 API 调用映射
D3D12_EVENT_MAPPING: Dict[str, EventType] = {
    # Draw 调用
    "DrawInstanced": EventType.DRAW_INSTANCED,
    "DrawIndexedInstanced": EventType.DRAW_INDEXED_INSTANCED,
    "ExecuteIndirect": EventType.DRAW_INDIRECT,
    
    # Compute
    "Dispatch": EventType.DISPATCH,
    
    # Clear
    "ClearRenderTargetView": EventType.CLEAR_RTV,
    "ClearDepthStencilView": EventType.CLEAR_DSV,
    "ClearUnorderedAccessViewUint": EventType.CLEAR_UAV,
    "ClearUnorderedAccessViewFloat": EventType.CLEAR_UAV,
    
    # Copy
    "CopyResource": EventType.COPY_TEXTURE,
    "CopyBufferRegion": EventType.COPY_BUFFER_REGION,
    "CopyTextureRegion": EventType.COPY_TEXTURE,
    
    # Resolve
    "ResolveSubresource": EventType.RESOLVE,
    
    # Barriers
    "ResourceBarrier": EventType.BARRIER,
    
    # Present
    "Present": EventType.PRESENT,
    
    # Markers
    "BeginEvent": EventType.MARKER_PUSH,
    "EndEvent": EventType.MARKER_POP,
    "SetMarker": EventType.MARKER_PUSH,
}

# Vulkan API 调用映射
VULKAN_EVENT_MAPPING: Dict[str, EventType] = {
    # Draw 调用
    "vkCmdDraw": EventType.DRAW,
    "vkCmdDrawIndexed": EventType.DRAW_INDEXED,
    "vkCmdDrawIndirect": EventType.DRAW_INDIRECT,
    "vkCmdDrawIndexedIndirect": EventType.DRAW_INDEXED_INDIRECT,
    "vkCmdDrawIndirectCount": EventType.DRAW_INDIRECT_COUNT,
    "vkCmdDrawIndexedIndirectCount": EventType.DRAW_INDIRECT_COUNT,
    
    # Compute
    "vkCmdDispatch": EventType.DISPATCH,
    "vkCmdDispatchIndirect": EventType.DISPATCH_INDIRECT,
    
    # Clear
    "vkCmdClearColorImage": EventType.CLEAR_RTV,
    "vkCmdClearDepthStencilImage": EventType.CLEAR_DSV,
    "vkCmdClearAttachments": EventType.CLEAR_RTV,
    
    # Copy
    "vkCmdCopyBuffer": EventType.COPY_BUFFER,
    "vkCmdCopyImage": EventType.COPY_TEXTURE,
    "vkCmdCopyBufferToImage": EventType.COPY_TEXTURE,
    "vkCmdCopyImageToBuffer": EventType.COPY_TEXTURE,
    "vkCmdBlitImage": EventType.COPY_TEXTURE,
    "vkCmdUpdateBuffer": EventType.UPDATE_BUFFER,
    
    # Resolve
    "vkCmdResolveImage": EventType.RESOLVE,
    
    # Barriers
    "vkCmdPipelineBarrier": EventType.BARRIER,
    "vkCmdPipelineBarrier2": EventType.BARRIER,
    
    # Markers
    "vkCmdBeginDebugUtilsLabelEXT": EventType.MARKER_PUSH,
    "vkCmdEndDebugUtilsLabelEXT": EventType.MARKER_POP,
    "vkCmdInsertDebugUtilsLabelEXT": EventType.MARKER_PUSH,
}

# OpenGL API 调用映射
OPENGL_EVENT_MAPPING: Dict[str, EventType] = {
    # Draw 调用
    "glDrawArrays": EventType.DRAW,
    "glDrawElements": EventType.DRAW_INDEXED,
    "glDrawArraysInstanced": EventType.DRAW_INSTANCED,
    "glDrawElementsInstanced": EventType.DRAW_INDEXED_INSTANCED,
    "glDrawArraysIndirect": EventType.DRAW_INDIRECT,
    "glDrawElementsIndirect": EventType.DRAW_INDEXED_INDIRECT,
    "glMultiDrawArrays": EventType.DRAW,
    "glMultiDrawElements": EventType.DRAW_INDEXED,
    
    # Compute
    "glDispatchCompute": EventType.DISPATCH,
    "glDispatchComputeIndirect": EventType.DISPATCH_INDIRECT,
    
    # Clear
    "glClear": EventType.CLEAR_RTV,
    "glClearBufferfv": EventType.CLEAR_RTV,
    "glClearBufferiv": EventType.CLEAR_RTV,
    "glClearBufferfi": EventType.CLEAR_DSV,
    
    # Copy
    "glCopyTexImage2D": EventType.COPY_TEXTURE,
    "glCopyTexSubImage2D": EventType.COPY_TEXTURE,
    "glCopyBufferSubData": EventType.COPY_BUFFER,
    "glBlitFramebuffer": EventType.COPY_TEXTURE,
    
    # Present
    "SwapBuffers": EventType.PRESENT,
    "eglSwapBuffers": EventType.PRESENT,
    
    # Markers
    "glPushDebugGroup": EventType.MARKER_PUSH,
    "glPopDebugGroup": EventType.MARKER_POP,
}

# 合并所有映射
ALL_EVENT_MAPPINGS: Dict[str, Dict[str, EventType]] = {
    "D3D11": D3D11_EVENT_MAPPING,
    "D3D12": D3D12_EVENT_MAPPING,
    "Vulkan": VULKAN_EVENT_MAPPING,
    "OpenGL": OPENGL_EVENT_MAPPING,
}


# =============================================================================
# 事件解析器
# =============================================================================

class EventParser:
    """
    RenderDoc 事件解析器
    
    将 RenderDoc 的扁平事件列表转换为层级化的调用树
    """
    
    def __init__(self, api: str = "D3D11"):
        """
        初始化解析器
        
        Args:
            api: 图形 API 名称 ("D3D11", "D3D12", "Vulkan", "OpenGL")
        """
        self.api = api
        self.event_mapping = ALL_EVENT_MAPPINGS.get(api, D3D11_EVENT_MAPPING)
        
        # 解析状态
        self._marker_stack: List[str] = []
        self._parent_stack: List[EventInfo] = []
        self._depth: int = 0
    
    def parse_events(self, raw_events: List[Any]) -> List[EventInfo]:
        """
        解析 RenderDoc 事件列表
        
        Args:
            raw_events: 从 ReplayController 获取的原始事件列表
                       每个事件应有 eventId, name, children 等属性
        
        Returns:
            层级化的 EventInfo 列表（根级事件）
        """
        # 重置状态
        self._marker_stack = []
        self._parent_stack = []
        self._depth = 0
        
        root_events: List[EventInfo] = []
        
        for raw_event in raw_events:
            parsed = self._parse_single_event(raw_event)
            if parsed:
                root_events.append(parsed)
        
        return root_events
    
    def parse_from_controller(self, controller: Any) -> List[EventInfo]:
        """
        从 ReplayController 解析事件
        
        Args:
            controller: RenderDoc ReplayController 实例
            
        Returns:
            层级化的 EventInfo 列表
        """
        # 获取根动作（DrawcallDescription 树的根）
        root_actions = controller.GetRootActions()
        
        # 重置状态
        self._marker_stack = []
        self._parent_stack = []
        self._depth = 0
        
        root_events: List[EventInfo] = []
        
        for action in root_actions:
            parsed = self._parse_action_recursive(action, parent_id=None, depth=0)
            if parsed:
                root_events.extend(parsed)
        
        return root_events
    
    def _parse_single_event(self, raw_event: Any) -> Optional[EventInfo]:
        """解析单个原始事件"""
        # 提取基本信息
        event_id = getattr(raw_event, 'eventId', 0)
        name = getattr(raw_event, 'name', str(raw_event))
        
        # 确定事件类型
        event_type = self._classify_event(name)
        
        # 构建标记路径
        marker_path = "/".join(self._marker_stack) if self._marker_stack else ""
        
        # 处理标记 Push/Pop
        if event_type == EventType.MARKER_PUSH:
            # 提取标记名称
            marker_name = self._extract_marker_name(name)
            self._marker_stack.append(marker_name)
            self._depth += 1
        elif event_type == EventType.MARKER_POP:
            if self._marker_stack:
                self._marker_stack.pop()
            if self._depth > 0:
                self._depth -= 1
        
        # 创建 EventInfo
        event_info = EventInfo(
            event_id=event_id,
            name=name,
            event_type=event_type,
            depth=self._depth,
            marker_path=marker_path,
        )
        
        # 递归解析子事件
        children = getattr(raw_event, 'children', [])
        if children:
            for child in children:
                child_event = self._parse_single_event(child)
                if child_event:
                    child_event.parent_id = event_id
                    event_info.children.append(child_event)
        
        return event_info
    
    def _parse_action_recursive(
        self, 
        action: Any, 
        parent_id: Optional[int], 
        depth: int
    ) -> List[EventInfo]:
        """
        递归解析 RenderDoc DrawcallDescription
        
        Args:
            action: DrawcallDescription 对象
            parent_id: 父事件 ID
            depth: 当前深度
            
        Returns:
            解析出的 EventInfo 列表
        """
        events: List[EventInfo] = []
        
        # 获取事件基本信息
        event_id = action.eventId
        name = action.name
        
        # 分类事件
        event_type = self._classify_event(name)
        
        # 检查是否有 flags 来更精确判断
        if hasattr(action, 'flags'):
            flags = action.flags
            # RenderDoc 的 ActionFlags 枚举
            if hasattr(flags, 'Drawcall') and flags.Drawcall:
                if hasattr(flags, 'Indexed') and flags.Indexed:
                    if hasattr(flags, 'Instanced') and flags.Instanced:
                        event_type = EventType.DRAW_INDEXED_INSTANCED
                    else:
                        event_type = EventType.DRAW_INDEXED
                elif hasattr(flags, 'Instanced') and flags.Instanced:
                    event_type = EventType.DRAW_INSTANCED
                elif hasattr(flags, 'Indirect') and flags.Indirect:
                    event_type = EventType.DRAW_INDIRECT
                else:
                    event_type = EventType.DRAW
            elif hasattr(flags, 'Dispatch') and flags.Dispatch:
                event_type = EventType.DISPATCH
            elif hasattr(flags, 'Clear') and flags.Clear:
                if "Depth" in name or "DSV" in name:
                    event_type = EventType.CLEAR_DSV
                elif "UAV" in name:
                    event_type = EventType.CLEAR_UAV
                else:
                    event_type = EventType.CLEAR_RTV
            elif hasattr(flags, 'Copy') and flags.Copy:
                if "Buffer" in name:
                    event_type = EventType.COPY_BUFFER
                else:
                    event_type = EventType.COPY_TEXTURE
            elif hasattr(flags, 'Resolve') and flags.Resolve:
                event_type = EventType.RESOLVE
            elif hasattr(flags, 'Present') and flags.Present:
                event_type = EventType.PRESENT
            elif hasattr(flags, 'PushMarker') and flags.PushMarker:
                event_type = EventType.MARKER_PUSH
            elif hasattr(flags, 'PopMarker') and flags.PopMarker:
                event_type = EventType.MARKER_POP
        
        # 构建标记路径
        if event_type == EventType.MARKER_PUSH:
            marker_name = self._extract_marker_name(name)
            self._marker_stack.append(marker_name)
        
        marker_path = "/".join(self._marker_stack) if self._marker_stack else ""
        
        # 提取绘制参数
        draw_params = self._extract_draw_params(action)
        
        # 创建事件
        event_info = EventInfo(
            event_id=event_id,
            name=name,
            event_type=event_type,
            parent_id=parent_id,
            depth=depth,
            marker_path=marker_path,
            draw_params=draw_params,
        )
        
        events.append(event_info)
        
        # 递归处理子事件
        children = getattr(action, 'children', [])
        for child in children:
            child_events = self._parse_action_recursive(
                child, 
                parent_id=event_id, 
                depth=depth + 1
            )
            event_info.children.extend(child_events)
            events.extend(child_events)
        
        # Pop 标记
        if event_type == EventType.MARKER_PUSH and self._marker_stack:
            # 在处理完所有子事件后 pop
            pass  # 实际上 RenderDoc 的树结构已经处理了层级
        
        return [event_info]  # 只返回当前事件，子事件已添加到 children
    
    def _classify_event(self, name: str) -> EventType:
        """
        根据名称分类事件
        
        Args:
            name: 事件名称
            
        Returns:
            EventType 枚举值
        """
        # 首先尝试精确匹配
        for api_name, event_type in self.event_mapping.items():
            if name.startswith(api_name):
                return event_type
        
        # 模糊匹配
        name_lower = name.lower()
        
        if "draw" in name_lower:
            if "indexed" in name_lower and "instanced" in name_lower:
                return EventType.DRAW_INDEXED_INSTANCED
            elif "indexed" in name_lower:
                return EventType.DRAW_INDEXED
            elif "instanced" in name_lower:
                return EventType.DRAW_INSTANCED
            elif "indirect" in name_lower:
                return EventType.DRAW_INDIRECT
            else:
                return EventType.DRAW
        
        if "dispatch" in name_lower:
            if "indirect" in name_lower:
                return EventType.DISPATCH_INDIRECT
            return EventType.DISPATCH
        
        if "clear" in name_lower:
            if "depth" in name_lower or "dsv" in name_lower:
                return EventType.CLEAR_DSV
            elif "uav" in name_lower:
                return EventType.CLEAR_UAV
            else:
                return EventType.CLEAR_RTV
        
        if "copy" in name_lower:
            if "buffer" in name_lower:
                return EventType.COPY_BUFFER
            return EventType.COPY_TEXTURE
        
        if "resolve" in name_lower:
            return EventType.RESOLVE
        
        if "present" in name_lower or "swap" in name_lower:
            return EventType.PRESENT
        
        if "barrier" in name_lower:
            return EventType.BARRIER
        
        if "beginmarker" in name_lower or "pushmarker" in name_lower or "beginevent" in name_lower:
            return EventType.MARKER_PUSH
        
        if "endmarker" in name_lower or "popmarker" in name_lower or "endevent" in name_lower:
            return EventType.MARKER_POP
        
        return EventType.UNKNOWN
    
    def _extract_marker_name(self, name: str) -> str:
        """
        从事件名称中提取标记名
        
        例如: "PushMarker(Shadow)" -> "Shadow"
              "BeginEvent: MainPass" -> "MainPass"
        """
        # 尝试括号内容
        match = re.search(r'\(([^)]+)\)', name)
        if match:
            return match.group(1).strip()
        
        # 尝试冒号后内容
        if ':' in name:
            return name.split(':', 1)[1].strip()
        
        # 尝试空格后内容
        parts = name.split(' ', 1)
        if len(parts) > 1:
            return parts[1].strip()
        
        return name
    
    def _extract_draw_params(self, action: Any) -> Dict[str, Any]:
        """
        从 DrawcallDescription 提取绘制参数
        
        Args:
            action: DrawcallDescription 对象
            
        Returns:
            包含绘制参数的字典
        """
        params = {}
        
        # 顶点/索引数量
        if hasattr(action, 'numIndices'):
            params['index_count'] = action.numIndices
        if hasattr(action, 'numInstances'):
            params['instance_count'] = max(1, action.numInstances)
        if hasattr(action, 'vertexOffset'):
            params['base_vertex'] = action.vertexOffset
        if hasattr(action, 'indexOffset'):
            params['start_index'] = action.indexOffset
        if hasattr(action, 'instanceOffset'):
            params['start_instance'] = action.instanceOffset
        
        # 如果没有索引，使用 numIndices 作为顶点数
        if 'index_count' in params and 'vertex_count' not in params:
            # 判断是否是 indexed draw
            is_indexed = False
            if hasattr(action, 'flags'):
                flags = action.flags
                if hasattr(flags, 'Indexed') and flags.Indexed:
                    is_indexed = True
            
            if not is_indexed:
                params['vertex_count'] = params.get('index_count', 0)
        
        # Dispatch 参数
        if hasattr(action, 'dispatchDimension'):
            dim = action.dispatchDimension
            if hasattr(dim, '__len__') and len(dim) >= 3:
                params['thread_group_x'] = dim[0]
                params['thread_group_y'] = dim[1]
                params['thread_group_z'] = dim[2]
        
        return params


# =============================================================================
# 便捷函数
# =============================================================================

def parse_events_from_controller(controller: Any, api: str = "D3D11") -> List[EventInfo]:
    """
    便捷函数：从 ReplayController 解析事件
    
    Args:
        controller: RenderDoc ReplayController 实例
        api: 图形 API 名称
        
    Returns:
        层级化的 EventInfo 列表
    """
    parser = EventParser(api)
    return parser.parse_from_controller(controller)


def flatten_events(events: List[EventInfo]) -> List[EventInfo]:
    """
    将事件树展平为列表
    
    Args:
        events: 层级化的事件列表
        
    Returns:
        展平的事件列表（深度优先）
    """
    result = []
    for event in events:
        result.append(event)
        result.extend(flatten_events(event.children))
    return result


def filter_actionable_events(events: List[EventInfo]) -> List[EventInfo]:
    """
    过滤出可操作的事件（Draw/Dispatch/Clear/Copy）
    
    Args:
        events: 事件列表
        
    Returns:
        只包含可操作事件的列表
    """
    flat = flatten_events(events)
    return [e for e in flat if e.is_actionable()]


def get_events_by_marker(events: List[EventInfo], marker: str) -> List[EventInfo]:
    """
    按标记路径过滤事件
    
    Args:
        events: 事件列表
        marker: 要匹配的标记路径（部分匹配）
        
    Returns:
        匹配的事件列表
    """
    flat = flatten_events(events)
    return [e for e in flat if marker in e.marker_path]


def count_events_by_type(events: List[EventInfo]) -> Dict[EventType, int]:
    """
    按类型统计事件数量
    
    Args:
        events: 事件列表
        
    Returns:
        类型 -> 数量的字典
    """
    flat = flatten_events(events)
    counts: Dict[EventType, int] = {}
    for event in flat:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    return counts
