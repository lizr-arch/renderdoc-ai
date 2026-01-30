"""
热点可视化组件 (Hotspot Visualization Component)
=================================================

为 HTML 报告生成热点分析的可视化 UI 组件。

包括:
- 热点 Top N 排行榜
- Pass 级别热力图
- 复杂度分布图表
- Event Browser 热点高亮样式

Author: RDC Analyzer Team
Date: 2025-01
"""

from typing import Dict, Any, List, Optional


def generate_hotspot_css() -> str:
    """生成热点组件的 CSS 样式"""
    return '''
/* ========== 热点分析面板样式 ========== */
.hotspot-panel {
    position: fixed;
    right: -400px;
    top: 50px;
    width: 400px;
    height: calc(100vh - 60px);
    background: var(--bg-darker);
    border-left: 1px solid var(--border);
    transition: right 0.3s ease;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 12px rgba(0,0,0,0.3);
}

.hotspot-panel.visible {
    right: 0;
}

.hotspot-panel-header {
    padding: 12px 16px;
    background: linear-gradient(135deg, #e94560 0%, #f39c12 100%);
    color: white;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.hotspot-panel-close {
    cursor: pointer;
    font-size: 18px;
    opacity: 0.8;
}

.hotspot-panel-close:hover {
    opacity: 1;
}

.hotspot-panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}

/* 统计卡片 */
.hotspot-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-bottom: 16px;
}

.hotspot-stat-card {
    background: var(--bg-dark);
    border-radius: 6px;
    padding: 12px;
    text-align: center;
}

.hotspot-stat-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--accent-red);
}

.hotspot-stat-label {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* 热点列表 */
.hotspot-list {
    margin-top: 12px;
}

.hotspot-section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.hotspot-item {
    background: var(--bg-dark);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 8px;
    cursor: pointer;
    border-left: 3px solid transparent;
    transition: all 0.2s;
}

.hotspot-item:hover {
    background: var(--bg-medium);
    transform: translateX(2px);
}

.hotspot-item.critical {
    border-left-color: #e94560;
}

.hotspot-item.high {
    border-left-color: #f39c12;
}

.hotspot-item.medium {
    border-left-color: #3498db;
}

.hotspot-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.hotspot-item-eid {
    font-weight: 600;
    color: var(--accent-blue);
}

.hotspot-item-score {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 10px;
    background: rgba(233, 69, 96, 0.2);
    color: var(--accent-red);
}

.hotspot-item-name {
    font-size: 11px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.hotspot-item-details {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    font-size: 10px;
    color: var(--text-muted);
}

.hotspot-item-detail {
    display: flex;
    align-items: center;
    gap: 3px;
}

/* Pass 热力图 */
.pass-heatmap {
    margin-top: 16px;
}

.pass-heatmap-row {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
}

.pass-heatmap-label {
    width: 60px;
    font-size: 11px;
    color: var(--text-secondary);
}

.pass-heatmap-bar {
    flex: 1;
    height: 20px;
    background: var(--bg-dark);
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}

.pass-heatmap-fill {
    height: 100%;
    transition: width 0.3s;
    display: flex;
    align-items: center;
    padding-left: 6px;
    font-size: 10px;
    color: white;
    font-weight: 600;
}

.pass-heatmap-fill.critical {
    background: linear-gradient(90deg, #e94560, #c0392b);
}

.pass-heatmap-fill.high {
    background: linear-gradient(90deg, #f39c12, #d35400);
}

.pass-heatmap-fill.medium {
    background: linear-gradient(90deg, #3498db, #2980b9);
}

.pass-heatmap-fill.low {
    background: linear-gradient(90deg, #27ae60, #1e8449);
}

/* 热点浮动按钮 */
.hotspot-toggle-btn {
    position: fixed;
    right: 20px;
    bottom: 80px;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: linear-gradient(135deg, #e94560 0%, #f39c12 100%);
    color: white;
    border: none;
    cursor: pointer;
    font-size: 20px;
    box-shadow: 0 4px 12px rgba(233, 69, 96, 0.4);
    z-index: 999;
    transition: transform 0.2s, box-shadow 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.hotspot-toggle-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 16px rgba(233, 69, 96, 0.5);
}

.hotspot-toggle-btn .badge {
    position: absolute;
    top: -5px;
    right: -5px;
    background: #fff;
    color: #e94560;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 10px;
    min-width: 18px;
    text-align: center;
}

/* Event Browser 热点高亮 */
.event-row.hotspot-critical {
    background: rgba(233, 69, 96, 0.15) !important;
}

.event-row.hotspot-critical:hover {
    background: rgba(233, 69, 96, 0.25) !important;
}

.event-row.hotspot-high {
    background: rgba(243, 156, 18, 0.12) !important;
}

.event-row.hotspot-high:hover {
    background: rgba(243, 156, 18, 0.22) !important;
}

.event-row.hotspot-medium {
    background: rgba(52, 152, 219, 0.1) !important;
}

.hotspot-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 1.5s infinite;
}

.hotspot-indicator.critical {
    background: #e94560;
    box-shadow: 0 0 6px #e94560;
}

.hotspot-indicator.high {
    background: #f39c12;
    box-shadow: 0 0 6px #f39c12;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* 建议弹窗 */
.hotspot-suggestion-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--bg-darker);
    border: 1px solid var(--border);
    border-radius: 8px;
    width: 500px;
    max-height: 80vh;
    z-index: 2000;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    display: none;
}

.hotspot-suggestion-modal.visible {
    display: block;
}

.hotspot-suggestion-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.hotspot-suggestion-content {
    padding: 16px;
    overflow-y: auto;
    max-height: calc(80vh - 60px);
}

.suggestion-reason {
    background: rgba(233, 69, 96, 0.1);
    border-left: 3px solid var(--accent-red);
    padding: 10px 12px;
    margin-bottom: 8px;
    border-radius: 0 4px 4px 0;
    font-size: 12px;
}

.suggestion-recommendation {
    background: rgba(59, 185, 80, 0.1);
    border-left: 3px solid var(--accent-green);
    padding: 10px 12px;
    margin-bottom: 8px;
    border-radius: 0 4px 4px 0;
    font-size: 12px;
}
'''


