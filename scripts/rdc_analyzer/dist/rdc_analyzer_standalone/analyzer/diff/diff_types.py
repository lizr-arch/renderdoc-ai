"""
差异对比数据类型定义
===================

定义 DiffEngine 输出的所有数据结构。

TASK-010 实现
Created: 2026-01-20
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import json


class DiffStatus(Enum):
    """差异状态枚举"""
    UNCHANGED = "unchanged"  # 无变化
    ADDED = "added"          # 新增
    REMOVED = "removed"      # 删除
    MODIFIED = "modified"    # 修改
    

@dataclass
class MetricDiff:
    """
    数值指标差异
    
    用于对比 Draw Call 数量、内存使用等数值指标。
    """
    name: str
    baseline: float
    target: float
    
    @property
    def delta(self) -> float:
        """绝对差值"""
        return self.target - self.baseline
    
    @property
    def delta_percent(self) -> float:
        """百分比变化 (相对于 baseline)"""
        if self.baseline == 0:
            return 100.0 if self.target > 0 else 0.0
        return ((self.target - self.baseline) / self.baseline) * 100
    
    @property
    def status(self) -> DiffStatus:
        """变化状态"""
        if self.delta == 0:
            return DiffStatus.UNCHANGED
        return DiffStatus.MODIFIED
    
    @property
    def is_increase(self) -> bool:
        """是否增加"""
        return self.delta > 0
    
    @property
    def is_decrease(self) -> bool:
        """是否减少"""
        return self.delta < 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "baseline": self.baseline,
            "target": self.target,
            "delta": self.delta,
            "delta_percent": round(self.delta_percent, 2),
            "status": self.status.value,
        }


@dataclass
class ResourceDiff:
    """
    资源差异基类
    
    表示纹理、Buffer、Shader 等资源的变化。
    """
    resource_id: str
    name: str
    status: DiffStatus
    
    # 变化详情 (key: 字段名, value: (baseline, target))
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    
    def add_change(self, field_name: str, baseline: Any, target: Any):
        """记录一个字段的变化"""
        if baseline != target:
            self.changes[field_name] = (baseline, target)
    
    def to_dict(self) -> Dict[str, Any]:
        changes_dict = {}
        for k, (b, t) in self.changes.items():
            changes_dict[k] = {"baseline": b, "target": t}
        
        return {
            "resource_id": self.resource_id,
            "name": self.name,
            "status": self.status.value,
            "changes": changes_dict,
        }


@dataclass
class TextureDiff(ResourceDiff):
    """纹理差异"""
    width: int = 0
    height: int = 0
    format: str = ""
    memory_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "memory_size": self.memory_size,
        })
        return base


@dataclass
class ShaderDiff(ResourceDiff):
    """Shader 差异"""
    shader_type: str = ""  # VS, PS, CS, etc.
    hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "shader_type": self.shader_type,
            "hash": self.hash,
        })
        return base


@dataclass
class BufferDiff(ResourceDiff):
    """Buffer 差异"""
    size: int = 0
    usage: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "size": self.size,
            "usage": self.usage,
        })
        return base


@dataclass
class DrawCallDiff:
    """
    Draw Call 差异
    
    表示单个 Draw Call 的变化。
    """
    event_id: int
    status: DiffStatus
    
    # 匹配信息 (当 status 为 MODIFIED 时)
    matched_event_id: Optional[int] = None
    
    # 变化详情
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    
    # 基础属性
    draw_type: str = ""
    index_count: int = 0
    vertex_count: int = 0
    
    # 证据链属性 (用于跳转到 RenderDoc)
    marker_path: str = ""        # Debug Marker 路径
    name: str = ""               # Draw Call 名称/描述
    
    # 匹配类型 (P5-03: Marker 对齐增强)
    # - "marker+shader": Marker + Shader 复合签名匹配（最强）
    # - "marker_only": 仅 Marker 路径匹配
    # - "shader_fallback": 仅 Shader 签名匹配（回退）
    # - "order": 按顺序匹配
    match_type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        changes_dict = {}
        for k, (b, t) in self.changes.items():
            changes_dict[k] = {"baseline": b, "target": t}
        
        result = {
            "event_id": self.event_id,
            "status": self.status.value,
            "matched_event_id": self.matched_event_id,
            "draw_type": self.draw_type,
            "index_count": self.index_count,
            "vertex_count": self.vertex_count,
            "marker_path": self.marker_path,
            "name": self.name,
            "changes": changes_dict,
        }
        
        # 仅在有值时输出 match_type
        if self.match_type:
            result["match_type"] = self.match_type
        
        return result


@dataclass
class StateDiff:
    """
    渲染状态差异
    
    表示 Blend/Depth/Rasterizer 等状态的变化。
    """
    state_type: str  # blend | depth | rasterizer | viewport
    event_id: int
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        changes_dict = {}
        for k, (b, t) in self.changes.items():
            changes_dict[k] = {"baseline": b, "target": t}
        
        return {
            "state_type": self.state_type,
            "event_id": self.event_id,
            "changes": changes_dict,
        }


@dataclass
class SummaryDiff:
    """
    帧摘要差异
    
    汇总两帧之间的关键指标变化。
    """
    # 核心指标
    draw_calls: MetricDiff = field(default_factory=lambda: MetricDiff("draw_calls", 0, 0))
    dispatches: MetricDiff = field(default_factory=lambda: MetricDiff("dispatches", 0, 0))
    triangles: MetricDiff = field(default_factory=lambda: MetricDiff("triangles", 0, 0))
    vertices: MetricDiff = field(default_factory=lambda: MetricDiff("vertices", 0, 0))
    
    # 资源指标
    texture_count: MetricDiff = field(default_factory=lambda: MetricDiff("texture_count", 0, 0))
    buffer_count: MetricDiff = field(default_factory=lambda: MetricDiff("buffer_count", 0, 0))
    shader_count: MetricDiff = field(default_factory=lambda: MetricDiff("shader_count", 0, 0))
    
    # 内存指标 (字节)
    texture_memory: MetricDiff = field(default_factory=lambda: MetricDiff("texture_memory", 0, 0))
    buffer_memory: MetricDiff = field(default_factory=lambda: MetricDiff("buffer_memory", 0, 0))
    
    # 状态变更指标
    shader_changes: MetricDiff = field(default_factory=lambda: MetricDiff("shader_changes", 0, 0))
    rt_switches: MetricDiff = field(default_factory=lambda: MetricDiff("rt_switches", 0, 0))
    blend_changes: MetricDiff = field(default_factory=lambda: MetricDiff("blend_changes", 0, 0))
    depth_changes: MetricDiff = field(default_factory=lambda: MetricDiff("depth_changes", 0, 0))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "draw_calls": self.draw_calls.to_dict(),
            "dispatches": self.dispatches.to_dict(),
            "triangles": self.triangles.to_dict(),
            "vertices": self.vertices.to_dict(),
            "texture_count": self.texture_count.to_dict(),
            "buffer_count": self.buffer_count.to_dict(),
            "shader_count": self.shader_count.to_dict(),
            "texture_memory": self.texture_memory.to_dict(),
            "buffer_memory": self.buffer_memory.to_dict(),
            "shader_changes": self.shader_changes.to_dict(),
            "rt_switches": self.rt_switches.to_dict(),
            "blend_changes": self.blend_changes.to_dict(),
            "depth_changes": self.depth_changes.to_dict(),
        }
    
    def get_key_metrics(self) -> List[MetricDiff]:
        """获取所有关键指标列表"""
        return [
            self.draw_calls,
            self.dispatches,
            self.triangles,
            self.vertices,
            self.texture_count,
            self.buffer_count,
            self.shader_count,
            self.texture_memory,
            self.buffer_memory,
            self.shader_changes,
            self.rt_switches,
        ]


@dataclass
class DiffResult:
    """
    完整差异报告
    
    DiffEngine.compare() 的输出结果。
    """
    # 元信息
    baseline_file: str = ""
    target_file: str = ""
    api_type: str = ""
    
    # 差异摘要
    summary: SummaryDiff = field(default_factory=SummaryDiff)
    
    # 详细差异
    texture_diffs: List[TextureDiff] = field(default_factory=list)
    shader_diffs: List[ShaderDiff] = field(default_factory=list)
    buffer_diffs: List[BufferDiff] = field(default_factory=list)
    draw_call_diffs: List[DrawCallDiff] = field(default_factory=list)
    state_diffs: List[StateDiff] = field(default_factory=list)
    
    # 统计信息
    @property
    def textures_added(self) -> int:
        return sum(1 for t in self.texture_diffs if t.status == DiffStatus.ADDED)
    
    @property
    def textures_removed(self) -> int:
        return sum(1 for t in self.texture_diffs if t.status == DiffStatus.REMOVED)
    
    @property
    def textures_modified(self) -> int:
        return sum(1 for t in self.texture_diffs if t.status == DiffStatus.MODIFIED)
    
    @property
    def shaders_added(self) -> int:
        return sum(1 for s in self.shader_diffs if s.status == DiffStatus.ADDED)
    
    @property
    def shaders_removed(self) -> int:
        return sum(1 for s in self.shader_diffs if s.status == DiffStatus.REMOVED)
    
    @property
    def shaders_modified(self) -> int:
        return sum(1 for s in self.shader_diffs if s.status == DiffStatus.MODIFIED)
    
    @property
    def draw_calls_added(self) -> int:
        return sum(1 for d in self.draw_call_diffs if d.status == DiffStatus.ADDED)
    
    @property
    def draw_calls_removed(self) -> int:
        return sum(1 for d in self.draw_call_diffs if d.status == DiffStatus.REMOVED)
    
    @property
    def has_changes(self) -> bool:
        """是否有任何变化"""
        return (
            len(self.texture_diffs) > 0 or
            len(self.shader_diffs) > 0 or
            len(self.buffer_diffs) > 0 or
            len(self.draw_call_diffs) > 0 or
            len(self.state_diffs) > 0 or
            any(m.delta != 0 for m in self.summary.get_key_metrics())
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式 (用于 JSON 序列化)"""
        return {
            "baseline_file": self.baseline_file,
            "target_file": self.target_file,
            "api_type": self.api_type,
            "has_changes": self.has_changes,
            "summary": self.summary.to_dict(),
            "statistics": {
                "textures": {
                    "added": self.textures_added,
                    "removed": self.textures_removed,
                    "modified": self.textures_modified,
                },
                "shaders": {
                    "added": self.shaders_added,
                    "removed": self.shaders_removed,
                    "modified": self.shaders_modified,
                },
                "draw_calls": {
                    "added": self.draw_calls_added,
                    "removed": self.draw_calls_removed,
                },
            },
            "texture_diffs": [t.to_dict() for t in self.texture_diffs],
            "shader_diffs": [s.to_dict() for s in self.shader_diffs],
            "buffer_diffs": [b.to_dict() for b in self.buffer_diffs],
            "draw_call_diffs": [d.to_dict() for d in self.draw_call_diffs],
            "state_diffs": [s.to_dict() for s in self.state_diffs],
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiffResult":
        """从字典创建 DiffResult (反序列化)"""
        # TODO: 完整实现反序列化
        result = cls()
        result.baseline_file = data.get("baseline_file", "")
        result.target_file = data.get("target_file", "")
        result.api_type = data.get("api_type", "")
        return result
