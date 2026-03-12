"""
Markdown 报告生成器
===================

将分析结果输出为 Markdown 格式，方便阅读。
"""

from datetime import datetime
from typing import List
from ..core.result import AnalysisResult
from ..core.types import Issue
from ..core.enums import Severity


class MarkdownReporter:
    """
    Markdown 格式报告生成器
    """
    
    def __init__(self, result: AnalysisResult):
        """
        初始化报告器
        
        Args:
            result: 分析结果
        """
        self.result = result
    
    def generate(self) -> str:
        """
        生成 Markdown 报告
        
        Returns:
            Markdown 字符串
        """
        sections = [
            self._header(),
            self._summary_section(),
            self._issues_section(),
            self._passes_section(),
            self._resources_section(),
            self._footer(),
        ]
        return "\n\n".join(sections)
    
    def save(self, filepath: str):
        """
        保存报告到文件
        
        Args:
            filepath: 输出文件路径
        """
        content = self.generate()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _header(self) -> str:
        """报告头部"""
        return f"""# RDC 分析报告

- **文件**: `{self.result.file_path}`
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **平台**: {self.result.platform}
- **API**: {self.result.api}
- **解析模式**: {self.result.parse_mode}"""
    
    def _summary_section(self) -> str:
        """帧摘要部分"""
        s = self.result.frame_summary
        tex_mb = s.total_texture_memory / (1024 * 1024)
        buf_mb = s.total_buffer_memory / (1024 * 1024)
        
        return f"""## 帧摘要

| 指标 | 数值 |
|------|------|
| Draw Call | {s.draw_call_count} |
| 顶点数 | {s.vertex_count:,} |
| 图元数 | {s.primitive_count:,} |
| 纹理数 | {s.texture_count} |
| Buffer 数 | {s.buffer_count} |
| Pass 数 | {s.pass_count} |
| RT 切换 | {s.rt_switches} |
| Shader 切换 | {s.shader_changes} |
| 纹理内存 | {tex_mb:.1f} MB |
| Buffer 内存 | {buf_mb:.1f} MB |"""
    
    def _issues_section(self) -> str:
        """问题部分"""
        if not self.result.issues:
            return """## 检测问题

[+] 未发现问题！"""
        
        # 按严重程度分组
        critical = [i for i in self.result.issues if i.severity == Severity.CRITICAL]
        warnings = [i for i in self.result.issues if i.severity == Severity.WARNING]
        info = [i for i in self.result.issues if i.severity == Severity.INFO]
        
        lines = ["## 检测问题", ""]
        lines.append(f"共发现 **{len(self.result.issues)}** 个问题 "
                    f"(严重: {len(critical)}, 警告: {len(warnings)}, 提示: {len(info)})")
        lines.append("")
        
        if critical:
            lines.append("### [!] 严重问题")
            lines.append("")
            for issue in critical:
                lines.append(self._format_issue(issue))
            lines.append("")
        
        if warnings:
            lines.append("### [*] 警告")
            lines.append("")
            for issue in warnings:
                lines.append(self._format_issue(issue))
            lines.append("")
        
        if info:
            lines.append("### [i] 提示")
            lines.append("")
            for issue in info:
                lines.append(self._format_issue(issue))
        
        return "\n".join(lines)
    
    def _format_issue(self, issue: Issue) -> str:
        """格式化单个问题"""
        location = f" @ `{issue.location_path}`" if issue.location_path else ""
        return f"- **[{issue.code}]** {issue.message}{location}"
    
    def _passes_section(self) -> str:
        """Pass 结构部分"""
        if not self.result.passes:
            return "## Pass 结构\n\n未检测到 Pass 信息。"
        
        lines = ["## Pass 结构", ""]
        lines.append("| Pass | Draw Count | Render Targets | 类型 |")
        lines.append("|------|------------|----------------|------|")
        
        for p in self.result.passes:
            rts = ", ".join([rt.resource_id for rt in p.render_targets[:3]])
            if len(p.render_targets) > 3:
                rts += "..."
            
            pass_type = []
            if p.is_fullscreen:
                pass_type.append("全屏")
            if p.is_depth_only:
                pass_type.append("深度")
            type_str = ", ".join(pass_type) if pass_type else "-"
            
            lines.append(f"| {p.name} | {p.draw_count} | {rts} | {type_str} |")
        
        return "\n".join(lines)
    
    def _resources_section(self) -> str:
        """资源部分"""
        lines = ["## 资源概览", ""]
        
        # 大纹理
        large_textures = [t for t in self.result.textures if t.width > 1024 or t.height > 1024]
        if large_textures:
            lines.append("### 大纹理 (>1024)")
            lines.append("")
            lines.append("| 名称 | 尺寸 | 格式 | 内存 |")
            lines.append("|------|------|------|------|")
            for t in large_textures[:10]:
                size_kb = t.memory_size / 1024
                name = t.name or t.resource_id
                lines.append(f"| {name} | {t.width}x{t.height} | {t.format} | {size_kb:.1f} KB |")
            if len(large_textures) > 10:
                lines.append(f"| ... | 还有 {len(large_textures)-10} 张 | | |")
            lines.append("")
        
        # 大 Buffer
        large_buffers = [b for b in self.result.buffers if b.size > 1024 * 1024]
        if large_buffers:
            lines.append("### 大 Buffer (>1MB)")
            lines.append("")
            lines.append("| 名称 | 大小 |")
            lines.append("|------|------|")
            for b in large_buffers[:10]:
                size_mb = b.size / (1024 * 1024)
                name = b.name or b.resource_id
                lines.append(f"| {name} | {size_mb:.1f} MB |")
            lines.append("")
        
        return "\n".join(lines) if len(lines) > 2 else ""
    
    def _footer(self) -> str:
        """报告尾部"""
        return """---

*Report generated by RDC Analyzer v2.0*"""
