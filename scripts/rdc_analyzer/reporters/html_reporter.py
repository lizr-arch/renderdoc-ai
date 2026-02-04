"""
HTML 报告器
===========

生成带可视化图表的 HTML 报告。

重构说明：
- CSS 已提取到 assets/styles/html_reporter.css
- JS 已提取到 assets/scripts/html_reporter.js
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import html

from .base import BaseReporter, ReportData

# 资源目录路径
_ASSETS_DIR = Path(__file__).parent.parent / "assets"


class HTMLReporter(BaseReporter):
    """HTML 格式报告器"""
    
    format_name = "html"
    file_extension = ".html"
    
    def generate(self) -> str:
        """
        生成 HTML 报告
        
        Returns:
            HTML 格式的报告字符串
        """
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RDC 性能分析报告</title>
    {self._generate_styles()}
</head>
<body>
    <div class="container">
        {self._generate_header()}
        {self._generate_summary_cards()}
        {self._generate_frame_stats()}
        {self._generate_issues_by_severity()}
        {self._generate_issues_table()}
        {self._generate_footer()}
    </div>
    {self._generate_scripts()}
</body>
</html>"""

    def _generate_styles(self) -> str:
        """从外部文件加载 CSS 样式"""
        css_path = _ASSETS_DIR / "styles" / "html_reporter.css"
        try:
            css_content = css_path.read_text(encoding='utf-8')
            return f"<style>\n{css_content}</style>"
        except FileNotFoundError:
            # 回退：返回最小样式
            return """<style>
body { font-family: sans-serif; margin: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
</style>"""

    def _generate_header(self) -> str:
        """生成页头"""
        file_name = self.data.file_path.split('/')[-1].split('\\')[-1] if self.data.file_path else "Unknown"
        return f"""<header class="header">
    <h1>🎮 RDC 性能分析报告</h1>
    <div class="meta">
        <span>📁 {html.escape(file_name)}</span>
        <span>🖥️ {html.escape(self.data.platform.upper())}</span>
        <span>🔧 {html.escape(self.data.api)}</span>
        <span>⏰ {self.data.analysis_time.strftime('%Y-%m-%d %H:%M:%S')}</span>
    </div>
</header>"""

    def _generate_summary_cards(self) -> str:
        """生成摘要卡片"""
        total = len(self.data.issues)
        return f"""<div class="summary-cards">
    <div class="card {'error' if self.data.error_count > 0 else 'success'}">
        <div class="card-value">{self.data.error_count}</div>
        <div class="card-label">错误</div>
    </div>
    <div class="card {'warning' if self.data.warning_count > 0 else 'success'}">
        <div class="card-value">{self.data.warning_count}</div>
        <div class="card-label">警告</div>
    </div>
    <div class="card info">
        <div class="card-value">{self.data.info_count}</div>
        <div class="card-label">信息</div>
    </div>
    <div class="card">
        <div class="card-value">{total}</div>
        <div class="card-label">总计</div>
    </div>
</div>"""

    def _generate_frame_stats(self) -> str:
        """生成帧统计"""
        if not self.data.frame_summary:
            return ""
        
        fs = self.data.frame_summary
        tex_mem = round(fs.total_texture_memory / (1024*1024), 1) if fs.total_texture_memory else 0
        buf_mem = round(fs.total_buffer_memory / (1024*1024), 1) if fs.total_buffer_memory else 0
        
        return f"""<section class="stats-section">
    <h2>📊 帧统计</h2>
    <div class="stats-grid">
        <div class="stat-item">
            <div class="stat-value">{fs.draw_call_count:,}</div>
            <div class="stat-label">Draw Calls</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{fs.vertex_count:,}</div>
            <div class="stat-label">顶点数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{fs.primitive_count:,}</div>
            <div class="stat-label">图元数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{fs.texture_count}</div>
            <div class="stat-label">纹理数量</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{tex_mem} MB</div>
            <div class="stat-label">纹理内存</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{fs.buffer_count}</div>
            <div class="stat-label">缓冲区数量</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{buf_mem} MB</div>
            <div class="stat-label">缓冲区内存</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{fs.pass_count}</div>
            <div class="stat-label">渲染 Pass</div>
        </div>
    </div>
</section>"""

    def _generate_issues_by_severity(self) -> str:
        """生成严重度分布图"""
        total = len(self.data.issues)
        if total == 0:
            return """<section class="stats-section">
    <h2>✅ 未发现问题</h2>
    <p style="color: var(--color-success); margin-top: 8px;">恭喜！分析未发现任何性能问题。</p>
</section>"""
        
        error_pct = (self.data.error_count / total * 100) if total > 0 else 0
        warning_pct = (self.data.warning_count / total * 100) if total > 0 else 0
        info_pct = (self.data.info_count / total * 100) if total > 0 else 0
        
        return f"""<section class="stats-section">
    <h2>📈 问题分布</h2>
    <div class="severity-chart">
        {"<div class='severity-bar error' style='flex: " + str(error_pct) + ";'>" + str(self.data.error_count) + "</div>" if error_pct > 0 else ""}
        {"<div class='severity-bar warning' style='flex: " + str(warning_pct) + ";'>" + str(self.data.warning_count) + "</div>" if warning_pct > 0 else ""}
        {"<div class='severity-bar info' style='flex: " + str(info_pct) + ";'>" + str(self.data.info_count) + "</div>" if info_pct > 0 else ""}
    </div>
</section>"""

    def _generate_issues_table(self) -> str:
        """生成问题表格"""
        if not self.data.issues:
            return ""
        
        rows = []
        for issue in self.data.issues:
            severity_class = issue.severity.name.lower()
            category = issue.category.name if issue.category else "UNKNOWN"
            suggestion_html = f'<div class="suggestion">💡 {html.escape(issue.suggestion)}</div>' if issue.suggestion else ""
            
            rows.append(f"""<tr data-severity="{severity_class}" data-category="{category.lower()}">
    <td><span class="code-badge">{html.escape(issue.code)}</span></td>
    <td><span class="severity-badge {severity_class}">{issue.severity.name}</span></td>
    <td>{category}</td>
    <td class="message-cell">
        {html.escape(issue.message)}
        {suggestion_html}
    </td>
    <td>{html.escape(issue.location_path or '-')}</td>
</tr>""")
        
        # 获取所有分类
        categories = sorted(set(
            i.category.name for i in self.data.issues if i.category
        ))
        category_buttons = ''.join(
            f'<button class="filter-btn" data-filter="category-{c.lower()}">{c}</button>'
            for c in categories
        )
        
        return f"""<section class="issues-section">
    <h2>🔍 问题详情 ({len(self.data.issues)})</h2>
    <div class="filter-bar">
        <button class="filter-btn active" data-filter="all">全部</button>
        <button class="filter-btn" data-filter="error">错误</button>
        <button class="filter-btn" data-filter="warning">警告</button>
        <button class="filter-btn" data-filter="info">信息</button>
        {category_buttons}
    </div>
    <table class="issues-table">
        <thead>
            <tr>
                <th>规则代码</th>
                <th>严重度</th>
                <th>分类</th>
                <th>问题描述</th>
                <th>位置</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</section>"""

    def _generate_footer(self) -> str:
        """生成页脚"""
        return f"""<footer class="footer">
    <p>Generated by RDC Analyzer v{self.data.analyzer_version}</p>
    <p>© {datetime.now().year} RenderDoc Performance Analysis Tool</p>
</footer>"""

    def _generate_scripts(self) -> str:
        """从外部文件加载 JavaScript"""
        js_path = _ASSETS_DIR / "scripts" / "html_reporter.js"
        try:
            js_content = js_path.read_text(encoding='utf-8')
            return f"<script>\n{js_content}</script>"
        except FileNotFoundError:
            # 回退：返回最小脚本
            return """<script>
document.addEventListener('DOMContentLoaded', function() {
    console.log('HTML Reporter loaded (fallback mode)');
});
</script>"""