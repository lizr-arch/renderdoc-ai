/**
 * navigation.js - 跨页面导航与高亮模块
 * 
 * 功能：
 * 1. 解析 URL 查询参数（?target=xxx&highlight=true）
 * 2. 跳转到目标元素并高亮
 * 3. 生成跨页面跳转链接
 * 
 * 使用方式：
 * 1. 在 HTML 中引入此脚本
 * 2. 调用 RdcNav.init() 初始化
 * 3. 使用 RdcNav.jumpTo() 跳转到元素
 * 4. 使用 RdcNav.buildLink() 生成跳转链接
 */

const RdcNav = (function() {
    'use strict';

    // ==================== 配置 ====================
    const CONFIG = {
        // URL 参数名（支持多种别名以兼容各页面）
        PARAM_TARGET: 'target',      // 目标元素 ID（主参数）
        PARAM_TARGET_ALIASES: ['id', 'eid', 'sid', 'tid'],  // 兼容别名
        PARAM_HIGHLIGHT: 'highlight', // 是否高亮
        PARAM_SOURCE: 'from',        // 来源页面
        
        // 高亮样式
        HIGHLIGHT_CLASS: 'rdc-nav-highlight',
        HIGHLIGHT_DURATION: 3000,    // 高亮持续时间 (ms)
        
        // 滚动配置
        SCROLL_BEHAVIOR: 'smooth',
        SCROLL_BLOCK: 'center'
    };

    // ==================== CSS 样式注入 ====================
    function injectStyles() {
        if (document.getElementById('rdc-nav-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'rdc-nav-styles';
        style.textContent = `
            /* 高亮动画 */
            @keyframes rdc-highlight-pulse {
                0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
                50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.3); }
                100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
            }
            
            @keyframes rdc-highlight-flash {
                0%, 100% { background-color: transparent; }
                25%, 75% { background-color: rgba(59, 130, 246, 0.2); }
            }
            
            .rdc-nav-highlight {
                animation: rdc-highlight-pulse 0.6s ease-out 3, rdc-highlight-flash 0.6s ease-out 3;
                outline: 2px solid var(--accent-blue, #3b82f6) !important;
                outline-offset: 2px;
                position: relative;
            }
            
            .rdc-nav-highlight::before {
                content: '';
                position: absolute;
                inset: -4px;
                border: 2px solid var(--accent-blue, #3b82f6);
                border-radius: 4px;
                animation: rdc-highlight-pulse 0.6s ease-out 3;
                pointer-events: none;
            }
            
            /* 跳转按钮样式 */
            .rdc-jump-btn {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                background: var(--bg-medium, #374151);
                border: 1px solid var(--border, #4b5563);
                border-radius: 4px;
                color: var(--accent-cyan, #22d3ee);
                font-size: 10px;
                cursor: pointer;
                text-decoration: none;
                transition: all 0.15s;
            }
            
            .rdc-jump-btn:hover {
                background: var(--bg-dark, #1f2937);
                border-color: var(--accent-blue, #3b82f6);
                color: var(--accent-blue, #3b82f6);
            }
            
            .rdc-jump-btn .icon {
                font-size: 12px;
            }
        `;
        document.head.appendChild(style);
    }

    // ==================== URL 参数解析 ====================
    function parseUrlParams() {
        const params = new URLSearchParams(window.location.search);
        
        // 尝试主参数
        let target = params.get(CONFIG.PARAM_TARGET);
        
        // 尝试别名参数（兼容 ?id=, ?eid=, ?sid=, ?tid=）
        if (!target) {
            for (const alias of CONFIG.PARAM_TARGET_ALIASES) {
                target = params.get(alias);
                if (target) break;
            }
        }
        
        return {
            target: target,
            highlight: params.get(CONFIG.PARAM_HIGHLIGHT) === 'true',
            source: params.get(CONFIG.PARAM_SOURCE)
        };
    }

    // ==================== 元素查找 ====================
    function findElement(targetId) {
        if (!targetId) return null;
        
        // 1. 直接 ID 查找
        let el = document.getElementById(targetId);
        if (el) return el;
        
        // 2. data-id 属性查找
        el = document.querySelector(`[data-id="${targetId}"]`);
        if (el) return el;
        
        // 3. data-eid 属性查找（事件页面 - 优先）
        el = document.querySelector(`[data-eid="${targetId}"]`);
        if (el) return el;
        
        // 4. data-event-id 属性查找（事件页面备选）
        el = document.querySelector(`[data-event-id="${targetId}"]`);
        if (el) return el;
        
        // 5. data-texture-id 属性查找（纹理页面）
        el = document.querySelector(`[data-texture-id="${targetId}"]`);
        if (el) return el;
        
        // 6. data-resource-id 属性查找（通用资源）
        el = document.querySelector(`[data-resource-id="${targetId}"]`);
        if (el) return el;
        
        // 7. 带 event_ 前缀的查找（用于跳转链接）
        if (targetId.startsWith('event_')) {
            const eid = targetId.replace('event_', '');
            el = document.querySelector(`[data-eid="${eid}"]`);
            if (el) return el;
        }
        
        // 8. 带 texture_ 前缀的查找
        if (targetId.startsWith('texture_')) {
            const texId = targetId.replace('texture_', '');
            el = document.querySelector(`[data-texture-id="${texId}"]`);
            if (el) return el;
        }
        
        return null;
    }

    // ==================== 跳转与高亮 ====================
    function jumpTo(targetId, options = {}) {
        const el = findElement(targetId);
        if (!el) {
            console.warn(`[RdcNav] Element not found: ${targetId}`);
            return false;
        }
        
        // 滚动到元素
        el.scrollIntoView({
            behavior: options.smooth !== false ? CONFIG.SCROLL_BEHAVIOR : 'auto',
            block: options.block || CONFIG.SCROLL_BLOCK
        });
        
        // 应用高亮
        if (options.highlight !== false) {
            highlight(el, options.duration);
        }
        
        return true;
    }

    function highlight(el, duration = CONFIG.HIGHLIGHT_DURATION) {
        if (!el) return;
        
        // 移除之前的高亮
        document.querySelectorAll('.' + CONFIG.HIGHLIGHT_CLASS).forEach(e => {
            e.classList.remove(CONFIG.HIGHLIGHT_CLASS);
        });
        
        // 添加高亮
        el.classList.add(CONFIG.HIGHLIGHT_CLASS);
        
        // 定时移除
        setTimeout(() => {
            el.classList.remove(CONFIG.HIGHLIGHT_CLASS);
        }, duration);
    }

    // ==================== 链接构建 ====================
    function buildLink(page, targetId, options = {}) {
        const params = new URLSearchParams();
        
        if (targetId) {
            params.set(CONFIG.PARAM_TARGET, targetId);
        }
        
        if (options.highlight !== false) {
            params.set(CONFIG.PARAM_HIGHLIGHT, 'true');
        }
        
        if (options.source) {
            params.set(CONFIG.PARAM_SOURCE, options.source);
        }
        
        const queryString = params.toString();
        return queryString ? `${page}?${queryString}` : page;
    }

    // ==================== 跳转按钮生成 ====================
    function createJumpButton(page, targetId, label, options = {}) {
        const link = buildLink(page, targetId, options);
        const icon = options.icon || '→';
        
        const btn = document.createElement('a');
        btn.href = link;
        btn.className = 'rdc-jump-btn';
        btn.innerHTML = `<span class="icon">${icon}</span><span>${label}</span>`;
        
        if (options.title) {
            btn.title = options.title;
        }
        
        return btn;
    }

    // ==================== 初始化 ====================
    function init() {
        injectStyles();
        
        // 解析 URL 参数
        const params = parseUrlParams();
        
        // 如果有目标参数，执行跳转
        if (params.target) {
            // 延迟执行，等待页面完全加载
            setTimeout(() => {
                const success = jumpTo(params.target, { highlight: params.highlight });
                if (success) {
                    console.log(`[RdcNav] Jumped to: ${params.target}`);
                }
            }, 100);
        }
    }

    // ==================== 公开 API ====================
    return {
        init,
        jumpTo,
        highlight,
        buildLink,
        createJumpButton,
        findElement,
        parseUrlParams,
        CONFIG
    };
})();

// 页面加载后自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', RdcNav.init);
} else {
    RdcNav.init();
}

// ==================== RenderDoc GUI 跳转 ====================
async function jumpToRenderDoc(eid) {
    const value = Number.parseInt(eid, 10);
    if (!Number.isFinite(value)) {
        return;
    }
    try {
        await fetch(`/api/jump?eid=${value}`);
    } catch (err) {
        console.warn('[RdcNav] Jump to RenderDoc failed', err);
    }
}

window.jumpToRenderDoc = jumpToRenderDoc;
