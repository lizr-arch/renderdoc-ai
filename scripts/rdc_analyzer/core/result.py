"""
分析结果定义
============

包含帧摘要和完整分析结果的数据类。
"""

from dataclasses import dataclass, field
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import TextureInfo, BufferInfo, PassInfo, Issue, FrameSummary, PerformanceReport


@dataclass
class AnalysisResult:
    """完整分析结果"""
    # 元数据
    file_path: str = ""
    api: str = ""
    platform: str = "pc"
    parse_mode: str = "api"  # api | binary
    
    # 帧摘要 - 使用 types.py 中定义的 FrameSummary
    frame_summary: "FrameSummary" = None  # type: ignore
    
    # 资源列表
    textures: List["TextureInfo"] = field(default_factory=list)
    buffers: List["BufferInfo"] = field(default_factory=list)
    passes: List["PassInfo"] = field(default_factory=list)
    
    # 检测到的问题
    issues: List["Issue"] = field(default_factory=list)
    
    # 动态属性 (由 PerformanceAnalyzer 使用)
    draws: List = field(default_factory=list)
    dispatches: List = field(default_factory=list)
    shaders: List = field(default_factory=list)
    
    # 性能报告 (C.2)
    performance_report: "PerformanceReport" = None  # type: ignore
    
    def __post_init__(self):
        """初始化后处理"""
        if self.frame_summary is None:
            from .types import FrameSummary
            self.frame_summary = FrameSummary()
