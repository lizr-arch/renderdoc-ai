"""
回归检测器
==========

分析 DiffResult 并根据规则检测性能回归。

规则实现:
- REG001: Draw Call 数量增加 (>5%)
- REG002: 纹理分辨率增加 (>50%)
- REG003: Shader 变更检测
- REG004: 缓冲区大小增加 (>30%)
- REG005: 三角形数量增加 (>10%)
- REG006: Overdraw 风险检测
- REG007: 新增渲染 Pass
"""

from typing import List, Dict, Optional, Set
from dataclasses import replace
from .diff_types import DiffResult, DiffStatus, TextureDiff, ShaderDiff
from .regression_types import (
    RegressionRule,
    RegressionRuleId,
    RegressionSeverity,
    RegressionIssue,
    RegressionReport,
    EvidenceAnchor,
    DEFAULT_RULES,
)


class RegressionDetector:
    """
    性能回归检测器
    
    分析 DiffResult 并根据配置的规则检测潜在的性能回归问题。
    """
    
    def __init__(
        self,
        rules: Optional[Dict[RegressionRuleId, RegressionRule]] = None,
        custom_thresholds: Optional[Dict[RegressionRuleId, float]] = None,
    ):
        """
        初始化检测器
        
        Args:
            rules: 自定义规则配置 (None 使用默认规则)
            custom_thresholds: 自定义阈值覆盖
        """
        # 深拷贝规则，避免修改全局 DEFAULT_RULES
        if rules:
            self.rules = {k: replace(v) for k, v in rules.items()}
        else:
            self.rules = {k: replace(v) for k, v in DEFAULT_RULES.items()}
        
        # 应用自定义阈值
        if custom_thresholds:
            for rule_id, threshold in custom_thresholds.items():
                if rule_id in self.rules:
                    self.rules[rule_id].threshold = threshold
    
    def detect(self, diff_result: DiffResult) -> RegressionReport:
        """
        执行回归检测
        
        Args:
            diff_result: DiffEngine 的对比结果
            
        Returns:
            RegressionReport 回归检测报告
        """
        report = RegressionReport()
        issues: List[RegressionIssue] = []
        rules_triggered: Set[RegressionRuleId] = set()
        
        # REG001: Draw Call 数量检测
        if self.rules[RegressionRuleId.REG001].enabled:
            issue = self._check_draw_call_count(diff_result)
            if issue:
                issues.append(issue)
                rules_triggered.add(RegressionRuleId.REG001)
        
        # REG002: 纹理分辨率检测
        if self.rules[RegressionRuleId.REG002].enabled:
            tex_issues = self._check_texture_resolution(diff_result)
            issues.extend(tex_issues)
            if tex_issues:
                rules_triggered.add(RegressionRuleId.REG002)
        
        # REG003: Shader 变更检测
        if self.rules[RegressionRuleId.REG003].enabled:
            shader_issues = self._check_shader_changes(diff_result)
            issues.extend(shader_issues)
            if shader_issues:
                rules_triggered.add(RegressionRuleId.REG003)
        
        # REG004: 缓冲区大小检测
        if self.rules[RegressionRuleId.REG004].enabled:
            buffer_issues = self._check_buffer_size(diff_result)
            issues.extend(buffer_issues)
            if buffer_issues:
                rules_triggered.add(RegressionRuleId.REG004)
        
        # REG005: 三角形数量检测
        if self.rules[RegressionRuleId.REG005].enabled:
            issue = self._check_triangle_count(diff_result)
            if issue:
                issues.append(issue)
                rules_triggered.add(RegressionRuleId.REG005)
        
        # REG006: Overdraw 风险检测
        if self.rules[RegressionRuleId.REG006].enabled:
            overdraw_issues = self._check_overdraw_risk(diff_result)
            issues.extend(overdraw_issues)
            if overdraw_issues:
                rules_triggered.add(RegressionRuleId.REG006)
        
        # REG007: 新增渲染 Pass 检测
        if self.rules[RegressionRuleId.REG007].enabled:
            pass_issues = self._check_new_render_pass(diff_result)
            issues.extend(pass_issues)
            if pass_issues:
                rules_triggered.add(RegressionRuleId.REG007)
        
        report.issues = issues
        report.rules_checked = sum(1 for r in self.rules.values() if r.enabled)
        report.rules_triggered = len(rules_triggered)
        
        return report
    
    def _check_draw_call_count(self, diff: DiffResult) -> Optional[RegressionIssue]:
        """
        REG001: 检测 Draw Call 数量增加
        """
        rule = self.rules[RegressionRuleId.REG001]
        
        if not diff.summary or not diff.summary.draw_calls:
            return None
        
        dc = diff.summary.draw_calls
        if dc.baseline == 0:
            return None
        
        if dc.delta_percent > rule.threshold:
            return RegressionIssue(
                rule_id=RegressionRuleId.REG001,
                severity=rule.severity,
                message=f"Draw Call 数量增加了 {dc.delta_percent:.1f}%",
                details=f"从 {dc.baseline} 增加到 {dc.target}",
                baseline_value=dc.baseline,
                target_value=dc.target,
                delta_percent=dc.delta_percent,
            )
        return None
    
    def _check_texture_resolution(self, diff: DiffResult) -> List[RegressionIssue]:
        """
        REG002: 检测纹理分辨率增加
        """
        rule = self.rules[RegressionRuleId.REG002]
        issues: List[RegressionIssue] = []
        
        for tex_diff in diff.texture_diffs:
            if tex_diff.status == DiffStatus.MODIFIED:
                # 检查 width/height 变化
                # changes 格式是 Dict[str, Tuple[baseline, target]]
                if "width" in tex_diff.changes or "height" in tex_diff.changes:
                    width_change = tex_diff.changes.get("width", (1, 1))
                    height_change = tex_diff.changes.get("height", (1, 1))
                    
                    # 计算像素数变化 (Tuple: (baseline, target))
                    old_pixels = width_change[0] * height_change[0]
                    new_pixels = width_change[1] * height_change[1]
                    
                    if old_pixels > 0:
                        change_percent = ((new_pixels - old_pixels) / old_pixels) * 100
                        
                        if change_percent > rule.threshold:
                            issues.append(RegressionIssue(
                                rule_id=RegressionRuleId.REG002,
                                severity=rule.severity,
                                message=f"纹理 '{tex_diff.name}' 分辨率增加了 {change_percent:.1f}%",
                                details=f"从 {width_change[0]}x{height_change[0]} 到 {width_change[1]}x{height_change[1]}",
                                baseline_value=old_pixels,
                                target_value=new_pixels,
                                delta_percent=change_percent,
                                affected_resources=[tex_diff.resource_id],
                            ))
        
        return issues
    
    def _check_shader_changes(self, diff: DiffResult) -> List[RegressionIssue]:
        """
        REG003: 检测 Shader 变更
        """
        rule = self.rules[RegressionRuleId.REG003]
        issues: List[RegressionIssue] = []
        
        # 统计修改和新增的 Shader
        modified_shaders = [s for s in diff.shader_diffs if s.status == DiffStatus.MODIFIED]
        added_shaders = [s for s in diff.shader_diffs if s.status == DiffStatus.ADDED]
        
        if modified_shaders:
            affected = [s.resource_id for s in modified_shaders]
            issues.append(RegressionIssue(
                rule_id=RegressionRuleId.REG003,
                severity=rule.severity,
                message=f"{len(modified_shaders)} 个 Shader 代码发生变化",
                details=", ".join([f"{s.name}({s.shader_type})" for s in modified_shaders]),
                affected_resources=affected,
            ))
        
        if added_shaders:
            affected = [s.resource_id for s in added_shaders]
            issues.append(RegressionIssue(
                rule_id=RegressionRuleId.REG003,
                severity=rule.severity,
                message=f"新增 {len(added_shaders)} 个 Shader",
                details=", ".join([f"{s.name}({s.shader_type})" for s in added_shaders]),
                affected_resources=affected,
            ))
        
        return issues
    
    def _check_buffer_size(self, diff: DiffResult) -> List[RegressionIssue]:
        """
        REG004: 检测缓冲区大小增加
        """
        rule = self.rules[RegressionRuleId.REG004]
        issues: List[RegressionIssue] = []
        
        for buf_diff in diff.buffer_diffs:
            if buf_diff.status == DiffStatus.MODIFIED and "size" in buf_diff.changes:
                # changes 格式是 Dict[str, Tuple[baseline, target]]
                size_change = buf_diff.changes["size"]
                old_size = size_change[0]  # Tuple: (baseline, target)
                new_size = size_change[1]
                
                if old_size > 0:
                    change_percent = ((new_size - old_size) / old_size) * 100
                    
                    if change_percent > rule.threshold:
                        issues.append(RegressionIssue(
                            rule_id=RegressionRuleId.REG004,
                            severity=rule.severity,
                            message=f"缓冲区 '{buf_diff.name}' 大小增加了 {change_percent:.1f}%",
                            details=f"从 {old_size:,} 字节 到 {new_size:,} 字节",
                            baseline_value=old_size,
                            target_value=new_size,
                            delta_percent=change_percent,
                            affected_resources=[buf_diff.resource_id],
                        ))
        
        return issues
    
    def _check_triangle_count(self, diff: DiffResult) -> Optional[RegressionIssue]:
        """
        REG005: 检测三角形数量增加
        """
        rule = self.rules[RegressionRuleId.REG005]
        
        # SummaryDiff 使用 'triangles' 字段 (不是 'triangle_count')
        if not diff.summary or not diff.summary.triangles:
            return None
        
        tri = diff.summary.triangles
        if tri.baseline == 0:
            return None
        
        if tri.delta_percent > rule.threshold:
            return RegressionIssue(
                rule_id=RegressionRuleId.REG005,
                severity=rule.severity,
                message=f"三角形数量增加了 {tri.delta_percent:.1f}%",
                details=f"从 {int(tri.baseline):,} 增加到 {int(tri.target):,}",
                baseline_value=tri.baseline,
                target_value=tri.target,
                delta_percent=tri.delta_percent,
            )
        return None
    
    def _check_overdraw_risk(self, diff: DiffResult) -> List[RegressionIssue]:
        """
        REG006: 检测 Overdraw 风险
        
        检测条件:
        1. 新增的 Draw Call 使用相同的渲染目标
        2. 顶点数相近但 Shader 不同 (可能是同一物体多次绘制)
        """
        rule = self.rules[RegressionRuleId.REG006]
        issues: List[RegressionIssue] = []
        
        # 获取新增的 Draw Calls
        added_draws = [d for d in diff.draw_call_diffs if d.status == DiffStatus.ADDED]
        
        if len(added_draws) > 1:
            # 简单启发式: 如果多个新增 Draw Call 使用相同顶点数
            vertex_counts: Dict[int, List] = {}
            for draw in added_draws:
                # DrawCallDiff 使用 vertex_count 字段
                vc = draw.vertex_count
                if vc > 0:
                    if vc not in vertex_counts:
                        vertex_counts[vc] = []
                    vertex_counts[vc].append(draw)
            
            for vc, draws in vertex_counts.items():
                if len(draws) > 1:
                    # 构建证据锚点列表
                    evidence_list = [
                        EvidenceAnchor(
                            event_id=d.event_id,
                            marker_path=d.marker_path,
                            description=d.name or f"{d.draw_type} (vertices={d.vertex_count})"
                        )
                        for d in draws
                    ]
                    
                    issues.append(RegressionIssue(
                        rule_id=RegressionRuleId.REG006,
                        severity=rule.severity,
                        message=f"检测到 {len(draws)} 个新增 Draw Call 具有相同顶点数 ({vc})，可能存在 Overdraw",
                        details=f"Event IDs: {[d.event_id for d in draws]}",
                        affected_resources=[str(d.event_id) for d in draws],
                        evidence=evidence_list,
                    ))
        
        return issues
    
    def _check_new_render_pass(self, diff: DiffResult) -> List[RegressionIssue]:
        """
        REG007: 检测新增渲染 Pass
        
        通过检测新增的使用不同渲染目标的 Draw Call 组来推断
        """
        rule = self.rules[RegressionRuleId.REG007]
        issues: List[RegressionIssue] = []
        
        # 获取新增的 Draw Calls
        added_draws = [d for d in diff.draw_call_diffs if d.status == DiffStatus.ADDED]
        
        if added_draws:
            # 按 marker_path 分组，推断 Pass 结构
            marker_groups: Dict[str, List] = {}
            for draw in added_draws:
                # 取 marker_path 的第一级作为分组依据
                marker_key = draw.marker_path.split("/")[0] if draw.marker_path else "(no marker)"
                if marker_key not in marker_groups:
                    marker_groups[marker_key] = []
                marker_groups[marker_key].append(draw)
            
            # 构建证据锚点列表 (限制前 10 个)
            evidence_list = [
                EvidenceAnchor(
                    event_id=d.event_id,
                    marker_path=d.marker_path,
                    description=d.name or f"{d.draw_type} (vertices={d.vertex_count})"
                )
                for d in added_draws[:10]
            ]
            
            # 生成详情
            pass_summary = ", ".join([f"{k}: {len(v)} DC" for k, v in marker_groups.items()])
            
            issues.append(RegressionIssue(
                rule_id=RegressionRuleId.REG007,
                severity=rule.severity,
                message=f"新增 {len(added_draws)} 个 Draw Call",
                details=f"按 Pass 分布: {pass_summary}" if len(marker_groups) > 1 else "可能表示新增了渲染 Pass 或功能",
                evidence=evidence_list,
            ))
        
        return issues
    
    def enable_rule(self, rule_id: RegressionRuleId, enabled: bool = True) -> None:
        """启用/禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
    
    def set_threshold(self, rule_id: RegressionRuleId, threshold: float) -> None:
        """设置规则阈值"""
        if rule_id in self.rules:
            self.rules[rule_id].threshold = threshold
    
    def set_severity(self, rule_id: RegressionRuleId, severity: RegressionSeverity) -> None:
        """设置规则严重程度"""
        if rule_id in self.rules:
            self.rules[rule_id].severity = severity
