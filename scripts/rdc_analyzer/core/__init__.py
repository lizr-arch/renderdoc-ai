"""
RDC Analyzer Core Module
========================

核心分析组件，包含数据类型、证据链构建器、资源索引等。
"""

# 数据类型
from .types import (
    # 基础资源类型
    TextureInfo,
    BufferInfo,
    ShaderInfo,
    ShaderInfoBasic,
    PassInfo,
    RenderPassInfo,
    DrawCallInfo,
    
    # 问题类型
    Issue,
    CanonicalIssue,
    PerformanceIssue,
    
    # 性能分析
    PerformanceMetrics,
    PerformanceReport,
    PerformanceRule,
    PERFORMANCE_RULES,
    
    # 资源索引 (M1)
    UsageRecord,
    ResourceUsageIndex,
    
    # 证据链 (M2)
    EvidenceChain,
    ContextEvidence,
    Action,
    
    # 解析数据
    ParsedData,
    FrameSummary,
)

# 证据链构建器 (M2.2)
from .evidence_builder import (
    EvidenceBuilder,
    attach_evidence_to_issue,
)

# 资源使用索引构建器 (M1.2)
try:
    from .resource_usage_builder import ResourceUsageBuilder
except ImportError:
    ResourceUsageBuilder = None  # 可选依赖

__all__ = [
    # 基础类型
    "TextureInfo",
    "BufferInfo", 
    "ShaderInfo",
    "ShaderInfoBasic",
    "PassInfo",
    "RenderPassInfo",
    "DrawCallInfo",
    
    # 问题类型
    "Issue",
    "CanonicalIssue",
    "PerformanceIssue",
    
    # 性能分析
    "PerformanceMetrics",
    "PerformanceReport",
    "PerformanceRule",
    "PERFORMANCE_RULES",
    
    # 资源索引
    "UsageRecord",
    "ResourceUsageIndex",
    "ResourceUsageBuilder",
    
    # 证据链
    "EvidenceChain",
    "ContextEvidence",
    "Action",
    "EvidenceBuilder",
    "attach_evidence_to_issue",
    
    # 解析数据
    "ParsedData",
    "FrameSummary",
]