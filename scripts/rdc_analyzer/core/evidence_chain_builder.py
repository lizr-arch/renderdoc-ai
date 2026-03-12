"""
证据链构建器 (M2.1)
===================

为每个 PerformanceIssue 生成完整的 EvidenceChain。
根据不同的规则 ID 生成对应的证据和操作。

使用示例:
    from core.evidence_chain_builder import EvidenceChainBuilder
    
    builder = EvidenceChainBuilder(usage_index)
    chain = builder.build(issue)
    issue.evidence_chain = chain
"""

from typing import Optional, Dict, Any, List
from .types import (
    EvidenceChain,
    ContextEvidence,
    Action,
    PerformanceIssue,
    ResourceUsageIndex,
)


class EvidenceChainBuilder:
    """
    证据链构建器
    
    根据 Issue 类型生成完整的证据链。
    支持的规则:
    - PERF001: 过度绘制
    - PERF002: 状态冗余
    - PERF003: 小批次绘制
    - PERF004: 大纹理
    - PERF005: 未压缩纹理
    - PERF006: Alpha 混合过度使用
    - PERF007: 频繁绑定
    """
    
    # 规则描述映射
    RULE_DESCRIPTIONS = {
        "PERF001": {
            "name": "过度绘制",
            "verification": "使用 RenderDoc 的 Quad Overdraw 可视化功能检查优化效果",
            "category": "overdraw"
        },
        "PERF002": {
            "name": "状态冗余",
            "verification": "减少状态切换后，检查帧时间是否下降",
            "category": "state"
        },
        "PERF003": {
            "name": "小批次绘制",
            "verification": "合并批次后，检查 Draw Call 数量是否减少",
            "category": "batch"
        },
        "PERF004": {
            "name": "大纹理",
            "verification": "降低纹理分辨率后，检查 VRAM 占用是否下降",
            "category": "texture"
        },
        "PERF005": {
            "name": "未压缩纹理",
            "verification": "使用压缩格式后，检查 VRAM 占用是否下降 50-75%",
            "category": "texture"
        },
        "PERF006": {
            "name": "Alpha 混合过度使用",
            "verification": "减少半透明对象后，检查 GPU 填充率指标",
            "category": "blend"
        },
        "PERF007": {
            "name": "频繁绑定",
            "verification": "使用 Bindless 或合并后，检查 API 调用次数",
            "category": "binding"
        },
    }
    
    def __init__(self, usage_index: Optional[ResourceUsageIndex] = None):
        """
        初始化构建器
        
        Args:
            usage_index: 资源使用索引，用于查找相关事件
        """
        self.usage_index = usage_index
    
    def build(self, issue: PerformanceIssue) -> EvidenceChain:
        """
        为 Issue 构建证据链
        
        Args:
            issue: 性能问题
            
        Returns:
            完整的证据链
        """
        rule_id = issue.rule_id
        
        # 创建基础证据链
        chain = EvidenceChain(
            issue_code=rule_id,
            summary=issue.message,
            impact_score=issue.impact_score,
        )
        
        # 根据规则类型调用对应的构建器
        builder_method = getattr(self, f"_build_{rule_id.lower()}", None)
        if builder_method:
            builder_method(chain, issue)
        else:
            # 通用构建逻辑
            self._build_generic(chain, issue)
        
        # 添加验证方案
        rule_info = self.RULE_DESCRIPTIONS.get(rule_id, {})
        chain.verification_plan = rule_info.get("verification", "")
        
        # 填充受影响的资源和事件
        if issue.resource_id:
            chain.affected_resources.append(issue.resource_id)
        if issue.related_events:
            chain.affected_events = issue.related_events[:20]  # 限制数量
        elif issue.event_id:
            chain.affected_events = [issue.event_id]
        
        return chain
    
    def _build_generic(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """通用证据链构建"""
        # 添加基础证据
        if issue.actual_value is not None:
            chain.add_evidence(
                label="实际值",
                value=issue.actual_value,
                threshold=issue.threshold_value,
                evidence_type="metric",
                severity="warning" if issue.severity == "warning" else "normal"
            )
        
        # 添加跳转操作
        if issue.resource_id:
            chain.add_action(
                action_type="jump_to_texture",
                label=f"查看资源 {issue.resource_id}",
                target_page="textures.html",
                target_id=issue.resource_id,
                highlight="true"
            )
    
    def _build_perf001(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF001: 过度绘制"""
        chain.summary = f"RenderTarget 被绘制 {issue.actual_value} 次，超过阈值 {issue.threshold_value}"
        
        # 添加证据
        chain.add_evidence(
            label="绘制次数",
            value=issue.actual_value,
            threshold=issue.threshold_value,
            unit="次",
            evidence_type="metric",
            severity="critical" if issue.actual_value > issue.threshold_value * 2 else "warning"
        )
        
        overdraw_ratio = (issue.actual_value / issue.threshold_value) if issue.threshold_value else 1.0
        chain.add_evidence(
            label="过度绘制倍数",
            value=f"{overdraw_ratio:.1f}x",
            evidence_type="metric",
            severity="warning"
        )
        
        # 添加 RT 跳转
        if issue.resource_id:
            chain.add_action(
                action_type="jump_to_texture",
                label=f"查看 RT {issue.resource_id}",
                target_page="textures.html",
                target_id=issue.resource_id,
                highlight="true"
            )
    
    def _build_perf002(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF002: 状态冗余"""
        chain.summary = f"连续 {issue.actual_value} 次设置相同状态"
        
        chain.add_evidence(
            label="冗余次数",
            value=issue.actual_value,
            threshold=issue.threshold_value,
            unit="次",
            evidence_type="metric",
            severity="warning"
        )
        
        if issue.event_range:
            start, end = issue.event_range
            chain.add_evidence(
                label="事件范围",
                value=f"#{start} - #{end}",
                evidence_type="state"
            )
    def _build_perf003(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF003: 小批次绘制"""
        chain.summary = f"绘制调用顶点数仅 {issue.actual_value}，低于阈值 {issue.threshold_value}"
        
        chain.add_evidence(
            label="顶点数",
            value=issue.actual_value,
            threshold=issue.threshold_value,
            unit="个",
            evidence_type="metric",
            severity="warning"
        )
        
    def _build_perf004(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF004: 大纹理"""
        chain.summary = f"纹理尺寸 {issue.actual_value}，超过推荐阈值 {issue.threshold_value}"
        
        chain.add_evidence(
            label="纹理尺寸",
            value=issue.actual_value,
            threshold=issue.threshold_value,
            unit="px",
            evidence_type="metric",
            severity="warning",
            resource_id=issue.resource_id
        )
        
        if issue.resource_id:
            chain.add_action(
                action_type="jump_to_texture",
                label=f"查看纹理 {issue.resource_id}",
                target_page="textures.html",
                target_id=issue.resource_id,
                highlight="true"
            )
            
            # 从 usage_index 获取使用该纹理的事件
            if self.usage_index:
                usages = self.usage_index.get_texture_usages(issue.resource_id)
                if usages:
                    chain.add_evidence(
                        label="被使用次数",
                        value=len(usages),
                        unit="次",
                        evidence_type="resource"
                    )
    def _build_perf005(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF005: 未压缩纹理"""
        chain.summary = f"纹理未使用压缩格式，浪费带宽和显存"
        
        chain.add_evidence(
            label="当前格式",
            value=str(issue.actual_value),
            evidence_type="state",
            severity="warning",
            resource_id=issue.resource_id
        )
        
        chain.add_evidence(
            label="推荐格式",
            value="BC1/BC3/BC7 (DXT)",
            evidence_type="state"
        )
        
        if issue.resource_id:
            chain.add_action(
                action_type="jump_to_texture",
                label=f"查看纹理 {issue.resource_id}",
                target_page="textures.html",
                target_id=issue.resource_id,
                highlight="true"
            )
    
    def _build_perf006(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF006: Alpha 混合过度使用"""
        chain.summary = f"Alpha 混合使用率 {issue.actual_value:.1%}，超过阈值 {issue.threshold_value:.1%}"
        
        chain.add_evidence(
            label="混合使用率",
            value=f"{issue.actual_value * 100:.1f}%",
            threshold=f"{issue.threshold_value * 100:.1f}%",
            evidence_type="metric",
            severity="warning"
        )
        
    def _build_perf007(self, chain: EvidenceChain, issue: PerformanceIssue) -> None:
        """PERF007: 频繁绑定"""
        chain.summary = f"资源被绑定 {issue.actual_value} 次，超过阈值 {issue.threshold_value}"
        
        chain.add_evidence(
            label="绑定次数",
            value=issue.actual_value,
            threshold=issue.threshold_value,
            unit="次",
            evidence_type="metric",
            severity="warning",
            resource_id=issue.resource_id
        )
        
        if issue.resource_id:
            chain.add_action(
                action_type="jump_to_texture",
                label=f"查看资源 {issue.resource_id}",
                target_page="textures.html",
                target_id=issue.resource_id,
                highlight="true"
            )
            
            # 从 usage_index 获取绑定事件
def build_evidence_chain(
    issue: PerformanceIssue,
    usage_index: Optional[ResourceUsageIndex] = None
) -> EvidenceChain:
    """
    便捷函数：为 Issue 构建证据链
    
    Args:
        issue: 性能问题
        usage_index: 资源使用索引
        
    Returns:
        证据链
    """
    builder = EvidenceChainBuilder(usage_index)
    return builder.build(issue)
