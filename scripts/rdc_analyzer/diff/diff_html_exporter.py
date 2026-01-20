"""
差异对比 HTML 报告导出器
========================

生成可视化的 RDC 对比报告，包含：
- 指标变化统计卡片
- 回归警告面板
- 资源差异对比表
- Draw Call 变化列表

TASK-012 实现
Created: 2026-01-20
"""

import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .diff_types import (
    DiffResult, DiffStatus, MetricDiff,
    TextureDiff, ShaderDiff, BufferDiff, DrawCallDiff
)
from .regression_types import (
    RegressionReport, RegressionIssue, RegressionSeverity
)


@dataclass
class DiffHTMLConfig:
    """HTML 导出配置"""
    
    title: str = "RDC Comparison Report"
    theme: str = "dark"  # 'dark' or 'light'
    
    # 功能开关
    include_summary: bool = True
    include_regression_panel: bool = True
    include_resource_diff: bool = True
    include_draw_calls: bool = True
    
    # 显示限制
    max_draw_calls: int = 500
    max_resources: int = 200


# ============================================================
# HTML 模板
# ============================================================

DIFF_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-primary: {bg_primary};
            --bg-secondary: {bg_secondary};
            --bg-tertiary: {bg_tertiary};
            --text-primary: {text_primary};
            --text-secondary: {text_secondary};
            --accent: #4a9eff;
            --critical: #ff6b6b;
            --warning: #ffa94d;
            --info: #74c0fc;
            --success: #69db7c;
            --added: #2ecc71;
            --removed: #e74c3c;
            --modified: #f39c12;
            --border: {border_color};
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
        }}
        
        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 8px;
        }}
        
        .header-meta {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            font-size: 14px;
            color: var(--text-secondary);
        }}
        
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .meta-label {{
            font-weight: 500;
        }}
        
        /* Regression Alert Banner */
        .regression-banner {{
            border-radius: 12px;
            padding: 16px 24px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .regression-banner.critical {{
            background: linear-gradient(135deg, rgba(255,107,107,0.15), rgba(255,107,107,0.05));
            border: 1px solid var(--critical);
        }}
        
        .regression-banner.warning {{
            background: linear-gradient(135deg, rgba(255,169,77,0.15), rgba(255,169,77,0.05));
            border: 1px solid var(--warning);
        }}
        
        .regression-banner.clean {{
            background: linear-gradient(135deg, rgba(105,219,124,0.15), rgba(105,219,124,0.05));
            border: 1px solid var(--success);
        }}
        
        .banner-icon {{
            font-size: 28px;
        }}
        
        .banner-content h2 {{
            font-size: 18px;
            font-weight: 600;
        }}
        
        .banner-content p {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        
        /* Statistics Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .stat-card::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent);
        }}
        
        .stat-card.increase::before {{ background: var(--critical); }}
        .stat-card.decrease::before {{ background: var(--success); }}
        .stat-card.unchanged::before {{ background: var(--text-secondary); }}
        
        .stat-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        
        .stat-value {{
            font-size: 28px;
            font-weight: 700;
        }}
        
        .stat-card.increase .stat-value {{ color: var(--critical); }}
        .stat-card.decrease .stat-value {{ color: var(--success); }}
        
        .stat-delta {{
            font-size: 13px;
            margin-top: 4px;
            font-weight: 500;
        }}
        
        .stat-delta.positive {{ color: var(--critical); }}
        .stat-delta.negative {{ color: var(--success); }}
        .stat-delta.zero {{ color: var(--text-secondary); }}
        
        .stat-baseline {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 8px;
        }}
        
        /* Two Column Layout */
        .main-content {{
            display: grid;
            grid-template-columns: 400px 1fr;
            gap: 20px;
        }}
        
        @media (max-width: 1200px) {{
            .main-content {{
                grid-template-columns: 1fr;
            }}
        }}
        
        /* Panel */
        .panel {{
            background: var(--bg-secondary);
            border-radius: 12px;
            overflow: hidden;
        }}
        
        .panel-header {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            font-weight: 600;
            font-size: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .panel-badge {{
            background: var(--accent);
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        .panel-badge.critical {{ background: var(--critical); }}
        .panel-badge.warning {{ background: var(--warning); }}
        
        .panel-content {{
            padding: 16px 20px;
            max-height: 600px;
            overflow-y: auto;
        }}
        
        /* Regression Issues */
        .issue-item {{
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 12px;
            border-left: 4px solid;
        }}
        
        .issue-item.critical {{
            background: rgba(255,107,107,0.1);
            border-color: var(--critical);
        }}
        
        .issue-item.warning {{
            background: rgba(255,169,77,0.1);
            border-color: var(--warning);
        }}
        
        .issue-item.info {{
            background: rgba(116,192,252,0.1);
            border-color: var(--info);
        }}
        
        .issue-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        
        .issue-rule {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 11px;
            background: var(--bg-tertiary);
            padding: 2px 8px;
            border-radius: 4px;
        }}
        
        .issue-severity {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .issue-severity.critical {{ color: var(--critical); }}
        .issue-severity.warning {{ color: var(--warning); }}
        .issue-severity.info {{ color: var(--info); }}
        
        .issue-message {{
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 4px;
        }}
        
        .issue-details {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .issue-values {{
            display: flex;
            gap: 16px;
            margin-top: 8px;
            font-size: 12px;
        }}
        
        .issue-value {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        .issue-value .label {{
            color: var(--text-secondary);
        }}
        
        /* Evidence Anchors */
        .evidence-list {{
            margin-top: 10px;
            padding: 8px 12px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            font-size: 12px;
        }}
        
        .evidence-header {{
            font-weight: 600;
            margin-bottom: 6px;
            color: var(--text-secondary);
            font-size: 11px;
            text-transform: uppercase;
        }}
        
        .evidence-anchor {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            margin: 2px 4px 2px 0;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        
        .evidence-anchor:hover {{
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }}
        
        .evidence-anchor .eid {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-weight: 600;
            color: var(--accent);
        }}
        
        .evidence-anchor:hover .eid {{
            color: white;
        }}
        
        .evidence-anchor .marker {{
            color: var(--text-secondary);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .evidence-anchor:hover .marker {{
            color: rgba(255,255,255,0.8);
        }}
        
        .evidence-more {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-left: 4px;
        }}
        
        /* Resource Diff Table */
        .diff-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .diff-table th {{
            text-align: left;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            font-weight: 600;
            border-bottom: 1px solid var(--border);
        }}
        
        .diff-table td {{
            padding: 10px 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .diff-table tr:hover {{
            background: var(--bg-tertiary);
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .status-badge.added {{
            background: rgba(46,204,113,0.2);
            color: var(--added);
        }}
        
        .status-badge.removed {{
            background: rgba(231,76,60,0.2);
            color: var(--removed);
        }}
        
        .status-badge.modified {{
            background: rgba(243,156,18,0.2);
            color: var(--modified);
        }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            gap: 4px;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border);
        }}
        
        .tab-btn {{
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        .tab-btn:hover {{
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        
        .tab-btn.active {{
            background: var(--accent);
            color: white;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        /* Change Indicators */
        .change-cell {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .change-arrow {{
            font-size: 14px;
        }}
        
        .change-arrow.up {{ color: var(--critical); }}
        .change-arrow.down {{ color: var(--success); }}
        
        .old-value {{
            color: var(--text-secondary);
            text-decoration: line-through;
        }}
        
        .new-value {{
            font-weight: 500;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }}
        
        .empty-state-icon {{
            font-size: 48px;
            margin-bottom: 12px;
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 12px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        {header_section}
        {banner_section}
        {stats_section}
        <div class="main-content">
            {regression_panel}
            {diff_panel}
        </div>
        <footer class="footer">
            Generated by RDC Analyzer · {timestamp}
        </footer>
    </div>
    
    <script>
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                const tabGroup = btn.closest('.panel');
                const tabId = btn.dataset.tab;
                
                // Update buttons
                tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // Update content
                tabGroup.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tabGroup.querySelector(`#${{tabId}}`).classList.add('active');
            }});
        }});
        
        // Evidence anchor click handler
        function jumpToEventId(eventId, markerPath) {{
            // Copy to clipboard for easy use in RenderDoc
            const text = `Event ID: ${{eventId}}\\nMarker: ${{markerPath}}`;
            navigator.clipboard.writeText(eventId.toString()).then(() => {{
                // Show tooltip notification
                const anchor = event.currentTarget;
                const tooltip = document.createElement('div');
                tooltip.textContent = '已复制 Event ID';
                tooltip.style.cssText = `
                    position: fixed;
                    top: ${{event.clientY - 40}}px;
                    left: ${{event.clientX}}px;
                    background: var(--accent);
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    z-index: 1000;
                    animation: fadeOut 1.5s forwards;
                `;
                document.body.appendChild(tooltip);
                setTimeout(() => tooltip.remove(), 1500);
            }});
        }}
        
        // Add fadeOut animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeOut {{
                0% {{ opacity: 1; transform: translateY(0); }}
                70% {{ opacity: 1; transform: translateY(-5px); }}
                100% {{ opacity: 0; transform: translateY(-10px); }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>'''


class DiffHTMLExporter:
    """差异对比 HTML 导出器"""
    
    # 主题色配置
    THEMES = {
        "dark": {
            "bg_primary": "#0d1117",
            "bg_secondary": "#161b22",
            "bg_tertiary": "#21262d",
            "text_primary": "#c9d1d9",
            "text_secondary": "#8b949e",
            "border_color": "#30363d",
        },
        "light": {
            "bg_primary": "#f6f8fa",
            "bg_secondary": "#ffffff",
            "bg_tertiary": "#f0f3f6",
            "text_primary": "#24292f",
            "text_secondary": "#57606a",
            "border_color": "#d0d7de",
        },
    }
    
    def __init__(self, config: Optional[DiffHTMLConfig] = None):
        self.config = config or DiffHTMLConfig()
    
    def export(
        self,
        diff: DiffResult,
        regression: Optional[RegressionReport] = None,
        output_path: Optional[Path] = None
    ) -> str:
        """
        导出差异报告为 HTML
        
        Args:
            diff: 差异结果
            regression: 回归检测报告 (可选)
            output_path: 输出文件路径 (可选)
            
        Returns:
            生成的 HTML 字符串
        """
        theme = self.THEMES.get(self.config.theme, self.THEMES["dark"])
        
        html_content = DIFF_HTML_TEMPLATE.format(
            title=html.escape(self.config.title),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            header_section=self._render_header(diff),
            banner_section=self._render_banner(regression),
            stats_section=self._render_stats(diff),
            regression_panel=self._render_regression_panel(regression),
            diff_panel=self._render_diff_panel(diff),
            **theme
        )
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding="utf-8")
        
        return html_content
    
    def _render_header(self, diff: DiffResult) -> str:
        """渲染页头"""
        baseline_name = Path(diff.baseline_file).name if diff.baseline_file else "Unknown"
        target_name = Path(diff.target_file).name if diff.target_file else "Unknown"
        
        return f'''
        <header class="header">
            <h1>🔬 {html.escape(self.config.title)}</h1>
            <div class="header-meta">
                <div class="meta-item">
                    <span class="meta-label">基准:</span>
                    <span>{html.escape(baseline_name)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">目标:</span>
                    <span>{html.escape(target_name)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">API:</span>
                    <span>{html.escape(diff.api_type or "Unknown")}</span>
                </div>
            </div>
        </header>
        '''
    
    def _render_banner(self, regression: Optional[RegressionReport]) -> str:
        """渲染回归警告横幅"""
        if not regression:
            return ""
        
        if regression.has_critical:
            css_class = "critical"
            icon = "🚨"
            title = "检测到严重回归问题"
            desc = f"发现 {regression.critical_count} 个严重问题需要立即关注"
        elif regression.has_warning:
            css_class = "warning"
            icon = "⚠️"
            title = "检测到性能回归"
            desc = f"发现 {regression.warning_count} 个警告问题"
        else:
            css_class = "clean"
            icon = "✅"
            title = "未检测到回归问题"
            desc = f"已检查 {regression.rules_checked} 条规则，全部通过"
        
        return f'''
        <div class="regression-banner {css_class}">
            <span class="banner-icon">{icon}</span>
            <div class="banner-content">
                <h2>{title}</h2>
                <p>{desc}</p>
            </div>
        </div>
        '''
    
    def _render_stats(self, diff: DiffResult) -> str:
        """渲染统计卡片"""
        if not self.config.include_summary:
            return ""
        
        cards = []
        metrics = [
            (diff.summary.draw_calls, "Draw Calls"),
            (diff.summary.triangles, "三角形"),
            (diff.summary.vertices, "顶点数"),
            (diff.summary.texture_count, "纹理数量"),
            (diff.summary.texture_memory, "纹理内存"),
            (diff.summary.buffer_count, "缓冲区"),
            (diff.summary.shader_count, "Shader"),
        ]
        
        for metric, label in metrics:
            cards.append(self._render_stat_card(metric, label))
        
        return f'''
        <div class="stats-grid">
            {"".join(cards)}
        </div>
        '''
    
    def _render_stat_card(self, metric: MetricDiff, label: str) -> str:
        """渲染单个统计卡片"""
        if metric.delta > 0:
            css_class = "increase"
            arrow = "↑"
            delta_class = "positive"
        elif metric.delta < 0:
            css_class = "decrease"
            arrow = "↓"
            delta_class = "negative"
        else:
            css_class = "unchanged"
            arrow = ""
            delta_class = "zero"
        
        # 格式化数值
        target_val = self._format_value(metric.target, metric.name)
        baseline_val = self._format_value(metric.baseline, metric.name)
        delta_pct = f"{metric.delta_percent:+.1f}%" if metric.delta != 0 else "无变化"
        
        return f'''
        <div class="stat-card {css_class}">
            <div class="stat-label">{html.escape(label)}</div>
            <div class="stat-value">{target_val}</div>
            <div class="stat-delta {delta_class}">{arrow} {delta_pct}</div>
            <div class="stat-baseline">基准: {baseline_val}</div>
        </div>
        '''
    
    def _format_value(self, value: float, metric_name: str) -> str:
        """格式化数值显示"""
        if "memory" in metric_name.lower():
            # 字节转 MB
            mb = value / (1024 * 1024)
            if mb >= 1:
                return f"{mb:.1f} MB"
            kb = value / 1024
            if kb >= 1:
                return f"{kb:.1f} KB"
            return f"{int(value)} B"
        
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(int(value))
    
    def _render_regression_panel(self, regression: Optional[RegressionReport]) -> str:
        """渲染回归问题面板"""
        if not self.config.include_regression_panel or not regression:
            return '<div class="panel"><div class="panel-header">回归检测</div><div class="panel-content"><div class="empty-state"><div class="empty-state-icon">🔍</div><p>未运行回归检测</p></div></div></div>'
        
        if not regression.issues:
            return '''
            <div class="panel">
                <div class="panel-header">
                    回归检测
                    <span class="panel-badge" style="background: var(--success);">通过</span>
                </div>
                <div class="panel-content">
                    <div class="empty-state">
                        <div class="empty-state-icon">✅</div>
                        <p>所有规则检查通过，未发现回归问题</p>
                    </div>
                </div>
            </div>
            '''
        
        # 按严重程度排序
        sorted_issues = sorted(
            regression.issues,
            key=lambda i: (
                0 if i.severity == RegressionSeverity.CRITICAL else
                1 if i.severity == RegressionSeverity.WARNING else 2
            )
        )
        
        issue_items = []
        for issue in sorted_issues:
            issue_items.append(self._render_issue_item(issue))
        
        badge_class = "critical" if regression.has_critical else "warning"
        badge_text = f"{len(regression.issues)} 问题"
        
        return f'''
        <div class="panel">
            <div class="panel-header">
                回归检测
                <span class="panel-badge {badge_class}">{badge_text}</span>
            </div>
            <div class="panel-content">
                {"".join(issue_items)}
            </div>
        </div>
        '''
    
    def _render_issue_item(self, issue: RegressionIssue) -> str:
        """渲染单个回归问题"""
        severity = issue.severity.value
        
        values_html = ""
        if issue.baseline_value is not None and issue.target_value is not None:
            values_html = f'''
            <div class="issue-values">
                <div class="issue-value">
                    <span class="label">基准:</span>
                    <span>{issue.baseline_value:.0f}</span>
                </div>
                <div class="issue-value">
                    <span class="label">目标:</span>
                    <span>{issue.target_value:.0f}</span>
                </div>
                <div class="issue-value">
                    <span class="label">变化:</span>
                    <span>{issue.delta_percent:+.1f}%</span>
                </div>
            </div>
            '''
        
        # 渲染证据锚点
        evidence_html = self._render_evidence_anchors(issue.evidence)
        
        return f'''
        <div class="issue-item {severity}">
            <div class="issue-header">
                <span class="issue-rule">{issue.rule_id.value}</span>
                <span class="issue-severity {severity}">{severity.upper()}</span>
            </div>
            <div class="issue-message">{html.escape(issue.message)}</div>
            <div class="issue-details">{html.escape(issue.details)}</div>
            {values_html}
            {evidence_html}
        </div>
        '''
    
    def _render_evidence_anchors(self, evidence: list) -> str:
        """渲染证据锚点列表"""
        if not evidence:
            return ""
        
        # 限制显示数量，避免 UI 过于拥挤
        max_display = 5
        anchors = []
        
        for ev in evidence[:max_display]:
            marker_display = ev.marker_path if ev.marker_path else "(no marker)"
            # 截断过长的 marker path
            if len(marker_display) > 30:
                marker_display = "..." + marker_display[-27:]
            
            # 使用 description 作为 title tooltip
            tooltip = html.escape(ev.description) if ev.description else f"Event {ev.event_id}"
            
            anchors.append(f'''
                <span class="evidence-anchor" 
                      onclick="jumpToEventId({ev.event_id}, '{html.escape(ev.marker_path)}')"
                      title="{tooltip}">
                    <span class="eid">#{ev.event_id}</span>
                    <span class="marker">{html.escape(marker_display)}</span>
                </span>
            ''')
        
        # 如果有更多证据，显示提示
        more_html = ""
        if len(evidence) > max_display:
            more_html = f'<span class="evidence-more">+{len(evidence) - max_display} more</span>'
        
        return f'''
        <div class="evidence-list">
            <div class="evidence-header">📍 证据锚点 (点击复制 Event ID)</div>
            {"".join(anchors)}
            {more_html}
        </div>
        '''
    
    def _render_diff_panel(self, diff: DiffResult) -> str:
        """渲染差异详情面板"""
        if not self.config.include_resource_diff:
            return ""
        
        tabs = []
        tab_contents = []
        
        # 纹理标签页
        tex_count = len(diff.texture_diffs)
        tabs.append(f'<button class="tab-btn active" data-tab="textures">纹理 ({tex_count})</button>')
        tab_contents.append(self._render_texture_tab(diff.texture_diffs))
        
        # Shader 标签页
        shader_count = len(diff.shader_diffs)
        tabs.append(f'<button class="tab-btn" data-tab="shaders">Shader ({shader_count})</button>')
        tab_contents.append(self._render_shader_tab(diff.shader_diffs))
        
        # Buffer 标签页
        buffer_count = len(diff.buffer_diffs)
        tabs.append(f'<button class="tab-btn" data-tab="buffers">缓冲区 ({buffer_count})</button>')
        tab_contents.append(self._render_buffer_tab(diff.buffer_diffs))
        
        # Draw Call 标签页
        if self.config.include_draw_calls:
            dc_count = len(diff.draw_call_diffs)
            tabs.append(f'<button class="tab-btn" data-tab="drawcalls">Draw Calls ({dc_count})</button>')
            tab_contents.append(self._render_drawcall_tab(diff.draw_call_diffs))
        
        return f'''
        <div class="panel">
            <div class="tabs">
                {"".join(tabs)}
            </div>
            {"".join(tab_contents)}
        </div>
        '''
    
    def _render_texture_tab(self, textures: List[TextureDiff]) -> str:
        """渲染纹理标签页"""
        if not textures:
            return '''
            <div id="textures" class="tab-content active">
                <div class="empty-state">
                    <div class="empty-state-icon">🖼️</div>
                    <p>无纹理变化</p>
                </div>
            </div>
            '''
        
        rows = []
        for tex in textures[:self.config.max_resources]:
            status_badge = f'<span class="status-badge {tex.status.value}">{tex.status.value}</span>'
            
            # 分辨率变化
            res_html = f"{tex.width}×{tex.height}"
            if tex.changes.get("width") or tex.changes.get("height"):
                old_w, new_w = tex.changes.get("width", (tex.width, tex.width))
                old_h, new_h = tex.changes.get("height", (tex.height, tex.height))
                res_html = f'<span class="old-value">{old_w}×{old_h}</span> → {new_w}×{new_h}'
            
            rows.append(f'''
            <tr>
                <td>{status_badge}</td>
                <td>{html.escape(tex.name or tex.resource_id)}</td>
                <td>{res_html}</td>
                <td>{html.escape(tex.format)}</td>
                <td>{self._format_value(tex.memory_size, "memory")}</td>
            </tr>
            ''')
        
        return f'''
        <div id="textures" class="tab-content active">
            <table class="diff-table">
                <thead>
                    <tr>
                        <th style="width:80px">状态</th>
                        <th>名称</th>
                        <th>分辨率</th>
                        <th>格式</th>
                        <th>大小</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        '''
    
    def _render_shader_tab(self, shaders: List[ShaderDiff]) -> str:
        """渲染 Shader 标签页"""
        if not shaders:
            return '''
            <div id="shaders" class="tab-content">
                <div class="empty-state">
                    <div class="empty-state-icon">📜</div>
                    <p>无 Shader 变化</p>
                </div>
            </div>
            '''
        
        rows = []
        for shader in shaders[:self.config.max_resources]:
            status_badge = f'<span class="status-badge {shader.status.value}">{shader.status.value}</span>'
            
            rows.append(f'''
            <tr>
                <td>{status_badge}</td>
                <td>{html.escape(shader.shader_type)}</td>
                <td>{html.escape(shader.name or shader.resource_id)}</td>
                <td><code>{html.escape(shader.hash[:16] + "..." if len(shader.hash) > 16 else shader.hash)}</code></td>
            </tr>
            ''')
        
        return f'''
        <div id="shaders" class="tab-content">
            <table class="diff-table">
                <thead>
                    <tr>
                        <th style="width:80px">状态</th>
                        <th style="width:80px">类型</th>
                        <th>名称</th>
                        <th>Hash</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        '''
    
    def _render_buffer_tab(self, buffers: List[BufferDiff]) -> str:
        """渲染缓冲区标签页"""
        if not buffers:
            return '''
            <div id="buffers" class="tab-content">
                <div class="empty-state">
                    <div class="empty-state-icon">💾</div>
                    <p>无缓冲区变化</p>
                </div>
            </div>
            '''
        
        rows = []
        for buf in buffers[:self.config.max_resources]:
            status_badge = f'<span class="status-badge {buf.status.value}">{buf.status.value}</span>'
            
            # 大小变化
            size_html = self._format_value(buf.size, "memory")
            if buf.changes.get("size"):
                old_size, new_size = buf.changes["size"]
                size_html = f'<span class="old-value">{self._format_value(old_size, "memory")}</span> → {self._format_value(new_size, "memory")}'
            
            rows.append(f'''
            <tr>
                <td>{status_badge}</td>
                <td>{html.escape(buf.name or buf.resource_id)}</td>
                <td>{size_html}</td>
                <td>{html.escape(buf.usage)}</td>
            </tr>
            ''')
        
        return f'''
        <div id="buffers" class="tab-content">
            <table class="diff-table">
                <thead>
                    <tr>
                        <th style="width:80px">状态</th>
                        <th>名称</th>
                        <th>大小</th>
                        <th>用途</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        '''
    
    def _render_drawcall_tab(self, draw_calls: List[DrawCallDiff]) -> str:
        """渲染 Draw Call 标签页"""
        if not draw_calls:
            return '''
            <div id="drawcalls" class="tab-content">
                <div class="empty-state">
                    <div class="empty-state-icon">🎨</div>
                    <p>无 Draw Call 变化</p>
                </div>
            </div>
            '''
        
        rows = []
        for dc in draw_calls[:self.config.max_draw_calls]:
            status_badge = f'<span class="status-badge {dc.status.value}">{dc.status.value}</span>'
            
            match_html = ""
            if dc.matched_event_id is not None:
                match_html = f" → {dc.matched_event_id}"
            
            rows.append(f'''
            <tr>
                <td>{status_badge}</td>
                <td>{dc.event_id}{match_html}</td>
                <td>{html.escape(dc.draw_type)}</td>
                <td>{dc.vertex_count:,}</td>
                <td>{dc.index_count:,}</td>
            </tr>
            ''')
        
        return f'''
        <div id="drawcalls" class="tab-content">
            <table class="diff-table">
                <thead>
                    <tr>
                        <th style="width:80px">状态</th>
                        <th>Event ID</th>
                        <th>类型</th>
                        <th>顶点数</th>
                        <th>索引数</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        '''
