"""
JSON 报告器
===========

生成 JSON 格式的分析报告。
"""

import json
from typing import Dict, Any

from .base import BaseReporter, ReportData


class JSONReporter(BaseReporter):
    """JSON 格式报告器"""
    
    format_name = "json"
    file_extension = ".json"
    
    def __init__(self, report_data: ReportData, indent: int = 2, ensure_ascii: bool = False):
        """
        初始化 JSON 报告器
        
        Args:
            report_data: 报告数据
            indent: JSON 缩进级别
            ensure_ascii: 是否转义非 ASCII 字符
        """
        super().__init__(report_data)
        self.indent = indent
        self.ensure_ascii = ensure_ascii
    
    def generate(self) -> str:
        """
        生成 JSON 报告
        
        Returns:
            JSON 格式的报告字符串
        """
        data = self.data.to_dict()
        return json.dumps(
            data,
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
            default=str  # 处理不可序列化的对象
        )
    
    def generate_minimal(self) -> str:
        """
        生成最小化 JSON（无缩进）
        
        Returns:
            压缩的 JSON 字符串
        """
        data = self.data.to_dict()
        return json.dumps(data, ensure_ascii=self.ensure_ascii, default=str)
    
    def generate_summary_only(self) -> str:
        """
        只生成摘要信息
        
        Returns:
            只包含摘要的 JSON 字符串
        """
        data = self.data.to_dict()
        summary_data = {
            "metadata": data["metadata"],
            "summary": data["summary"],
            "frame_summary": data["frame_summary"],
        }
        return json.dumps(
            summary_data,
            indent=self.indent,
            ensure_ascii=self.ensure_ascii
        )