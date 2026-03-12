"""
Draw Call 相关规则
==================

检测 Draw Call 相关的性能问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class DrawCallCountRule(BaseRule):
    """检测 Draw Call 数量过多"""
    
    rule_id = "RD_DC_001"
    name = "Draw Call Count"
    description = "检测每帧 Draw Call 数量是否超过阈值"
    severity = Severity.WARNING
    category = Category.DRAW_CALL
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("draw_call_count", 2000)
        
        draw_count = self.context.frame_summary.draw_call_count
        if draw_count > threshold:
            issues.append(self.create_issue(
                f"Draw Call 数量过多: {draw_count} (阈值: {threshold})",
                location_path="Frame Summary",
            ))
        
        return issues


@RuleRegistry.register
class LowPolyDrawCallRule(BaseRule):
    """检测低多边形 Draw Call"""
    
    rule_id = "RD_DC_002"
    name = "Low Poly Draw Call"
    description = "检测顶点数过少的 Draw Call，建议合批"
    severity = Severity.INFO
    category = Category.DRAW_CALL
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("min_vertices_per_draw", 100)
        
        low_poly_count = 0
        for draw in self.context.parsed.draws:
            vertex_count = draw.get("vertex_count", 0)
            if 0 < vertex_count < threshold:
                low_poly_count += 1
        
        if low_poly_count > 10:
            issues.append(self.create_issue(
                f"发现 {low_poly_count} 个低多边形 Draw Call (顶点数 < {threshold})，建议合批",
                location_path="Draw Calls",
            ))
        
        return issues


@RuleRegistry.register
class InstancedDrawRule(BaseRule):
    """检测未使用实例化绘制"""
    
    rule_id = "RD_DC_003"
    name = "Non-Instanced Draw"
    description = "检测重复绘制相同网格但未使用 Instancing"
    severity = Severity.WARNING
    category = Category.DRAW_CALL
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 统计相同顶点配置的 Draw Call
        vertex_configs = {}
        for draw in self.context.parsed.draws:
            key = (
                draw.get("vertex_count", 0),
                draw.get("index_count", 0),
            )
            if key[0] > 0:  # 有效的配置
                vertex_configs[key] = vertex_configs.get(key, 0) + 1
        
        # 检测重复配置
        threshold = self.get_threshold("instancing_threshold", 5)
        for config, count in vertex_configs.items():
            if count >= threshold:
                issues.append(self.create_issue(
                    f"相同顶点配置 ({config[0]} verts) 绘制 {count} 次，建议使用 GPU Instancing",
                    location_path="Draw Calls",
                    severity=Severity.WARNING if count > 10 else Severity.INFO,
                ))
        
        return issues


@RuleRegistry.register
class EmptyDrawCallRule(BaseRule):
    """检测空 Draw Call"""
    
    rule_id = "RD_DC_004"
    name = "Empty Draw Call"
    description = "检测顶点数为 0 的无效 Draw Call"
    severity = Severity.WARNING
    category = Category.DRAW_CALL
    
    def check(self) -> List[Issue]:
        issues = []
        
        empty_count = 0
        for draw in self.context.parsed.draws:
            if draw.get("vertex_count", 0) == 0 and draw.get("index_count", 0) == 0:
                empty_count += 1
        
        if empty_count > 0:
            issues.append(self.create_issue(
                f"发现 {empty_count} 个空 Draw Call (0 顶点)，应该消除",
                location_path="Draw Calls",
            ))
        
        return issues


@RuleRegistry.register
class VertexCountRule(BaseRule):
    """检测单次 Draw Call 顶点数过多"""
    
    rule_id = "RD_DC_005"
    name = "High Vertex Count"
    description = "检测单次 Draw Call 顶点数过多"
    severity = Severity.INFO
    category = Category.DRAW_CALL
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("max_vertices_per_draw", 100000)
        
        high_vertex_draws = []
        for draw in self.context.parsed.draws:
            vertex_count = draw.get("vertex_count", 0)
            if vertex_count > threshold:
                high_vertex_draws.append({
                    "event_id": draw.get("event_id"),
                    "vertex_count": vertex_count,
                })
        
        if high_vertex_draws:
            issues.append(self.create_issue(
                f"发现 {len(high_vertex_draws)} 个高顶点数 Draw Call (> {threshold})",
                location_path="Draw Calls",
            ))
        
        return issues
