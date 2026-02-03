#!/usr/bin/env python3
"""
RDC Report Bundle Generator - 4 页面报告系统

生成互联的 HTML 报告包：
- index.html: 概览仪表盘
- textures.html: 纹理浏览器  
- events.html: 事件时间线
- shaders.html: Shader 分析

所有页面共享 common.css 和 manifest.json，通过 URL 参数实现深度链接。
"""

import json
import base64
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

# 模板目录
TEMPLATES_DIR = Path(__file__).parent / "templates"


class ReportBundleGenerator:
    """4 页面报告包生成器"""
    
    def __init__(self, output_dir: Union[str, Path], capture_name: str):
        """
        初始化生成器
        
        Args:
            output_dir: 输出目录路径
            capture_name: 捕获文件名（用于标题和 manifest）
        """
        self.output_dir = Path(output_dir)
        self.capture_name = capture_name
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 数据存储
        self.textures: List[Dict] = []
        self.events: List[Dict] = []
        self.shaders: List[Dict] = []
        self.performance_data: Dict = {}
        self.mali_data: Dict = {}
        self.frame_thumbnail: str = ""
        self.texture_usage_map: Dict = {}
        
        # 统计数据（用于 index 页面）
        self.stats: Dict = {
            "total_textures": 0,
            "total_events": 0,
            "total_shaders": 0,
            "draw_calls": 0,
            "dispatch_calls": 0,
            "clear_calls": 0,
            "vram_usage": 0,
            "issues_count": 0,
            "issues": []
        }
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _format_texture_name(self, raw_name: str, tex_id: str, width: int, height: int) -> str:
        """
        优化纹理名称显示
        
        策略：
        1. 如果有有意义的名称（不是自动生成的），直接使用
        2. 否则显示简短的 "#ID (WxH)" 格式
        """
        if not raw_name:
            return f"#{tex_id} ({width}×{height})"
        
        # 检测是否为自动生成的名称（如 Texture2D_68x26_R8G8B8A8_TYPELESS）
        auto_patterns = [
            r'^Texture2D_\d+x\d+_',   # D3D11 自动名称
            r'^Texture_\d+x\d+_',     # 通用自动名称
            r'^Image_\d+x\d+_',       # Vulkan 自动名称
            r'^Resource_\d+$',        # 资源 ID 名称
        ]
        
        import re
        for pattern in auto_patterns:
            if re.match(pattern, raw_name):
                # 是自动生成的名称，简化显示
                return f"#{tex_id} ({width}×{height})"
        
        # 如果名称太长（>30字符），截断并添加省略号
        if len(raw_name) > 30:
            return raw_name[:27] + "..."
        
        return raw_name
    
    def _simplify_format_name(self, fmt: str) -> str:
        """简化纹理格式名称，去掉冗长前缀"""
        if not fmt:
            return "Unknown"
        # 去掉 VK_FORMAT_ 前缀
        if fmt.startswith("VK_FORMAT_"):
            fmt = fmt[10:]
        # 去掉 DXGI_FORMAT_ 前缀
        if fmt.startswith("DXGI_FORMAT_"):
            fmt = fmt[12:]
        # 简化常见后缀
        fmt = fmt.replace("_UNORM", "").replace("_SFLOAT", "F")
        fmt = fmt.replace("_PACK32", "").replace("_BLOCK", "")
        # 限制长度
        if len(fmt) > 16:
            fmt = fmt[:14] + ".."
        return fmt

    def _normalize_thumbnail(self, thumbnail: str) -> str:
        """确保缩略图是 data URL，便于 HTML 直接渲染"""
        if not thumbnail:
            return ""
        if thumbnail.startswith("data:"):
            return thumbnail
        return f"data:image/png;base64,{thumbnail}"
    
    def set_textures(self, textures: List[Dict], usage_map: Dict = None):
        """设置纹理数据"""
        self.textures = textures or []
        self.texture_usage_map = usage_map or {}
        self.stats["total_textures"] = len(self.textures)
        
        # 计算 VRAM 使用量
        total_vram = 0
        for tex in self.textures:
            w = tex.get("width", 0)
            h = tex.get("height", 0)
            d = tex.get("depth", 1)
            mips = tex.get("mips", 1)
            layers = tex.get("arrayLayers", 1)
            bpp = self._estimate_bpp(tex.get("format", ""))
            # 粗略估计：考虑 mipmap 链约 1.33 倍
            size = w * h * d * layers * bpp * 1.33
            total_vram += size
        self.stats["vram_usage"] = int(total_vram)
    
    def set_events(self, events: List[Dict]):
        """设置事件数据"""
        self.events = events or []
        self.stats["total_events"] = len(self.events)
        
        # 统计各类调用
        draw = dispatch = clear = 0
        for evt in self.events:
            evt_type = evt.get("type", "").lower()
            name = evt.get("name", "").lower()
            if "draw" in evt_type or "draw" in name:
                draw += 1
            elif "dispatch" in evt_type or "dispatch" in name:
                dispatch += 1
            elif "clear" in evt_type or "clear" in name:
                clear += 1
        
        self.stats["draw_calls"] = draw
        self.stats["dispatch_calls"] = dispatch
        self.stats["clear_calls"] = clear
    
    def set_shaders(self, shaders: List[Dict], mali_data: Dict = None):
        """设置 Shader 数据"""
        self.shaders = shaders or []
        self.mali_data = mali_data or {}
        self.stats["total_shaders"] = len(self.shaders)
    
    def set_performance_data(self, data: Dict):
        """设置性能分析数据"""
        self.performance_data = data or {}
        
        # 提取问题列表
        issues = data.get("issues", [])
        self.stats["issues"] = issues
        self.stats["issues_count"] = len(issues)
        
        # 提取结构化建议列表
        recommendations = data.get("recommendations", [])
        self.stats["recommendations"] = recommendations
    
    def set_frame_thumbnail(self, thumbnail: str):
        """设置帧缩略图（Base64 Data URI）"""
        self.frame_thumbnail = thumbnail or ""
    
    def _estimate_bpp(self, format_str: str) -> float:
        """根据格式字符串估算每像素字节数"""
        fmt = format_str.upper()
        
        # 压缩格式
        if any(x in fmt for x in ["BC1", "DXT1", "BC4", "ATI1"]):
            return 0.5
        if any(x in fmt for x in ["BC2", "BC3", "DXT3", "DXT5", "BC5", "ATI2", "BC6", "BC7"]):
            return 1.0
        if any(x in fmt for x in ["ASTC", "ETC2", "EAC"]):
            return 1.0
        
        # 非压缩格式
        if "R32G32B32A32" in fmt:
            return 16.0
        if "R32G32B32" in fmt:
            return 12.0
        if "R16G16B16A16" in fmt or "R32G32" in fmt:
            return 8.0
        if "R32" in fmt or "R16G16" in fmt or "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
            return 4.0
        if "R16" in fmt or "R8G8" in fmt:
            return 2.0
        if "R8" in fmt or "A8" in fmt:
            return 1.0
        
        # 深度/模板
        if "D32" in fmt:
            return 4.0
        if "D24" in fmt or "D16" in fmt:
            return 4.0  # 通常对齐到 4
        
        return 4.0  # 默认 RGBA8
    
    def _load_template(self, name: str) -> str:
        """加载 HTML 模板文件"""
        template_path = TEMPLATES_DIR / name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        return template_path.read_text(encoding="utf-8")
    
    def _load_css(self) -> str:
        """加载公共 CSS"""
        css_path = TEMPLATES_DIR / "common.css"
        if css_path.exists():
            return css_path.read_text(encoding="utf-8")
        return ""
    
    def _render_template(self, template: str, replacements: Dict[str, str]) -> str:
        """渲染模板，替换占位符"""
        result = template
        for key, value in replacements.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        return result
    
    def _format_bytes(self, bytes_val: int) -> str:
        """格式化字节大小"""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
    
    def generate_index(self) -> str:
        """生成 index.html 概览页面"""
        template = self._load_template("index.html")
        css = self._load_css()
        
        # 构建 VRAM 分布数据（按格式分类）
        format_usage = {}
        for tex in self.textures:
            fmt = tex.get("format", "UNKNOWN")
            # 使用简化格式名方法
            simple_fmt = self._simplify_format_name(fmt)
            w, h, d = tex.get("width", 0), tex.get("height", 0), tex.get("depth", 1)
            layers = tex.get("arrayLayers", 1)
            bpp = self._estimate_bpp(fmt)
            size = int(w * h * d * layers * bpp * 1.33)
            format_usage[simple_fmt] = format_usage.get(simple_fmt, 0) + size
        
        # 按使用量排序，取前 6 个
        sorted_formats = sorted(format_usage.items(), key=lambda x: -x[1])[:6]
        
        # 生成 VRAM 甜甜圈图 SVG 段
        total_vram = self.stats["vram_usage"]
        vram_chart_segments = ""
        vram_legend_items = ""
        colors = ["#58a6ff", "#3fb950", "#f0883e", "#a371f7", "#f9c513", "#8b949e"]
        
        if total_vram > 0 and sorted_formats:
            start_angle = 0
            for i, (fmt, size) in enumerate(sorted_formats):
                pct = (size / total_vram) * 100
                sweep = (pct / 100) * 360
                color = colors[i % len(colors)]
                
                # SVG 圆弧
                circumference = 2 * 3.14159 * 15.5
                dash_length = (sweep / 360) * circumference
                dash_offset = -(start_angle / 360) * circumference
                
                vram_chart_segments += f'''
                    <circle cx="18" cy="18" r="15.5" fill="none" 
                        stroke="{color}" stroke-width="3" 
                        stroke-dasharray="{dash_length:.1f} {circumference - dash_length:.1f}"
                        stroke-dashoffset="{dash_offset:.1f}"/>'''
                
                # 图例项
                vram_legend_items += f'''
                    <div class="vram-legend-item">
                        <span class="vram-legend-dot" style="background:{color}"></span>
                        <span class="vram-legend-label">{fmt}</span>
                        <span class="vram-legend-value">{self._format_bytes(size)}</span>
                    </div>'''
                
                start_angle += sweep
        
        # 生成 Mali Shader 性能排序列表（按 cycles 降序）
        mali_shaders_html = ""
        mali_shader_list = []
        for shader in self.shaders:
            shader_id = shader.get("id") or shader.get("resource_id")
            mali_result = self.mali_data.get(str(shader_id), {}) if shader_id and self.mali_data else {}
            if mali_result:
                cycles = mali_result.get("cycles", {})
                total_cycles = cycles.get("total", 0) or cycles.get("longest_path", 0)
                if total_cycles > 0:
                    mali_shader_list.append({
                        "id": shader_id,
                        "name": shader.get("name", f"Shader {shader_id}"),
                        "type": shader.get("type", "unknown"),
                        "cycles": total_cycles,
                        "bound": mali_result.get("bound", ""),
                    })
        
        # 按 cycles 降序排序，取前 5 个
        mali_shader_list.sort(key=lambda x: -x["cycles"])
        for s in mali_shader_list[:5]:
            bound_icon = {"arithmetic": "🔢", "texture": "🖼️", "load_store": "💾", "varying": "📊"}.get(s["bound"], "⚡")
            mali_shaders_html += f'''
                <div class="shader-perf-item" onclick="location.href='shaders.html?id={s["id"]}'">
                    <div class="shader-perf-icon">{bound_icon}</div>
                    <div class="shader-perf-info">
                        <div class="shader-perf-name">{s["name"][:30]}</div>
                        <div class="shader-perf-type">{s["type"]}</div>
                    </div>
                    <div class="shader-perf-cycles">{s["cycles"]:.1f}</div>
                </div>'''
        
        # 生成问题列表 HTML（增强版：支持详细建议格式）
        issues_html = ""
        critical_count = 0
        
        # 优先使用 recommendations（新格式），回退到 issues（旧格式）
        recommendations = self.stats.get("recommendations", [])
        issues = self.stats.get("issues", [])
        
        # 渲染新格式的 recommendations
        for rec in recommendations[:5]:
            if isinstance(rec, dict):
                priority = rec.get("priority", "info")
                rule = rec.get("rule", "")
                title = rec.get("title", "未知问题")
                detail = rec.get("detail", "")
                action = rec.get("action", "")
                impact = rec.get("impact", "")
                
                # 映射优先级到样式
                if priority in ["critical", "high"]:
                    severity_class = "error"
                    icon = "🔴"
                    critical_count += 1
                elif priority in ["warning", "medium"]:
                    severity_class = ""
                    icon = "⚠️"
                else:
                    severity_class = "info"
                    icon = "ℹ️"
                
                # 构建详细描述
                desc_parts = []
                if detail:
                    desc_parts.append(detail[:100])
                if action:
                    desc_parts.append(f"💡 {action[:80]}")
                if impact:
                    desc_parts.append(f"📊 {impact[:60]}")
                
                full_desc = " | ".join(desc_parts) if desc_parts else ""
                
                issues_html += f'''
                <div class="issue-item {severity_class}">
                    <span class="issue-icon">{icon}</span>
                    <div class="issue-content">
                        <div class="issue-title">[{rule}] {title}</div>
                        <div class="issue-desc">{full_desc}</div>
                    </div>
                </div>'''
            else:
                # 字符串格式的旧建议
                issues_html += f'''
                <div class="issue-item info">
                    <span class="issue-icon">💡</span>
                    <div class="issue-content">
                        <div class="issue-title">{str(rec)[:80]}</div>
                    </div>
                </div>'''
        
        # 渲染旧格式的 issues（如果没有 recommendations）
        if not recommendations:
            for issue in issues[:8]:
                severity = issue.get("severity", "info")
                title = issue.get("title", "Unknown Issue")
                desc = issue.get("description", "")[:80]
                
                severity_class = "error" if severity in ["critical", "high"] else ("" if severity == "warning" else "info")
                icon = "🔴" if severity in ["critical", "high"] else ("⚠️" if severity == "warning" else "ℹ️")
                
                if severity in ["critical", "high"]:
                    critical_count += 1
                
                issues_html += f'''
                <div class="issue-item {severity_class}">
                    <span class="issue-icon">{icon}</span>
                    <div class="issue-content">
                        <div class="issue-title">{title}</div>
                        <div class="issue-desc">{desc}</div>
                    </div>
                </div>'''
        
        # 计算问题类样式
        issue_count = self.stats["issues_count"]
        issue_class = ""
        issue_value_class = "success" if issue_count == 0 else ("error" if critical_count > 0 else "warn")
        
        # VRAM 值（MB）
        total_vram_mb = total_vram / (1024 * 1024)
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "CAPTURE_DATE": self.timestamp,
            "CAPTURE_FILENAME": self.capture_name,
            "REPORT_DATE": self.timestamp,
            "GRAPHICS_API": self.performance_data.get("api", "Unknown"),
            "GPU_NAME": self.performance_data.get("gpu", "Unknown"),
            "RESOLUTION": self.performance_data.get("resolution", "Unknown"),
            "FRAME_THUMBNAIL": self.frame_thumbnail,
            
            "TEXTURE_COUNT": str(self.stats["total_textures"]),
            "TEXTURE_VRAM": self._format_bytes(self.stats["vram_usage"]),
            "TOTAL_VRAM": self._format_bytes(self.stats["vram_usage"]),
            "TOTAL_VRAM_VALUE": f"{total_vram_mb:.1f}",
            
            "EVENT_COUNT": str(self.stats["total_events"]),
            "DRAWCALL_COUNT": str(self.stats["draw_calls"]),
            
            "SHADER_COUNT": str(self.stats["total_shaders"]),
            "PIPELINE_COUNT": str(len(self.mali_data) if self.mali_data else 0),
            "MALI_ANALYZED_COUNT": str(len([s for s in self.shaders if s.get("mali")])),
            
            "ISSUE_COUNT": str(issue_count),
            "ISSUE_CLASS": issue_class,
            "ISSUE_VALUE_CLASS": issue_value_class,
            "CRITICAL_COUNT": str(critical_count),
            "ISSUE_TEXTURE_COUNT": str(len([t for t in self.textures if t.get("issues")])),
            
            "VRAM_CHART_SEGMENTS": vram_chart_segments,
            "VRAM_LEGEND_ITEMS": vram_legend_items,
            "MALI_SHADERS_HTML": mali_shaders_html,
            "ISSUES_HTML": issues_html if issues_html else '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-text">没有发现明显问题</div></div>'
        }
        
        # 处理条件块 {{#if ISSUES}}...{{else}}...{{/if}}
        html = self._render_template(template, replacements)
        
        # 简单处理条件块
        if issues_html:
            html = re.sub(r'\{\{#if ISSUES\}\}(.*?)\{\{else\}\}.*?\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
        else:
            html = re.sub(r'\{\{#if ISSUES\}\}.*?\{\{else\}\}(.*?)\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
        
        if self.frame_thumbnail:
            html = re.sub(r'\{\{#if FRAME_THUMBNAIL\}\}(.*?)\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
        else:
            html = re.sub(r'\{\{#if FRAME_THUMBNAIL\}\}.*?\{\{/if\}\}', '', html, flags=re.DOTALL)
        
        # Mali Shader 列表条件块
        if mali_shaders_html:
            html = re.sub(r'\{\{#if MALI_SHADERS\}\}(.*?)\{\{else\}\}.*?\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
        else:
            html = re.sub(r'\{\{#if MALI_SHADERS\}\}.*?\{\{else\}\}(.*?)\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
        
        return html
    
    def generate_textures(self) -> str:
        """生成 textures.html 纹理浏览器"""
        template = self._load_template("textures.html")
        css = self._load_css()
        
        # 为纹理数据添加使用信息，并优化名称显示
        textures_with_usage = []
        for tex in self.textures:
            tex_copy = dict(tex)
            tex_id = tex.get("id") or tex.get("resource_id")
            raw_name = tex.get("name", "")
            width = tex.get("width", 0)
            height = tex.get("height", 0)
            fmt = tex.get("format", "UNKNOWN")
            
            # 优化名称和格式显示
            tex_copy["display_name"] = self._format_texture_name(raw_name, tex_id, width, height)
            tex_copy["simple_format"] = self._simplify_format_name(fmt)
            tex_copy["usages"] = self.texture_usage_map.get(str(tex_id), [])
            tex_copy["thumbnail"] = self._normalize_thumbnail(tex.get("thumbnail", ""))
            textures_with_usage.append(tex_copy)
        
        # 生成纹理列表 HTML（用于无 JS 环境的 fallback）
        texture_list_html = ""
        for tex in self.textures[:50]:  # 限制初始渲染数量
            tex_id = tex.get("id") or tex.get("resource_id", "")
            raw_name = tex.get("name", "")
            width = tex.get("width", 0)
            height = tex.get("height", 0)
            fmt = tex.get("format", "UNKNOWN")
            thumb = self._normalize_thumbnail(tex.get("thumbnail", ""))
            
            # 优化纹理名称显示
            display_name = self._format_texture_name(raw_name, tex_id, width, height)
            simple_fmt = self._simplify_format_name(fmt)
            
            # 尺寸标签（大尺寸标记）
            size_tag = ""
            max_dim = max(width, height)
            if max_dim >= 4096:
                size_tag = '<span class="size-tag huge">4K+</span>'
            elif max_dim >= 2048:
                size_tag = '<span class="size-tag large">2K</span>'
            
            texture_list_html += f'''
                <div class="texture-item" data-id="{tex_id}" onclick="selectTexture('{tex_id}')">
                    <div class="texture-thumb">
                        <div class='thumb-placeholder'>?</div>
                    </div>
                    <div class="texture-info">
                        <div class="texture-name">{display_name}{size_tag}</div>
                        <div class="texture-meta">{width}×{height} • {simple_fmt}</div>
                    </div>
                </div>'''
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "TEXTURE_COUNT": str(len(self.textures)),
            "TOTAL_VRAM": self._format_bytes(self.stats["vram_usage"]),
            "TEXTURE_LIST_HTML": texture_list_html,
            "TEXTURE_DATA_JSON": json.dumps(textures_with_usage, ensure_ascii=False)
        }
        
        return self._render_template(template, replacements)
    
    def generate_events(self) -> str:
        """生成 events.html 事件时间线"""
        template = self._load_template("events.html")
        
        # 构建事件树结构
        events_tree = self._build_events_tree()
        
        # 生成聚合的时间线条形图 HTML（按 RenderPass/Marker 聚合）
        timeline_bars_html = self._build_aggregated_timeline()
        
        # 为前端准备完整的事件数据（包含 shaders, textures, renderTargets）
        prepared_events = self._prepare_events_for_frontend()
        
        # 生成事件列表 HTML（用于初始渲染）
        event_list_html = ""
        for evt in prepared_events[:100]:  # 限制初始渲染
            eid = evt.get("eventId") or evt.get("eid", 0)
            name = evt.get("name", "Unknown Event")
            evt_type = evt.get("type", "")
            
            # 类型图标
            if "draw" in evt_type.lower() or "draw" in name.lower():
                icon = "🎯"
                type_class = "draw"
            elif "dispatch" in evt_type.lower():
                icon = "⚡"
                type_class = "dispatch"
            elif "clear" in evt_type.lower():
                icon = "🧹"
                type_class = "clear"
            else:
                icon = "📌"
                type_class = "other"
            
            # 添加绑定资源数量标签（如果有）
            shader_count = len(evt.get("shaders", []))
            texture_count = len(evt.get("textures", []))
            binding_badge = ""
            if shader_count > 0 or texture_count > 0:
                binding_badge = f'<span class="binding-badge" title="{shader_count} shaders, {texture_count} textures">📎</span>'
            
            event_list_html += f'''
                <div class="event-item {type_class}" data-eid="{eid}" onclick="selectEvent({eid})">
                    <span class="event-icon">{icon}</span>
                    <span class="event-eid">#{eid}</span>
                    <span class="event-name">{name}</span>
                    {binding_badge}
                </div>'''
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "EVENT_COUNT": str(len(self.events)),
            "DRAW_CALL_COUNT": str(self.stats["draw_calls"]),
            "TIMELINE_BARS_HTML": timeline_bars_html,
            "EVENT_LIST_HTML": event_list_html,
            "EVENT_DATA_JSON": json.dumps(prepared_events, ensure_ascii=False)
        }
        
        return self._render_template(template, replacements)
    
    def generate_shaders(self) -> str:
        """生成 shaders.html Shader 分析页面"""
        template = self._load_template("shaders.html")
        
        # 处理 Mali 分析数据
        shader_with_mali = []
        mali_analyzed_count = 0
        
        for shader in self.shaders:
            shader_copy = dict(shader)
            shader_id = shader.get("id") or shader.get("resource_id")
            
            # 查找对应的 Mali 分析结果
            if shader_id and self.mali_data:
                mali_result = self.mali_data.get(str(shader_id), {})
                if mali_result:
                    shader_copy["mali"] = mali_result
                    mali_analyzed_count += 1
            
            shader_with_mali.append(shader_copy)
        
        # 生成 Shader 列表 HTML（用于初始渲染）
        shader_list_html = ""
        for shader in self.shaders[:50]:  # 限制初始渲染
            shader_id = shader.get("id") or shader.get("resource_id", "")
            name = shader.get("name", f"Shader {shader_id}")
            shader_type = shader.get("type", "Unknown")
            
            # Shader 类型图标
            type_icons = {
                "vertex": "📐",
                "pixel": "🎨",
                "fragment": "🎨",
                "compute": "⚡",
                "geometry": "📊",
                "hull": "🔷",
                "domain": "🔶",
            }
            icon = type_icons.get(shader_type.lower(), "📜")
            
            # 是否有 Mali 数据
            has_mali = bool(self.mali_data.get(str(shader_id)))
            mali_badge = '<span class="mali-badge">Mali</span>' if has_mali else ''
            
            shader_list_html += f'''
                <div class="shader-item" data-id="{shader_id}" onclick="selectShader('{shader_id}')">
                    <span class="shader-icon">{icon}</span>
                    <div class="shader-info">
                        <div class="shader-name">{name}</div>
                        <div class="shader-type">{shader_type} {mali_badge}</div>
                    </div>
                </div>'''
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "SHADER_COUNT": str(len(self.shaders)),
            "MALI_ANALYZED_COUNT": str(mali_analyzed_count),
            "SHADER_LIST_HTML": shader_list_html,
            "SHADER_DATA_JSON": json.dumps(shader_with_mali, ensure_ascii=False)
        }
        
        return self._render_template(template, replacements)
    
    def generate_recommendations(self) -> str:
        """生成优化建议专页 recommendations.html"""
        template = self._load_template("recommendations.html")
        
        # 统计各严重程度的问题数量
        issues = self.performance_data.get("issues", []) if self.performance_data else []
        recommendations = self.performance_data.get("recommendations", []) if self.performance_data else []
        
        # 合并问题和建议
        all_issues = []
        
        # 处理结构化问题
        for issue in issues:
            if isinstance(issue, dict):
                all_issues.append({
                    "severity": issue.get("severity", "info"),
                    "category": issue.get("category", "general"),
                    "rule": issue.get("rule_id", ""),
                    "title": issue.get("title", ""),
                    "detail": issue.get("message", ""),
                    "action": issue.get("suggestion", ""),
                    "impact": issue.get("impact_score", 5),
                    "resource_id": issue.get("resource_id", ""),
                    "actual_value": issue.get("actual_value", ""),
                    "threshold_value": issue.get("threshold_value", ""),
                })
            else:
                # 字符串格式
                all_issues.append({
                    "severity": "info",
                    "category": "general",
                    "rule": "",
                    "title": str(issue)[:60],
                    "detail": str(issue),
                    "action": "",
                    "impact": 3,
                    "resource_id": "",
                })
        
        # 处理建议
        for rec in recommendations:
            if isinstance(rec, dict):
                all_issues.append({
                    "severity": rec.get("severity", "info"),
                    "category": rec.get("category", "general"),
                    "rule": rec.get("rule_id", ""),
                    "title": rec.get("title", ""),
                    "detail": rec.get("detail", rec.get("message", "")),
                    "action": rec.get("action", rec.get("suggestion", "")),
                    "impact": rec.get("impact", 3),
                    "resource_id": "",
                })
            else:
                all_issues.append({
                    "severity": "info",
                    "category": "general",
                    "rule": "",
                    "title": str(rec)[:60],
                    "detail": str(rec),
                    "action": "",
                    "impact": 3,
                    "resource_id": "",
                })
        
        # 按严重程度排序
        severity_order = {"critical": 0, "high": 0, "error": 1, "warning": 2, "info": 3}
        all_issues.sort(key=lambda x: severity_order.get(x["severity"], 5))
        
        # 统计
        critical_count = sum(1 for i in all_issues if i["severity"] in ["critical", "high", "error"])
        warning_count = sum(1 for i in all_issues if i["severity"] == "warning")
        info_count = sum(1 for i in all_issues if i["severity"] == "info")
        total_count = len(all_issues)
        
        # 分类统计
        category_counts = {}
        for issue in all_issues:
            cat = issue["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # 分类标签 HTML
        category_icons = {
            "texture": "🖼️",
            "shader": "🎨",
            "drawcall": "🎯",
            "memory": "💾",
            "bandwidth": "📡",
            "general": "📋",
        }
        category_names = {
            "texture": "纹理",
            "shader": "着色器",
            "drawcall": "绘制调用",
            "memory": "内存",
            "bandwidth": "带宽",
            "general": "通用",
        }
        
        category_tabs_html = ""
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            icon = category_icons.get(cat, "📌")
            name = category_names.get(cat, cat.capitalize())
            category_tabs_html += f'''
                <button class="category-tab" data-category="{cat}">
                    {icon} {name}<span class="count">{count}</span>
                </button>'''
        
        # 生成问题摘要
        summary_items_html = ""
        perf = self.performance_data or {}
        
        # 大纹理统计
        large_tex_count = perf.get("large_texture_count", 0)
        if large_tex_count > 0:
            summary_items_html += f'''
                <div class="summary-item">
                    <span class="summary-icon">📐</span>
                    <div class="summary-content">
                        <div class="summary-label">大尺寸纹理</div>
                        <div class="summary-value">{large_tex_count} 个纹理超过 2048px</div>
                    </div>
                </div>'''
        
        # 未压缩纹理
        uncompressed_count = perf.get("uncompressed_count", 0)
        if uncompressed_count > 0:
            summary_items_html += f'''
                <div class="summary-item">
                    <span class="summary-icon">📦</span>
                    <div class="summary-content">
                        <div class="summary-label">未压缩纹理</div>
                        <div class="summary-value">{uncompressed_count} 个可优化为压缩格式</div>
                    </div>
                </div>'''
        
        # VRAM 使用
        vram_bytes = perf.get("total_vram", 0)
        if vram_bytes > 0:
            vram_mb = vram_bytes / (1024 * 1024)
            summary_items_html += f'''
                <div class="summary-item">
                    <span class="summary-icon">💾</span>
                    <div class="summary-content">
                        <div class="summary-label">VRAM 使用</div>
                        <div class="summary-value">{vram_mb:.1f} MB 纹理内存</div>
                    </div>
                </div>'''
        
        # Draw Call 统计
        draw_calls = self.stats.get("draw_calls", 0)
        if draw_calls > 1000:
            summary_items_html += f'''
                <div class="summary-item">
                    <span class="summary-icon">🎯</span>
                    <div class="summary-content">
                        <div class="summary-label">Draw Call 数量</div>
                        <div class="summary-value">{draw_calls} 次调用（较多）</div>
                    </div>
                </div>'''
        
        # 预估节省
        estimated_savings = ""
        if vram_bytes > 100 * 1024 * 1024:  # > 100MB
            potential_save = int(vram_bytes * 0.3 / (1024 * 1024))  # 假设可节省30%
            estimated_savings = f"~{potential_save}MB"
        else:
            estimated_savings = "待分析"
        
        # 生成建议卡片 HTML
        recommendations_html = ""
        for i, issue in enumerate(all_issues):
            severity = issue["severity"]
            if severity in ["critical", "high", "error"]:
                severity_class = "critical"
                severity_icon = "🚨"
                severity_badge = "严重"
            elif severity == "warning":
                severity_class = "warning"
                severity_icon = "⚠️"
                severity_badge = "警告"
            else:
                severity_class = "info"
                severity_icon = "💡"
                severity_badge = "建议"
            
            # 影响评分
            impact_raw = issue.get("impact", 5)
            try:
                impact = int(impact_raw)
            except (ValueError, TypeError):
                impact = 5
            impact_pct = min(impact * 10, 100)
            impact_class = "high" if impact >= 8 else ("medium" if impact >= 5 else "low")
            
            # 操作建议（拆分为步骤）
            action = issue.get("action", "")
            action_steps_html = ""
            if action:
                steps = [s.strip() for s in action.replace("；", ";").split(";") if s.strip()]
                if len(steps) > 1:
                    for j, step in enumerate(steps, 1):
                        action_steps_html += f'''
                            <li class="action-step">
                                <span class="step-number">{j}</span>
                                <span class="step-text">{step}</span>
                            </li>'''
                else:
                    action_steps_html = f'<p class="section-content">{action}</p>'
            
            # 资源链接
            resource_id = issue.get("resource_id", "")
            resource_link_html = ""
            category = issue.get("category", "general")
            if resource_id:
                if category == "texture":
                    resource_link_html = f'<a href="textures.html?id={resource_id}" class="resource-link">🖼️ 查看纹理 #{resource_id}</a>'
                elif category == "shader":
                    resource_link_html = f'<a href="shaders.html?id={resource_id}" class="resource-link">🎨 查看 Shader #{resource_id}</a>'
            
            recommendations_html += f'''
                <div class="recommendation-card {severity_class}" data-category="{category}">
                    <div class="recommendation-header">
                        <span class="severity-icon">{severity_icon}</span>
                        <div class="recommendation-title-section">
                            <div class="recommendation-title">{issue["title"]}</div>
                            <div class="recommendation-rule">{issue["rule"]}</div>
                        </div>
                        <div class="recommendation-badges">
                            <span class="badge severity-{severity_class}">{severity_badge}</span>
                            <span class="badge category">{category_names.get(category, category)}</span>
                        </div>
                        <span class="expand-icon">▼</span>
                    </div>
                    <div class="recommendation-body">
                        <div class="recommendation-section">
                            <div class="section-title">问题描述</div>
                            <div class="detail-text">{issue["detail"]}</div>
                        </div>
                        
                        {"<div class='recommendation-section'><div class='section-title'>建议操作</div>" + ("<ul class='action-steps'>" + action_steps_html + "</ul>" if "action-step" in action_steps_html else action_steps_html) + "</div>" if action else ""}
                        
                        <div class="recommendation-section">
                            <div class="section-title">影响评估</div>
                            <div class="impact-meter">
                                <div class="impact-bar">
                                    <div class="impact-fill {impact_class}" style="width:{impact_pct}%"></div>
                                </div>
                                <span class="impact-label">影响评分: {impact}/10</span>
                            </div>
                        </div>
                        
                        {f"<div class='recommendation-section'><div class='section-title'>相关资源</div>{resource_link_html}</div>" if resource_link_html else ""}
                    </div>
                </div>'''
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "TOTAL_ISSUES": str(total_count),
            "CRITICAL_COUNT": str(critical_count),
            "WARNING_COUNT": str(warning_count),
            "INFO_COUNT": str(info_count),
            "ESTIMATED_SAVINGS": estimated_savings,
            "SUMMARY_ITEMS": summary_items_html if summary_items_html else '<div class="summary-item"><span class="summary-icon">✅</span><div class="summary-content"><div class="summary-value">没有发现明显问题</div></div></div>',
            "CATEGORY_TABS": category_tabs_html,
            "RECOMMENDATIONS_HTML": recommendations_html if recommendations_html else "",
            "NO_ISSUES": "" if total_count > 0 else "true",
        }
        
        return self._render_template(template, replacements)
    
    def generate_manifest(self) -> Dict:
        """生成 manifest.json"""
        return {
            "version": "1.0",
            "generator": "RDC Report Bundle Generator",
            "generated_at": self.timestamp,
            "capture": {
                "name": self.capture_name,
                "frame_thumbnail": bool(self.frame_thumbnail)
            },
            "pages": {
                "index": "index.html",
                "textures": "textures.html",
                "events": "events.html",
                "shaders": "shaders.html",
                "recommendations": "recommendations.html"
            },
            "stats": {
                "textures": self.stats["total_textures"],
                "events": self.stats["total_events"],
                "shaders": self.stats["total_shaders"],
                "draw_calls": self.stats["draw_calls"],
                "dispatch_calls": self.stats["dispatch_calls"],
                "vram_bytes": self.stats["vram_usage"],
                "issues": self.stats["issues_count"]
            }
        }
    
    def _build_aggregated_timeline(self) -> str:
        """
        构建聚合的时间线 HTML
        
        策略：
        1. 按 marker_push/marker_pop 分组，每个 RenderPass 为一个色块
        2. 没有 Marker 的事件按固定数量（每50个）聚合为一个块
        3. 每个块显示：位置区间、颜色（按主要类型）、tooltip 显示事件数
        """
        if not self.events:
            return ""
        
        # 获取 EID 范围
        all_eids = [e.get("eventId") or e.get("eid", 0) for e in self.events]
        if not all_eids:
            return ""
        min_eid = min(all_eids)
        max_eid = max(all_eids) or 1
        eid_range = max_eid - min_eid or 1
        
        # 聚合块列表 [{start_eid, end_eid, name, type, count, color}]
        blocks = []
        
        # 方案1：按 depth=0 的 marker_push 分组
        # 找出所有顶级 Marker（depth=0 或 1）
        marker_stack = []
        current_block = None
        ungrouped_events = []
        
        for evt in self.events:
            eid = evt.get("eventId") or evt.get("eid", 0)
            evt_type = evt.get("type", "").lower()
            depth = evt.get("depth", 0)
            name = evt.get("name", "")
            
            if evt_type == "marker_push" and depth <= 1:
                # 保存之前的未分组事件
                if ungrouped_events and len(ungrouped_events) >= 5:
                    blocks.append(self._create_block_from_events(ungrouped_events, "Events"))
                    ungrouped_events = []
                
                # 开始新的 RenderPass 块
                current_block = {
                    "start_eid": eid,
                    "name": name,
                    "events": [evt],
                    "draw_count": 0,
                    "dispatch_count": 0,
                    "clear_count": 0
                }
                marker_stack.append(current_block)
                
            elif evt_type == "marker_pop" and marker_stack:
                # 结束当前块
                block = marker_stack.pop()
                block["end_eid"] = eid
                block["events"].append(evt)
                
                # 计算主类型和颜色
                total = len(block["events"])
                draw_pct = block["draw_count"] / max(total, 1)
                dispatch_pct = block["dispatch_count"] / max(total, 1)
                
                if dispatch_pct > 0.3:
                    color = "var(--accent-purple)"  # Compute-heavy
                    main_type = "dispatch"
                elif draw_pct > 0.3:
                    color = "var(--accent-green)"   # Draw-heavy
                    main_type = "draw"
                elif block["clear_count"] > 0:
                    color = "var(--accent-yellow)"  # Clear
                    main_type = "clear"
                else:
                    color = "var(--accent-blue)"    # Mixed
                    main_type = "mixed"
                
                blocks.append({
                    "start_eid": block["start_eid"],
                    "end_eid": block["end_eid"],
                    "name": block["name"],
                    "count": len(block["events"]),
                    "color": color,
                    "main_type": main_type,
                    "draw_count": block["draw_count"],
                    "dispatch_count": block["dispatch_count"]
                })
                
                # 如果还有父级块，继续累加
                if marker_stack:
                    current_block = marker_stack[-1]
                else:
                    current_block = None
                    
            else:
                # 普通事件
                if current_block:
                    current_block["events"].append(evt)
                    if "draw" in evt_type:
                        current_block["draw_count"] += 1
                    elif "dispatch" in evt_type:
                        current_block["dispatch_count"] += 1
                    elif "clear" in evt_type:
                        current_block["clear_count"] += 1
                else:
                    ungrouped_events.append(evt)
        
        # 处理剩余的未分组事件
        if ungrouped_events:
            # 每 50 个事件一组
            for i in range(0, len(ungrouped_events), 50):
                chunk = ungrouped_events[i:i+50]
                if chunk:
                    blocks.append(self._create_block_from_events(chunk, f"Events {i+1}-{i+len(chunk)}"))
        
        # 如果没有聚合出块（可能没有 marker），按固定数量分块
        if not blocks and self.events:
            chunk_size = max(50, len(self.events) // 20)  # 最多 20 个块
            for i in range(0, len(self.events), chunk_size):
                chunk = self.events[i:i+chunk_size]
                if chunk:
                    blocks.append(self._create_block_from_events(chunk, f"Events {i+1}-{i+len(chunk)}"))
        
        # 生成 HTML
        html_parts = []
        for block in blocks:
            start_eid = block["start_eid"]
            end_eid = block.get("end_eid", start_eid)
            
            # 计算位置和宽度（百分比）
            left_pct = ((start_eid - min_eid) / eid_range) * 100
            width_pct = max(((end_eid - start_eid) / eid_range) * 100, 0.5)  # 最小 0.5%
            
            # Tooltip
            name = block.get("name", "")
            count = block.get("count", 0)
            draw_count = block.get("draw_count", 0)
            dispatch_count = block.get("dispatch_count", 0)
            tooltip = f"{name} ({count} events"
            if draw_count > 0:
                tooltip += f", {draw_count} draws"
            if dispatch_count > 0:
                tooltip += f", {dispatch_count} dispatches"
            tooltip += f") EID {start_eid}-{end_eid}"
            
            color = block.get("color", "var(--accent-blue)")
            
            html_parts.append(
                f'<div class="timeline-bar" '
                f'style="left:{left_pct:.2f}%;width:{width_pct:.2f}%;background:{color}" '
                f'data-start-eid="{start_eid}" data-end-eid="{end_eid}" '
                f'title="{tooltip}" onclick="scrollToEvent({start_eid})"></div>'
            )
        
        # 添加 Marker 分隔线（仅顶级）
        marker_lines = []
        for evt in self.events:
            evt_type = evt.get("type", "").lower()
            depth = evt.get("depth", 0)
            if evt_type == "marker_push" and depth == 0:
                eid = evt.get("eventId") or evt.get("eid", 0)
                pos_pct = ((eid - min_eid) / eid_range) * 100
                name = evt.get("name", "")[:15]  # 截断名称
                marker_lines.append(
                    f'<div class="timeline-marker" style="left:{pos_pct:.2f}%" '
                    f'data-label="{name}"></div>'
                )
        
        return "\n".join(html_parts + marker_lines[:10])  # 限制 Marker 数量避免过密
    
    def _create_block_from_events(self, events: List[Dict], default_name: str) -> Dict:
        """从事件列表创建聚合块"""
        if not events:
            return {}
        
        eids = [e.get("eventId") or e.get("eid", 0) for e in events]
        draw_count = sum(1 for e in events if "draw" in e.get("type", "").lower())
        dispatch_count = sum(1 for e in events if "dispatch" in e.get("type", "").lower())
        clear_count = sum(1 for e in events if "clear" in e.get("type", "").lower())
        
        # 确定主类型和颜色
        total = len(events)
        if dispatch_count / max(total, 1) > 0.3:
            color = "var(--accent-purple)"
        elif draw_count / max(total, 1) > 0.3:
            color = "var(--accent-green)"
        elif clear_count > 0:
            color = "var(--accent-yellow)"
        else:
            color = "var(--accent-blue)"
        
        return {
            "start_eid": min(eids),
            "end_eid": max(eids),
            "name": default_name,
            "count": len(events),
            "color": color,
            "draw_count": draw_count,
            "dispatch_count": dispatch_count
        }
    
    def _prepare_events_for_frontend(self) -> List[Dict]:
        """
        为前端转换事件数据，将 pipelineState 和 resourceBindings 
        转换为前端期望的 shaders, textures, renderTargets 格式
        """
        prepared_events = []
        
        # 创建纹理快速查找表 (resourceId -> texture info)
        texture_lookup = {}
        for tex in self.textures:
            tex_id = str(tex.get("id") or tex.get("resourceId", ""))
            if tex_id:
                texture_lookup[tex_id] = tex
        
        # 创建 Shader 快速查找表 (resourceId -> shader info)
        shader_lookup = {}
        for shader in self.shaders:
            shader_id = str(shader.get("id") or shader.get("resource_id", ""))
            if shader_id:
                shader_lookup[shader_id] = shader
        
        for evt in self.events:
            # 复制基础事件数据
            prepared = dict(evt)
            
            # 确保 eid 字段存在（前端期望使用 eid）
            if "eid" not in prepared:
                prepared["eid"] = evt.get("eventId") or evt.get("eid", 0)
            
            # 提取 Shader 信息
            shaders_list = []
            pipeline_state = evt.get("pipelineState", {})
            shaders_data = pipeline_state.get("shaders", {})
            
            # 映射 Shader 类型
            shader_type_map = {
                "vs": "Vertex",
                "ps": "Pixel", 
                "gs": "Geometry",
                "hs": "Hull",
                "ds": "Domain",
                "cs": "Compute"
            }
            
            for shader_key, shader_type_name in shader_type_map.items():
                shader_info = shaders_data.get(shader_key)
                if shader_info and shader_info is not None:
                    shader_id = str(shader_info.get("id", ""))
                    shader_name = shader_info.get("name", f"{shader_type_name} Shader")
                    
                    # 尝试从 Shader 列表获取更多信息
                    full_shader = shader_lookup.get(shader_id, {})
                    if full_shader:
                        shader_name = full_shader.get("name", shader_name)
                    
                    shaders_list.append({
                        "type": shader_key.upper(),
                        "name": shader_name,
                        "id": shader_id
                    })
            
            # 检查 pipeline 对象（Vulkan 常用）
            pipeline_info = shaders_data.get("pipeline")
            if pipeline_info and isinstance(pipeline_info, dict):
                pipeline_id = pipeline_info.get("id", "")
                if pipeline_id and not shaders_list:
                    # 如果没有单独的 shader，使用 pipeline ID
                    shaders_list.append({
                        "type": "Pipeline",
                        "name": f"Graphics Pipeline {pipeline_id}",
                        "id": str(pipeline_id)
                    })
            
            prepared["shaders"] = shaders_list
            
            # 提取纹理绑定信息
            textures_list = []
            render_targets_list = []
            
            resource_bindings = evt.get("resourceBindings", {})
            
            # 从 descriptorSets 提取绑定的纹理
            descriptor_sets = resource_bindings.get("descriptorSets", [])
            for ds in descriptor_sets:
                bindings = ds.get("bindings", [])
                for binding in bindings:
                    desc_type = binding.get("descriptorType", "")
                    resources = binding.get("resources", [])
                    
                    # 检查是否是图像/纹理类型
                    is_texture_type = any(t in desc_type.upper() for t in [
                        "SAMPLED_IMAGE", "COMBINED_IMAGE", "STORAGE_IMAGE",
                        "TEXTURE", "SRV", "UAV"
                    ])
                    
                    if is_texture_type:
                        for res in resources:
                            res_id = str(res.get("resourceId", ""))
                            if res_id and res_id != "0":
                                # 从纹理列表查找详细信息
                                tex_info = texture_lookup.get(res_id, {})
                                tex_name = tex_info.get("name", f"Texture {res_id}")
                                thumbnail = tex_info.get("thumbnail", "")
                                
                                # 避免重复
                                if not any(t["id"] == res_id for t in textures_list):
                                    textures_list.append({
                                        "id": res_id,
                                        "name": tex_name,
                                        "thumbnail": thumbnail,
                                        "binding": binding.get("binding", 0),
                                        "type": desc_type
                                    })
            
            # 从 shaderResources 提取（D3D11/12 风格）
            shader_resources = resource_bindings.get("shaderResources", [])
            for sr in shader_resources:
                res_id = str(sr.get("resourceId", sr.get("id", "")))
                if res_id and res_id != "0":
                    tex_info = texture_lookup.get(res_id, {})
                    tex_name = tex_info.get("name", f"Texture {res_id}")
                    thumbnail = tex_info.get("thumbnail", "")
                    
                    if not any(t["id"] == res_id for t in textures_list):
                        textures_list.append({
                            "id": res_id,
                            "name": tex_name,
                            "thumbnail": thumbnail,
                            "slot": sr.get("slot", 0),
                            "stage": sr.get("stage", "")
                        })
            
            prepared["textures"] = textures_list
            
            # 提取 Render Target 信息（从 renderTargets 字段或推断）
            rt_data = evt.get("renderTargets", [])
            if isinstance(rt_data, list):
                for rt in rt_data:
                    rt_id = str(rt.get("id", rt.get("resourceId", "")))
                    if rt_id:
                        tex_info = texture_lookup.get(rt_id, {})
                        rt_name = tex_info.get("name", f"RT {rt_id}")
                        thumbnail = tex_info.get("thumbnail", "")
                        
                        render_targets_list.append({
                            "id": rt_id,
                            "name": rt_name,
                            "thumbnail": thumbnail,
                            "slot": rt.get("slot", len(render_targets_list))
                        })
            
            prepared["renderTargets"] = render_targets_list
            
            # 添加 viewport 信息（如果存在）
            viewport = pipeline_state.get("viewport")
            if viewport:
                prepared["viewport"] = viewport
            
            prepared_events.append(prepared)
        
        return prepared_events
    
    def _build_events_tree(self) -> List[Dict]:
        """将扁平事件列表转换为树结构（按 Pass 分组）"""
        # 简单分组：按 pass 或 marker 名称
        tree = []
        current_pass = None
        current_children = []
        
        for evt in self.events:
            markers = evt.get("markers", [])
            pass_name = markers[0] if markers else None
            
            if pass_name and pass_name != current_pass:
                # 保存上一个 Pass
                if current_pass and current_children:
                    tree.append({
                        "name": current_pass,
                        "type": "pass",
                        "children": current_children,
                        "count": len(current_children)
                    })
                current_pass = pass_name
                current_children = []
            
            current_children.append({
                "eid": evt.get("eventId") or evt.get("eid"),
                "name": evt.get("name", "Unknown"),
                "type": evt.get("type", "unknown")
            })
        
        # 保存最后一个 Pass
        if current_pass and current_children:
            tree.append({
                "name": current_pass,
                "type": "pass",
                "children": current_children,
                "count": len(current_children)
            })
        elif current_children:
            # 无 Pass 分组，直接添加事件
            tree = current_children
        
        return tree
    
    def generate_all(self) -> Dict[str, str]:
        """
        生成所有页面和 manifest
        
        Returns:
            字典：{文件名: 文件路径}
        """
        output_files = {}
        
        # 1. 生成 index.html
        index_html = self.generate_index()
        index_path = self.output_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        output_files["index"] = str(index_path)
        print(f"  [OK] Generated: {index_path.name}")
        
        # 2. 生成 textures.html
        textures_html = self.generate_textures()
        textures_path = self.output_dir / "textures.html"
        textures_path.write_text(textures_html, encoding="utf-8")
        output_files["textures"] = str(textures_path)
        print(f"  [OK] Generated: {textures_path.name}")
        
        # 3. 生成 events.html
        events_html = self.generate_events()
        events_path = self.output_dir / "events.html"
        events_path.write_text(events_html, encoding="utf-8")
        output_files["events"] = str(events_path)
        print(f"  [OK] Generated: {events_path.name}")
        
        # 4. 生成 shaders.html
        shaders_html = self.generate_shaders()
        shaders_path = self.output_dir / "shaders.html"
        shaders_path.write_text(shaders_html, encoding="utf-8")
        output_files["shaders"] = str(shaders_path)
        print(f"  [OK] Generated: {shaders_path.name}")
        
        # 5. 生成 recommendations.html (优化建议专页)
        recommendations_html = self.generate_recommendations()
        recommendations_path = self.output_dir / "recommendations.html"
        recommendations_path.write_text(recommendations_html, encoding="utf-8")
        output_files["recommendations"] = str(recommendations_path)
        print(f"  [OK] Generated: {recommendations_path.name}")
        
        # 6. 生成 manifest.json
        manifest = self.generate_manifest()
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        output_files["manifest"] = str(manifest_path)
        print(f"  [OK] Generated: {manifest_path.name}")
        
        # 6. 复制 common.css 到输出目录
        css_src = TEMPLATES_DIR / "common.css"
        css_dst = self.output_dir / "common.css"
        if css_src.exists():
            import shutil
            shutil.copy2(css_src, css_dst)
            output_files["css"] = str(css_dst)
            print(f"  [OK] Copied: {css_dst.name}")
        else:
            print(f"  [WARN] common.css not found at {css_src}")
        
        return output_files


def generate_report_bundle(
    output_dir: Union[str, Path],
    capture_name: str,
    textures: List[Dict] = None,
    events: List[Dict] = None,
    shaders: List[Dict] = None,
    performance_data: Dict = None,
    mali_data: Dict = None,
    frame_thumbnail: str = None,
    texture_usage_map: Dict = None
) -> Dict[str, str]:
    """
    便捷函数：生成完整的 4 页面报告包
    
    Args:
        output_dir: 输出目录
        capture_name: 捕获名称
        textures: 纹理数据列表
        events: 事件数据列表
        shaders: Shader 数据列表
        performance_data: 性能分析数据
        mali_data: Mali Offline Compiler 数据
        frame_thumbnail: 帧缩略图 Base64
        texture_usage_map: 纹理使用映射
        
    Returns:
        生成的文件路径字典
    """
    generator = ReportBundleGenerator(output_dir, capture_name)
    
    generator.set_textures(textures or [], texture_usage_map)
    generator.set_events(events or [])
    generator.set_shaders(shaders or [], mali_data)
    
    if performance_data:
        generator.set_performance_data(performance_data)
    
    if frame_thumbnail:
        generator.set_frame_thumbnail(frame_thumbnail)
    
    return generator.generate_all()


# ============ CLI 入口 ============
def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate 4-page RDC report bundle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 从 JSON 数据文件生成报告
  python report_bundle_generator.py data.json -o ./report_output
  
  # 指定捕获名称
  python report_bundle_generator.py data.json -o ./report -n "MyCapture"
        """
    )
    
    parser.add_argument("input", help="Input JSON file (textures/events/shaders data)")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("-n", "--name", help="Capture name (default: input filename)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1
    
    # 加载输入数据
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    capture_name = args.name or input_path.stem
    
    print(f"\n=== Generating Report Bundle: {capture_name} ===\n")
    
    # 提取数据
    textures = data.get("textures", []) if isinstance(data, dict) else data
    events = data.get("events", []) if isinstance(data, dict) else []
    shaders = data.get("shaders", []) if isinstance(data, dict) else []
    mali_data = data.get("mali", {}) if isinstance(data, dict) else {}
    performance = data.get("performance", {}) if isinstance(data, dict) else {}
    frame_thumb = data.get("frame_thumbnail", "") if isinstance(data, dict) else ""
    usage_map = data.get("texture_usage_map", {}) if isinstance(data, dict) else {}
    
    # 生成报告
    output_files = generate_report_bundle(
        output_dir=args.output,
        capture_name=capture_name,
        textures=textures,
        events=events,
        shaders=shaders,
        performance_data=performance,
        mali_data=mali_data,
        frame_thumbnail=frame_thumb,
        texture_usage_map=usage_map
    )
    
    print(f"\n=== Report Bundle Generated ===")
    print(f"  Output: {args.output}")
    print(f"  Files: {len(output_files)}")
    for name, path in output_files.items():
        print(f"    - {name}: {Path(path).name}")
    
    return 0


if __name__ == "__main__":
    exit(main())
