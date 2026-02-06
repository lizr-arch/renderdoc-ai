"""
帧级分析器
==========

分析帧级统计数据:
- Draw Call 数量
- 顶点/三角形/索引数
- Dispatch 数量
- 实例化/间接绘制统计
"""

from typing import Any, Dict, List, Optional
from .base import BaseAnalyzer
from ..core.types import DrawCallInfo


class FrameAnalyzer(BaseAnalyzer):
    """帧级分析器"""
    
    name = "frame"
    description = "Frame-level statistics analyzer"
    dependencies = []
    
    def analyze(self) -> None:
        """执行帧级分析"""
        if self.is_api_mode():
            self._analyze_api_mode()
        else:
            self._analyze_binary_mode()
    
    def _analyze_api_mode(self) -> None:
        """API 模式分析 (简化版)"""
        parsed = self.context.parsed
        summary = self.context.frame_summary
        
        draws = parsed.draws
        dispatches = parsed.dispatches
        
        total_vertices = 0
        draw_calls = []
        
        for draw in draws:
            vertex_count = draw.get("vertex_count", 0)
            total_vertices += vertex_count
            
            draw_info = DrawCallInfo(
                event_id=draw.get("event_id", 0),
                type=draw.get("type", "Draw"),
                vertex_count=vertex_count,
                index_count=draw.get("index_count", 0),
                instance_count=draw.get("instance_count", 1),
            )
            draw_calls.append(draw_info)
        
        # 更新摘要
        summary.draw_call_count = len(draw_calls)
        summary.dispatch_count = len(dispatches)
        summary.vertex_count = total_vertices
        summary.primitive_count = total_vertices // 3  # 假设三角形列表
        
        # 记录 Draw Call 列表
        self.context.draw_calls = draw_calls
    
    def _analyze_binary_mode(self) -> None:
        """二进制模式分析"""
        parsed = self.context.parsed
        summary = self.context.frame_summary
        
        draws = parsed.draws
        dispatches = parsed.dispatches
        
        total_vertices = 0
        draw_calls = []
        
        for draw in draws:
            vertex_count = draw.get("vertex_count", 0)
            total_vertices += vertex_count
            
            draw_info = DrawCallInfo(
                event_id=draw.get("event_id", 0),
                type=draw.get("type", "Draw"),
                vertex_count=vertex_count,
                index_count=draw.get("index_count", 0),
                instance_count=draw.get("instance_count", 1),
            )
            draw_calls.append(draw_info)
        
        # 更新摘要
        summary.draw_call_count = len(draw_calls)
        summary.dispatch_count = len(dispatches)
        summary.vertex_count = total_vertices
        summary.primitive_count = total_vertices // 3
        
        # 记录 Draw Call 列表
        self.context.draw_calls = draw_calls
    
    def _is_draw_action(self, action: Any, flags: int) -> bool:
        """检查是否为 Draw 操作"""
        # RenderDoc ActionFlags
        # Drawcall = 0x1, ...
        try:
            import renderdoc as rd
            return bool(flags & rd.ActionFlags.Drawcall)
        except ImportError:
            # 回退到名称检测
            name = str(getattr(action, 'customName', ''))
            return 'Draw' in name
    
    def _is_dispatch_action(self, action: Any, flags: int) -> bool:
        """检查是否为 Dispatch 操作"""
        try:
            import renderdoc as rd
            return bool(flags & rd.ActionFlags.Dispatch)
        except ImportError:
            name = str(getattr(action, 'customName', ''))
            return 'Dispatch' in name
    
    def _is_instanced_action(self, action: Any, flags: int) -> bool:
        """检查是否为实例化绘制"""
        try:
            import renderdoc as rd
            return bool(flags & rd.ActionFlags.Instanced)
        except ImportError:
            return getattr(action, 'numInstances', 1) > 1
    
    def _is_indirect_action(self, action: Any, flags: int) -> bool:
        """检查是否为间接绘制"""
        try:
            import renderdoc as rd
            return bool(flags & rd.ActionFlags.Indirect)
        except ImportError:
            name = str(getattr(action, 'customName', ''))
            return 'Indirect' in name