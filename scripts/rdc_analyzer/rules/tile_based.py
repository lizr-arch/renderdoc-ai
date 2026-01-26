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
class TileLoadStoreRule(BaseRule):
    """检测 RenderPass Load/Store 操作"""
    rule_id = "TILE_003"
    name = "Unnecessary RT Load/Store"
    description = "检测到不必要的 Render Target Load/Store 操作"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        if not metrics.get("load_store_available"):
            return issues

        load_ops = metrics.get("load_ops", 0)
        store_ops = metrics.get("store_ops", 0)
        pass_count = metrics.get("load_store_passes", 0)
        if load_ops > 0 or store_ops > 0:
            issues.append(self.create_issue(
                f"检测到 Load {load_ops} 次 / Store {store_ops} 次 (涉及 {pass_count} 个 Pass)",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileMsaaResolveRule(BaseRule):
    """检测 MSAA Resolve 使用"""
    rule_id = "TILE_004"
    name = "MSAA Resolve Missing"
    description = "检测 MSAA Pass 未启用 Resolve 优化"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        if not metrics.get("msaa_check_available"):
            return issues

        no_resolve = metrics.get("msaa_no_resolve_passes", 0)
        msaa_passes = metrics.get("msaa_passes", 0)
        samples = metrics.get("msaa_samples", 1)
        if no_resolve > 0 and samples >= 2:
            issues.append(self.create_issue(
                f"MSAA {samples}x 下有 {no_resolve}/{msaa_passes} 个 Pass 未检测到 Resolve",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileTransientAttachmentRule(BaseRule):
    """检测 Transient Attachment"""
    rule_id = "TILE_005"
    name = "Transient Attachment"
    description = "检测 Depth/Stencil 未启用 Transient Attachment"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        if not metrics.get("transient_check_available"):
            return issues

        missing = metrics.get("transient_missing_passes", 0)
        checked = metrics.get("transient_checked_passes", 0)
        if missing > 0:
            issues.append(self.create_issue(
                f"{missing}/{checked} 个 Pass Depth/Stencil 未启用 Transient Attachment",
                location_path="Tile Metrics",
            ))
        return issues


@RuleRegistry.register
class TileDebugMarkerRule(BaseRule):
    """检测 Debug Marker"""
    rule_id = "TILE_006"
    name = "Missing Debug Marker"
    description = "检测 Render Pass 缺少 Debug Marker"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]

    def check(self) -> List[Issue]:
        issues: List[Issue] = []
        metrics = _get_tile_metrics(self.context)
        checked = metrics.get("marker_checked_passes", 0)
        if checked == 0:
            return issues

        missing = metrics.get("marker_missing_passes", 0)
        if missing > 0:
            issues.append(self.create_issue(
                f"{missing}/{checked} 个 Pass 缺少 Debug Marker",
                location_path="Tile Metrics",
            ))
        return issues
