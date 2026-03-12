#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tile-Based 分析规则定义
======================

提供规则元数据（标题/严重度/阈值键/建议），供 Tile-Based Analyzer 使用。
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TileRuleSpec:
    rule_id: str
    title: str
    severity: str
    category: str
    description: str
    threshold_key: Optional[str] = None
    suggestion: str = ""


TILE_RULES: Dict[str, TileRuleSpec] = {
    "TILE_001": TileRuleSpec(
        rule_id="TILE_001",
        title="Tile Overdraw 过高",
        severity="warning",
        category="performance",
        description="Tile 级别的 Overdraw 比例偏高，可能导致片段处理压力上升。",
        threshold_key="tile_overdraw_ratio",
        suggestion="降低过度绘制：合并透明物体、优化遮挡、减少无效绘制。",
    ),
    "TILE_002": TileRuleSpec(
        rule_id="TILE_002",
        title="Tile 内存开销过高",
        severity="warning",
        category="memory",
        description="单 Tile 估算内存超出阈值，可能导致片上缓存压力。",
        threshold_key="tile_memory_kb",
        suggestion="减少同时绑定的 RT 数量或降低 RT 精度/分辨率。",
    ),
    "TILE_003": TileRuleSpec(
        rule_id="TILE_003",
        title="Pass RT 字节量过高",
        severity="warning",
        category="memory",
        description="单 Pass 的 RT 字节量过高，增加片上/片外带宽压力。",
        threshold_key="tile_rt_bytes",
        suggestion="拆分 Pass 或降低 RT 精度/分辨率，减少一次性写入。",
    ),
    "TILE_004": TileRuleSpec(
        rule_id="TILE_004",
        title="Load/Store 负载偏高",
        severity="info",
        category="performance",
        description="Tile 的 Load/Store 估算偏高，可能导致带宽瓶颈。",
        threshold_key=None,
        suggestion="减少不必要的 Load/Store，或使用更合适的 Load/Store 操作。",
    ),
    "TILE_005": TileRuleSpec(
        rule_id="TILE_005",
        title="MSAA 成本偏高",
        severity="info",
        category="performance",
        description="较高的 MSAA 采样会放大 Tile 成本。",
        threshold_key=None,
        suggestion="评估是否需要高采样数，或仅在关键 Pass 启用 MSAA。",
    ),
    "TILE_006": TileRuleSpec(
        rule_id="TILE_006",
        title="Tile Pass 切换频繁",
        severity="info",
        category="performance",
        description="频繁的 Pass 切换可能导致 Tile 复用效率下降。",
        threshold_key=None,
        suggestion="合并相邻 Pass，减少无效的 RT/状态切换。",
    ),
}
