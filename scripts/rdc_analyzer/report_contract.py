"""
Report Data Contract - 统一的报告数据契约

此模块定义了所有报告类型的统一数据格式和 Manifest 构建逻辑。
用于解耦数据层（Python 解析器）和展示层（HTML/JS）。

Usage:
    from report_contract import ReportDataContract, build_manifest
    
    report = ReportDataContract(
        meta={"capture_name": "test.rdc"},
        textures=[...],
        events=[...]
    )
    manifest = build_manifest(report)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ReportDataContract:
    """
    统一的报告数据契约
    
    所有报告生成器（V3/Offline/XML）都应输出此格式的数据，
    UI Shell 只需根据此契约渲染，无需关心数据来源。
    
    Attributes:
        meta: 元数据（capture 名称、API 类型、生成时间等）
        textures: 纹理资源列表
        shaders: Shader 资源列表
        events: 事件/Draw Call 列表
        buffers: Buffer 资源列表
        issues: 检测到的问题列表
        performance: 性能统计数据
        pipeline_states: Pipeline State 数据（可选）
    """
    meta: Dict[str, Any] = field(default_factory=dict)
    textures: List[Dict[str, Any]] = field(default_factory=list)
    shaders: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    buffers: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    pipeline_states: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于 JSON 序列化"""
        return {
            "meta": self.meta,
            "textures": self.textures,
            "shaders": self.shaders,
            "events": self.events,
            "buffers": self.buffers,
            "issues": self.issues,
            "performance": self.performance,
            "pipeline_states": self.pipeline_states,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportDataContract":
        """从字典创建实例"""
        return cls(
            meta=data.get("meta", {}),
            textures=data.get("textures", []),
            shaders=data.get("shaders", []),
            events=data.get("events", []),
            buffers=data.get("buffers", []),
            issues=data.get("issues", []),
            performance=data.get("performance", {}),
            pipeline_states=data.get("pipeline_states", []),
        )


def build_manifest(report: ReportDataContract) -> Dict[str, Any]:
    """
    构建报告 Manifest，统计字段覆盖率
    
    Manifest 用于：
    1. 统计各数据字段的数量
    2. 计算数据覆盖率（非空字段占比）
    3. 标识数据来源和生成时间
    4. 供 UI 显示状态栏和校验
    
    Args:
        report: ReportDataContract 实例
        
    Returns:
        包含统计信息的 Manifest 字典
        
    Example:
        >>> report = ReportDataContract(textures=[{"name": "t1"}])
        >>> manifest = build_manifest(report)
        >>> manifest["counts"]["textures"]
        1
    """
    # 统计各字段数量
    counts = {
        "textures": len(report.textures),
        "shaders": len(report.shaders),
        "events": len(report.events),
        "buffers": len(report.buffers),
        "issues": len(report.issues),
        "pipeline_states": len(report.pipeline_states),
    }
    
    # 计算覆盖率：非空字段数 / 总字段数
    non_empty = sum(1 for v in counts.values() if v > 0)
    total_fields = len(counts)
    coverage = non_empty / total_fields if total_fields > 0 else 0.0
    
    # 统计问题严重程度分布
    issue_stats = {
        "critical": 0,
        "warning": 0,
        "info": 0,
        "pass": 0,
    }
    for issue in report.issues:
        severity = issue.get("severity", "info")
        if severity in issue_stats:
            issue_stats[severity] += 1
    
    # 构建 Manifest
    manifest = {
        "version": "2.0",
        "generated_at": datetime.now().isoformat(),
        "counts": counts,
        "coverage": coverage,
        "issue_stats": issue_stats,
        "meta": {
            "capture_name": report.meta.get("capture_name", "Unknown"),
            "api": report.meta.get("api", "Unknown"),
            "source": report.meta.get("source", "unknown"),
        },
    }
    
    return manifest


def validate_manifest(manifest: Dict[str, Any], min_coverage: float = 0.5) -> tuple:
    """
    验证 Manifest 是否满足最低覆盖率要求
    
    Args:
        manifest: build_manifest() 返回的 Manifest
        min_coverage: 最低覆盖率阈值，默认 0.5 (50%)
        
    Returns:
        (is_valid: bool, message: str) 元组
    """
    coverage = manifest.get("coverage", 0.0)
    
    if coverage < min_coverage:
        empty_fields = [
            k for k, v in manifest.get("counts", {}).items() if v == 0
        ]
        return (
            False,
            f"覆盖率不足: {coverage:.0%} < {min_coverage:.0%}，"
            f"空字段: {', '.join(empty_fields)}"
        )
    
    return (True, f"覆盖率通过: {coverage:.0%}")
