"""
渲染 Pass 相关规则
==================

检测渲染 Pass 结构和效率问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class PassCountRule(BaseRule):
    """检测 Pass 数量过多"""
    
    rule_id = "RD_PASS_001"
    name = "Pass Count"
    description = "检测渲染 Pass 数量是否过多"
    severity = Severity.WARNING
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("max_pass_count", 20)
        
        pass_count = len(self.context.passes)
        if pass_count > threshold:
            issues.append(self.create_issue(
                f"渲染 Pass 数量过多: {pass_count} (阈值: {threshold})",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class RTSwitchRule(BaseRule):
    """检测 Render Target 切换频繁"""
    
    rule_id = "RD_PASS_002"
    name = "RT Switch"
    description = "检测 Render Target 切换次数过多"
    severity = Severity.WARNING
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("max_rt_switches", 30)
        
        rt_switches = self.context.frame_summary.rt_switches
        if rt_switches > threshold:
            issues.append(self.create_issue(
                f"Render Target 切换 {rt_switches} 次 (阈值: {threshold})，带宽压力大",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class EmptyPassRule(BaseRule):
    """检测空 Pass"""
    
    rule_id = "RD_PASS_003"
    name = "Empty Pass"
    description = "检测没有 Draw Call 的空 Pass"
    severity = Severity.WARNING
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        
        empty_passes = []
        for pass_info in self.context.passes:
            if pass_info.draw_count == 0:
                empty_passes.append(pass_info.name)
        
        if empty_passes:
            issues.append(self.create_issue(
                f"发现 {len(empty_passes)} 个空 Pass: {', '.join(empty_passes[:3])}...",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class FullscreenPassRule(BaseRule):
    """检测全屏 Pass 效率"""
    
    rule_id = "RD_PASS_004"
    name = "Fullscreen Pass"
    description = "检测重复的全屏 Pass (可能可以合并)"
    severity = Severity.INFO
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 统计全屏 Pass
        fullscreen_passes = []
        for pass_info in self.context.passes:
            if pass_info.is_fullscreen:
                fullscreen_passes.append(pass_info.name)
        
        threshold = self.get_threshold("max_fullscreen_passes", 10)
        if len(fullscreen_passes) > threshold:
            issues.append(self.create_issue(
                f"全屏 Pass {len(fullscreen_passes)} 个 (阈值: {threshold})，考虑合并后处理",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class ClearOptimizationRule(BaseRule):
    """检测 Clear 操作优化"""
    
    rule_id = "RD_PASS_005"
    name = "Clear Optimization"
    description = "检测不必要的 Clear 操作"
    severity = Severity.INFO
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测连续 Clear
        clears = self.context.parsed.clears
        consecutive_clears = 0
        prev_target = None
        
        for clear in clears:
            target = clear.get("target")
            if target == prev_target:
                consecutive_clears += 1
            prev_target = target
        
        if consecutive_clears > 5:
            issues.append(self.create_issue(
                f"检测到 {consecutive_clears} 次连续 Clear 相同目标，可能可以合并",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class DepthPrepassRule(BaseRule):
    """检测是否使用 Depth PrePass"""
    
    rule_id = "RD_PASS_006"
    name = "Depth PrePass"
    description = "检测复杂场景是否使用 Depth PrePass"
    severity = Severity.INFO
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检查是否有 depth-only pass
        has_depth_prepass = False
        for pass_info in self.context.passes:
            if (pass_info.is_depth_only or 
                "prepass" in pass_info.name.lower() or
                "depth" in pass_info.name.lower()):
                has_depth_prepass = True
                break
        
        # 如果 draw call 多但没有 depth prepass
        draw_count = self.context.frame_summary.draw_call_count
        threshold = self.get_threshold("depth_prepass_threshold", 500)
        
        if draw_count > threshold and not has_depth_prepass:
            issues.append(self.create_issue(
                f"Draw Call 较多 ({draw_count}) 但未检测到 Depth PrePass，"
                "复杂场景建议使用 Depth PrePass 减少 Overdraw",
                location_path="Pass Structure",
            ))
        
        return issues


@RuleRegistry.register
class ShadowMapRule(BaseRule):
    """检测 Shadow Map 配置"""
    
    rule_id = "RD_PASS_007"
    name = "Shadow Map"
    description = "检测 Shadow Map 的尺寸和更新频率"
    severity = Severity.INFO
    category = Category.PASS
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测 shadow pass
        shadow_passes = []
        for pass_info in self.context.passes:
            if "shadow" in pass_info.name.lower():
                shadow_passes.append(pass_info)
        
        # 检查 Shadow Map 尺寸
        threshold = self.get_threshold("max_shadowmap_size", 4096)
        for pass_info in shadow_passes:
            for rt in pass_info.render_targets:
                if rt.width > threshold or rt.height > threshold:
                    issues.append(self.create_issue(
                        f"Shadow Map 尺寸过大: {rt.width}x{rt.height} (阈值: {threshold})",
                        location_path=f"Pass/{pass_info.name}",
                    ))
        
        return issues