def generate_hotspot_js() -> str:
    """生成热点组件的 JavaScript"""
    return '''
// ========== 热点分析模块 ==========
const HotspotModule = {
    data: null,
    panelVisible: false,
    
    init: function(data) {
        this.data = data;
        if (data && data.hotspots && data.hotspots.length > 0) {
            this.createToggleButton();
            this.createPanel();
            this.highlightEvents();
        }
    },
    
    createToggleButton: function() {
        const btn = document.createElement('button');
        btn.className = 'hotspot-toggle-btn';
        btn.innerHTML = '🔥';
        btn.title = '性能热点分析';
        
        if (this.data.hotspots) {
            const criticalCount = this.data.hotspots.filter(h => h.level === 'critical').length;
            if (criticalCount > 0) {
                const badge = document.createElement('span');
                badge.className = 'badge';
                badge.textContent = criticalCount;
                btn.appendChild(badge);
            }
        }
        
        btn.onclick = () => this.togglePanel();
        document.body.appendChild(btn);
    },
    
    createPanel: function() {
        const panel = document.createElement('div');
        panel.className = 'hotspot-panel';
        panel.id = 'hotspotPanel';
        
        panel.innerHTML = `
            <div class="hotspot-panel-header">
                <span>🔥 性能热点分析</span>
                <span class="hotspot-panel-close" onclick="HotspotModule.togglePanel()">✕</span>
            </div>
            <div class="hotspot-panel-content">
                ${this.renderStats()}
                ${this.renderHotspotList()}
                ${this.renderPassHeatmap()}
            </div>
        `;
        
        document.body.appendChild(panel);
    },
    
    renderStats: function() {
        const d = this.data;
        return `
            <div class="hotspot-stats">
                <div class="hotspot-stat-card">
                    <div class="hotspot-stat-value">${d.total_draws || 0}</div>
                    <div class="hotspot-stat-label">Draw Calls</div>
                </div>
                <div class="hotspot-stat-card">
                    <div class="hotspot-stat-value">${this.formatScore(d.total_score)}</div>
                    <div class="hotspot-stat-label">总复杂度</div>
                </div>
                <div class="hotspot-stat-card">
                    <div class="hotspot-stat-value">${this.formatScore(d.avg_score)}</div>
                    <div class="hotspot-stat-label">平均复杂度</div>
                </div>
                <div class="hotspot-stat-card">
                    <div class="hotspot-stat-value" style="color: var(--accent-red)">
                        ${d.hotspots ? d.hotspots.filter(h => h.level === 'critical' || h.level === 'high').length : 0}
                    </div>
                    <div class="hotspot-stat-label">高负载热点</div>
                </div>
            </div>
        `;
    },
    
    renderHotspotList: function() {
        if (!this.data.hotspots || this.data.hotspots.length === 0) {
            return '<div style="color: var(--text-muted); text-align: center; padding: 20px;">暂无热点数据</div>';
        }
        
        const items = this.data.hotspots.slice(0, 15).map(h => `
            <div class="hotspot-item ${h.level}" onclick="HotspotModule.showSuggestion(${h.event_id})">
                <div class="hotspot-item-header">
                    <span class="hotspot-item-eid">EID ${h.event_id}</span>
                    <span class="hotspot-item-score">${this.formatScore(h.score)}</span>
                </div>
                <div class="hotspot-item-name">${h.name || 'Draw Call'}</div>
                <div class="hotspot-item-details">
                    <span class="hotspot-item-detail">🔺 ${this.formatNumber(h.primitives)} tris</span>
                    <span class="hotspot-item-detail">📦 ${h.instances || 1}x</span>
                    <span class="hotspot-item-detail">🎨 ${h.rt_count || 1} RT</span>
                </div>
            </div>
        `).join('');
        
        return `
            <div class="hotspot-list">
                <div class="hotspot-section-title">🔥 Top 热点 Draw Calls</div>
                ${items}
            </div>
        `;
    },
    
    renderPassHeatmap: function() {
        if (!this.data.pass_hotspots || this.data.pass_hotspots.length === 0) {
            return '';
        }
        
        const maxScore = Math.max(...this.data.pass_hotspots.map(p => p.total_score));
        
        const rows = this.data.pass_hotspots.slice(0, 8).map(p => {
            const pct = maxScore > 0 ? (p.total_score / maxScore * 100) : 0;
            return `
                <div class="pass-heatmap-row">
                    <span class="pass-heatmap-label">Pass ${p.pass_index}</span>
                    <div class="pass-heatmap-bar">
                        <div class="pass-heatmap-fill ${p.level}" style="width: ${pct}%">
                            ${this.formatScore(p.total_score)}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        return `
            <div class="pass-heatmap">
                <div class="hotspot-section-title">📊 Pass 负载分布</div>
                ${rows}
            </div>
        `;
    },
    
    togglePanel: function() {
        const panel = document.getElementById('hotspotPanel');
        if (panel) {
            this.panelVisible = !this.panelVisible;
            panel.classList.toggle('visible', this.panelVisible);
        }
    },
    
    highlightEvents: function() {
        if (!this.data.hotspots) return;
        
        // 构建热点映射
        const hotspotMap = {};
        this.data.hotspots.forEach(h => {
            hotspotMap[h.event_id] = h.level;
        });
        
        // 延迟执行，等待 Event Browser 渲染
        setTimeout(() => {
            document.querySelectorAll('.event-row').forEach(row => {
                const eidMatch = row.textContent.match(/EID\\s*(\\d+)/);
                if (eidMatch) {
                    const eid = parseInt(eidMatch[1]);
                    if (hotspotMap[eid]) {
                        row.classList.add('hotspot-' + hotspotMap[eid]);
                        
                        // 添加指示器
                        const firstCell = row.querySelector('td');
                        if (firstCell && !firstCell.querySelector('.hotspot-indicator')) {
                            const indicator = document.createElement('span');
                            indicator.className = 'hotspot-indicator ' + hotspotMap[eid];
                            firstCell.insertBefore(indicator, firstCell.firstChild);
                        }
                    }
                }
            });
        }, 500);
    },
    
    showSuggestion: function(eventId) {
        const suggestion = this.data.suggestions?.find(s => s.event_id === eventId);
        if (!suggestion) {
            // 跳转到 Event Browser
            if (typeof jumpToEventBrowser === 'function') {
                jumpToEventBrowser(eventId);
            }
            return;
        }
        
        // 创建或更新建议弹窗
        let modal = document.getElementById('hotspotSuggestionModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.className = 'hotspot-suggestion-modal';
            modal.id = 'hotspotSuggestionModal';
            document.body.appendChild(modal);
        }
        
        const reasons = suggestion.reasons?.map(r => 
            `<div class="suggestion-reason">⚠️ ${r}</div>`
        ).join('') || '';
        
        const recommendations = suggestion.recommendations?.map(r => 
            `<div class="suggestion-recommendation">💡 ${r}</div>`
        ).join('') || '';
        
        modal.innerHTML = `
            <div class="hotspot-suggestion-header">
                <span>🔍 EID ${eventId} 优化建议</span>
                <span style="cursor:pointer" onclick="document.getElementById('hotspotSuggestionModal').classList.remove('visible')">✕</span>
            </div>
            <div class="hotspot-suggestion-content">
                <div style="margin-bottom: 16px;">
                    <div class="hotspot-section-title">问题原因</div>
                    ${reasons || '<div style="color: var(--text-muted)">暂无详细原因</div>'}
                </div>
                <div>
                    <div class="hotspot-section-title">优化建议</div>
                    ${recommendations || '<div style="color: var(--text-muted)">暂无具体建议</div>'}
                </div>
                <div style="margin-top: 16px; text-align: center;">
                    <button onclick="jumpToEventBrowser(${eventId}); document.getElementById('hotspotSuggestionModal').classList.remove('visible');" 
                            style="background: var(--accent-blue); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                        🔍 跳转到 Event Browser
                    </button>
                </div>
            </div>
        `;
        
        modal.classList.add('visible');
    },
    
    formatScore: function(score) {
        if (score === undefined || score === null) return '-';
        if (score >= 1000000) return (score / 1000000).toFixed(1) + 'M';
        if (score >= 1000) return (score / 1000).toFixed(1) + 'K';
        return Math.round(score).toString();
    },
    
    formatNumber: function(num) {
        if (num === undefined || num === null) return '-';
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }
};
'''


