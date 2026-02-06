"""
证据链构建器 (M2.2)
==================

为不同类型的性能问题构建完整的证据链。

用法:
    from core.evidence_builder import EvidenceBuilder
    
    # 为超大纹理构建证据链
    chain = EvidenceBuilder.for_oversized_texture(
        texture_info=tex,
        usage_index=resource_usage_index,
        threshold_dimension=4096
    )
    
    # 将证据链附加到 Issue
    issue.evidence_chain = chain
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .types import (
    EvidenceChain,
    ContextEvidence,
    Action,
    TextureInfo,
    ShaderInfo,
    ResourceUsageIndex,
    UsageRecord,
)


class EvidenceBuilder:
    """
    证据链构建器
    
    提供静态工厂方法，为不同类型的性能问题构建证据链。
    每个方法遵循统一的模式：
    1. 收集量化证据（actual vs threshold）
    2. 提取上下文（使用位置、影响范围）
    3. 生成操作按钮（跳转到相关页面）
    4. 计算影响评分
    """
    
    # ========================================================================
    # M2.2.2: 超大纹理证据链
    # ========================================================================
    
    @staticmethod
    def for_oversized_texture(
        texture_info: TextureInfo,
        usage_index: Optional[ResourceUsageIndex] = None,
        threshold_dimension: int = 4096,
        threshold_memory_mb: float = 64.0
    ) -> EvidenceChain:
        """
        构建超大纹理问题的证据链 (PERF004)
        
        Args:
            texture_info: 纹理信息
            usage_index: 资源使用索引（用于查找使用位置）
            threshold_dimension: 尺寸阈值（像素）
            threshold_memory_mb: 内存阈值（MB）
        
        Returns:
            完整的证据链对象
        """
        tex_id = texture_info.resource_id
        width = texture_info.width
        height = texture_info.height
        memory_mb = texture_info.memory_size / (1024 * 1024) if texture_info.memory_size else 0
        max_dim = max(width, height)
        
        # 创建证据链
        chain = EvidenceChain(
            issue_code="PERF004",
            summary=f"纹理 {texture_info.name or tex_id} 尺寸过大 ({width}×{height})",
            affected_resources=[tex_id],
        )
        
        # 添加尺寸证据
        dim_severity = "critical" if max_dim >= threshold_dimension * 2 else (
            "warning" if max_dim >= threshold_dimension else "normal"
        )
        chain.add_evidence(
            label="纹理尺寸",
            value=f"{width}×{height}",
            threshold=f"{threshold_dimension}×{threshold_dimension}",
            unit="px",
            evidence_type="metric",
            severity=dim_severity,
            resource_id=tex_id
        )
        
        # 添加内存证据
        if memory_mb > 0:
            mem_severity = "critical" if memory_mb >= threshold_memory_mb * 2 else (
                "warning" if memory_mb >= threshold_memory_mb else "normal"
            )
            chain.add_evidence(
                label="显存占用",
                value=round(memory_mb, 2),
                threshold=threshold_memory_mb,
                unit="MB",
                evidence_type="metric",
                severity=mem_severity,
                resource_id=tex_id
            )
        
        # 添加格式证据
        if texture_info.format:
            fmt = texture_info.format
            is_compressed = any(x in fmt.upper() for x in ["BC", "DXT", "ASTC", "ETC"])
            chain.add_evidence(
                label="纹理格式",
                value=fmt,
                evidence_type="state",
                severity="normal" if is_compressed else "warning",
                resource_id=tex_id
            )
        
        # 从使用索引获取使用位置
        if usage_index:
            usages = usage_index.get_texture_usages(tex_id)
            if usages:
                chain.affected_events = [u.event_id for u in usages]
                
                # 添加使用次数证据
                chain.add_evidence(
                    label="绑定次数",
                    value=len(usages),
                    evidence_type="metric",
                )
                
                # 为前 3 个使用位置添加跳转操作
                for i, usage in enumerate(usages[:3]):
                    chain.add_action(
                        action_type="jump_to_event",
                        label=f"跳转到 Event #{usage.event_id}",
                        target_page="events.html",
                        target_id=str(usage.event_id),
                        highlight="true"
                    )
        
        # 添加查看纹理详情的操作
        chain.add_action(
            action_type="jump_to_texture",
            label="查看纹理详情",
            target_page="textures.html",
            target_id=tex_id,
            highlight="true"
        )
        
        # 计算影响评分 (基于尺寸和内存)
        dim_score = min(100, (max_dim / threshold_dimension) * 50)
        mem_score = min(100, (memory_mb / threshold_memory_mb) * 50) if memory_mb > 0 else 0
        chain.impact_score = min(100, dim_score + mem_score)
        
        # 验证方案
        chain.verification_plan = (
            f"1. 检查纹理 '{texture_info.name or tex_id}' 是否需要如此高分辨率\n"
            f"2. 考虑降低分辨率到 {threshold_dimension}×{threshold_dimension} 或使用 mipmap\n"
            f"3. 如果是 UI 纹理，确认是否需要支持 4K 显示器"
        )
        
        return chain
    
    # ========================================================================
    # M2.2.3: 冗余绑定证据链
    # ========================================================================
    
    @staticmethod
    def for_redundant_binding(
        resource_id: str,
        resource_name: str,
        binding_events: List[int],
        threshold_count: int = 10,
        usage_index: Optional[ResourceUsageIndex] = None
    ) -> EvidenceChain:
        """
        构建冗余绑定问题的证据链 (PERF007)
        
        Args:
            resource_id: 资源 ID
            resource_name: 资源名称
            binding_events: 绑定该资源的事件 ID 列表
            threshold_count: 绑定次数阈值
            usage_index: 资源使用索引
        
        Returns:
            完整的证据链对象
        """
        bind_count = len(binding_events)
        
        chain = EvidenceChain(
            issue_code="PERF007",
            summary=f"资源 {resource_name or resource_id} 被绑定 {bind_count} 次，超过阈值 {threshold_count}",
            affected_resources=[resource_id],
            affected_events=binding_events,
        )
        
        # 添加绑定次数证据
        severity = "critical" if bind_count >= threshold_count * 3 else (
            "warning" if bind_count >= threshold_count else "normal"
        )
        chain.add_evidence(
            label="绑定次数",
            value=bind_count,
            threshold=threshold_count,
            unit="次",
            evidence_type="metric",
            severity=severity,
            resource_id=resource_id
        )
        
        # 分析绑定模式（连续 vs 分散）
        if len(binding_events) >= 2:
            sorted_events = sorted(binding_events)
            gaps = [sorted_events[i+1] - sorted_events[i] for i in range(len(sorted_events)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            pattern = "密集" if avg_gap < 5 else ("分散" if avg_gap > 20 else "中等")
            chain.add_evidence(
                label="绑定模式",
                value=pattern,
                evidence_type="state",
                severity="normal" if pattern == "密集" else "warning"
            )
            
            chain.add_evidence(
                label="平均间隔",
                value=round(avg_gap, 1),
                unit="事件",
                evidence_type="metric"
            )
        
        # 添加跳转到热点事件的操作
        if binding_events:
            # 跳转到第一个绑定事件
            chain.add_action(
                action_type="jump_to_event",
                label=f"跳转到首次绑定 (Event #{binding_events[0]})",
                target_page="events.html",
                target_id=str(binding_events[0]),
                highlight="true"
            )
            
            # 跳转到中间事件（热点）
            mid_idx = len(binding_events) // 2
            if mid_idx > 0:
                chain.add_action(
                    action_type="jump_to_event",
                    label=f"跳转到中间绑定 (Event #{binding_events[mid_idx]})",
                    target_page="events.html",
                    target_id=str(binding_events[mid_idx]),
                    highlight="true"
                )
        
        # 计算影响评分
        chain.impact_score = min(100, (bind_count / threshold_count) * 30)
        
        # 验证方案
        chain.verification_plan = (
            f"1. 检查资源 '{resource_name or resource_id}' 是否可以合并到纹理图集\n"
            f"2. 考虑使用 Bindless 资源避免频繁绑定\n"
            f"3. 按材质排序 Draw Call 以减少状态切换"
        )
        
        return chain
    
    # ========================================================================
    # M2.2.4: 高指令数 Shader 证据链
    # ========================================================================
    
    @staticmethod
    def for_high_instruction_shader(
        shader_info: ShaderInfo,
        instruction_count: int,
        threshold_count: int = 500,
        mali_result: Optional[Dict[str, Any]] = None,
        usage_index: Optional[ResourceUsageIndex] = None
    ) -> EvidenceChain:
        """
        构建高指令数 Shader 问题的证据链
        
        Args:
            shader_info: Shader 信息
            instruction_count: 指令数
            threshold_count: 指令数阈值
            mali_result: Mali Offline Compiler 分析结果（可选）
            usage_index: 资源使用索引
        
        Returns:
            完整的证据链对象
        """
        shader_id = shader_info.resource_id
        shader_type = shader_info.type or shader_info.stage or "Unknown"
        shader_name = shader_info.name or shader_id
        
        chain = EvidenceChain(
            issue_code="SHADER001",
            summary=f"{shader_type} Shader '{shader_name}' 指令数过高 ({instruction_count})",
            affected_resources=[shader_id],
        )
        
        # 添加指令数证据
        severity = "critical" if instruction_count >= threshold_count * 2 else (
            "warning" if instruction_count >= threshold_count else "normal"
        )
        chain.add_evidence(
            label="指令数",
            value=instruction_count,
            threshold=threshold_count,
            unit="条",
            evidence_type="metric",
            severity=severity,
            resource_id=shader_id
        )
        
        # 添加 Shader 类型证据
        chain.add_evidence(
            label="Shader 类型",
            value=shader_type,
            evidence_type="state",
            resource_id=shader_id
        )
        
        # 如果有 Mali 分析结果，添加详细指标
        if mali_result:
            cycles = mali_result.get("cycles", {})
            if cycles:
                total_cycles = cycles.get("total", 0) or cycles.get("longest_path", 0)
                if total_cycles:
                    chain.add_evidence(
                        label="GPU Cycles",
                        value=total_cycles,
                        unit="cycles",
                        evidence_type="metric",
                        severity="warning" if total_cycles > 100 else "normal"
                    )
            
            bound = mali_result.get("bound", "")
            if bound:
                bound_names = {
                    "arithmetic": "计算受限",
                    "texture": "纹理受限",
                    "load_store": "带宽受限",
                    "varying": "插值受限"
                }
                chain.add_evidence(
                    label="性能瓶颈",
                    value=bound_names.get(bound, bound),
                    evidence_type="state",
                    severity="warning"
                )
            
            # 寄存器使用
            registers = mali_result.get("registers", {})
            if registers:
                work_regs = registers.get("work", 0)
                uniform_regs = registers.get("uniform", 0)
                if work_regs:
                    chain.add_evidence(
                        label="工作寄存器",
                        value=work_regs,
                        unit="个",
                        evidence_type="metric",
                        severity="warning" if work_regs > 32 else "normal"
                    )
        
        # 从使用索引获取使用位置
        if usage_index:
            usages = usage_index.get_shader_usages(shader_id)
            if usages:
                chain.affected_events = [u.event_id for u in usages]
                chain.add_evidence(
                    label="使用次数",
                    value=len(usages),
                    unit="次",
                    evidence_type="metric"
                )
                
                # 添加跳转操作
                for i, usage in enumerate(usages[:2]):
                    chain.add_action(
                        action_type="jump_to_event",
                        label=f"跳转到 Event #{usage.event_id}",
                        target_page="events.html",
                        target_id=str(usage.event_id),
                        highlight="true"
                    )
        
        # 添加查看 Shader 详情的操作
        chain.add_action(
            action_type="jump_to_shader",
            label="查看 Shader 详情",
            target_page="shaders.html",
            target_id=shader_id,
            highlight="true"
        )
        
        # 计算影响评分
        base_score = min(50, (instruction_count / threshold_count) * 25)
        usage_multiplier = 1.0
        if usage_index:
            usages = usage_index.get_shader_usages(shader_id)
            usage_multiplier = min(2.0, 1.0 + len(usages) / 100)
        chain.impact_score = min(100, base_score * usage_multiplier)
        
        # 验证方案
        chain.verification_plan = (
            f"1. 检查 Shader '{shader_name}' 是否有冗余计算\n"
            f"2. 考虑将复杂计算移到顶点着色器或预计算\n"
            f"3. 使用 LOD 或简化版 Shader 用于远距离物体"
        )
        
        return chain
    
    # ========================================================================
    # M2.2.5: 通用问题证据链（适用于未定义专用构建器的问题）
    # ========================================================================
    
    @staticmethod
    def for_generic_issue(
        issue_code: str,
        message: str,
        actual_value: Any = None,
        threshold_value: Any = None,
        resource_ids: List[str] = None,
        event_ids: List[int] = None,
        suggestion: str = ""
    ) -> EvidenceChain:
        """
        构建通用问题的证据链
        
        Args:
            issue_code: 规则 ID
            message: 问题描述
            actual_value: 实际值
            threshold_value: 阈值
            resource_ids: 相关资源 ID 列表
            event_ids: 相关事件 ID 列表
            suggestion: 修复建议
        
        Returns:
            证据链对象
        """
        chain = EvidenceChain(
            issue_code=issue_code,
            summary=message,
            affected_resources=resource_ids or [],
            affected_events=event_ids or [],
        )
        
        # 添加值对比证据
        if actual_value is not None:
            chain.add_evidence(
                label="实际值",
                value=actual_value,
                threshold=threshold_value,
                evidence_type="metric",
                severity="warning" if threshold_value and actual_value > threshold_value else "normal"
            )
        
        # 添加跳转操作
        if event_ids:
            chain.add_action(
                action_type="jump_to_event",
                label=f"跳转到 Event #{event_ids[0]}",
                target_page="events.html",
                target_id=str(event_ids[0]),
                highlight="true"
            )
        
        if resource_ids:
            chain.add_action(
                action_type="jump_to_resource",
                label="查看相关资源",
                target_page="textures.html",
                target_id=resource_ids[0],
                highlight="true"
            )
        
        # 验证方案
        if suggestion:
            chain.verification_plan = suggestion
        
        return chain


# ============================================================================
# 辅助函数
# ============================================================================

def attach_evidence_to_issue(issue, evidence_chain: EvidenceChain) -> None:
    """
    将证据链附加到 Issue 对象
    
    Args:
        issue: Issue 或 PerformanceIssue 对象
        evidence_chain: 证据链
    """
    if hasattr(issue, 'evidence_chain'):
        issue.evidence_chain = evidence_chain
    elif hasattr(issue, 'evidence'):
        # 对于 CanonicalIssue，将证据链存入 evidence 字典
        if isinstance(issue.evidence, dict):
            issue.evidence['evidence_chain'] = evidence_chain.to_dict()
        else:
            issue.evidence = {'evidence_chain': evidence_chain.to_dict()}
