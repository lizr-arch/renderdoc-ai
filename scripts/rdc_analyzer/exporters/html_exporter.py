"""
HTML 可交互视图导出器
=====================

生成带搜索/筛选功能的调用链浏览器
支持依赖图可视化、问题高亮、资源追踪等功能
"""

import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.pipeline_state import DrawCallDetail
from ..analysis.call_analyzer import BindingIssue
from ..analysis.resource_tracker import ResourceDependency, ResourceLifetime
from .json_exporter import JSONExporter, EnhancedJSONEncoder
from .templates import TemplateLoader, DARK_THEME, LIGHT_THEME


@dataclass
class HTMLExportConfig:
    """HTML 导出配置"""
    
    # 页面标题
    title: str = "RDC Call Chain Analyzer"
    
    # 主题
    theme: str = "dark"  # 'dark' or 'light'
    
    # 功能开关
    include_search: bool = True
    include_filter: bool = True
    include_dependency_graph: bool = True
    include_statistics: bool = True
    include_timeline: bool = True
    
    # 性能优化
    lazy_load_threshold: int = 1000  # 超过此数量时启用懒加载



class HTMLExporter:
    """HTML 导出器"""
    
    def __init__(self, config: Optional[HTMLExportConfig] = None):
        self.config = config or HTMLExportConfig()
        self.json_exporter = JSONExporter()
        self.template_loader = TemplateLoader()
    
    def export(
        self,
        draws: List[DrawCallDetail],
        issues: Optional[List[BindingIssue]] = None,
        dependencies: Optional[List[ResourceDependency]] = None,
        lifetimes: Optional[Dict[int, ResourceLifetime]] = None,
        source_file: Optional[str] = None,
        api_type: Optional[str] = None,
        performance_report: Optional[Dict[str, Any]] = None,
        mali_report: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        导出为 HTML 字符串
        
        Args:
            draws: Draw call 详情列表
            issues: 绑定问题列表
            dependencies: 资源依赖列表
            lifetimes: 资源生命周期字典
            source_file: 源文件名
            api_type: API 类型
            performance_report: 性能分析报告字典
            mali_report: Mali GPU 分析报告字典
        
        Returns:
            完整的 HTML 页面内容
        """
        # 首先获取 JSON 数据
        json_str = self.json_exporter.export(
            draws, issues, dependencies, lifetimes, source_file, api_type
        )
        json_data = json.loads(json_str)
        
        # 生成各部分 HTML
        statistics_html = self._generate_statistics_html(json_data.get('statistics', {}))
        call_list_html = self._generate_call_list_html(json_data.get('draw_calls', []), json_data.get('issues', []))
        issues_html = self._generate_issues_html(json_data.get('issues', []))
        dependencies_html = self._generate_dependencies_html(json_data.get('dependencies', []))
        resources_html = self._generate_resources_html(json_data.get('resource_lifetimes', []), len(draws))
        performance_html = self._generate_performance_html(performance_report)
        mali_html = self._generate_mali_html(mali_report)
        
        # 主题颜色 - 使用 templates 模块中的常量
        colors = DARK_THEME if self.config.theme == 'dark' else LIGHT_THEME
        
        # 元数据
        metadata = json_data.get('metadata', {})
        header_meta = f"Source: {metadata.get('source_file', 'N/A')} | API: {metadata.get('api_type', 'N/A')}"
        
        # 加载模板资源
        styles_css = self.template_loader.load_styles(self.config.theme)
        scripts_js = self.template_loader.load_scripts()
        base_html = self.template_loader.load_base_html()
        
        # 在 JavaScript 中替换 {json_data} 占位符
        # 注意: json_data 在 main.js 中，不在 base.html 中
        scripts_js = scripts_js.replace('{json_data}', json_str)
        
        # 渲染模板
        return base_html.format(
            title=html.escape(self.config.title),
            export_time=metadata.get('export_time', datetime.now().isoformat()),
            header_meta=html.escape(header_meta),
            statistics_html=statistics_html,
            call_list_html=call_list_html,
            call_count=len(draws),
            issues_html=issues_html,
            dependencies_html=dependencies_html,
            resources_html=resources_html,
            performance_html=performance_html,
            mali_html=mali_html,
            styles=styles_css,
            scripts=scripts_js,
        )
    
    def export_to_file(
        self,
        output_path: Union[str, Path],
        draws: List[DrawCallDetail],
        issues: Optional[List[BindingIssue]] = None,
        dependencies: Optional[List[ResourceDependency]] = None,
        lifetimes: Optional[Dict[int, ResourceLifetime]] = None,
        source_file: Optional[str] = None,
        api_type: Optional[str] = None,
        performance_report: Optional[Dict[str, Any]] = None,
        mali_report: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """导出为 HTML 文件"""
        output_path = Path(output_path)
        html_content = self.export(
            draws, issues, dependencies, lifetimes, source_file, api_type,
            performance_report=performance_report,
            mali_report=mali_report
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_statistics_html(self, stats: Dict[str, Any]) -> str:
        """生成统计卡片 HTML"""
        cards = [
            ('📊', 'Draw Calls', stats.get('total_draw_calls', 0), ''),
            ('⚠️', 'Issues', stats.get('total_issues', 0), 'error' if stats.get('total_issues', 0) > 0 else ''),
            ('🔗', 'Dependencies', stats.get('total_dependencies', 0), ''),
            ('📦', 'Resources', stats.get('total_resources', 0), ''),
        ]
        
        html_parts = []
        for icon, label, value, extra_class in cards:
            html_parts.append(f'''
                <div class="stat-card {extra_class}">
                    <div class="stat-value">{icon} {value}</div>
                    <div class="stat-label">{html.escape(label)}</div>
                </div>
            ''')
        
        return '\n'.join(html_parts)
    
    def _generate_call_list_html(self, draws: List[Dict], issues: List[Dict]) -> str:
        """生成调用列表 HTML"""
        issue_by_event = {}
        for issue in issues:
            eid = issue.get('event_id')
            issue_by_event[eid] = issue_by_event.get(eid, 0) + 1
        
        html_parts = []
        for draw in draws:
            event_id = draw.get('event_id', 0)
            name = draw.get('name', 'Unknown')
            issue_count = issue_by_event.get(event_id, 0)
            has_issues_class = 'has-issues' if issue_count > 0 else ''
            issue_badge = f'<span class="issue-badge">{issue_count}</span>' if issue_count > 0 else ''
            
            html_parts.append(f'''
                <div class="call-item {has_issues_class}" data-event-id="{event_id}">
                    <span class="call-id">#{event_id}</span>
                    <span class="call-name">{html.escape(name)}</span>
                    {issue_badge}
                </div>
            ''')
        
        return '\n'.join(html_parts)
    
    def _generate_issues_html(self, issues: List[Dict]) -> str:
        """生成问题列表 HTML"""
        if not issues:
            return '''
                <div class="empty-state">
                    <div class="empty-state-icon">✅</div>
                    <p>No issues detected</p>
                </div>
            '''
        
        html_parts = []
        for issue in issues:
            severity = issue.get('severity', 'info').lower()
            severity_class = f'severity-{severity}'
            item_class = 'warning' if severity == 'warning' else ('info' if severity == 'info' else '')
            
            html_parts.append(f'''
                <div class="issue-item {item_class}">
                    <div class="issue-header">
                        <span class="issue-rule">[{html.escape(issue.get('rule_id', 'UNKNOWN'))}] Event #{issue.get('event_id', 0)}</span>
                        <span class="issue-severity {severity_class}">{html.escape(severity)}</span>
                    </div>
                    <div class="issue-message">{html.escape(issue.get('message', ''))}</div>
                </div>
            ''')
        
        return '\n'.join(html_parts)
    
    def _generate_dependencies_html(self, dependencies: List[Dict]) -> str:
        """生成依赖关系 HTML"""
        if not dependencies:
            return '''
                <div class="empty-state">
                    <div class="empty-state-icon">🔗</div>
                    <p>No resource dependencies detected</p>
                </div>
            '''
        
        html_parts = ['<div class="dep-graph">']
        for dep in dependencies:
            dep_type = dep.get('dependency_type', 'UNKNOWN')
            resource_name = dep.get('resource_name', '')
            resource_id = dep.get('resource_id', 0)
            resource_type = dep.get('resource_type', 'BUFFER')
            
            # 创建可点击的资源链接
            if resource_name:
                resource_link = f'''<span class="resource-link" 
                    data-resource-id="{resource_id}"
                    onclick="openResourceModal({resource_id}, '{html.escape(resource_name)}', '{html.escape(resource_type)}')"
                    style="margin-left: auto; font-size: 12px;">{html.escape(resource_name)}</span>'''
            else:
                resource_link = ''
            
            html_parts.append(f'''
                <div class="dep-item">
                    <span class="dep-node">#{dep.get('source_event', 0)}</span>
                    <span class="dep-arrow">→</span>
                    <span class="dep-node">#{dep.get('target_event', 0)}</span>
                    <span class="dep-type {dep_type}">{dep_type}</span>
                    {resource_link}
                </div>
            ''')
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def _generate_resources_html(self, lifetimes: List[Dict], total_events: int) -> str:
        """生成资源生命周期 HTML"""
        if not lifetimes:
            return '''
                <div class="empty-state">
                    <div class="empty-state-icon">📦</div>
                    <p>No resource tracking data available</p>
                </div>
            '''
        
        # 找出实际的事件 ID 范围
        all_first = [lt.get('first_access_event', 0) for lt in lifetimes]
        all_last = [lt.get('last_access_event', 0) for lt in lifetimes]
        min_event = min(all_first) if all_first else 0
        max_event = max(all_last) if all_last else 1
        event_range = max(max_event - min_event, 1)  # 避免除零
        
        # 按资源类型和名称排序
        sorted_lifetimes = sorted(lifetimes, key=lambda x: (x.get('resource_type', ''), x.get('resource_name', '')))
        
        # 只显示前 50 个最活跃的资源（按读写次数排序）
        active_lifetimes = sorted(sorted_lifetimes, 
                                   key=lambda x: x.get('read_count', 0) + x.get('write_count', 0), 
                                   reverse=True)[:50]
        
        html_parts = [f'''
            <div style="margin-bottom: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                <strong>Resource Lifetime Overview</strong>
                <div style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Showing top {len(active_lifetimes)} of {len(lifetimes)} tracked resources 
                    (Event range: #{min_event} - #{max_event})
                </div>
            </div>
        ''']
        
        for lt in active_lifetimes:
            first = lt.get('first_access_event', 0)
            last = lt.get('last_access_event', 0)
            resource_name = str(lt.get('resource_name', 'Unknown'))
            resource_type = str(lt.get('resource_type', 'Unknown'))
            resource_id = lt.get('resource_id', 0)
            read_count = lt.get('read_count', 0)
            write_count = lt.get('write_count', 0)
            
            # 计算条形图位置 - 相对于事件范围
            left_pct = ((first - min_event) / event_range) * 100
            width_pct = max(((last - first) / event_range) * 100, 3)  # 最小 3% 宽度
            
            # 根据读写情况确定颜色
            if write_count > 0 and read_count > 0:
                bar_color = 'linear-gradient(90deg, var(--success), var(--accent))'  # 读写都有
            elif write_count > 0:
                bar_color = 'linear-gradient(90deg, var(--warning), var(--error))'  # 只写
            else:
                bar_color = 'linear-gradient(90deg, var(--info), var(--accent))'  # 只读
            
            # 警告标记
            warning_html = ''
            if lt.get('is_written_never_read'):
                warning_html = '<span style="color: var(--warning); margin-left: 8px;">⚠️ Written but never read</span>'
            
            # 资源名称使用可点击链接
            name_short = resource_name[:40]
            resource_link = f'''<span class="resource-link" 
                data-resource-id="{resource_id}" 
                data-resource-name="{html.escape(resource_name)}" 
                data-resource-type="{html.escape(resource_type)}"
                onclick="openResourceModal({resource_id}, '{html.escape(resource_name)}', '{html.escape(resource_type)}')"
                title="Click to view details">{html.escape(name_short)}</span>'''
            
            html_parts.append(f'''
                <div class="lifetime-item">
                    <div class="lifetime-header">
                        <span class="lifetime-name">{resource_link}</span>
                        <span class="lifetime-type">{html.escape(resource_type)}</span>
                    </div>
                    <div class="lifetime-bar" title="Events #{first} - #{last}">
                        <div class="lifetime-range" style="left: {left_pct:.1f}%; width: {width_pct:.1f}%; background: {bar_color};">
                            #{first} - #{last}
                        </div>
                    </div>
                    <div class="lifetime-stats">
                        <span>📖 Reads: {read_count}</span>
                        <span>✏️ Writes: {write_count}</span>
                        {warning_html}
                    </div>
                </div>
            ''')
        
        return '\n'.join(html_parts)
    
    def _generate_performance_html(self, report: Optional[Dict[str, Any]]) -> str:
        """生成性能分析 HTML"""
        if not report:
            return '''
                <div class="empty-state">
                    <div class="empty-state-icon">⚡</div>
                    <p>No performance analysis data available</p>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-top: 8px;">
                        Run performance analysis to see optimization opportunities
                    </p>
                </div>
            '''
        
        # 获取数据
        overall_score = report.get('overall_score', 0)
        issues = report.get('issues', [])
        metrics = report.get('metrics', {})
        recommendations = report.get('recommendations', [])
        
        # 计算分数等级和颜色
        if overall_score >= 90:
            score_class = 'perf-score-excellent'
            score_label = 'Excellent'
            ring_color = '#69db7c'  # success green
        elif overall_score >= 70:
            score_class = 'perf-score-good'
            score_label = 'Good'
            ring_color = '#a9e34b'  # lime
        elif overall_score >= 50:
            score_class = 'perf-score-fair'
            score_label = 'Fair'
            ring_color = '#ffa94d'  # warning orange
        else:
            score_class = 'perf-score-poor'
            score_label = 'Needs Improvement'
            ring_color = '#ff6b6b'  # error red
        
        # SVG 环形进度条参数
        radius = 70
        circumference = 2 * 3.14159 * radius
        progress_offset = circumference - (overall_score / 100) * circumference
        
        # 按规则分类问题
        issue_by_rule: Dict[str, List[Dict]] = {}
        for issue in issues:
            rule_id = issue.get('rule_id', 'UNKNOWN')
            if rule_id not in issue_by_rule:
                issue_by_rule[rule_id] = []
            issue_by_rule[rule_id].append(issue)
        
        # 规则描述映射
        rule_names = {
            'PERF001': '过度绘制 (Overdraw)',
            'PERF002': '状态冗余 (State Redundancy)',
            'PERF003': '小批次绘制 (Small Batches)',
            'PERF004': '大纹理 (Large Textures)',
            'PERF005': '未压缩纹理 (Uncompressed)',
            'PERF006': 'Alpha 混合过度',
            'PERF007': '频繁资源绑定',
        }
        
        # 构建 HTML
        html_parts = ['<div class="perf-dashboard">']
        
        # === 分数环和摘要 ===
        html_parts.append(f'''
            <div class="perf-score-container">
                <div class="perf-score-ring">
                    <svg width="160" height="160">
                        <circle class="bg" cx="80" cy="80" r="{radius}"></circle>
                        <circle class="progress" cx="80" cy="80" r="{radius}"
                            stroke="{ring_color}"
                            stroke-dasharray="{circumference}"
                            stroke-dashoffset="{progress_offset}">
                        </circle>
                    </svg>
                    <div class="perf-score-text">
                        <div class="perf-score-value {score_class}">{overall_score}</div>
                        <div class="perf-score-label">{score_label}</div>
                    </div>
                </div>
                
                <div class="perf-summary-stats">
                    <div class="perf-summary-item">
                        <div class="perf-summary-icon issues">⚠️</div>
                        <div>
                            <div class="perf-summary-value">{len(issues)}</div>
                            <div class="perf-summary-label">Performance Issues</div>
                        </div>
                    </div>
                    <div class="perf-summary-item">
                        <div class="perf-summary-icon draws">📊</div>
                        <div>
                            <div class="perf-summary-value">{metrics.get('total_draw_calls', 0)}</div>
                            <div class="perf-summary-label">Draw Calls Analyzed</div>
                        </div>
                    </div>
                    <div class="perf-summary-item">
                        <div class="perf-summary-icon textures">🖼️</div>
                        <div>
                            <div class="perf-summary-value">{metrics.get('total_textures', 0)}</div>
                            <div class="perf-summary-label">Textures Analyzed</div>
                        </div>
                    </div>
                </div>
            </div>
        ''')
        
        # === 分类卡片 ===
        if issue_by_rule:
            html_parts.append('<div class="perf-categories">')
            for rule_id, rule_issues in sorted(issue_by_rule.items()):
                count = len(rule_issues)
                rule_name = rule_names.get(rule_id, rule_id)
                
                # 根据问题数量确定严重程度
                if count >= 10:
                    card_class = 'error'
                    fill_class = 'high'
                    fill_width = 100
                elif count >= 5:
                    card_class = 'warning'
                    fill_class = 'medium'
                    fill_width = 60
                else:
                    card_class = 'success'
                    fill_class = 'low'
                    fill_width = 30
                
                html_parts.append(f'''
                    <div class="perf-category-card {card_class}">
                        <div class="perf-category-header">
                            <span class="perf-category-name">{html.escape(rule_name)}</span>
                            <span class="perf-category-count">{count}</span>
                        </div>
                        <div class="perf-category-bar">
                            <div class="perf-category-fill {fill_class}" style="width: {fill_width}%;"></div>
                        </div>
                    </div>
                ''')
            html_parts.append('</div>')
        
        # === 问题列表 ===
        if issues:
            html_parts.append('''
                <div class="perf-issues-section">
                    <div class="perf-issues-header">
                        <span class="perf-issues-title">⚠️ Detected Issues</span>
                        <div class="perf-issues-filter">
                            <button class="perf-filter-btn active" onclick="filterPerfIssues('all')">All</button>
                            <button class="perf-filter-btn" onclick="filterPerfIssues('critical')">Critical</button>
                            <button class="perf-filter-btn" onclick="filterPerfIssues('warning')">Warning</button>
                        </div>
                    </div>
                    <div id="perf-issues-list">
            ''')
            
            # 按影响分数排序
            sorted_issues = sorted(issues, key=lambda x: x.get('impact_score', 0), reverse=True)
            
            for issue in sorted_issues[:50]:  # 最多显示50个
                rule_id = issue.get('rule_id', 'UNKNOWN')
                message = issue.get('message', '')
                impact = issue.get('impact_score', 0)
                event_id = issue.get('event_id')
                resource_id = issue.get('resource_id')
                
                # 确定严重程度
                if impact >= 10:
                    severity_class = 'critical'
                    impact_color = '#ff6b6b'
                elif impact >= 5:
                    severity_class = 'warning'
                    impact_color = '#ffa94d'
                else:
                    severity_class = 'info'
                    impact_color = '#74c0fc'
                
                # 位置信息
                location_parts = []
                if event_id is not None:
                    location_parts.append(f'📍 Event #{event_id}')
                if resource_id is not None:
                    location_parts.append(f'📦 Resource #{resource_id}')
                location_html = ' &nbsp;|&nbsp; '.join(location_parts) if location_parts else ''
                
                html_parts.append(f'''
                    <div class="perf-issue-card {severity_class}" data-severity="{severity_class}">
                        <div class="perf-issue-header">
                            <span class="perf-issue-rule">{html.escape(rule_id)}</span>
                            <div class="perf-issue-impact">
                                <span>Impact: {impact}</span>
                                <div class="perf-impact-bar">
                                    <div class="perf-impact-fill" style="width: {min(impact * 10, 100)}%; background: {impact_color};"></div>
                                </div>
                            </div>
                        </div>
                        <div class="perf-issue-message">{html.escape(message)}</div>
                        <div class="perf-issue-details">
                            <span class="perf-issue-location">{location_html}</span>
                        </div>
                    </div>
                ''')
            
            html_parts.append('</div></div>')
        
        # === 建议 ===
        if recommendations:
            html_parts.append('''
                <div class="perf-recommendations">
                    <div class="perf-rec-title">💡 Optimization Recommendations</div>
                    <ul class="perf-rec-list">
            ''')
            
            for rec in recommendations:
                text = rec.get('text', '') if isinstance(rec, dict) else str(rec)
                priority = rec.get('priority', 'medium') if isinstance(rec, dict) else 'medium'
                
                priority_icons = {'high': '🔴', 'medium': '🟡', 'low': '🔵'}
                icon = priority_icons.get(priority, '🟡')
                
                html_parts.append(f'''
                    <li class="perf-rec-item">
                        <div class="perf-rec-icon {priority}">{icon}</div>
                        <div class="perf-rec-content">
                            <span class="perf-rec-text">{html.escape(text)}</span>
                            <span class="perf-rec-priority {priority}">{priority.upper()}</span>
                        </div>
                    </li>
                ''')
            
            html_parts.append('</ul></div>')
        
        html_parts.append('</div>')
        
        # 添加筛选 JavaScript
        html_parts.append('''
            <script>
                function filterPerfIssues(severity) {
                    document.querySelectorAll('.perf-filter-btn').forEach(btn => {
                        btn.classList.toggle('active', btn.textContent.toLowerCase() === severity);
                    });
                    
                    document.querySelectorAll('.perf-issue-card').forEach(card => {
                        if (severity === 'all') {
                            card.style.display = 'block';
                        } else {
                            card.style.display = card.dataset.severity === severity ? 'block' : 'none';
                        }
                    });
                }
            </script>
        ''')
        
        return '\n'.join(html_parts)
    
    def _generate_mali_html(self, report: Optional[Dict[str, Any]]) -> str:
        """生成 Mali GPU 分析 HTML"""
        if not report:
            return '''
                <div class="empty-state">
                    <div class="empty-state-icon">📱</div>
                    <p>No Mali GPU analysis data available</p>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-top: 8px;">
                        Enable Mali analysis and ensure malioc is installed to see GPU performance data.
                        <br><br>
                        <a href="https://developer.arm.com/Tools%20and%20Software/Mali%20Offline%20Compiler" 
                           target="_blank" style="color: var(--accent);">
                            Download Mali Offline Compiler
                        </a>
                    </p>
                </div>
            '''
        
        # 获取数据
        gpu_name = report.get('gpu_name', 'Unknown')
        total_shaders = report.get('total_shaders', 0)
        success_count = report.get('success_count', 0)
        failed_count = report.get('failed_count', 0)
        results = report.get('results', [])
        summary = report.get('summary', {})
        malioc_available = report.get('malioc_available', True)
        malioc_version = report.get('malioc_version', '')
        
        # 计算汇总统计
        total_arithmetic = summary.get('total_arithmetic_cycles', 0)
        total_texture = summary.get('total_texture_cycles', 0)
        high_pressure_count = len(summary.get('high_register_pressure', []))
        spill_count = len(summary.get('stack_spilling', []))
        arithmetic_bound = len(summary.get('arithmetic_bound', []))
        texture_bound = len(summary.get('texture_bound', []))
        
        # 构建 HTML
        html_parts = ['<div class="mali-dashboard">']
        
        # === 头部：GPU 选择器和状态 ===
        status_class = 'available' if malioc_available else 'unavailable'
        status_text = f'✓ malioc ready ({malioc_version})' if malioc_available else '✗ malioc not found'
        
        html_parts.append(f'''
            <div class="mali-header">
                <h3>📱 Mali GPU Performance Analysis</h3>
                <div class="mali-gpu-selector">
                    <label>Target GPU:</label>
                    <span class="mali-gpu-select" style="display: inline-block;">{html.escape(gpu_name)}</span>
                </div>
                <div class="mali-status {status_class}">
                    {status_text}
                </div>
            </div>
        ''')
        
        # === 汇总卡片 ===
        html_parts.append('<div class="mali-summary">')
        
        cards = [
            ('💻', 'Shaders Analyzed', f'{success_count}/{total_shaders}', ''),
            ('⚡', 'Total A Cycles', f'{total_arithmetic:.1f}', ''),
            ('🖼️', 'Total T Cycles', f'{total_texture:.1f}', ''),
            ('📊', 'A-Bound Shaders', str(arithmetic_bound), 'warning' if arithmetic_bound > 0 else ''),
            ('🎨', 'T-Bound Shaders', str(texture_bound), 'warning' if texture_bound > 0 else ''),
            ('⚠️', 'High Reg Pressure', str(high_pressure_count), 'error' if high_pressure_count > 0 else ''),
        ]
        
        for icon, label, value, extra_class in cards:
            html_parts.append(f'''
                <div class="mali-summary-card {extra_class}">
                    <div class="value">{icon} {value}</div>
                    <div class="label">{html.escape(label)}</div>
                </div>
            ''')
        
        html_parts.append('</div>')
        
        # === 周期图例 ===
        html_parts.append('''
            <div class="mali-legend">
                <div class="mali-legend-item">
                    <div class="mali-legend-color arithmetic"></div>
                    <span>Arithmetic (A)</span>
                </div>
                <div class="mali-legend-item">
                    <div class="mali-legend-color load-store"></div>
                    <span>Load/Store (LS)</span>
                </div>
                <div class="mali-legend-item">
                    <div class="mali-legend-color texture"></div>
                    <span>Texture (T)</span>
                </div>
                <div class="mali-legend-item">
                    <div class="mali-legend-color varying"></div>
                    <span>Varying (V)</span>
                </div>
            </div>
        ''')
        
        # === Shader 分析表格 ===
        if results:
            html_parts.append('''
                <div class="mali-shaders-section">
                    <h4>📋 Shader Analysis Results</h4>
                    <table class="mali-shader-table">
                        <thead>
                            <tr>
                                <th>Shader</th>
                                <th>Stage</th>
                                <th>Cycles</th>
                                <th>Breakdown</th>
                                <th>Bound</th>
                                <th>Registers</th>
                            </tr>
                        </thead>
                        <tbody>
            ''')
            
            for shader_result in results:
                name = shader_result.get('shader_name', 'Unknown')
                shader_type = shader_result.get('shader_type', '')
                cycles = shader_result.get('cycles', {})
                registers = shader_result.get('registers', {})
                success = shader_result.get('success', False)
                
                if not success:
                    # 分析失败的 Shader
                    error_msg = shader_result.get('error_message', 'Analysis failed')
                    html_parts.append(f'''
                        <tr>
                            <td class="mali-shader-name">{html.escape(name)}</td>
                            <td><span class="mali-stage-badge {shader_type[:2].lower()}">{shader_type}</span></td>
                            <td colspan="4" style="color: var(--error);">⚠️ {html.escape(error_msg)}</td>
                        </tr>
                    ''')
                    continue
                
                # 周期数据
                a_cycles = cycles.get('arithmetic', 0)
                ls_cycles = cycles.get('load_store', 0)
                t_cycles = cycles.get('texture', 0)
                v_cycles = cycles.get('varying', 0)
                total_cycles = cycles.get('total', 0) or (a_cycles + ls_cycles + t_cycles + v_cycles)
                bound = cycles.get('bound', '')
                
                # 计算百分比用于条形图
                if total_cycles > 0:
                    a_pct = (a_cycles / total_cycles) * 100
                    ls_pct = (ls_cycles / total_cycles) * 100
                    t_pct = (t_cycles / total_cycles) * 100
                    v_pct = (v_cycles / total_cycles) * 100
                else:
                    a_pct = ls_pct = t_pct = v_pct = 0
                
                # 寄存器信息
                work_regs = registers.get('work', 0)
                spilling = registers.get('stack_spilling', False)
                pressure_high = registers.get('pressure_high', False)
                
                reg_html = f'{work_regs}'
                if spilling:
                    reg_html += ' <span class="mali-reg-spill">⚠️ Spill!</span>'
                elif pressure_high:
                    reg_html += ' <span class="mali-reg-warning">⚠️</span>'
                
                # Stage badge class
                stage_class = shader_type[:2].lower() if shader_type else 'vs'
                
                html_parts.append(f'''
                    <tr>
                        <td class="mali-shader-name">{html.escape(name)}</td>
                        <td><span class="mali-stage-badge {stage_class}">{shader_type}</span></td>
                        <td>{total_cycles:.1f}</td>
                        <td>
                            <div class="mali-cycle-bar" title="A:{a_cycles:.1f} LS:{ls_cycles:.1f} T:{t_cycles:.1f} V:{v_cycles:.1f}">
                                <div class="segment arithmetic" style="width: {a_pct:.1f}%;"></div>
                                <div class="segment load-store" style="width: {ls_pct:.1f}%;"></div>
                                <div class="segment texture" style="width: {t_pct:.1f}%;"></div>
                                <div class="segment varying" style="width: {v_pct:.1f}%;"></div>
                            </div>
                        </td>
                        <td><span class="mali-bottleneck {bound}">{bound}</span></td>
                        <td>{reg_html}</td>
                    </tr>
                ''')
            
            html_parts.append('</tbody></table></div>')
        
        # === 优化建议 ===
        all_recommendations = []
        for shader_result in results:
            name = shader_result.get('shader_name', 'Unknown')
            recs = shader_result.get('recommendations', [])
            for rec in recs:
                all_recommendations.append((name, rec))
        
        if all_recommendations:
            html_parts.append('''
                <div class="mali-recommendations">
                    <div class="mali-rec-title">💡 Optimization Recommendations</div>
                    <ul class="mali-rec-list">
            ''')
            
            for shader_name, rec_text in all_recommendations[:20]:  # 最多显示20条
                html_parts.append(f'''
                    <li class="mali-rec-item">
                        <div class="mali-rec-icon">💡</div>
                        <div>
                            <div class="mali-rec-text">{html.escape(rec_text)}</div>
                            <div class="mali-rec-shader">Shader: {html.escape(shader_name)}</div>
                        </div>
                    </li>
                ''')
            
            html_parts.append('</ul></div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)


# 便捷函数
def export_to_html(
    draws: List[DrawCallDetail],
    output_path: Union[str, Path],
    issues: Optional[List[BindingIssue]] = None,
    dependencies: Optional[List[ResourceDependency]] = None,
    lifetimes: Optional[Dict[int, ResourceLifetime]] = None,
    source_file: Optional[str] = None,
    api_type: Optional[str] = None,
    config: Optional[HTMLExportConfig] = None,
    performance_report: Optional[Dict[str, Any]] = None,
    mali_report: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    导出分析结果为交互式 HTML 页面
    
    Args:
        draws: Draw Call 详情列表
        output_path: 输出文件路径
        issues: 检测到的问题列表
        dependencies: 资源依赖关系列表
        lifetimes: 资源生命周期字典
        source_file: 源 RDC 文件路径
        api_type: API 类型
        config: HTML 导出配置
        performance_report: 性能分析报告字典
        mali_report: Mali GPU 分析报告字典
    
    Returns:
        输出文件的 Path 对象
    """
    exporter = HTMLExporter(config)
    return exporter.export_to_file(
        output_path,
        draws,
        issues=issues,
        dependencies=dependencies,
        lifetimes=lifetimes,
        source_file=source_file,
        api_type=api_type,
        performance_report=performance_report,
        mali_report=mali_report,
    )
