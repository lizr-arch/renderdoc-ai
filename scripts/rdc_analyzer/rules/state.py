"""
渲染状态相关规则
================

检测渲染状态切换和配置问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class StateChangeRule(BaseRule):
    """检测渲染状态切换过多"""
    
    rule_id = "RD_STATE_001"
    name = "Excessive State Changes"
    description = "检测渲染状态切换次数过多"
    severity = Severity.WARNING
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检查各种状态切换
        stats = self.context.frame_summary
        thresholds = {
            "shader_changes": self.get_threshold("max_shader_changes", 500),
            "blend_state_changes": self.get_threshold("max_blend_changes", 200),
            "depth_state_changes": self.get_threshold("max_depth_changes", 200),
            "rasterizer_changes": self.get_threshold("max_rasterizer_changes", 200),
        }
        
        for key, threshold in thresholds.items():
            value = getattr(stats, key, 0)
            if value > threshold:
                issues.append(self.create_issue(
                    f"{key} 过多: {value} 次 (阈值: {threshold})",
                    location_path="State Changes",
                ))
        
        return issues


@RuleRegistry.register
class ShaderSwitchRule(BaseRule):
    """检测 Shader 切换频繁"""
    
    rule_id = "RD_STATE_002"
    name = "Shader Thrashing"
    description = "检测频繁切换相同 Shader 组合"
    severity = Severity.WARNING
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 分析 Shader 切换模式
        state_history = self.context.state_history
        if not state_history:
            return issues
        
        # 检测 A->B->A 这种切换模式
        thrash_count = 0
        for i in range(2, len(state_history)):
            if (state_history[i].get("shader") == state_history[i-2].get("shader") and
                state_history[i].get("shader") != state_history[i-1].get("shader")):
                thrash_count += 1
        
        if thrash_count > 50:
            issues.append(self.create_issue(
                f"Shader 切换抖动 {thrash_count} 次，建议按材质排序",
                location_path="State Changes",
            ))
        
        return issues


@RuleRegistry.register
class RedundantStateRule(BaseRule):
    """检测冗余状态设置"""
    
    rule_id = "RD_STATE_003"
    name = "Redundant State"
    description = "检测设置相同状态的冗余调用"
    severity = Severity.INFO
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        redundant = self.context.frame_summary.redundant_state_sets
        if redundant > 100:
            issues.append(self.create_issue(
                f"冗余状态设置 {redundant} 次，存在优化空间",
                location_path="State Changes",
            ))
        
        return issues


@RuleRegistry.register
class ScissorTestRule(BaseRule):
    """检测未使用裁剪测试"""
    
    rule_id = "RD_STATE_004"
    name = "Scissor Test Usage"
    description = "检测 UI 绘制未启用 Scissor Test"
    severity = Severity.INFO
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检查 UI Pass 中是否使用 Scissor
        for pass_info in self.context.passes:
            if "ui" in pass_info.name.lower() or "gui" in pass_info.name.lower():
                if not pass_info.uses_scissor:
                    issues.append(self.create_issue(
                        f"UI Pass '{pass_info.name}' 未使用 Scissor Test，可能有过度绘制",
                        location_path=f"Pass/{pass_info.name}",
                    ))
        
        return issues


@RuleRegistry.register
class DepthTestRule(BaseRule):
    """检测深度测试配置问题"""
    
    rule_id = "RD_STATE_005"
    name = "Depth Test Issues"
    description = "检测不当的深度测试配置"
    severity = Severity.WARNING
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检查是否有大量禁用深度测试的非 UI 绘制
        depth_disabled_draws = 0
        total_draws = 0
        
        for draw in self.context.parsed.draws:
            total_draws += 1
            state = draw.get("state", {})
            if not state.get("depth_test_enabled", True):
                # 排除 UI 和后处理
                if not draw.get("is_ui") and not draw.get("is_postprocess"):
                    depth_disabled_draws += 1
        
        if total_draws > 0:
            ratio = depth_disabled_draws / total_draws
            if ratio > 0.3:  # 超过 30% 的绘制禁用深度
                issues.append(self.create_issue(
                    f"{depth_disabled_draws}/{total_draws} ({ratio:.1%}) 绘制禁用深度测试",
                    location_path="State",
                ))
        
        return issues


@RuleRegistry.register
class AlphaBlendRule(BaseRule):
    """检测 Alpha Blend 使用"""
    
    rule_id = "RD_STATE_006"
    name = "Alpha Blend Overdraw"
    description = "检测过多的透明混合绘制"
    severity = Severity.WARNING
    category = Category.STATE
    
    def check(self) -> List[Issue]:
        issues = []
        
        blend_draws = 0
        for draw in self.context.parsed.draws:
            state = draw.get("state", {})
            if state.get("blend_enabled"):
                blend_draws += 1
        
        threshold = self.get_threshold("max_blend_draws", 200)
        if blend_draws > threshold:
            issues.append(self.create_issue(
                f"透明混合绘制 {blend_draws} 次 (阈值: {threshold})，注意 Overdraw",
                location_path="State",
            ))
        
        return issues
