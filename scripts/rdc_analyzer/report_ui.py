"""
Report UI Shell - 四视图报告骨架

职责：
- 生成统一的 HTML 报告壳
- 提供四个主视图：Issues, Events, Resources, Performance
- 渲染 Manifest 状态栏
- 支持深色/浅色主题

设计原则：
- 渐进增强：骨架先行，内容后填
- 模块化：每个视图独立渲染函数
- 主题化：CSS 变量支持切换
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import html as html_module

from scripts.rdc_analyzer.report_contract import ReportDataContract, build_manifest
from scripts.rdc_analyzer.core.issue_detector import Issue, detect_all_issues


# =============================================================================
# 配置类
# =============================================================================

@dataclass
class ReportUIConfig:
    """UI 渲染配置"""
    theme: str = "dark"  # "dark" or "light"
    show_manifest_bar: bool = True
    default_view: str = "issues"  # "issues", "events", "resources", "performance"
    embed_css: bool = True  # 是否内嵌 CSS（否则引用外部文件）


# =============================================================================
# CSS 模板
# =============================================================================

DARK_THEME_CSS = """
:root {
    --bg-primary: #1e1e1e;
    --bg-secondary: #252526;
    --bg-tertiary: #2d2d30;
    --text-primary: #d4d4d4;
    --text-secondary: #9d9d9d;
    --accent-color: #569cd6;
    --success-color: #4ec9b0;
    --warning-color: #dcdcaa;
    --error-color: #f14c4c;
    --border-color: #3c3c3c;
}
"""

LIGHT_THEME_CSS = """
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f3f3f3;
    --bg-tertiary: #e8e8e8;
    --text-primary: #1e1e1e;
    --text-secondary: #6e6e6e;
    --accent-color: #0066cc;
    --success-color: #107c10;
    --warning-color: #ca5010;
    --error-color: #d13438;
    --border-color: #d4d4d4;
}
"""

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
}
.container { max-width: 1400px; margin: 0 auto; padding: 16px; }

/* Manifest Bar */
.manifest-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    font-size: 13px;
}
.manifest-bar .coverage { font-weight: 600; }
.manifest-bar .coverage.warning { color: var(--warning-color); }
.manifest-bar .coverage.ok { color: var(--success-color); }
.manifest-bar .stats { color: var(--text-secondary); }

/* Navigation Tabs */
.nav-tabs {
    display: flex;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
}
.nav-tab {
    padding: 12px 24px;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    transition: all 0.2s;
}
.nav-tab:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.nav-tab.active { 
    color: var(--accent-color); 
    border-bottom-color: var(--accent-color);
}

/* View Panels */
.view-panel { display: none; padding: 16px; }
.view-panel.active { display: block; }

/* Issues View */
.issue-group { margin-bottom: 24px; }
.issue-group-title {
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 12px;
}
.issue-group-title.critical { color: var(--error-color); }
.issue-group-title.warning { color: var(--warning-color); }
.issue-group-title.info { color: var(--text-secondary); }

.issue-card {
    padding: 12px;
    background: var(--bg-secondary);
    border-radius: 4px;
    margin-bottom: 8px;
    border-left: 3px solid var(--border-color);
}
.issue-card.critical { border-left-color: var(--error-color); }
.issue-card.warning { border-left-color: var(--warning-color); }
.issue-card.info { border-left-color: var(--accent-color); }

.issue-title { font-weight: 600; margin-bottom: 4px; }
.issue-desc { font-size: 13px; color: var(--text-secondary); }
.issue-suggestion { font-size: 12px; color: var(--success-color); margin-top: 8px; }

/* Empty State */
.empty-state {
    text-align: center;
    padding: 48px;
    color: var(--text-secondary);
}
.empty-state .icon { font-size: 48px; margin-bottom: 16px; }

/* Placeholder Views */
.placeholder-view {
    text-align: center;
    padding: 64px;
    color: var(--text-secondary);
}
"""

# =============================================================================
# HTML 模板
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
{theme_css}
{base_css}
    </style>
</head>
<body>
{manifest_bar}
<nav class="nav-tabs">
    <div class="nav-tab{issues_active}" data-view="issues">🔍 Issues</div>
    <div class="nav-tab{events_active}" data-view="events">📋 Events</div>
    <div class="nav-tab{resources_active}" data-view="resources">📦 Resources</div>
    <div class="nav-tab{performance_active}" data-view="performance">📊 Performance</div>
</nav>
<main class="container">
    <div id="view-issues" class="view-panel{issues_panel_active}">
{issues_content}
    </div>
    <div id="view-events" class="view-panel{events_panel_active}">
{events_content}
    </div>
    <div id="view-resources" class="view-panel{resources_panel_active}">
{resources_content}
    </div>
    <div id="view-performance" class="view-panel{performance_panel_active}">
{performance_content}
    </div>
