"""
分析上下文
==========

贯穿整个分析流程的共享状态容器。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .types import (
    TextureInfo,
    BufferInfo,
    ShaderInfo,
    PassInfo,
    DrawCallInfo,
    Issue,
    FrameSummary,
    ParsedData,
    PerformanceReport,
)
from .result import AnalysisResult


@dataclass
class AnalysisContext:
    """
    分析上下文 (贯穿整个分析流程的共享状态)
    
    - 由 Parser 创建，包含 ParsedData
    - 由各 Analyzer 填充分析结果
    - 由 Rule 读取数据进行检测
    - 最终转换为 AnalysisResult
    """
    # 原始解析数据
    parsed: ParsedData = field(default_factory=ParsedData)
    
    # 平台配置
    platform: str = "pc"
    thresholds: Dict[str, Any] = field(default_factory=dict)
    
    # 分析结果 (由各 Analyzer 填充)
    frame_summary: FrameSummary = field(default_factory=FrameSummary)
    textures: List[TextureInfo] = field(default_factory=list)
    buffers: List[BufferInfo] = field(default_factory=list)
    shaders: List[ShaderInfo] = field(default_factory=list)
    draw_calls: List[DrawCallInfo] = field(default_factory=list)
    passes: List[PassInfo] = field(default_factory=list)  # 渲染 Pass 列表
    
    # 状态历史 (供规则检测)
    state_history: List[Dict] = field(default_factory=list)
    
    # 状态跟踪 (供分析器共享)
    _marker_stack: List[str] = field(default_factory=list)
    _rt_usage: Dict[str, int] = field(default_factory=dict)
    _rt_clear_counts: Dict[str, int] = field(default_factory=dict)
    _shader_bind_counts: Dict[str, int] = field(default_factory=dict)
    _texture_bind_counts: Dict[str, int] = field(default_factory=dict)
    _buffer_bind_counts: Dict[str, int] = field(default_factory=dict)
    
    # 性能报告 (由 PerformanceAnalyzer 填充)
    performance_report: Optional[PerformanceReport] = None
    
    # 兼容性: 提供 result 属性供 PerformanceAnalyzer 访问
    @property
    def result(self) -> "AnalysisResult":
        """获取结果对象 (供 PerformanceAnalyzer 使用)"""
        from .result import AnalysisResult
        return AnalysisResult(
            file_path=self.parsed.file_path,
            api=self.parsed.api,
            platform=self.platform,
            frame_summary=self.frame_summary,
            textures=self.textures,
            buffers=self.buffers,
            passes=self.passes,
            issues=[],
            # 动态属性
            draws=self.draw_calls,
            dispatches=[],
            shaders=self.shaders,
        )
    
    def to_result(self, issues: List[Issue]) -> AnalysisResult:
        """转换为最终分析结果"""
        return AnalysisResult(
            file_path=self.parsed.file_path,
            api=self.parsed.api,
            platform=self.platform,
            parse_mode="api" if hasattr(self.parsed, "controller") else "binary",
            frame_summary=self.frame_summary,
            textures=self.textures,
            buffers=self.buffers,
            passes=self.passes,
            issues=issues,
        )
    
    def get_threshold(self, key: str, default: Any = None) -> Any:
        """获取阈值配置"""
        return self.thresholds.get(key, default)