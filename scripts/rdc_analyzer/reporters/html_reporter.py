"""
HTML 报告器
===========

生成带可视化图表的 HTML 报告。
"""

from datetime import datetime
from typing import Dict, List, Any
import html

from .base import BaseReporter, ReportData


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
        """生成内嵌 CSS"""
        return """<style>
:root {
    --color-error: #dc3545;
    --color-warning: #ffc107;
    --color-info: #17a2b8;
    --color-success: #28a745;
    --color-bg: #f8f9fa;
    --color-card: #ffffff;
    --color-text: #212529;
    --color-muted: #6c757d;
    --color-border: #dee2e6;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background-color: var(--color-bg);
    color: var(--color-text);
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* Header */
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.header h1 {
    font-size: 28px;
    margin-bottom: 8px;
}

.header .meta {
    opacity: 0.9;
    font-size: 14px;
}

.header .meta span {
    margin-right: 20px;
}

/* Summary Cards */
.summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.card {
    background: var(--color-card);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.card-value {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 4px;
}

.card-label {
    color: var(--color-muted);
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.card.error .card-value { color: var(--color-error); }
.card.warning .card-value { color: var(--color-warning); }
.card.info .card-value { color: var(--color-info); }
.card.success .card-value { color: var(--color-success); }

/* Stats Section */
.stats-section {
    background: var(--color-card);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.stats-section h2 {
    font-size: 18px;
    margin-bottom: 16px;
    color: var(--color-text);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
}

.stat-item {
    text-align: center;
    padding: 12px;
    background: var(--color-bg);
    border-radius: 8px;
}

.stat-value {
    font-size: 24px;
    font-weight: 600;
    color: #667eea;
}

.stat-label {
    font-size: 12px;
    color: var(--color-muted);
    margin-top: 4px;
}

/* Severity Chart */
.severity-chart {
    display: flex;
    height: 24px;
    border-radius: 12px;
    overflow: hidden;
    margin-top: 16px;
}

.severity-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 12px;
    font-weight: 600;
    transition: flex 0.3s;
}

.severity-bar.error { background: var(--color-error); }
.severity-bar.warning { background: var(--color-warning); color: #212529; }
.severity-bar.info { background: var(--color-info); }

/* Issues Table */
.issues-section {
    background: var(--color-card);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.issues-section h2 {
    font-size: 18px;
    margin-bottom: 16px;
}

.filter-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.filter-btn {
    padding: 6px 16px;
    border: 1px solid var(--color-border);
    border-radius: 20px;
    background: white;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.filter-btn:hover {
    background: var(--color-bg);
}

.filter-btn.active {
    background: #667eea;
    color: white;
    border-color: #667eea;
}

.issues-table {
    width: 100%;
    border-collapse: collapse;
}

.issues-table th,
.issues-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid var(--color-border);
}

.issues-table th {
    font-weight: 600;
    color: var(--color-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.issues-table tr:hover {
    background: var(--color-bg);
}

.severity-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

.severity-badge.error {
    background: #ffeaec;
    color: var(--color-error);
}

.severity-badge.warning {
    background: #fff8e6;
    color: #856404;
}

.severity-badge.info {
    background: #e7f5f7;
    color: #0c5460;
}

.code-badge {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    background: var(--color-bg);
    padding: 2px 8px;
    border-radius: 4px;
}

.message-cell {
    max-width: 400px;
}

.suggestion {
    font-size: 12px;
    color: var(--color-muted);
    margin-top: 4px;
}

/* Footer */
.footer {
    text-align: center;
    padding: 20px;
    color: var(--color-muted);
    font-size: 13px;
}

/* Responsive */
@media (max-width: 768px) {
    .container {
        padding: 12px;
    }
    
    .header {
        padding: 20px;
    }
    
    .header h1 {
        font-size: 22px;
    }
    
    .issues-table {
        display: block;
        overflow-x: auto;
    }
}
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
        """生成交互脚本"""
        return """<script>
document.addEventListener('DOMContentLoaded', function() {
    const filterBtns = document.querySelectorAll('.filter-btn');
    const rows = document.querySelectorAll('.issues-table tbody tr');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            
            rows.forEach(row => {
                if (filter === 'all') {
                    row.style.display = '';
                } else if (filter.startsWith('category-')) {
                    const category = filter.replace('category-', '');
                    row.style.display = row.dataset.category === category ? '' : 'none';
                } else {
                    row.style.display = row.dataset.severity === filter ? '' : 'none';
                }
            });
        });
    });
});
</script>"""