</main>
<script>
document.querySelectorAll('.nav-tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('view-' + tab.dataset.view).classList.add('active');
    }});
}});
</script>
</body>
</html>
"""


# =============================================================================
# 渲染函数
# =============================================================================

def render_manifest_bar(manifest: Dict[str, Any]) -> str:
    """
    渲染 Manifest 状态栏
    
    Args:
        manifest: build_manifest() 返回的字典
        
    Returns:
        HTML 字符串
    """
    coverage = manifest.get("coverage_percent", 0)
    counts = manifest.get("counts", {})
    
    # 覆盖率状态
    coverage_class = "warning" if coverage < 80 else "ok"
    
    # 统计信息
    stats_parts = []
    if counts.get("textures", 0) > 0:
        stats_parts.append(f"Textures: {counts['textures']}")
    if counts.get("events", 0) > 0:
        stats_parts.append(f"Events: {counts['events']}")
    if counts.get("shaders", 0) > 0:
        stats_parts.append(f"Shaders: {counts['shaders']}")
    
    stats_html = " | ".join(stats_parts) if stats_parts else "No data loaded"
    
    return f'''<div class="manifest-bar">
    <span class="coverage {coverage_class}">Coverage: {coverage:.1f}%</span>
    <span class="stats">{stats_html}</span>
</div>'''


def render_issues_view(issues: List[Issue]) -> str:
    """
    渲染 Issues 视图
    
    Args:
        issues: Issue 对象列表
        
    Returns:
        HTML 字符串
    """
    if not issues:
        return '''<div class="empty-state">
    <div class="icon">✅</div>
    <p>No issues detected. Your frame looks good!</p>
</div>'''
    
    # 按严重性分组
    grouped = {"critical": [], "warning": [], "info": []}
    for issue in issues:
        grouped[issue.severity.value].append(issue)
    
    html_parts = []
    for severity in ["critical", "warning", "info"]:
        group_issues = grouped[severity]
        if not group_issues:
            continue
        
        html_parts.append(f'<div class="issue-group">')
        html_parts.append(f'<div class="issue-group-title {severity}">{severity.upper()} ({len(group_issues)})</div>')
        
        for issue in group_issues:
            title = html_module.escape(issue.title)
            desc = html_module.escape(issue.description)
            
            card = f'''<div class="issue-card {severity}">
    <div class="issue-title">{title}</div>
    <div class="issue-desc">{desc}</div>'''
            
            if issue.suggestion:
                suggestion = html_module.escape(issue.suggestion)
                card += f'\n    <div class="issue-suggestion">💡 {suggestion}</div>'
            
            card += '\n</div>'
            html_parts.append(card)
        
        html_parts.append('</div>')
    
    return '\n'.join(html_parts)


def render_events_view(events: List[Dict[str, Any]]) -> str:
    """
    渲染 Events 视图 - 层级化事件浏览器
    
    Args:
        events: 事件列表，支持嵌套 children 结构
                每个事件: {eid, name, type, children: [...]}
    
    Returns:
        HTML 字符串
    """
    if not events:
        return '''<div class="events-view">
    <div class="placeholder-view">
        <h2>📋 Events Browser</h2>
        <p>No events found in this capture</p>
    </div>
</div>'''
    
    def render_event_node(event: Dict[str, Any], depth: int = 0) -> str:
        """递归渲染单个事件节点"""
        eid = event.get('eid', 0)
        name = event.get('name', 'Unknown')
        event_type = event.get('type', 'unknown')
        children = event.get('children', [])
        
        has_children = len(children) > 0
        expanded_class = 'expanded' if has_children else ''
        node_class = f'event-node event-type-{event_type} {expanded_class}'.strip()
        
        # 缩进样式
        indent_px = depth * 20
        
        # 展开/折叠图标
        if has_children:
            toggle_icon = '<span class="tree-toggle">▼</span>'
        else:
            toggle_icon = '<span class="tree-leaf">•</span>'
        
        # 类型图标
        type_icons = {
            'marker': '🏷️',
            'pass': '📁',
            'draw': '🎨',
            'dispatch': '⚡',
            'clear': '🧹',
            'copy': '📋',
            'resolve': '🔄',
        }
        type_icon = type_icons.get(event_type, '📌')
        
        # 构建节点 HTML
        node_html = f'''<div class="{node_class}" data-eid="{eid}" data-type="{event_type}" style="padding-left: {indent_px}px;">
    <div class="event-header">
        {toggle_icon}
        <span class="event-icon">{type_icon}</span>
        <span class="event-eid">[{eid}]</span>
        <span class="event-name">{name}</span>
    </div>'''
        
        # 递归渲染子节点
        if has_children:
            node_html += '\n    <div class="event-children">'
            for child in children:
                node_html += '\n' + render_event_node(child, depth + 1)
            node_html += '\n    </div>'
        
        node_html += '\n</div>'
        return node_html
    
    # 构建完整视图
    html_parts = [
        '<div class="events-view">',
        '  <div class="events-toolbar">',
        '    <button class="btn-expand-all" title="Expand All">📂 Expand All</button>',
        '    <button class="btn-collapse-all" title="Collapse All">📁 Collapse All</button>',
        f'    <span class="events-count">{len(events)} root events</span>',
        '  </div>',
        '  <div class="events-tree">',
    ]
    
    for event in events:
        html_parts.append(render_event_node(event, 0))
    
    html_parts.append('  </div>')
    html_parts.append('</div>')
    
    return '\n'.join(html_parts)


def render_resources_view(contract: ReportDataContract) -> str:
    """
    渲染 Resources 视图 - 资源浏览器
    
    Args:
        contract: ReportDataContract 实例，包含 textures 和 shaders
    
    Returns:
        HTML 字符串
    """
    textures = contract.textures or []
    shaders = contract.shaders or []
    
    has_textures = len(textures) > 0
    has_shaders = len(shaders) > 0
    
    # 空资源状态
    if not has_textures and not has_shaders:
        return '''<div class="resources-view">
    <div class="placeholder-view">
        <h2>📦 Resource Explorer</h2>
        <p>No resources found in this capture</p>
    </div>
</div>'''
    
    html_parts = ['<div class="resources-view">']
    
    # 纹理分区
    if has_textures:
        html_parts.append('  <div class="resource-section texture-section">')
        html_parts.append(f'    <h3 class="section-heading">🖼️ Textures ({len(textures)})</h3>')
        html_parts.append('    <div class="texture-grid">')
        
        for tex in textures:
            tex_id = tex.get('resource_id', 'unknown')
            name = html_module.escape(str(tex.get('name', 'Unnamed')))
            width = tex.get('width', 0)
            height = tex.get('height', 0)
            fmt = tex.get('format', 'Unknown')
            mips = tex.get('mips', 1)
            thumbnail = tex.get('thumbnail', '')
            
            # 缩略图或占位符
            if thumbnail:
                thumb_html = f'<img src="{thumbnail}" alt="{name}" class="texture-thumb" />'
            else:
                thumb_html = '<div class="texture-thumb-placeholder">📷</div>'
            
            html_parts.append(f'''      <div class="texture-card" data-id="{tex_id}">
        {thumb_html}
        <div class="texture-info">
          <div class="texture-name" title="{name}">{name}</div>
          <div class="texture-dims">{width} × {height}</div>
          <div class="texture-format">{fmt}</div>
          <div class="texture-mips">Mips: {mips}</div>
        </div>
      </div>''')
        
        html_parts.append('    </div>')
        html_parts.append('  </div>')
    
    # Shader 分区
    if has_shaders:
        html_parts.append('  <div class="resource-section shader-section">')
        html_parts.append(f'    <h3 class="section-heading">📜 Shaders ({len(shaders)})</h3>')
        html_parts.append('    <div class="shader-list">')
        
        # Shader 类型图标
        shader_icons = {
            'vertex': '🔺 VS',
            'pixel': '🎨 PS',
            'fragment': '🎨 FS',
            'compute': '⚡ CS',
            'geometry': '🔷 GS',
            'hull': '📐 HS',
            'domain': '📏 DS',
        }
        
        for shader in shaders:
            shader_id = shader.get('resource_id', 'unknown')
            name = html_module.escape(str(shader.get('name', 'Unnamed')))
            shader_type = shader.get('type', 'unknown').lower()
            entry = shader.get('entry_point', 'main')
            
            type_badge = shader_icons.get(shader_type, f'📄 {shader_type.upper()}')
            
            html_parts.append(f'''      <div class="shader-card" data-id="{shader_id}" data-type="{shader_type}">
        <span class="shader-type-badge">{type_badge}</span>
        <span class="shader-name" title="{name}">{name}</span>
        <span class="shader-entry">entry: {entry}</span>
      </div>''')
        
        html_parts.append('    </div>')
        html_parts.append('  </div>')
    
    html_parts.append('</div>')
    
    return '\n'.join(html_parts)


def render_performance_view(performance: Dict[str, Any]) -> str:
    """
    渲染 Performance 视图 - 性能仪表盘
    
    Args:
        performance: 性能数据字典，包含帧时间、DrawCall数量等
    
    Returns:
        HTML 字符串
    """
    if not performance:
        return '''<div class="performance-view">
    <div class="placeholder-view">
        <h2>📊 Performance Dashboard</h2>
        <p>No performance data available</p>
    </div>
</div>'''
    
    html_parts = ['<div class="performance-view">']
    
    # === 指标卡片区 ===
    html_parts.append('  <div class="metrics-section">')
    html_parts.append('    <h3 class="section-heading">📈 Key Metrics</h3>')
    html_parts.append('    <div class="metric-cards">')
    
    # 定义指标配置
    metrics = [
        ('frame_time_ms', '⏱️ Frame Time', 'ms', '{:.1f}'),
        ('draw_call_count', '🎨 Draw Calls', '', '{:,}'),
        ('triangle_count', '🔺 Triangles', '', '{:,}'),
        ('texture_memory_mb', '🖼️ Texture Memory', 'MB', '{:.1f}'),
        ('buffer_memory_mb', '📦 Buffer Memory', 'MB', '{:.1f}'),
        ('render_target_count', '🎯 Render Targets', '', '{}'),
    ]
    
    for key, label, unit, fmt in metrics:
        if key in performance:
            value = performance[key]
            try:
                formatted_value = fmt.format(value)
            except (ValueError, TypeError):
                formatted_value = str(value)
            
            unit_html = f' <span class="metric-unit">{unit}</span>' if unit else ''
            
            html_parts.append(f'''      <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{formatted_value}{unit_html}</div>
      </div>''')
    
    html_parts.append('    </div>')
    html_parts.append('  </div>')
    
    # === Pass 耗时分解 ===
    passes = performance.get('passes', [])
    if passes:
        html_parts.append('  <div class="passes-section">')
        html_parts.append('    <h3 class="section-heading">📊 Pass Breakdown</h3>')
        html_parts.append('    <div class="pass-list">')
        
        # 计算总时间用于百分比
        total_time = sum(p.get('duration_ms', 0) for p in passes)
        
        for p in passes:
            name = html_module.escape(str(p.get('name', 'Unknown')))
            duration = p.get('duration_ms', 0)
            pct = (duration / total_time * 100) if total_time > 0 else 0
            
            html_parts.append(f'''      <div class="pass-row">
        <span class="pass-name">{name}</span>
        <div class="pass-bar-container">
          <div class="pass-bar" style="width: {pct:.1f}%"></div>
        </div>
        <span class="pass-time">{duration:.2f} ms ({pct:.1f}%)</span>
      </div>''')
        
        html_parts.append('    </div>')
        html_parts.append('  </div>')
    
    # === 时序图占位 ===
    html_parts.append('  <div class="timeline-section">')
    html_parts.append('    <h3 class="section-heading">📈 Timeline Chart</h3>')
    
    timeline = performance.get('timeline', [])
    if timeline:
        html_parts.append('    <div class="timeline-placeholder">')
        html_parts.append(f'      <p>Timeline data available ({len(timeline)} events)</p>')
        html_parts.append('      <p class="coming-soon">Interactive chart coming soon</p>')
        html_parts.append('    </div>')
    else:
        html_parts.append('    <div class="timeline-placeholder">')
        html_parts.append('      <p class="coming-soon">Timeline chart coming soon</p>')
        html_parts.append('    </div>')
    
    html_parts.append('  </div>')
    html_parts.append('</div>')
    
    return '\n'.join(html_parts)


def render_report_shell(
    contract: ReportDataContract,
    config: Optional[ReportUIConfig] = None
) -> str:
    """
    渲染完整报告骨架
    
    Args:
        contract: ReportDataContract 实例
        config: UI 配置（可选）
        
    Returns:
        完整的 HTML 字符串
    """
    if config is None:
        config = ReportUIConfig()
    
    # 构建 Manifest
    manifest = build_manifest(contract)
    
    # 检测问题
    issues = detect_all_issues(contract)
    
    # 选择主题 CSS
    theme_css = DARK_THEME_CSS if config.theme == "dark" else LIGHT_THEME_CSS
    
    # 确定激活的视图
    active_view = config.default_view
    
    def active_class(view: str) -> str:
        return " active" if view == active_view else ""
    
    # 渲染各视图内容
    issues_content = render_issues_view(issues)
    events_content = render_events_view(contract.events)
    resources_content = render_resources_view(contract)
    performance_content = render_performance_view(contract.performance)
    
    # Manifest 状态栏
    manifest_bar = render_manifest_bar(manifest) if config.show_manifest_bar else ""
    
    # 标题
    title = contract.meta.get("title", "RDC Analysis Report")
    
    return HTML_TEMPLATE.format(
        title=html_module.escape(title),
        theme_css=theme_css,
        base_css=BASE_CSS,
        manifest_bar=manifest_bar,
        issues_active=active_class("issues"),
        events_active=active_class("events"),
        resources_active=active_class("resources"),
        performance_active=active_class("performance"),
        issues_panel_active=active_class("issues"),
        events_panel_active=active_class("events"),
        resources_panel_active=active_class("resources"),
        performance_panel_active=active_class("performance"),
        issues_content=issues_content,
        events_content=events_content,
        resources_content=resources_content,
        performance_content=performance_content,
    )
