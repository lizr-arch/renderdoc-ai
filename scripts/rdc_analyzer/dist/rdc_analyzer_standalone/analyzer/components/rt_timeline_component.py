"""
RT Timeline HTML Component - 渲染目标时间线可视化组件

用于在 HTML 报告中显示 RT 绑定/解绑/Clear/Draw 操作序列
"""

from typing import Dict, List, Any


def generate_rt_timeline_css() -> str:
    """生成 RT Timeline CSS 样式"""
    return '''
/* RT Timeline Panel Styles */
.rt-timeline-panel {
    position: fixed;
    bottom: 60px;
    right: 20px;
    width: 450px;
    max-height: 400px;
    background: linear-gradient(135deg, #2a2a3e 0%, #1e1e2e 100%);
    border: 1px solid #404060;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    z-index: 1000;
    overflow: hidden;
    display: none;
}

.rt-timeline-panel.visible {
    display: block;
    animation: slideInRight 0.3s ease-out;
}

@keyframes slideInRight {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

.rt-timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
    cursor: pointer;
    user-select: none;
}

.rt-timeline-title {
    display: flex;
    align-items: center;
    gap: 8px;
    color: white;
    font-weight: 600;
}

.rt-timeline-badge {
    background: rgba(255,255,255,0.2);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
}

.rt-timeline-toggle {
    color: white;
    font-size: 14px;
}

.rt-timeline-content {
    padding: 12px;
    max-height: 320px;
    overflow-y: auto;
}

/* RT Summary Cards */
.rt-summary-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.rt-summary-card {
    background: rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 10px;
    text-align: center;
}

.rt-summary-value {
    font-size: 18px;
    font-weight: 700;
    color: #a78bfa;
}

.rt-summary-label {
    font-size: 10px;
    color: #888;
    text-transform: uppercase;
    margin-top: 4px;
}

/* RT Issues List */
.rt-issues-list {
    margin-top: 12px;
}

.rt-issue-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px;
    margin-bottom: 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 8px;
    border-left: 3px solid #f59e0b;
}

.rt-issue-item.warning {
    border-left-color: #ef4444;
}

.rt-issue-item.info {
    border-left-color: #6366f1;
}

.rt-issue-icon {
    font-size: 18px;
    flex-shrink: 0;
}

.rt-issue-content {
    flex: 1;
}

.rt-issue-title {
    font-size: 12px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 4px;
}

.rt-issue-desc {
    font-size: 11px;
    color: #94a3b8;
    line-height: 1.4;
}

.rt-issue-suggestion {
    font-size: 10px;
    color: #22c55e;
    margin-top: 4px;
    font-style: italic;
}

/* Timeline Visualization */
.rt-timeline-viz {
    margin-top: 12px;
    border: 1px solid #404060;
    border-radius: 8px;
    overflow: hidden;
}

.rt-timeline-row {
    display: flex;
    align-items: center;
    padding: 6px 10px;
    border-bottom: 1px solid #333350;
}

.rt-timeline-row:last-child {
    border-bottom: none;
}

.rt-timeline-label {
    width: 80px;
    font-size: 10px;
    color: #94a3b8;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.rt-timeline-bar {
    flex: 1;
    height: 16px;
    background: #1a1a2e;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}

.rt-timeline-event {
    position: absolute;
    height: 100%;
    min-width: 3px;
    border-radius: 2px;
}

.rt-timeline-event.clear {
    background: #f59e0b;
}

.rt-timeline-event.bind {
    background: #22c55e;
}

.rt-timeline-event.unbind {
    background: #ef4444;
}

.rt-timeline-event.draw {
    background: #6366f1;
}

/* Floating Button */
.rt-timeline-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    color: white;
    font-size: 20px;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    z-index: 999;
    transition: transform 0.2s, box-shadow 0.2s;
}

.rt-timeline-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
}
'''


