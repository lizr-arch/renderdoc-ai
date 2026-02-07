"""
Heatmap Builder - 资源绑定热力图构建器 (M4.1)

构建资源绑定热力图数据，用于可视化资源在整帧中的绑定模式。

功能:
    - 分析资源绑定连续性
    - 检测冗余绑定模式（连续事件绑定相同资源到相同槽位）
    - 生成 BindingHeatmapEntry 列表
    - 计算效率评分

依赖:
    - types.py: BindingHeatmapData, BindingHeatmapEntry, UsageRecord, ResourceUsageIndex
    
使用示例:
    from core.heatmap_builder import HeatmapBuilder
    
    builder = HeatmapBuilder(usage_index, event_ids=[10, 20, 30, ...])
    collection = builder.build_all()
    
    # 获取单个资源的热力图
    heatmap = builder.build_for_resource("tex_0x1234")

Author: Codex Agent
Version: 1.0.0
Date: 2025-01-21
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from .types import (
    ResourceUsageIndex,
    UsageRecord,
    BindingStatus,
    BindingHeatmapEntry,
    BindingHeatmapData,
    HeatmapCollection,
)


@dataclass
class BindingSpan:
    """
    内部用：表示一段连续绑定区间
    """
    start_event: int
    end_event: int
    binding_type: str
    slot: int
    is_redundant: bool = False  # 是否为冗余绑定


class HeatmapBuilder:
    """
    热力图构建器
    
    基于 ResourceUsageIndex 构建资源绑定热力图。
    
    检测逻辑:
        1. FIRST_BIND: 资源在帧中的首次绑定
        2. REDUNDANT: 连续多个事件将同一资源绑定到相同槽位
        3. NORMAL: 正常的资源绑定使用
    
    效率评分:
        efficiency_score = 100 * (1 - redundant_events / total_events)
    """
    
    def __init__(
        self,
        usage_index: ResourceUsageIndex,
        event_ids: Optional[List[int]] = None,
    ):
        """
        初始化构建器
        
        Args:
            usage_index: 资源使用索引（包含 texture/shader/buffer/rt 使用记录）
            event_ids: 可选的事件 ID 列表，用于确定事件顺序。
                       如果不提供，将从 usage_index 中推断。
        """
        self.usage_index = usage_index
        self._event_ids = event_ids or []
        
        # 缓存事件顺序索引
        self._event_order: Dict[int, int] = {}
        if self._event_ids:
            self._event_order = {eid: idx for idx, eid in enumerate(self._event_ids)}
    
    def build_all(self) -> HeatmapCollection:
        """
        构建所有资源的热力图数据
        
        Returns:
            HeatmapCollection 包含所有资源类型的热力图
        """
        collection = HeatmapCollection()
        collection.draw_event_ids = self._event_ids.copy() if self._event_ids else []
        
        # 处理纹理
        for resource_id in self.usage_index.texture_usages:
            heatmap = self.build_for_resource(
                resource_id, 
                self.usage_index.texture_usages[resource_id],
                resource_type="texture"
            )
            if heatmap and heatmap.entries:
                collection.add_heatmap(heatmap)
        
        # 处理 Shader
        for resource_id in self.usage_index.shader_usages:
            heatmap = self.build_for_resource(
                resource_id,
                self.usage_index.shader_usages[resource_id],
                resource_type="shader"
            )
            if heatmap and heatmap.entries:
                collection.add_heatmap(heatmap)
        
        # 处理 Buffer
        for resource_id in self.usage_index.buffer_usages:
            heatmap = self.build_for_resource(
                resource_id,
                self.usage_index.buffer_usages[resource_id],
                resource_type="buffer"
            )
            if heatmap and heatmap.entries:
                collection.add_heatmap(heatmap)
        
        # 处理 RenderTarget
        for resource_id in self.usage_index.render_target_usages:
            heatmap = self.build_for_resource(
                resource_id,
                self.usage_index.render_target_usages[resource_id],
                resource_type="render_target"
            )
            if heatmap and heatmap.entries:
                collection.add_heatmap(heatmap)
        
        return collection
    
    def build_for_resource(
        self,
        resource_id: str,
        usages: Optional[List[UsageRecord]] = None,
        resource_type: str = "unknown",
    ) -> Optional[BindingHeatmapData]:
        """
        为单个资源构建热力图数据
        
        Args:
            resource_id: 资源 ID
            usages: 使用记录列表（如果为 None，从 usage_index 查找）
            resource_type: 资源类型标识
        
        Returns:
            BindingHeatmapData 或 None（如果没有使用记录）
        """
        # 获取使用记录
        if usages is None:
            usages = self.usage_index.get_all_usages(resource_id)
        
        if not usages:
            return None
        
        # 按事件 ID 排序
        sorted_usages = self._sort_by_event_order(usages)
        
        # 分析绑定模式，生成热力图条目
        entries = self._analyze_binding_pattern(sorted_usages, resource_type)
        
        if not entries:
            return None
        
        # 计算效率评分
        efficiency = self._calculate_efficiency(entries)
        
        return BindingHeatmapData(
            resource_id=resource_id,
            entries=entries,
            efficiency_score=efficiency,
        )
    
    def _sort_by_event_order(self, usages: List[UsageRecord]) -> List[UsageRecord]:
        """
        按事件顺序排序使用记录
        """
        if self._event_order:
            # 使用预定义顺序
            return sorted(usages, key=lambda u: self._event_order.get(u.event_id, u.event_id))
        else:
            # 简单按事件 ID 排序
            return sorted(usages, key=lambda u: u.event_id)
    
    def _analyze_binding_pattern(
        self,
        usages: List[UsageRecord],
        resource_type: str,
    ) -> List[BindingHeatmapEntry]:
        """
        分析绑定模式，生成热力图条目
        
        检测规则:
            - 首次绑定: FIRST_BIND
            - 连续相同绑定: REDUNDANT
            - 正常使用: NORMAL
        """
        entries: List[BindingHeatmapEntry] = []
        
        if not usages:
            return entries
        
        # 按 (binding_type, slot) 分组追踪状态
        # 用于检测同一槽位的连续绑定
        slot_state: Dict[Tuple[str, int], int] = {}  # (type, slot) -> last_event_id
        
        # 标记首次使用
        is_first = True
        
        for usage in usages:
            binding_key = (usage.binding_type, usage.slot)
            last_event = slot_state.get(binding_key)
            
            # 判断状态
            if is_first:
                status = BindingStatus.FIRST_BIND
                is_first = False
            elif last_event is not None and self._is_consecutive(last_event, usage.event_id):
                # 连续事件中相同槽位绑定 = 冗余
                status = BindingStatus.REDUNDANT
            else:
                status = BindingStatus.NORMAL
            
            # 创建条目
            tooltip = self._build_tooltip(usage, status, resource_type)
            entry = BindingHeatmapEntry(
                event_start=usage.event_id,
                event_end=usage.event_id,  # 单事件
                status=status,
                binding_type=usage.binding_type,
                slot=usage.slot,
                tooltip=tooltip,
            )
            entries.append(entry)
            
            # 更新槽位状态
            slot_state[binding_key] = usage.event_id
        
        # 合并连续相同状态的条目（优化可视化）
        merged_entries = self._merge_consecutive_entries(entries)
        
        return merged_entries
    
    def _is_consecutive(self, prev_event: int, curr_event: int) -> bool:
        """
        判断两个事件是否连续（用于检测冗余绑定）
        
        连续定义：
            - 如果有 event_ids 列表，使用列表索引判断相邻性
            - 回退：使用事件 ID 差值判断（<= 5 视为连续）
        
        注意：
            "连续" 在这里指的是渲染流程中相邻的 Draw Call，
            如果同一资源在相邻的 Draw Call 中被重复绑定到相同槽位，
            通常意味着冗余绑定。
        """
        if self._event_order:
            prev_idx = self._event_order.get(prev_event, -1)
            curr_idx = self._event_order.get(curr_event, -1)
            if prev_idx >= 0 and curr_idx >= 0:
                # 索引相邻（差值 = 1）才是连续
                return (curr_idx - prev_idx) == 1
        
        # 回退：ID 差值判断（仅允许小间隙，如中间有少量非 Draw 事件）
        return (curr_event - prev_event) <= 5
    
    def _build_tooltip(
        self,
        usage: UsageRecord,
        status: str,
        resource_type: str,
    ) -> str:
        """
        构建热力图条目的 tooltip 文本
        """
        status_label = {
            BindingStatus.FIRST_BIND: "首次绑定",
            BindingStatus.REDUNDANT: "⚠️ 冗余绑定",
            BindingStatus.NORMAL: "正常使用",
            BindingStatus.UNBOUND: "已解绑",
        }.get(status, status)
        
        parts = [
            f"Event #{usage.event_id}",
            f"状态: {status_label}",
        ]
        
        if usage.binding_type:
            parts.append(f"绑定: {usage.binding_type}")
        if usage.slot >= 0:
            parts.append(f"槽位: {usage.slot}")
        if usage.draw_name:
            parts.append(f"调用: {usage.draw_name}")
        if usage.pass_name:
            parts.append(f"Pass: {usage.pass_name}")
        
        return " | ".join(parts)
    
    def _merge_consecutive_entries(
        self,
        entries: List[BindingHeatmapEntry],
    ) -> List[BindingHeatmapEntry]:
        """
        合并连续相同状态的条目
        
        例如: [NORMAL@10, NORMAL@11, NORMAL@12] -> [NORMAL@10-12]
        """
        if not entries or len(entries) <= 1:
            return entries
        
        merged: List[BindingHeatmapEntry] = []
        current = entries[0]
        
        for next_entry in entries[1:]:
            # 判断是否可合并
            can_merge = (
                current.status == next_entry.status and
                current.binding_type == next_entry.binding_type and
                current.slot == next_entry.slot and
                self._is_consecutive(current.event_end, next_entry.event_start)
            )
            
            if can_merge:
                # 扩展当前条目的结束事件
                current = BindingHeatmapEntry(
                    event_start=current.event_start,
                    event_end=next_entry.event_end,
                    status=current.status,
                    binding_type=current.binding_type,
                    slot=current.slot,
                    color=current.color,
                    tooltip=f"Events #{current.event_start}-#{next_entry.event_end}",
                )
            else:
                merged.append(current)
                current = next_entry
        
        merged.append(current)
        return merged
    
    def _calculate_efficiency(self, entries: List[BindingHeatmapEntry]) -> float:
        """
        计算效率评分
        
        公式: 100 * (1 - redundant_events / total_events)
        """
        if not entries:
            return 100.0
        
        total_events = 0
        redundant_events = 0
        
        for entry in entries:
            span = entry.event_end - entry.event_start + 1
            total_events += span
            if entry.status == BindingStatus.REDUNDANT:
                redundant_events += span
        
        if total_events == 0:
            return 100.0
        
        efficiency = 100.0 * (1.0 - redundant_events / total_events)
        return round(efficiency, 2)


# ============================================================================
# 便捷函数
# ============================================================================

def build_heatmap_collection(
    usage_index: ResourceUsageIndex,
    event_ids: Optional[List[int]] = None,
) -> HeatmapCollection:
    """
    便捷函数：构建整帧的热力图集合
    
    Args:
        usage_index: 资源使用索引
        event_ids: 可选的事件 ID 列表（用于确定顺序）
    
    Returns:
        HeatmapCollection
    """
    builder = HeatmapBuilder(usage_index, event_ids)
    return builder.build_all()


def compute_binding_heatmap(
    resource_id: str,
    usages: List[UsageRecord],
    event_ids: Optional[List[int]] = None,
) -> Optional[BindingHeatmapData]:
    """
    便捷函数：为单个资源计算热力图数据
    
    Args:
        resource_id: 资源 ID
        usages: 该资源的使用记录列表
        event_ids: 可选的事件 ID 列表（用于确定顺序）
    
    Returns:
        BindingHeatmapData 或 None
    """
    # 创建临时索引
    temp_index = ResourceUsageIndex()
    for usage in usages:
        temp_index.texture_usages.setdefault(resource_id, []).append(usage)
    
    builder = HeatmapBuilder(temp_index, event_ids)
    return builder.build_for_resource(resource_id, usages)
