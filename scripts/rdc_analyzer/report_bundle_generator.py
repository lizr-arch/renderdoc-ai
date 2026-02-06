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
from typing import Dict, List, Union

# 拆分模块
from timeline_builder import (
    build_aggregated_timeline,
    prepare_events_for_frontend,
    build_events_tree
)
from server_scripts import generate_rt_server_scripts

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
        self.shader_usage_map: Dict = {}  # shader_id -> List[usage_record]
        
        # RT 预览服务配置
        self.rt_server_port: int = 8765  # 默认端口
        
        # 资源使用索引（证据链数据基础）
        self.resource_usage_index: Dict = {}
        
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
        """标准化缩略图地址：支持 data URL 与文件路径"""
        if not thumbnail:
            return ""
        if thumbnail.startswith("data:"):
            return thumbnail
        lower = thumbnail.lower()
        if lower.startswith("http://") or lower.startswith("https://"):
            return thumbnail
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
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
    
    def set_shaders(self, shaders: List[Dict], mali_data: Dict = None, usage_map: Dict = None):
        """
        设置 Shader 数据
        
        Args:
            shaders: Shader 数据列表
            mali_data: Mali Offline Compiler 分析结果
            usage_map: Shader 使用映射 {shader_id: [usage_record]}
        """
        self.shaders = shaders or []
        self.mali_data = mali_data or {}
        self.shader_usage_map = usage_map or {}
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
    
    def set_resource_usage_index(self, usage_index):
        """
        设置资源使用索引（证据链数据基础）
        
        Args:
            usage_index: ResourceUsageIndex 对象或其序列化后的字典
        """
        if hasattr(usage_index, 'to_dict'):
            self.resource_usage_index = usage_index.to_dict()
        elif isinstance(usage_index, dict):
            self.resource_usage_index = usage_index
        else:
            self.resource_usage_index = {}
    
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
        for tex in self.textures:
            tex_id = tex.get("id") or tex.get("resource_id", "")
            raw_name = tex.get("name", "")
            width = tex.get("width", 0)
            height = tex.get("height", 0)
            fmt = tex.get("format", "UNKNOWN")
            mips = tex.get("mips", 1)
            vram = tex.get("vram", 0)
            has_issue = bool(tex.get("issues"))
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
            
            thumb_html = "<div class='thumb-placeholder'>?</div>"
            if thumb:
                thumb_html = f'<img src="{thumb}" alt="">'

            texture_list_html += f'''
                <div class="texture-item"
                     data-id="{tex_id}"
                     data-name="{display_name}"
                     data-format="{fmt}"
                     data-width="{width}"
                     data-height="{height}"
                     data-mip-levels="{mips}"
                     data-vram="{vram}"
                     data-has-issue="{str(has_issue).lower()}"
                     onclick="selectTexture('{tex_id}')">
                    <div class="texture-item-thumb">
                        {thumb_html}
                    </div>
                    <div class="texture-item-info">
                        <div class="texture-item-name">{display_name}{size_tag}</div>
                        <div class="texture-item-meta">{width}×{height} • {simple_fmt}</div>
                    </div>
                </div>'''
        
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "TEXTURE_COUNT": str(len(self.textures)),
            "TOTAL_VRAM": self._format_bytes(self.stats["vram_usage"]),
            "TEXTURE_LIST_HTML": texture_list_html,
            "TEXTURE_DATA_JSON": json.dumps(textures_with_usage, ensure_ascii=False),
        }
        
        return self._render_template(template, replacements)
    
    def generate_events(self) -> str:
        """生成 events.html 事件时间线"""
        template = self._load_template("events.html")
        
        # 构建事件树结构（使用拆分模块）
        events_tree = build_events_tree(self.events)
        
        # 生成聚合的时间线条形图 HTML（按 RenderPass/Marker 聚合）
        timeline_bars_html = build_aggregated_timeline(self.events)
        
        # 为前端准备完整的事件数据（包含 shaders, textures, renderTargets）
        prepared_events = prepare_events_for_frontend(
            self.events, self.textures, self.shaders
        )
        
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
            "EVENT_DATA_JSON": json.dumps(prepared_events, ensure_ascii=False),
            "RT_SERVER_PORT": str(self.rt_server_port)  # RT 预览服务端口
        }
        
        return self._render_template(template, replacements)
    
    def generate_shaders(self) -> str:
        """生成 shaders.html Shader 分析页面"""
        template = self._load_template("shaders.html")
        
        # 处理 Mali 分析数据和使用信息
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
            
            # 注入 Shader 使用信息（从 shader_usage_map）
            shader_copy["usages"] = self.shader_usage_map.get(str(shader_id), [])
            
            shader_with_mali.append(shader_copy)
        
        # 生成 Shader 列表 HTML（用于初始渲染）
        shader_list_html = ""
        for shader in self.shaders[:50]:  # 限制初始渲染
            shader_id = shader.get("id") or shader.get("resource_id", "")
            name = shader.get("name", f"Shader {shader_id}")
            shader_type = shader.get("type", "Unknown")
            shader_type_lower = str(shader_type).lower()
            # 从 shader_usage_map 获取使用次数，回退到 usedBy
            usage_count = len(self.shader_usage_map.get(str(shader_id), []) or shader.get("usedBy", []) or [])
            has_issue = bool(shader.get("issues") or shader.get("suggestions"))
            mali_cycles = 0
            if isinstance(shader.get("mali"), dict):
                mali_cycles = shader.get("mali", {}).get("totalCycles", 0) or 0
            type_tag_map = {
                "vertex": "vs",
                "vs": "vs",
                "pixel": "fs",
                "fragment": "fs",
                "fs": "fs",
                "compute": "cs",
                "cs": "cs",
            }
            type_tag = type_tag_map.get(shader_type_lower, "")
            
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
                <div class="shader-item" data-id="{shader_id}" data-name="{name}" data-type="{shader_type_lower}"
                     data-usage="{usage_count}" data-cycles="{mali_cycles}"
                     data-has-issue="{str(has_issue).lower()}" onclick="selectShader('{shader_id}')">
                    <span class="shader-item-type">{icon}</span>
                    <div class="shader-item-info">
                        <div class="shader-item-name">{name}</div>
                        <div class="shader-item-meta">
                            <span class="shader-meta-tag {type_tag}">{shader_type}</span>
                            {mali_badge}
                        </div>
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
        """生成优化建议专页 recommendations.html (高密度列表风格)"""
        template = self._load_template("recommendations.html")
        
        # 统计各严重程度的问题数量
        issues = self.performance_data.get("issues", []) if self.performance_data else []
        recommendations = self.performance_data.get("recommendations", []) if self.performance_data else []
        
        # 合并问题和建议，使用新的数据结构
        all_issues = []
        
        # 处理结构化问题
        for issue in issues:
            if isinstance(issue, dict):
                item = {
                    "id": issue.get("rule_id", f"ISSUE-{len(all_issues)+1:03d}"),
                    "severity": issue.get("severity", "info"),
                    "category": issue.get("category", "general"),
                    "title": issue.get("title", ""),
                    "description": issue.get("message", ""),
                    "suggestion": issue.get("suggestion", ""),
                    "impact": issue.get("impact", ""),
                }
                # M3.3: 保留证据链数据
                if "evidence" in issue:
                    item["evidence"] = issue["evidence"]
                all_issues.append(item)
            else:
                # 字符串格式
                all_issues.append({
                    "id": f"ISSUE-{len(all_issues)+1:03d}",
                    "severity": "info",
                    "category": "general",
                    "title": str(issue)[:60],
                    "description": str(issue),
                    "suggestion": "",
                    "impact": "",
                })
        
        # 处理建议
        for rec in recommendations:
            if isinstance(rec, dict):
                all_issues.append({
                    "id": rec.get("id", rec.get("rule_id", f"REC-{len(all_issues)+1:03d}")),
                    "severity": rec.get("severity", "info"),
                    "category": rec.get("category", "general"),
                    "title": rec.get("title", ""),
                    "description": rec.get("description", rec.get("detail", rec.get("message", ""))),
                    "suggestion": rec.get("suggestion", rec.get("action", "")),
                    "impact": rec.get("impact", ""),
                })
            else:
                all_issues.append({
                    "id": f"REC-{len(all_issues)+1:03d}",
                    "severity": "info",
                    "category": "general",
                    "title": str(rec)[:60],
                    "description": str(rec),
                    "suggestion": "",
                    "impact": "",
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
        
        # 分类名称映射
        category_names = {
            "texture": "纹理",
            "shader": "着色器",
            "drawcall": "绘制调用",
            "memory": "内存",
            "bandwidth": "带宽",
            "general": "通用",
        }
        
        # 生成分类下拉选项 HTML
        category_options_html = ""
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            name = category_names.get(cat, cat.capitalize())
            category_options_html += f'<option value="{cat}">{name} ({count})</option>\n'
        
        # 生成建议列表 HTML (紧凑列表风格)
        recommendations_list_html = ""
        for issue in all_issues:
            severity = issue["severity"]
            if severity in ["critical", "high", "error"]:
                severity_class = "critical"
            elif severity == "warning":
                severity_class = "warning"
            else:
                severity_class = "info"
            
            category = issue["category"]
            cat_name = category_names.get(category, category)
            
            recommendations_list_html += f'''
                <div class="recommendation-item" data-id="{issue["id"]}" data-severity="{severity_class}" data-category="{category}">
                    <span class="severity-dot {severity_class}"></span>
                    <div class="recommendation-content">
                        <div class="recommendation-title">{issue["title"]}</div>
                        <div class="recommendation-meta">
                            <span class="recommendation-id">{issue["id"]}</span>
                            <span class="recommendation-category">{cat_name}</span>
                        </div>
                    </div>
                </div>'''
        
        # 空状态
        if not recommendations_list_html:
            recommendations_list_html = '''
                <div class="empty-state">
                    <div class="empty-icon">✅</div>
                    <div class="empty-title">没有发现问题</div>
                    <div>该帧渲染性能良好</div>
                </div>'''
        
        # JSON 数据供 JS 使用
        recommendations_json = json.dumps(all_issues, ensure_ascii=False)
        # 分析时间
        analysis_time = self.timestamp
        
        # 简化的 replacements (旧风格只需要基础变量)
        replacements = {
            "CAPTURE_NAME": self.capture_name,
            "ANALYSIS_TIME": analysis_time,
            "TOTAL_ISSUES": str(total_count),
            "CRITICAL_COUNT": str(critical_count),
            "WARNING_COUNT": str(warning_count),
            "INFO_COUNT": str(info_count),
            "CATEGORY_OPTIONS": category_options_html,
            "RECOMMENDATIONS_LIST": recommendations_list_html,
            "RECOMMENDATIONS_JSON": recommendations_json,
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
        
        # 6.5 生成 resource_usage.json（资源使用索引，证据链数据基础）
        if self.resource_usage_index:
            usage_path = self.output_dir / "resource_usage.json"
            usage_path.write_text(json.dumps(self.resource_usage_index, indent=2, ensure_ascii=False), encoding="utf-8")
            output_files["resource_usage"] = str(usage_path)
            print(f"  [OK] Generated: {usage_path.name}")
        
        # 6. 复制 CSS 和 JS 文件到输出目录
        import shutil
        static_files = [
            "common.css",      # 公共样式
            "navigation.js",   # 跨页面导航模块（M3: 证据链跳转）
        ]
        for file_name in static_files:
            file_src = TEMPLATES_DIR / file_name
            file_dst = self.output_dir / file_name
            if file_src.exists():
                shutil.copy2(file_src, file_dst)
                output_files[f"static_{file_name}"] = str(file_dst)
                print(f"  [OK] Copied: {file_dst.name}")
            else:
                print(f"  [WARN] {file_name} not found at {file_src}")
        
        # 7. 生成 RT 预览服务启动脚本（使用拆分模块）
        startup_scripts = generate_rt_server_scripts(self.output_dir, self.rt_server_port)
        for script_name, script_path in startup_scripts.items():
            output_files[script_name] = script_path
            print(f"  [OK] Generated: {Path(script_path).name}")
        
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