def generate_rt_timeline_html(rt_data: Dict[str, Any]) -> str:
    """生成 RT Timeline HTML 面板
    
    Args:
        rt_data: RT 追踪数据，支持两种格式:
            格式1 (RTTracker): render_targets[], issues[], summary{}
            格式2 (旧格式): lifecycles[], issues[], timeline{}
    """
    # 兼容两种数据格式
    render_targets = rt_data.get('render_targets', rt_data.get('lifecycles', []))
    issues = rt_data.get('issues', [])
    summary = rt_data.get('summary', rt_data.get('timeline', {}).get('summary', {}))
    
    # 统计摘要
    total_rts = summary.get('total_rts', summary.get('totalRTs', len(render_targets)))
    total_clears = summary.get('total_clears', 0)
    total_binds = summary.get('total_binds', 0)
    total_issues = summary.get('total_issues', len(issues))
    
    # 计算总操作数
    total_ops = total_clears + total_binds
    for rt in render_targets:
        total_ops += rt.get('draw_count', rt.get('totalDraws', 0))
    
    # 生成问题列表 HTML
    issues_html = ''
    for issue in issues[:5]:  # 最多显示 5 个问题
        # 兼容两种 key 名称
        issue_type = issue.get('type', issue.get('issueType', 'info'))
        severity = issue.get('severity', 'info')
        message = issue.get('description', issue.get('message', ''))
        suggestion = issue.get('recommendation', issue.get('suggestion', ''))
        icon = '⚠️' if severity == 'warning' else 'ℹ️'
        
        issues_html += f'''
        <div class="rt-issue-item {severity}">
            <span class="rt-issue-icon">{icon}</span>
            <div class="rt-issue-content">
                <div class="rt-issue-title">{message}</div>
                <div class="rt-issue-suggestion">💡 {suggestion}</div>
            </div>
        </div>
        '''
    
    if not issues:
        issues_html = '<div style="text-align:center; color:#22c55e; padding:20px;">✅ 未发现 RT 问题</div>'
    
    # 生成时间线可视化 HTML
    # 支持新格式（从 render_targets[].events 提取）或旧格式（timeline.timeline）
    timeline_rows = {}
    
    # 新格式：从 render_targets 提取
    for rt in render_targets:
        resource_id = rt.get('resource_id', rt.get('resourceId', ''))
        events = rt.get('events', [])
        if events and resource_id:
            timeline_rows[resource_id] = events
    
    # 旧格式回退
    if not timeline_rows:
        timeline_rows = rt_data.get('timeline', {}).get('timeline', {})
    
    timeline_html = ''
    
    # 计算最大 EID
    max_eid = 1
    for ops in timeline_rows.values():
        for op in ops:
            eid = op.get('eid', 0)
            if eid > max_eid:
                max_eid = eid
    
    for resource_id, ops in list(timeline_rows.items())[:8]:  # 最多显示 8 个 RT
        events_html = ''
        for op in ops:
            eid = op.get('eid', 0)
            # 兼容 RTOpType.CLEAR 枚举值或字符串
            op_type = op.get('type', '').lower()
            if op_type in ('clear', 'clear_depth'):
                css_class = 'clear'
            elif op_type in ('bind', 'unbind'):
                css_class = op_type
            elif op_type == 'draw':
                css_class = 'draw'
            else:
                css_class = 'bind'  # 默认
            
            left_pct = (eid / max_eid) * 100 if max_eid > 0 else 0
            events_html += f'<div class="rt-timeline-event {css_class}" style="left:{left_pct:.1f}%" title="EID {eid}: {op_type}"></div>'
        
        short_id = resource_id[-12:] if len(resource_id) > 12 else resource_id
        timeline_html += f'''
        <div class="rt-timeline-row">
            <div class="rt-timeline-label" title="{resource_id}">{short_id}</div>
            <div class="rt-timeline-bar">{events_html}</div>
        </div>
        '''
    
    return f'''
    <!-- RT Timeline Button -->
    <button class="rt-timeline-btn" onclick="toggleRTTimelinePanel()" title="RT Timeline">🎯</button>
    
    <!-- RT Timeline Panel -->
    <div class="rt-timeline-panel" id="rtTimelinePanel">
        <div class="rt-timeline-header" onclick="toggleRTTimelinePanel()">
            <div class="rt-timeline-title">
                <span>🎯 Render Target Timeline</span>
                <span class="rt-timeline-badge">{len(issues)} issues</span>
            </div>
            <span class="rt-timeline-toggle">▼</span>
        </div>
        <div class="rt-timeline-content">
            <div class="rt-summary-grid">
                <div class="rt-summary-card">
                    <div class="rt-summary-value">{total_rts}</div>
                    <div class="rt-summary-label">Total RTs</div>
                </div>
                <div class="rt-summary-card">
                    <div class="rt-summary-value">{total_ops}</div>
                    <div class="rt-summary-label">Operations</div>
                </div>
                <div class="rt-summary-card">
                    <div class="rt-summary-value">{total_issues}</div>
                    <div class="rt-summary-label">With Issues</div>
                </div>
            </div>
            
            <h4 style="color:#e2e8f0; font-size:12px; margin:12px 0 8px;">⚠️ 检测到的问题</h4>
            <div class="rt-issues-list">{issues_html}</div>
            
            <h4 style="color:#e2e8f0; font-size:12px; margin:16px 0 8px;">📊 操作时间线</h4>
            <div class="rt-timeline-viz">{timeline_html}</div>
            
            <div style="display:flex; gap:12px; margin-top:10px; font-size:10px;">
                <span><span style="color:#22c55e">●</span> Bind</span>
                <span><span style="color:#ef4444">●</span> Unbind</span>
                <span><span style="color:#f59e0b">●</span> Clear</span>
                <span><span style="color:#6366f1">●</span> Draw</span>
            </div>
        </div>
    </div>
    '''


