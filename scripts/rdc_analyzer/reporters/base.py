"""
报告器基类
==========

定义报告生成的统一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..core.types import Issue, FrameSummary, ParsedData


@dataclass
class ReportData:
    """报告数据容器"""
    
    # 元数据
    file_path: str = ""
    analysis_time: datetime = field(default_factory=datetime.now)
    analyzer_version: str = "1.0.0"
    platform: str = "pc"
    api: str = "D3D11"
    
    # 帧摘要
    frame_summary: Optional[FrameSummary] = None
    
    # 问题列表
    issues: List[Issue] = field(default_factory=list)
    
    # 统计信息
    total_rules_checked: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    
    # 额外数据
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def error_count(self) -> int:
        """错误数量"""
        return sum(1 for i in self.issues if i.severity.name == "ERROR")
    
    @property
    def warning_count(self) -> int:
        """警告数量"""
        return sum(1 for i in self.issues if i.severity.name == "WARNING")
    
    @property
    def info_count(self) -> int:
        """信息数量"""
        return sum(1 for i in self.issues if i.severity.name == "INFO")
    
    @property
    def has_issues(self) -> bool:
        """是否有问题"""
        return len(self.issues) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "metadata": {
                "file_path": self.file_path,
                "analysis_time": self.analysis_time.isoformat(),
                "analyzer_version": self.analyzer_version,
                "platform": self.platform,
                "api": self.api,
            },
            "summary": {
                "total_issues": len(self.issues),
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
                "rules_checked": self.total_rules_checked,
                "rules_passed": self.rules_passed,
                "rules_failed": self.rules_failed,
            },
            "frame_summary": self._frame_summary_to_dict(),
            "issues": [self._issue_to_dict(i) for i in self.issues],
            "extra": self.extra,
        }
    
    def _frame_summary_to_dict(self) -> Dict[str, Any]:
        """帧摘要转字典"""
        if not self.frame_summary:
            return {}
        fs = self.frame_summary
        return {
            "draw_call_count": fs.draw_call_count,
            "vertex_count": fs.vertex_count,
            "primitive_count": fs.primitive_count,
            "texture_count": fs.texture_count,
            "texture_memory_mb": round(fs.total_texture_memory / (1024*1024), 2) if fs.total_texture_memory else 0,
            "buffer_count": fs.buffer_count,
            "buffer_memory_mb": round(fs.total_buffer_memory / (1024*1024), 2) if fs.total_buffer_memory else 0,
            "rt_switches": fs.rt_switches,
            "pass_count": fs.pass_count,
            "viewport": f"{fs.viewport_width}x{fs.viewport_height}",
        }
    
    def _issue_to_dict(self, issue: Issue) -> Dict[str, Any]:
        """问题转字典"""
        return {
            "code": issue.code,
            "severity": issue.severity.name,
            "category": issue.category.name if issue.category else "UNKNOWN",
            "message": issue.message,
            "location": issue.location_path,
            "suggestion": issue.suggestion or "",
        }


class BaseReporter(ABC):
    """报告器抽象基类"""
    
    # 报告格式名称
    format_name: str = "base"
    
    # 文件扩展名
    file_extension: str = ".txt"
    
    def __init__(self, report_data: ReportData):
        """
        初始化报告器
        
        Args:
            report_data: 报告数据
        """
        self.data = report_data
    
    @abstractmethod
    def generate(self) -> str:
        """
        生成报告内容
        
        Returns:
            报告内容字符串
        """
        pass
    
    def save(self, output_path: str) -> Path:
        """
        保存报告到文件
        
        Args:
            output_path: 输出路径
            
        Returns:
            保存的文件路径
        """
        path = Path(output_path)
        
        # 如果是目录，自动生成文件名
        if path.is_dir():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rdc_report_{timestamp}{self.file_extension}"
            path = path / filename
        
        # 确保扩展名正确
        if path.suffix != self.file_extension:
            path = path.with_suffix(self.file_extension)
        
        # 创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        content = self.generate()
        path.write_text(content, encoding="utf-8")
        
        return path
    
    def print_to_console(self) -> None:
        """打印报告到控制台"""
        print(self.generate())
