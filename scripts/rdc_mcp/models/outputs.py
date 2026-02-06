"""
RDC MCP Server - Output Data Models
定义 MCP 工具返回的数据结构
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    """问题严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(str, Enum):
    """问题类别"""
    PERFORMANCE = "performance"
    TEXTURE = "texture"
    SHADER = "shader"
    MEMORY = "memory"
    CORRECTNESS = "correctness"


@dataclass
class CaptureInfo:
    """截帧基本信息"""
    session_id: str
    api: str
    frame_number: int
    device: str
    action_count: int
    texture_count: int
    buffer_count: int
    rdc_path: str = ""


@dataclass
class ActionInfo:
    """绘制调用信息"""
    eid: int
    name: str
    flags: list[str] = field(default_factory=list)
    num_indices: int = 0
    num_instances: int = 1
    vertex_offset: int = 0
    index_offset: int = 0


@dataclass
class ActionDetail(ActionInfo):
    """绘制调用详细信息"""
    outputs: list[dict] = field(default_factory=list)
    depth_output: Optional[dict] = None


@dataclass
class ActionListResult:
    """Action 列表查询结果"""
    total: int
    count: int
    offset: int
    has_more: bool
    actions: list[ActionInfo] = field(default_factory=list)


@dataclass
class TextureInfo:
    """纹理信息"""
    resource_id: int
    name: str
    width: int
    height: int
    depth: int = 1
    mips: int = 1
    array_size: int = 1
    format: str = ""
    texture_type: str = "Texture2D"


@dataclass
class TextureListResult:
    """纹理列表查询结果"""
    total: int
    count: int
    textures: list[TextureInfo] = field(default_factory=list)


@dataclass
class BufferInfo:
    """缓冲区信息"""
    resource_id: int
    name: str
    length: int
    usage: str = ""


@dataclass
class BufferListResult:
    """缓冲区列表查询结果"""
    total: int
    count: int
    buffers: list[BufferInfo] = field(default_factory=list)


@dataclass
class AnalysisSummary:
    """分析摘要"""
    total_events: int = 0
    draw_call_count: int = 0
    total_vertices: int = 0
    total_triangles: int = 0
    texture_count: int = 0
    buffer_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    summary: AnalysisSummary
    report_path: str = ""
    output_files: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: str = ""


@dataclass
class Issue:
    """检测到的问题"""
    id: str
    severity: str
    category: str
    title: str
    description: str
    event_id: Optional[int] = None
    resource_id: Optional[int] = None
    suggestion: str = ""


@dataclass
class IssueListResult:
    """问题列表结果"""
    total: int
    issues: list[Issue] = field(default_factory=list)


@dataclass
class Hotspot:
    """性能热点"""
    rank: int
    event_id: int
    name: str
    value: float
    percentage: float
    cumulative_percentage: float


@dataclass
class HotspotListResult:
    """热点列表结果"""
    metric: str
    hotspots: list[Hotspot] = field(default_factory=list)


@dataclass
class ExportResult:
    """导出结果"""
    success: bool
    output_path: str = ""
    size_bytes: int = 0
    error_message: str = ""


@dataclass
class ErrorResult:
    """错误响应"""
    error: bool = True
    error_type: str = ""
    message: str = ""
    suggestion: str = ""
