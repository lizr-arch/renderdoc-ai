"""
Heatmap Builder - 资源使用模式热力图构建器 (M4.1 - 重构版)

构建资源使用模式热力图数据，用于可视化资源在整帧中的使用分布。

设计理念（基于业界调研）:
    - NVIDIA Nsight: 使用 Shader 执行热点，关注时间分布
    - AMD RDNA Guide: 驱动不做冗余状态追踪，关注 Context Roll
    - 本实现: 分析资源使用的"连续性"和"复用率"，而非"冗余检测"

功能:
    - 分析资源使用连续性（连续使用 = 缓存友好）
    - 识别使用模式（首次/连续/稀疏/孤立）
    - 生成 BindingHeatmapEntry 列表
    - 计算复用评分和连续性评分

依赖:
    - types.py: UsagePattern, BindingHeatmapData, BindingHeatmapEntry, UsageRecord

使用示例:
    from core.heatmap_builder import HeatmapBuilder
    
    builder = HeatmapBuilder(usage_index, event_ids=[10, 20, 30, ...])
    collection = builder.build_all()
    
    # 获取单个资源的热力图
    heatmap = builder.build_for_resource("tex_0x1234")

Author: Codex Agent
Version: 2.0.0 (重构版 - 使用模式分析)
Date: 2025-01-21
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from .types import (
    ResourceUsageIndex,
    UsageRecord,
    UsagePattern,  # v2.0: 新的使用模式枚举
    BindingHeatmapEntry,
    BindingHeatmapData,
    HeatmapCollection,
)


class HeatmapBuilder:
    """
    热力图构建器 (v2.0 - 使用模式分析)
    
    基于 ResourceUsageIndex 构建资源使用模式热力图。
    
    使用模式定义（基于业界最佳实践）:
        1. FIRST_USE: 资源在帧中的首次使用（黄色）
        2. CONTINUOUS: 连续 Draw Call 使用同一资源（绿色，缓存友好）
        3. SPARSE: 分散使用，间隔多个 Draw Call（蓝色，潜在优化点）
        4. ISOLATED: 仅单次使用（灰色）
    
    评分系统:
        - reuse_score: 复用评分 = usage_count / total_draws * 100
        - continuity_score: 连续性评分 = continuous / (total - first) * 100
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
        分析使用模式，生成热力图条目 (v2.0 重构)
        
        使用模式定义:
            - FIRST_USE: 资源在帧中的首次使用
            - CONTINUOUS: 与上一次使用相邻（缓存友好）
            - SPARSE: 与上一次使用间隔多个事件（潜在优化点）
            - ISOLATED: 仅使用一次
        """
        entries: List[BindingHeatmapEntry] = []
        
        if not usages:
            return entries
        
        total_uses = len(usages)
        
        # 孤立使用：仅使用一次
        if total_uses == 1:
            usage = usages[0]
            tooltip = self._build_tooltip(usage, UsagePattern.ISOLATED, resource_type)
            return [BindingHeatmapEntry(
                event_start=usage.event_id,
                event_end=usage.event_id,
                status=UsagePattern.ISOLATED,
                binding_type=usage.binding_type,
                slot=usage.slot,
                tooltip=tooltip,
            )]
        
        # 多次使用：分析连续性
        prev_event_id: Optional[int] = None
        
        for i, usage in enumerate(usages):
            if i == 0:
                # 首次使用
                status = UsagePattern.FIRST_USE
            elif prev_event_id is not None and self._is_consecutive(prev_event_id, usage.event_id):
                # 与上一次使用相邻 = 连续（缓存友好）
                status = UsagePattern.CONTINUOUS
            else:
                # 与上一次使用有间隔 = 稀疏（潜在优化点）
                status = UsagePattern.SPARSE
            
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
            
            # 更新上一个事件 ID
            prev_event_id = usage.event_id
        
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
        构建热力图条目的 tooltip 文本 (v2.0 - 使用模式)
        """
        # 使用模式标签和图标
        status_label = {
            UsagePattern.FIRST_USE: "🟡 首次使用",
            UsagePattern.CONTINUOUS: "🟢 连续使用 (缓存友好)",
            UsagePattern.SPARSE: "🔵 稀疏使用 (可优化)",
            UsagePattern.ISOLATED: "⚪ 单次使用",
        }.get(status, status)
        
        parts = [
            f"Event #{usage.event_id}",
            f"模式: {status_label}",
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
        计算连续性评分 (v2.0 - 使用模式分析)
        
        公式: continuity_score = continuous_count / (total_uses - 1) * 100
        
        解释:
            - 除首次使用外，所有使用都可能是 CONTINUOUS 或 SPARSE
            - 连续性越高，缓存利用率越好
            - 100% = 全部连续使用（理想状态）
            - 0% = 全部稀疏使用（可能需要优化 Draw Call 排序）
        """
        if not entries:
            return 100.0
        
        # 统计各模式数量
        continuous_count = 0
        sparse_count = 0
        total_uses = 0
        
        for entry in entries:
            span = entry.event_end - entry.event_start + 1
            total_uses += span
            if entry.status == UsagePattern.CONTINUOUS:
                continuous_count += span
            elif entry.status == UsagePattern.SPARSE:
                sparse_count += span
        
        # 除首次使用外的使用次数
        usage_after_first = total_uses - 1
        
        if usage_after_first <= 0:
            # 只有一次使用（ISOLATED 或单个 FIRST_USE）
            return 100.0
        
        # 连续性评分
        continuity_score = (continuous_count / usage_after_first) * 100
        return round(continuity_score, 2)


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


def build_heatmap_from_bindings(
    resource_id: str,
    bindings: List[Dict],
    resource_type: str = "texture",
    all_event_ids: Optional[List[int]] = None,
) -> Optional[Dict]:
    """
    便捷函数：从简单绑定字典列表构建热力图数据 (M4.1 集成接口)
    
    专为 report_bundle_generator.py 设计，接受简化的输入格式。
    
    Args:
        resource_id: 资源 ID (如 "tex_0x1234")
        bindings: 绑定记录列表，每项为 {"event_id": int, "slot": int}
        resource_type: 资源类型 ("texture" | "shader" | "buffer")
        all_event_ids: 帧中所有事件 ID 的有序列表（用于判断连续性）
    
    Returns:
        热力图数据字典（可直接序列化为 JSON）:
        {
            "resource_id": str,
            "resource_type": str,
            "entries": [{"eventId": int, "eventIdEnd": int, "pattern": str}, ...],
            "continuity_score": float,
            "total_uses": int
        }
        或 None（如果绑定列表为空）
    
    使用示例:
        bindings = [
            {"event_id": 10, "slot": 0},
            {"event_id": 11, "slot": 0},
            {"event_id": 15, "slot": 1},
        ]
        result = build_heatmap_from_bindings("tex_1", bindings, "texture", [10, 11, 12, 13, 14, 15])
    """
    if not bindings:
        return None
    
    # 转换为 UsageRecord 列表
    usages = []
    for binding in bindings:
        event_id = binding.get("event_id", 0)
        slot = binding.get("slot", 0)
        binding_type = binding.get("binding_type", resource_type)
        
        usages.append(UsageRecord(
            event_id=event_id,
            binding_type=binding_type,
            slot=slot,
        ))
    
    if not usages:
        return None
    
    # 创建临时索引并构建热力图
    temp_index = ResourceUsageIndex()
    if resource_type == "texture":
        temp_index.texture_usages[resource_id] = usages
    elif resource_type == "shader":
        temp_index.shader_usages[resource_id] = usages
    elif resource_type == "buffer":
        temp_index.buffer_usages[resource_id] = usages
    else:
        temp_index.texture_usages[resource_id] = usages
    
    builder = HeatmapBuilder(temp_index, all_event_ids)
    heatmap_data = builder.build_for_resource(resource_id, usages, resource_type)
    
    if not heatmap_data:
        return None
    
    return heatmap_data.to_dict()
