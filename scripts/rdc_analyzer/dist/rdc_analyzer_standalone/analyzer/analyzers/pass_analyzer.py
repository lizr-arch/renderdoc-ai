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
        
        # XML 模式优先使用 renderPass 数据
        if self.context.parsed.render_passes:
            self._analyze_from_render_passes()
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
    
    def _analyze_from_render_passes(self) -> None:
        """从 XML renderPasses 构建 PassInfo"""
        parsed = self.context.parsed
        render_passes = parsed.render_passes or []
        markers = parsed.markers or []
        pass_infos: List[PassInfo] = []

        for index, rp in enumerate(render_passes, start=1):
            events = rp.get("events", []) or []
            start_event = rp.get("startEvent", 0)
            end_event = rp.get("endEvent", start_event)
            draw_count = sum(1 for e in events if e.get("type") == "draw")
            dispatch_count = sum(1 for e in events if e.get("type") == "dispatch")
            clear_count = sum(1 for e in events if e.get("type") == "clear")

            pass_info = PassInfo(
                index=index,
                name=rp.get("name", f"Pass_{index}"),
                start_event_id=start_event,
                end_event_id=end_event,
                draw_count=draw_count,
                dispatch_count=dispatch_count,
                clear_count=clear_count,
                has_clear=clear_count > 0,
            )

            # 渲染区域尺寸 (若有)
            pass_info.viewport_width = int(rp.get("width", 0) or 0)
            pass_info.viewport_height = int(rp.get("height", 0) or 0)

            # Debug Marker 名称
            marker_name = self._find_marker_in_range(markers, start_event, end_event)
            if marker_name:
                pass_info.marker_name = marker_name

            # RenderPass attachment 信息
            rp_info = None
            rp_id = rp.get("renderPassId")
            if rp_id and isinstance(parsed.render_pass_infos, dict):
                rp_info = parsed.render_pass_infos.get(str(rp_id))

            if rp_info is None and isinstance(rp.get("renderPassInfo"), dict):
                rp_info = rp.get("renderPassInfo")

            if rp_info:
                attachments = rp_info.get("attachments", []) or []
                color_attachments = []
                depth_attachment = None
                sample_count = 1

                for att in attachments:
                    fmt = att.get("format", "")
                    if self._is_depth_format(fmt):
                        depth_attachment = att
                    else:
                        color_attachments.append(att)
                    sample_count = max(sample_count, int(att.get("sampleCount", 1) or 1))

                pass_info.color_attachments = color_attachments
                pass_info.depth_attachment = depth_attachment
                pass_info.sample_count = sample_count
                pass_info.has_resolve = bool(
                    rp_info.get("hasResolve")
                    or (rp_info.get("resolveAttachmentCount", 0) or 0) > 0
                )
                pass_info.has_transient_attachment = self._has_transient_attachment(attachments)
                pass_info.is_depth_only = bool(depth_attachment and not color_attachments)

            pass_infos.append(pass_info)

        # 若没有 renderPasses，则回退 draws
        if pass_infos:
            self.context.passes = pass_infos
        else:
            self._analyze_from_draws()

    def _analyze_binary_mode(self) -> None:
        """二进制模式分析"""
        parsed = self.context.parsed
        draws = parsed.draws
        markers = parsed.markers
        
        # XML 模式优先使用 renderPass 数据
        if parsed.render_passes:
            self._analyze_from_render_passes()
            return

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

    @staticmethod
    def _is_depth_format(fmt: str) -> bool:
        fmt_upper = (fmt or "").upper()
        depth_tokens = ("D16", "D24", "D32", "S8", "DEPTH")
        return any(token in fmt_upper for token in depth_tokens)

    @staticmethod
    def _has_transient_attachment(attachments: List[Dict[str, Any]]) -> bool:
        for att in attachments:
            flags = (att.get("flags", "") or "").upper()
            if "TRANSIENT" in flags or "MAY_ALIAS" in flags or "LAZILY" in flags:
                return True
        return False

    @staticmethod
    def _find_marker_in_range(markers: List[Dict], start_event: int, end_event: int) -> Optional[str]:
        if not markers:
            return None
        name = None
        for marker in markers:
            event_id = marker.get("event_id", 0)
            if start_event <= event_id <= end_event:
                name = marker.get("name") or name
        return name
