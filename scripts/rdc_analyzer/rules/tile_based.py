"""
Tile-Based GPU 规则
==================

针对 Tile-Based 架构的启发式检测规则。
"""

from typing import List, Dict, Any

from .base import BaseRule, RuleRegistry
from ..core.enums import Severity, Category
from ..core.types import Issue


def _get_tile_metrics(context) -> Dict[str, Any]:
    """从上下文获取 Tile 指标（由 TileBasedAnalyzer 注入）"""
    return getattr(context, "tile_metrics", {}) or {}


@RuleRegistry.register
class TileOverdrawRule(BaseRule):
    """检测 Tile 级 Overdraw"""
    rule_id = "TILE_001"
    name = "Tile Overdraw"
    description = "检测 Tile 级别的过度绘制"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        ratio = metrics.get("overdraw_ratio")
        if ratio is None:
            return issues

        threshold = self.get_threshold("tile_overdraw_ratio", 2.5)
        if ratio > threshold:
            issues.append(self.create_issue(
                f"Tile Overdraw 估算 {ratio:.2f}x (阈值 {threshold}x)",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileMemoryRule(BaseRule):
    """检测 Tile 内存压力"""
    rule_id = "TILE_002"
    name = "Tile Memory"
    description = "检测单 Tile 内存估算超阈值"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        tile_bytes = metrics.get("tile_memory_bytes")
        if tile_bytes is None:
            return issues

        threshold_kb = self.get_threshold("tile_memory_kb", 512.0)
        actual_kb = tile_bytes / 1024.0
        if actual_kb > threshold_kb:
            issues.append(self.create_issue(
                f"Tile 内存估算 {actual_kb:.1f}KB (阈值 {threshold_kb:.1f}KB)",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileRenderTargetRule(BaseRule):
    """检测 Pass 级 RT 字节量"""
    rule_id = "TILE_003"
    name = "Tile RT Bytes"
    description = "检测单 Pass RT 字节量过高"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        rt_bytes = metrics.get("rt_bytes")
        if rt_bytes is None:
            return issues

        threshold = self.get_threshold("tile_rt_bytes", 128 * 1024 * 1024)
        if rt_bytes > threshold:
            mb = rt_bytes / (1024 * 1024)
            threshold_mb = threshold / (1024 * 1024)
            issues.append(self.create_issue(
                f"Pass RT 字节量 {mb:.1f}MB (阈值 {threshold_mb:.1f}MB)",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileLoadStoreRule(BaseRule):
    """检测 Load/Store 负载"""
    rule_id = "TILE_004"
    name = "Tile Load/Store"
    description = "检测 Load/Store 负载偏高"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        load_store_bytes = metrics.get("load_store_bytes")
        rt_bytes = metrics.get("rt_bytes")
        if load_store_bytes is None or rt_bytes is None:
            return issues

        if load_store_bytes > rt_bytes * 1.5:
            ratio = load_store_bytes / max(rt_bytes, 1)
            issues.append(self.create_issue(
                f"Load/Store 估算 {load_store_bytes / (1024 * 1024):.1f}MB (约 {ratio:.2f}x RT)",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileMsaaRule(BaseRule):
    """检测 MSAA 成本"""
    rule_id = "TILE_005"
    name = "Tile MSAA"
    description = "检测 MSAA 采样数对 Tile 成本的影响"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        samples = metrics.get("msaa_samples")
        if samples is None:
            return issues

        if samples >= 4:
            issues.append(self.create_issue(
                f"MSAA 采样数为 {samples}x，可能放大 Tile 成本",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TilePassSwitchRule(BaseRule):
    """检测 Pass 切换频率"""
    rule_id = "TILE_006"
    name = "Tile Pass Switch"
    description = "检测 Pass 切换导致的 Tile 复用下降"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        switches = metrics.get("pass_switches")
        if switches is None:
            return issues

        threshold = self.get_threshold("max_pass_count", 15)
        if switches > threshold:
            issues.append(self.create_issue(
                f"Pass 切换次数 {switches} (阈值 {threshold})",
                location_path="Tile Metrics",
            ))
        return issues