def generate_hotspot_html(hotspot_data: Optional[Dict[str, Any]] = None) -> str:
    """
    生成热点数据的初始化脚本
    
    Args:
        hotspot_data: 热点分析报告数据
    
    Returns:
        初始化 JavaScript 代码
    """
    if not hotspot_data:
        return '<!-- Hotspot data not available -->'
    
    import json
    data_json = json.dumps(hotspot_data, ensure_ascii=False)
    
    return f'''
<!-- Hotspot Analysis Initialization -->
<script>
    document.addEventListener('DOMContentLoaded', function() {{
        const hotspotData = {data_json};
        HotspotModule.init(hotspotData);
    }});
</script>
'''


def convert_report_to_js_data(report) -> Dict[str, Any]:
    """
    将 HotspotReport 转换为 JS 可用的数据格式
    
    Args:
        report: HotspotReport 对象
    
    Returns:
        Dict 格式的热点数据
    """
    hotspots = []
    for hs in report.hotspots:
        hotspots.append({
            "event_id": hs.event_id,
            "name": hs.name,
            "score": hs.weighted_score,
            "level": hs.hotspot_level.value,
            "percentile": hs.percentile,
            "primitives": hs.primitive_count,
            "instances": hs.instance_count,
            "rt_count": hs.rt_count,
            "pass_index": hs.pass_index,
        })
    
    pass_hotspots = []
    for ph in report.pass_hotspots:
        pass_hotspots.append({
            "pass_index": ph.pass_index,
            "pass_name": ph.pass_name,
            "draw_count": ph.draw_count,
            "total_score": ph.total_score,
            "avg_score": ph.avg_score,
            "max_score": ph.max_score,
            "level": ph.hotspot_level.value,
        })
    
    return {
        "total_draws": report.total_draws,
        "total_score": report.total_score,
        "avg_score": report.avg_score,
        "critical_threshold": report.critical_threshold,
        "high_threshold": report.high_threshold,
        "medium_threshold": report.medium_threshold,
        "hotspots": hotspots,
        "pass_hotspots": pass_hotspots,
        "suggestions": report.suggestions,
    }
