"""
CSV 报告器
==========

生成 CSV 格式的分析报告，兼容 Excel。
"""

import csv
import io
from typing import List

from .base import BaseReporter, ReportData


class CSVReporter(BaseReporter):
    """CSV 格式报告器"""
    
    format_name = "csv"
    file_extension = ".csv"
    
    # CSV 列定义
    ISSUE_COLUMNS = [
        "Code",
        "Severity", 
        "Category",
        "Message",
        "Location",
        "Suggestion"
    ]
    
    def __init__(self, report_data: ReportData, include_bom: bool = True):
        """
        初始化 CSV 报告器
        
        Args:
            report_data: 报告数据
            include_bom: 是否包含 UTF-8 BOM（Excel 兼容）
        """
        super().__init__(report_data)
        self.include_bom = include_bom
    
    def generate(self) -> str:
        """
        生成 CSV 报告（问题列表）
        
        Returns:
            CSV 格式的报告字符串
        """
        output = io.StringIO()
        
        # UTF-8 BOM for Excel
        if self.include_bom:
            output.write('\ufeff')
        
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # 写入头部信息
        writer.writerow(["# RDC Analyzer Report"])
        writer.writerow(["File", self.data.file_path])
        writer.writerow(["Analysis Time", self.data.analysis_time.isoformat()])
        writer.writerow(["Platform", self.data.platform])
        writer.writerow(["API", self.data.api])
        writer.writerow([])
        
        # 写入摘要
        writer.writerow(["# Summary"])
        writer.writerow(["Total Issues", len(self.data.issues)])
        writer.writerow(["Errors", self.data.error_count])
        writer.writerow(["Warnings", self.data.warning_count])
        writer.writerow(["Info", self.data.info_count])
        writer.writerow([])
        
        # 写入帧统计
        if self.data.frame_summary:
            fs = self.data.frame_summary
            writer.writerow(["# Frame Statistics"])
            writer.writerow(["Draw Calls", fs.draw_call_count])
            writer.writerow(["Vertices", fs.vertex_count])
            writer.writerow(["Triangles", fs.triangle_count])
            writer.writerow(["Textures", fs.texture_count])
            writer.writerow(["Buffers", fs.buffer_count])
            writer.writerow(["Render Targets", fs.render_target_count])
            writer.writerow(["Passes", fs.pass_count])
            writer.writerow([])
        
        # 写入问题列表
        writer.writerow(["# Issues"])
        writer.writerow(self.ISSUE_COLUMNS)
        
        for issue in self.data.issues:
            writer.writerow([
                issue.code,
                issue.severity.name,
                issue.category.name if issue.category else "",
                issue.message,
                issue.location_path or "",
                issue.suggestion or ""
            ])
        
        return output.getvalue()
    
    def generate_issues_only(self) -> str:
        """
        只生成问题列表（无头部信息）
        
        Returns:
            只包含问题的 CSV 字符串
        """
        output = io.StringIO()
        
        if self.include_bom:
            output.write('\ufeff')
        
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(self.ISSUE_COLUMNS)
        
        for issue in self.data.issues:
            writer.writerow([
                issue.code,
                issue.severity.name,
                issue.category.name if issue.category else "",
                issue.message,
                issue.location_path or "",
                issue.suggestion or ""
            ])
        
        return output.getvalue()