def generate_rt_timeline_js() -> str:
    """生成 RT Timeline JS 代码"""
    return '''
// RT Timeline Panel Toggle
function toggleRTTimelinePanel() {
    const panel = document.getElementById('rtTimelinePanel');
    if (panel) {
        panel.classList.toggle('visible');
    }
}
'''


def generate_mock_rt_data() -> Dict[str, Any]:
    """生成模拟 RT 数据用于测试"""
    return {
        "lifecycles": [
            {"resourceId": "RT_Color_Main", "totalClears": 3, "totalBinds": 5, "totalDraws": 120},
            {"resourceId": "RT_Depth", "totalClears": 1, "totalBinds": 5, "totalDraws": 120},
            {"resourceId": "RT_GBuffer_0", "totalClears": 1, "totalBinds": 2, "totalDraws": 45},
        ],
        "issues": [
            {
                "issueType": "redundant_clear",
                "severity": "warning",
                "resourceId": "RT_Bloom",
                "message": "RT_Bloom 在 EID 256 被 Clear 后没有被使用",
                "suggestion": "考虑移除该 Clear 操作"
            },
            {
                "issueType": "unused_rt",
                "severity": "info",
                "resourceId": "RT_Debug",
                "message": "RT_Debug 被绑定 3 次但从未用于 Draw",
                "suggestion": "检查是否是调试用途"
            }
        ],
        "timeline": {
            "timeline": {
                "RT_Color_Main": [
                    {"eid": 10, "type": "bind", "slot": 0},
                    {"eid": 15, "type": "clear", "slot": 0},
                    {"eid": 20, "type": "draw", "slot": 0},
                    {"eid": 50, "type": "draw", "slot": 0},
                    {"eid": 100, "type": "unbind", "slot": 0},
                ],
                "RT_Depth": [
                    {"eid": 10, "type": "bind", "slot": -1},
                    {"eid": 15, "type": "clear_depth", "slot": -1},
                    {"eid": 20, "type": "draw", "slot": -1},
                    {"eid": 100, "type": "unbind", "slot": -1},
                ],
            },
            "summary": {
                "totalRTs": 3,
                "totalOps": 45,
                "rtWithIssues": 2
            }
        }
    }
