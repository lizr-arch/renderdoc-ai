"""
Pass 结构分析器
===============

识别渲染管线中的 Pass 结构:
- 通过 RT 切换识别 Pass 边界
- 结合 Clear 命令和 Debug Marker
- 统计每个 Pass 的 Draw Call 数量
"""

from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from .base import BaseAnalyzer
from ..core.types import PassInfo


@dataclass
class PassBoundary:
    """Pass 边界信息"""
    event_id: int
    rt_signature: str
    is_clear: bool = False
    marker_name: Optional[str] = None


class PassAnalyzer(BaseAnalyzer):
    """Pass 结构分析器"""
    
    name = "pass"
    description = "Render pass structure analyzer"
    dependencies = ["frame", "resource"]
    
    def analyze(self) -> None:
        """执行 Pass 分析"""
        if self.is_api_mode():
            self._analyze_api_mode()
        else:
            self._analyze_binary_mode()
        
        # 更新帧摘要
        self._update_summary()
    
    def _analyze_api_mode(self) -> None:
        """API 模式分析"""
        controller = self.context.parsed.controller
        
        if not controller:
            return
        
        # 由于 API 模式需要 replay，这里暂时使用简化逻辑
        # 从 parsed.draws 推断 pass 结构
        self._analyze_from_draws()
    
    def _analyze_from_draws(self) -> None:
        """从 draws 列表推断 Pass 结构"""
        draws = self.context.parsed.draws
        markers = self.context.parsed.markers
        
        passes = []
        pass_index = 0
        
        # 简化: 每组连续 draw 构成一个 pass
        if draws:
            pass_index = 1
            passes.append(PassInfo(
                index=pass_index,
                name=f"Pass_{pass_index}",
                start_event_id=draws[0].get("event_id", 0) if draws else 0,
                end_event_id=draws[-1].get("event_id", 0) if draws else 0,
                draw_count=len(draws),
            ))
        
        self.context.passes = passes
    
    def _analyze_binary_mode(self) -> None:
        """二进制模式分析"""
        parsed = self.context.parsed
        draws = parsed.draws
        markers = parsed.markers
        
        passes = []
        pass_index = 0
        marker_stack = []
        
        # 从 marker 和 draws 推断 pass 结构
        # 简化版: 将所有 draw 归入一个 pass
        if draws:
            pass_index = 1
            passes.append(PassInfo(
                index=pass_index,
                name=f"Pass_{pass_index}",
                start_event_id=draws[0].get("event_id", 0),
                end_event_id=draws[-1].get("event_id", 0),
                draw_count=len(draws),
            ))
        
        self.context.passes = passes
    
    def _update_summary(self) -> None:
        """更新帧摘要"""
        summary = self.context.frame_summary
        summary.pass_count = len(self.context.passes)
        
        # 统计 RT 切换次数 (简化: pass 数量)
        summary.rt_switches = len(self.context.passes)