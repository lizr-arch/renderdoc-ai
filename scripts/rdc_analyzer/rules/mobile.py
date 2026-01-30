"""
移动端特定规则
==============

检测移动端 GPU (TBDR 架构) 特有的性能问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class TBDRFlushRule(BaseRule):
    """检测 TBDR 架构下的 Tile Flush"""
    
    rule_id = "RD_MOBILE_001"
    name = "TBDR Flush"
    description = "检测可能导致 Tile 提前 Flush 的操作"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测 RT 中间读取 (会导致 flush)
        rt_reads = []
        current_rts = set()
        
        for draw in self.context.parsed.draws:
            # 更新当前 RT
            for rt in draw.get("render_targets", []):
                current_rts.add(rt)
            
            # 检测是否读取当前 RT
            for tex in draw.get("bound_textures", []):
                if tex in current_rts:
                    rt_reads.append({
                        "event_id": draw.get("event_id"),
                        "texture": tex,
                    })
        
        if rt_reads:
            issues.append(self.create_issue(
                f"检测到 {len(rt_reads)} 次 RT 中间读取，TBDR 架构下会导致 Tile Flush",
                location_path="Draw Calls",
            ))
        
        return issues


@RuleRegistry.register
class MobileOverdrawRule(BaseRule):
    """检测移动端 Overdraw"""
    
    rule_id = "RD_MOBILE_002"
    name = "Mobile Overdraw"
    description = "检测移动端严重的过度绘制"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 估算 Overdraw
        total_pixels = 0
        screen_pixels = self.context.frame_summary.viewport_width * self.context.frame_summary.viewport_height
        
        if screen_pixels == 0:
            return issues
        
        for draw in self.context.parsed.draws:
            # 简单估算: 透明物体算全屏
            if draw.get("state", {}).get("blend_enabled"):
                total_pixels += screen_pixels
            else:
                # 不透明物体假设覆盖一部分
                total_pixels += screen_pixels * 0.3
        
        overdraw_ratio = total_pixels / screen_pixels
        threshold = self.get_threshold("mobile_max_overdraw", 3.0)
        
        if overdraw_ratio > threshold:
            issues.append(self.create_issue(
                f"估算 Overdraw: {overdraw_ratio:.1f}x (移动端阈值: {threshold}x)",
                location_path="Frame Summary",
            ))
        
        return issues


@RuleRegistry.register
class MobilePrecisionRule(BaseRule):
    """检测移动端精度使用"""
    
    rule_id = "RD_MOBILE_003"
    name = "Mobile Precision"
    description = "检测移动端是否合理使用 half/float16"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]
    
    # float32 格式列表
    FLOAT32_FORMATS = {
        "R32_FLOAT", "R32G32_FLOAT", "R32G32B32_FLOAT", "R32G32B32A32_FLOAT",
    }
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测使用 float32 的 RT
        float32_rts = []
        for tex in self.context.textures:
            if tex.is_render_target:
                if tex.format.upper() in self.FLOAT32_FORMATS:
                    float32_rts.append(tex)
        
        if len(float32_rts) > 3:
            issues.append(self.create_issue(
                f"{len(float32_rts)} 个 RT 使用 float32，移动端建议使用 float16",
                location_path="Render Targets",
            ))
        
        return issues


@RuleRegistry.register
class MobileBandwidthRule(BaseRule):
    """检测移动端带宽压力"""
    
    rule_id = "RD_MOBILE_004"
    name = "Mobile Bandwidth"
    description = "检测移动端带宽敏感操作"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测大纹理采样
        large_texture_samples = 0
        threshold_size = self.get_threshold("mobile_texture_size", 1024)
        
        for tex in self.context.textures:
            if tex.width > threshold_size or tex.height > threshold_size:
                if not tex.is_render_target:
                    large_texture_samples += 1
        
        if large_texture_samples > 20:
            issues.append(self.create_issue(
                f"{large_texture_samples} 张大纹理 (>{threshold_size})，移动端带宽压力大",
                location_path="Textures",
            ))
        
        return issues


@RuleRegistry.register
class MobileAlphaTestRule(BaseRule):
    """检测移动端 Alpha Test 使用"""
    
    rule_id = "RD_MOBILE_005"
    name = "Alpha Test Usage"
    description = "检测 Alpha Test/Clip 对 TBDR 的影响"
    severity = Severity.INFO
    category = Category.MOBILE
    platforms = ["mobile"]
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测使用 discard/clip 的 shader
        alpha_test_draws = 0
        for draw in self.context.parsed.draws:
            if draw.get("uses_discard") or draw.get("uses_alpha_test"):
                alpha_test_draws += 1
        
        threshold = self.get_threshold("mobile_max_alpha_test", 50)
        if alpha_test_draws > threshold:
            issues.append(self.create_issue(
                f"{alpha_test_draws} 个 Draw 使用 Alpha Test，TBDR 下会影响 Early-Z 效率",
                location_path="Draw Calls",
            ))
        
        return issues


@RuleRegistry.register
class MobileLoadStoreRule(BaseRule):
    """检测移动端 Load/Store 操作"""
    
    rule_id = "RD_MOBILE_006"
    name = "Load Store Action"
    description = "检测是否正确使用 Load/Store Action"
    severity = Severity.WARNING
    category = Category.MOBILE
    platforms = ["mobile"]
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测没有 Clear 但有绘制的 Pass (可能需要 Load)
        no_clear_passes = []
        for pass_info in self.context.passes:
            if pass_info.draw_count > 0 and not pass_info.has_clear:
                # 检查是否是第一次使用这个 RT
                no_clear_passes.append(pass_info.name)
        
        if no_clear_passes:
            issues.append(self.create_issue(
                f"{len(no_clear_passes)} 个 Pass 未 Clear 直接绘制，确保 LoadAction 正确",
                location_path="Pass Structure",
            ))
        
        return issues
