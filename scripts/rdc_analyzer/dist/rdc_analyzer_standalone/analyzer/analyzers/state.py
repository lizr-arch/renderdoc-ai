"""
状态切换分析器
==============

分析渲染状态切换:
- Shader 切换
- Blend State 切换
- Depth State 切换
- Rasterizer State 切换
- 冗余状态设置检测
"""

from typing import Any, Dict, List, Optional, Set
from .base import BaseAnalyzer


class StateAnalyzer(BaseAnalyzer):
    """状态切换分析器"""
    
    name = "state"
    description = "State change analyzer"
    dependencies = ["frame"]
    
    def analyze(self) -> None:
        """执行状态分析"""
        if self.is_api_mode():
            self._analyze_api_mode()
        else:
            self._analyze_binary_mode()
    
    def _analyze_api_mode(self) -> None:
        """API 模式分析 (简化版)"""
        controller = self.context.parsed.controller
        
        if not controller:
            return
        
        # API 模式需要详细的 replay 支持
        # 暂时使用简化估算
        draws = self.context.parsed.draws
        summary = self.context.frame_summary
        
        # 假设每个 draw 可能切换一次状态
        summary.shader_changes = len(draws) // 2
        summary.blend_state_changes = len(draws) // 5
        summary.depth_state_changes = len(draws) // 5
        summary.rasterizer_changes = len(draws) // 10
    
    def _analyze_binary_mode(self) -> None:
        """二进制模式分析"""
        # 从 chunks 统计状态设置
        chunks = self.context.parsed.chunks
        summary = self.context.frame_summary
        
        # 统计各类 Chunk 数量
        chunk_counts: Dict[str, int] = {}
        for chunk in chunks:
            name = chunk.get("type_name", "")
            chunk_counts[name] = chunk_counts.get(name, 0) + 1
        
        # 状态设置 Chunk 统计
        vs_sets = chunk_counts.get("VSSetShader", 0)
        ps_sets = chunk_counts.get("PSSetShader", 0)
        blend_sets = chunk_counts.get("OMSetBlendState", 0)
        depth_sets = chunk_counts.get("OMSetDepthStencilState", 0)
        raster_sets = chunk_counts.get("RSSetState", 0)
        
        # 更新摘要
        summary.shader_changes = vs_sets + ps_sets
        summary.blend_state_changes = blend_sets
        summary.depth_state_changes = depth_sets
        summary.rasterizer_changes = raster_sets
        
        # 计算冗余率 (简化估算)
        draw_count = summary.draw_call_count
        if draw_count > 0:
            total_state_sets = vs_sets + ps_sets + blend_sets + depth_sets + raster_sets
            # 假设每个 Draw 只需要一次状态设置
            expected_sets = draw_count * 5
            if total_state_sets > expected_sets:
                redundant = total_state_sets - expected_sets
                summary.redundant_state_sets = redundant
    
    def _is_draw_action(self, action: Any, flags: int) -> bool:
        """检查是否为 Draw 操作"""
        try:
            import renderdoc as rd
            return bool(flags & rd.ActionFlags.Drawcall)
        except ImportError:
            return False
    
    def _get_shader_id(self, state: Any, stage: str) -> Optional[int]:
        """获取 Shader ID"""
        try:
            shader = None
            if stage == "VS":
                shader = state.GetShader(0)  # Vertex
            elif stage == "PS":
                shader = state.GetShader(4)  # Pixel
            
            if shader:
                return int(shader.resourceId)
        except Exception:
            pass
        return None
    
    def _get_blend_state(self, state: Any) -> Optional[str]:
        """获取 Blend State 签名"""
        try:
            om = state.GetOutputMerger()
            blend = om.blendState
            # 简化: 用资源 ID 作为签名
            return str(blend.resourceId) if blend else None
        except Exception:
            return None
    
    def _get_depth_state(self, state: Any) -> Optional[str]:
        """获取 Depth State 签名"""
        try:
            om = state.GetOutputMerger()
            depth = om.depthStencilState
            return str(depth.resourceId) if depth else None
        except Exception:
            return None
    
    def _get_raster_state(self, state: Any) -> Optional[str]:
        """获取 Rasterizer State 签名"""
        try:
            rs = state.GetRasterizer()
            raster = rs.state
            return str(raster.resourceId) if raster else None
        except Exception:
            return None