"""
Report Data Contract - 统一的报告数据契约 v2.1

此模块定义了所有报告类型的统一数据格式，用于解耦数据层和展示层。

Changes from v2.0:
    - 新增 MetaData dataclass
    - 新增扩展字段（duplicate_analysis, usage_analysis 等）
    - 对齐 generate_offline_html() 的所有参数

Usage:
    from rdc_analyzer.report_engine.contract import ReportDataContract, build_manifest
    
    report = ReportDataContract(
        meta=MetaData(capture_name="test.rdc", api="D3D11"),
        textures=[...],
        events=[...]
    )
    manifest = build_manifest(report)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Protocol, Tuple
from datetime import datetime


@dataclass
class MetaData:
    """报告元信息"""
    capture_name: str = ""
    api: str = "Unknown"           # D3D11, D3D12, Vulkan, OpenGL
    source: str = "unknown"        # rdc, xml, json
    generated_at: str = ""
    frame_thumbnail: str = ""      # Base64 图像数据
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_name": self.capture_name,
            "api": self.api,
            "source": self.source,
            "generated_at": self.generated_at,
            "frame_thumbnail": self.frame_thumbnail,
        }


@dataclass
class ReportDataContract:
    """
    统一的报告数据契约 v2.1
    
    所有报告生成器都应输出此格式的数据，
    UI Shell 只需根据此契约渲染，无需关心数据来源。
    
    Attributes:
        meta: 元数据（capture 名称、API 类型、生成时间等）
        textures: 纹理资源列表
        shaders: Shader 资源列表
        events: 事件/Draw Call 列表
        buffers: Buffer 资源列表
        issues: 检测到的问题列表
        performance: 性能统计数据
        pipeline_states: Pipeline State 数据
        
        # 扩展字段 (v2.1)
        duplicate_analysis: 重复分析结果
        usage_analysis: 纹理热度分析
        event_pass_data: Event/Pass 数据
        optimization_data: 优化建议
        rt_tracking_data: RT 追踪数据
        hotspot_data: 热点分析数据
        texture_usage_map: 纹理使用映射
        report_links: 报告链接
        manifest_data: Manifest 数据
    """
    
    # --- 核心字段 (v2.0) ---
    meta: MetaData = field(default_factory=MetaData)
    textures: List[Dict[str, Any]] = field(default_factory=list)
    shaders: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    buffers: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    pipeline_states: List[Dict[str, Any]] = field(default_factory=list)
    
    # --- 扩展字段 (v2.1, 对应 generate_offline_html 参数) ---
    duplicate_analysis: Dict[str, Any] = field(default_factory=dict)
    usage_analysis: Dict[str, Any] = field(default_factory=dict)
    event_pass_data: Dict[str, Any] = field(default_factory=dict)
    optimization_data: Dict[str, Any] = field(default_factory=dict)
    rt_tracking_data: Dict[str, Any] = field(default_factory=dict)
    hotspot_data: Dict[str, Any] = field(default_factory=dict)
    texture_usage_map: Dict[str, Any] = field(default_factory=dict)
    report_links: Dict[str, str] = field(default_factory=dict)
    manifest_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于 JSON 序列化"""
        return {
            "meta": self.meta.to_dict() if isinstance(self.meta, MetaData) else self.meta,
            "textures": self.textures,
            "shaders": self.shaders,
            "events": self.events,
            "buffers": self.buffers,
            "issues": self.issues,
            "performance": self.performance,
            "pipeline_states": self.pipeline_states,
            "duplicate_analysis": self.duplicate_analysis,
            "usage_analysis": self.usage_analysis,
            "event_pass_data": self.event_pass_data,
            "optimization_data": self.optimization_data,
            "rt_tracking_data": self.rt_tracking_data,
            "hotspot_data": self.hotspot_data,
            "texture_usage_map": self.texture_usage_map,
            "report_links": self.report_links,
            "manifest_data": self.manifest_data,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportDataContract":
        """从字典创建实例"""
        meta_data = data.get("meta", {})
        if isinstance(meta_data, dict):
            meta = MetaData(
                capture_name=meta_data.get("capture_name", ""),
                api=meta_data.get("api", "Unknown"),
                source=meta_data.get("source", "unknown"),
                generated_at=meta_data.get("generated_at", ""),
                frame_thumbnail=meta_data.get("frame_thumbnail", ""),
            )
        else:
            meta = meta_data
            
        return cls(
            meta=meta,
            textures=data.get("textures", []),
            shaders=data.get("shaders", []),
            events=data.get("events", []),
            buffers=data.get("buffers", []),
            issues=data.get("issues", []),
            performance=data.get("performance", {}),
            pipeline_states=data.get("pipeline_states", []),
            duplicate_analysis=data.get("duplicate_analysis", {}),
            usage_analysis=data.get("usage_analysis", {}),
            event_pass_data=data.get("event_pass_data", {}),
            optimization_data=data.get("optimization_data", {}),
            rt_tracking_data=data.get("rt_tracking_data", {}),
            hotspot_data=data.get("hotspot_data", {}),
            texture_usage_map=data.get("texture_usage_map", {}),
            report_links=data.get("report_links", {}),
            manifest_data=data.get("manifest_data", {}),
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
    
    # 获取 meta 数据
    meta = report.meta
    if isinstance(meta, MetaData):
        capture_name = meta.capture_name
        api = meta.api
        source = meta.source
    else:
        capture_name = meta.get("capture_name", "Unknown")
        api = meta.get("api", "Unknown")
        source = meta.get("source", "unknown")
    
    # 构建 Manifest
    manifest = {
        "version": "2.1",
        "generated_at": datetime.now().isoformat(),
        "counts": counts,
        "coverage": coverage,
        "issue_stats": issue_stats,
        "meta": {
            "capture_name": capture_name,
            "api": api,
            "source": source,
        },
    }
    
    return manifest


def validate_manifest(manifest: Dict[str, Any], min_coverage: float = 0.5) -> Tuple[bool, str]:
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


# --- Protocol 定义 ---

class DataAdapter(Protocol):
    """数据适配器协议"""
    def load(self, source: Any) -> ReportDataContract:
        """从数据源加载并返回 Contract"""
        ...


class SectionRenderer(Protocol):
    """Section 渲染器协议"""
    def render(self, contract: ReportDataContract) -> str:
        """渲染并返回 HTML 片段"""
        ...
