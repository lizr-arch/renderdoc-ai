#!/usr/bin/env python3
"""
生成 100% 离线 HTML 报告 - 无任何外部依赖

专门用于 D3D11/D3D12 纹理分析，不依赖 CDN 或网络资源。
"""

import json
import base64
import argparse
import io
from pathlib import Path
from datetime import datetime

# RT Timeline 组件 (Direction C)
try:
    from components.rt_timeline_component import (
        generate_rt_timeline_css,
        generate_rt_timeline_html,
        generate_rt_timeline_js
    )
    HAS_RT_TIMELINE = True
except ImportError:
    HAS_RT_TIMELINE = False

# Hotspot 组件 (Direction F)
try:
    from components.hotspot_component import (
        generate_hotspot_css,
        generate_hotspot_html,
        generate_hotspot_js
    )
    HAS_HOTSPOT = True
except ImportError:
    HAS_HOTSPOT = False

# 尝试导入 PIL
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("  [WARN] Pillow not installed. Run: pip install Pillow")
    print("         RGBA channel separation will be disabled.")


def generate_channel_images(png_path: Path) -> dict:
    """
    用 PIL 将 PNG 拆分为 R/G/B/A 四个灰度图
    
    Args:
        png_path: PNG 文件路径
        
    Returns:
        {"r": base64_data, "g": base64_data, "b": base64_data, "a": base64_data}
        如果通道为纯色则返回 None
    """
    if not HAS_PIL:
        return {}
    
    try:
        img = Image.open(png_path).convert("RGBA")
        r, g, b, a = img.split()
        
        channels = {}
        for name, channel in [("r", r), ("g", g), ("b", b), ("a", a)]:
            # 检查是否为纯色通道（跳过无意义的通道）
            extrema = channel.getextrema()
            if extrema[0] == extrema[1]:
                # 纯色通道，跳过（但 alpha=255 的情况保留提示）
                if name == "a" and extrema[0] == 255:
                    channels[name] = None  # 表示全不透明
                continue
            
            # 转为灰度 PNG 并编码为 Base64
            buffer = io.BytesIO()
            channel.save(buffer, format="PNG", optimize=True)
            b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            channels[name] = f"data:image/png;base64,{b64_data}"
        
        return channels
    except Exception as e:
        print(f"    [WARN] Failed to split channels for {png_path.name}: {e}")
        return {}


def load_textures_from_export(rdc_path: str, enable_channels: bool = True) -> list:
    """从导出目录加载纹理元数据和缩略图"""
    rdc_path = Path(rdc_path)
    capture_name = rdc_path.stem
    
    # 查找 textures.json
    possible_paths = [
        rdc_path.parent / f"{capture_name}_textures" / "textures.json",
        rdc_path.parent / "textures" / "textures.json",
    ]
    
    for manifest_path in possible_paths:
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            textures = []
            textures_dir = manifest_path.parent
            
            # 支持两种格式: {"textures": [...]} 或直接 [...]
            tex_list = manifest if isinstance(manifest, list) else manifest.get("textures", [])
            for tex in tex_list:
                res_id = tex.get("resource_id") or tex.get("id")
                filename = tex.get("filename") or tex.get("file")
                
                thumbnail_data = ""
                channels = {}
                full_path = None
                
                # 优先使用 JSON 中已有的 thumbnail 字段（base64）
                if tex.get("thumbnail"):
                    thumbnail_data = tex["thumbnail"]
                    # 确保是完整的 Data URI 格式
                    if not thumbnail_data.startswith("data:"):
                        thumbnail_data = f"data:image/png;base64,{thumbnail_data}"
                # 否则从文件读取
                elif filename:
                    full_path = textures_dir / filename
                    if full_path.exists():
                        with open(full_path, 'rb') as img_file:
                            img_data = img_file.read()
                            b64_data = base64.b64encode(img_data).decode('utf-8')
                            thumbnail_data = f"data:image/png;base64,{b64_data}"
                        
                        # 生成通道分离图
                        if enable_channels and HAS_PIL:
                            channels = generate_channel_images(full_path)
                
                textures.append({
                    "id": res_id,
                    "name": tex.get("name", ""),
                    "width": tex.get("width", 0),
                    "height": tex.get("height", 0),
                    "depth": tex.get("depth", 1),
                    "format": tex.get("format", "UNKNOWN"),
                    "mips": tex.get("mips", 1),
                    "arrayLayers": tex.get("arrayLayers", 1),
                    "thumbnail": thumbnail_data,
                    "channels": channels  # {"r": base64, "g": base64, ...}
                })
            
            print(f"  [OK] Loaded {len(textures)} textures from {manifest_path}")
            return textures
    
    print("  [WARN] No textures.json found")
    return []


def generate_offline_html(textures: list, rdc_name: str, output_path: str, 
                          duplicate_analysis: dict = None, usage_analysis: dict = None,
                          event_pass_data: dict = None, frame_thumbnail: str = None,
                          optimization_data: dict = None, performance_data: dict = None,
                          rt_tracking_data: dict = None, hotspot_data: dict = None,
                          shader_data: list = None):
    """生成纯离线 HTML 报告
    
    Args:
        textures: 纹理数据列表
        rdc_name: RDC 文件名
        output_path: 输出 HTML 路径
        duplicate_analysis: 去重分析结果（可选）
        usage_analysis: 纹理热度分析结果（可选）
        event_pass_data: Event/Pass 数据（可选，用于 Event Browser 视图）
        frame_thumbnail: 帧缩略图 Base64 数据 (data:image/png;base64,...) （可选）
        optimization_data: 优化建议数据（可选，来自 OptimizationAdvisor）
        performance_data: 性能分析数据（可选，来自 PerformanceAnalyzer，TASK-008）
        rt_tracking_data: RT 追踪数据（可选，来自 RTTracker，Direction C）
        hotspot_data: 热点分析数据（可选，来自 HotspotAnalyzer，Direction F）
        shader_data: Shader 列表数据（可选，用于 Shader 资源浏览器，TASK-205）
    """
    
    textures_json = json.dumps(textures, ensure_ascii=False)
    duplicates_json = json.dumps(duplicate_analysis or {}, ensure_ascii=False)
    usage_json = json.dumps(usage_analysis or {}, ensure_ascii=False)
    event_pass_json = json.dumps(event_pass_data or {}, ensure_ascii=False)
    frame_thumbnail_json = json.dumps(frame_thumbnail or "", ensure_ascii=False)
    optimization_json = json.dumps(optimization_data or {}, ensure_ascii=False)
    performance_json = json.dumps(performance_data or {}, ensure_ascii=False)
    shader_json = json.dumps(shader_data or [], ensure_ascii=False)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RDC 纹理报告 - {rdc_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        :root {{
            --bg-darkest: #0d1117;
            --bg-darker: #161b22;
            --bg-dark: #21262d;
            --bg-medium: #30363d;
            --border: #30363d;
            --border-light: #484f58;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-red: #e94560;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #f9c513;
            --accent-orange: #f0883e;
            --accent-purple: #a371f7;
            --panel-header: 28px;
        }}
        
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-darkest);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
            font-size: 13px;
        }}
        
        /* ========== Photoshop 风格主布局 ========== */
        .app-container {{
            display: flex;
            flex-direction: column;
            height: 100vh;
        }}
        
        /* 顶部菜单栏 */
        .app-menubar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 32px;
            background: var(--bg-darker);
            border-bottom: 1px solid var(--border);
            padding: 0 12px;
            flex-shrink: 0;
        }}
        
        .app-title {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
            color: var(--accent-red);
            font-size: 12px;
        }}
        
        .app-title .logo {{
            width: 16px;
            height: 16px;
            background: var(--accent-red);
            border-radius: 3px;
        }}
        
        .app-menu {{
            display: flex;
            gap: 4px;
        }}
        
        .menu-item {{
            padding: 4px 10px;
            color: var(--text-secondary);
            font-size: 11px;
            cursor: pointer;
            border-radius: 3px;
        }}
        
        .menu-item:hover {{
            background: var(--bg-dark);
            color: var(--text-primary);
        }}
        
        /* 视图切换按钮特殊样式 */
        .menu-item.view-toggle {{
            background: var(--accent-blue);
            color: white;
            padding: 4px 12px;
            font-weight: 500;
        }}
        
        .menu-item.view-toggle:hover {{
            background: #3a8edc;
            color: white;
        }}
        
        /* 下拉菜单 */
        .dropdown-trigger {{
            position: relative;
        }}
        
        .dropdown-menu {{
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            min-width: 160px;
            background: var(--bg-medium);
            border: 1px solid var(--border-dark);
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            z-index: 1000;
            padding: 4px 0;
        }}
        
        .dropdown-trigger:hover .dropdown-menu {{
            display: block;
        }}
        
        .dropdown-item {{
            padding: 8px 12px;
            font-size: 11px;
            color: var(--text-secondary);
            cursor: pointer;
            white-space: nowrap;
        }}
        
        .dropdown-item:hover {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .dropdown-divider {{
            height: 1px;
            background: var(--border-dark);
            margin: 4px 0;
        }}
        
        .app-meta {{
            color: var(--text-muted);
            font-size: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .frame-thumb-preview {{
            display: inline-flex;
            align-items: center;
            cursor: pointer;
            border: 1px solid var(--border);
            border-radius: 3px;
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        
        .frame-thumb-preview:hover {{
            border-color: var(--accent-blue);
        }}
        
        .frame-thumb-preview img {{
            height: 20px;
            width: auto;
            display: block;
        }}
        
        /* 帧缩略图弹窗 */
        .frame-thumb-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.85);
            z-index: 10000;
            justify-content: center;
            align-items: center;
        }}
        
        .frame-thumb-modal.active {{
            display: flex;
        }}
        
        .frame-thumb-modal img {{
            max-width: 90%;
            max-height: 90%;
            border-radius: 4px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        }}
        
        .frame-thumb-modal .close-btn {{
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 32px;
            color: #fff;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
        }}
        
        .frame-thumb-modal .close-btn:hover {{
            opacity: 1;
        }}
        
        .frame-thumb-modal .caption {{
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            color: var(--text-secondary);
            font-size: 12px;
            background: rgba(0, 0, 0, 0.6);
            padding: 6px 12px;
            border-radius: 4px;
        }}
        
        /* 主工作区 */
        .app-workspace {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        
        /* ========== 左侧面板 - 纹理列表 ========== */
        .panel-left {{
            width: 280px;
            min-width: 200px;
            max-width: 400px;
            background: var(--bg-darker);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            overflow: hidden;  /* 确保 flex 子元素正确计算高度 */
        }}
        
        .panel-left.collapsed {{
            width: 36px;
            min-width: 36px;
        }}
        
        .panel-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: var(--panel-header);
            padding: 0 8px;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
        }}
        
        .panel-header:hover {{
            background: var(--bg-medium);
        }}
        
        .panel-title {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }}
        
        .panel-toggle {{
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            transition: transform 0.2s;
        }}
        
        .panel-left.collapsed .panel-toggle {{
            transform: rotate(-90deg);
        }}
        
        .panel-left.collapsed .panel-title,
        .panel-left.collapsed .panel-content {{
            display: none;
        }}
        
        /* 搜索和过滤工具栏 */
        .list-toolbar {{
            padding: 8px;
            background: var(--bg-darker);
            border-bottom: 1px solid var(--border);
        }}
        
        .search-box {{
            width: 100%;
            padding: 6px 10px;
            background: var(--bg-darkest);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 11px;
            margin-bottom: 6px;
        }}
        
        .search-box:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        .filter-row {{
            display: flex;
            gap: 6px;
            align-items: center;
        }}
        
        .sort-select {{
            flex: 1;
            padding: 4px 6px;
            background: var(--bg-darkest);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 10px;
            cursor: pointer;
        }}
        
        .stats-badge {{
            padding: 2px 6px;
            background: var(--bg-dark);
            border-radius: 3px;
            color: var(--text-muted);
            font-size: 10px;
        }}
        
        /* 纹理列表 */
        .texture-list {{
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            min-height: 200px;  /* 确保有最小高度 */
        }}
        
        .texture-list::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .texture-list::-webkit-scrollbar-track {{
            background: var(--bg-darker);
        }}
        
        .texture-list::-webkit-scrollbar-thumb {{
            background: var(--bg-medium);
            border-radius: 4px;
        }}
        
        .texture-list::-webkit-scrollbar-thumb:hover {{
            background: var(--border-light);
        }}
        
        /* ========== 资源浏览器双列表 (TASK-205) ========== */
        .resource-section {{
            border-top: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
        }}
        
        .resource-section:first-child {{
            border-top: none;
        }}
        
        .resource-section-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            background: linear-gradient(180deg, var(--bg-medium) 0%, var(--bg-dark) 100%);
            cursor: pointer;
            user-select: none;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .resource-section-header:hover {{
            background: linear-gradient(180deg, var(--bg-light) 0%, var(--bg-medium) 100%);
        }}
        
        .resource-section-icon {{
            font-size: 14px;
        }}
        
        .resource-section-title {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: 0.5px;
            flex: 1;
        }}
        
        .resource-section-badge {{
            background: var(--accent-blue);
            color: #fff;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 500;
        }}
        
        .resource-section-badge.shader-badge {{
            background: var(--accent-purple);
        }}
        
        .resource-section-toggle {{
            font-size: 10px;
            color: var(--text-muted);
            transition: transform 0.2s;
        }}
        
        .resource-section.collapsed .resource-section-toggle {{
            transform: rotate(-90deg);
        }}
        
        .resource-section.collapsed .resource-section-content {{
            display: none;
        }}
        
        .resource-section-content {{
            display: flex;
            flex-direction: column;
            flex: 1;
            min-height: 0;
        }}
        
        .resource-filter-bar {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg-darker);
            border-bottom: 1px solid var(--border-color);
        }}
        
        .filter-toggle-group {{
            display: flex;
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        
        .filter-toggle-btn {{
            padding: 4px 10px;
            font-size: 10px;
            background: var(--bg-dark);
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s;
        }}
        
        .filter-toggle-btn:hover {{
            background: var(--bg-medium);
            color: var(--text-primary);
        }}
        
        .filter-toggle-btn.active {{
            background: var(--accent-blue);
            color: #fff;
        }}
        
        .shader-section .filter-toggle-btn.active {{
            background: var(--accent-purple);
        }}
        
        .resource-search-box {{
            flex: 1;
            padding: 4px 8px;
            font-size: 11px;
            background: var(--bg-dark);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-primary);
            min-width: 60px;
        }}
        
        .resource-search-box::placeholder {{
            color: var(--text-muted);
        }}
        
        .resource-search-box:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        .shader-section .resource-search-box:focus {{
            border-color: var(--accent-purple);
        }}
        
        .resource-sort-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 12px;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border-color);
        }}
        
        /* 筛选提示条样式 */
        .optimization-filter-bar,
        .shader-filter-bar {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: linear-gradient(90deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.05) 100%);
            border-bottom: 1px solid rgba(34, 197, 94, 0.3);
            font-size: 11px;
        }}
        
        .shader-filter-bar {{
            background: linear-gradient(90deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%);
            border-bottom: 1px solid rgba(168, 85, 247, 0.3);
        }}
        
        .filter-indicator {{
            font-size: 12px;
        }}
        
        .filter-clear-btn {{
            margin-left: auto;
            background: var(--bg-medium);
            border: none;
            color: var(--text-muted);
            padding: 2px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 10px;
        }}
        
        .filter-clear-btn:hover {{
            background: var(--bg-light);
            color: var(--text-primary);
        }}
        
        /* Shader 列表样式 */
        .shader-list {{
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            max-height: 250px;
        }}
        
        .shader-list::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .shader-list::-webkit-scrollbar-track {{
            background: var(--bg-darker);
        }}
        
        .shader-list::-webkit-scrollbar-thumb {{
            background: var(--bg-medium);
            border-radius: 3px;
        }}
        
        .shader-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-bottom: 1px solid var(--bg-dark);
            cursor: pointer;
            transition: all 0.15s;
        }}
        
        .shader-item:hover {{
            background: var(--bg-dark);
        }}
        
        .shader-item.selected {{
            background: rgba(168, 85, 247, 0.15);
            border-left: 3px solid var(--accent-purple);
        }}
        
        .shader-item.has-issue {{
            background: rgba(251, 146, 60, 0.08);
        }}
        
        .shader-item.has-issue::before {{
            content: '⚠';
            font-size: 10px;
            margin-right: 4px;
        }}
        
        .shader-item-icon {{
            font-size: 14px;
            flex-shrink: 0;
        }}
        
        .shader-item-content {{
            flex: 1;
            min-width: 0;
        }}
        
        .shader-item-name {{
            font-size: 11px;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .shader-item-meta {{
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        
        .shader-item-type {{
            font-size: 9px;
            padding: 1px 5px;
            border-radius: 3px;
            background: var(--bg-medium);
            color: var(--text-secondary);
            flex-shrink: 0;
        }}
        
        .shader-item-type.vs {{ background: rgba(96, 165, 250, 0.2); color: #60a5fa; }}
        .shader-item-type.ps {{ background: rgba(251, 146, 60, 0.2); color: #fb923c; }}
        .shader-item-type.cs {{ background: rgba(34, 197, 94, 0.2); color: #22c55e; }}
        .shader-item-type.gs {{ background: rgba(168, 85, 247, 0.2); color: #a855f7; }}
        .shader-item-type.hs {{ background: rgba(236, 72, 153, 0.2); color: #ec4899; }}
        .shader-item-type.ds {{ background: rgba(20, 184, 166, 0.2); color: #14b8a6; }}
        
        .shader-empty {{
            padding: 20px;
            text-align: center;
            color: var(--text-muted);
            font-size: 11px;
        }}
        
        /* TASK-209: Shader 详情面板样式 */
        .shader-details-panel {{
            border-top: 1px solid var(--bg-medium);
            background: var(--bg-darker);
            padding: 12px;
            font-size: 11px;
            display: none;
        }}
        
        .shader-details-panel.active {{
            display: block;
        }}
        
        .shader-details-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--bg-medium);
        }}
        
        .shader-details-title {{
            flex: 1;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 12px;
        }}
        
        .shader-details-close {{
            width: 20px;
            height: 20px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }}
        
        .shader-details-close:hover {{
            background: var(--bg-medium);
            color: var(--text-primary);
        }}
        
        .shader-details-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 12px;
        }}
        
        .shader-detail-item {{
            background: var(--bg-dark);
            padding: 8px 10px;
            border-radius: 6px;
        }}
        
        .shader-detail-label {{
            font-size: 9px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }}
        
        .shader-detail-value {{
            font-size: 12px;
            color: var(--text-primary);
            font-weight: 500;
        }}
        
        .shader-detail-value.type-pipeline {{ color: #a855f7; }}
        .shader-detail-value.type-vs {{ color: #60a5fa; }}
        .shader-detail-value.type-ps {{ color: #fb923c; }}
        .shader-detail-value.type-cs {{ color: #22c55e; }}
        
        .shader-issues-summary {{
            background: rgba(251, 146, 60, 0.1);
            border: 1px solid rgba(251, 146, 60, 0.3);
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 12px;
        }}
        
        .shader-issues-summary.no-issues {{
            background: rgba(34, 197, 94, 0.1);
            border-color: rgba(34, 197, 94, 0.3);
        }}
        
        .shader-issues-title {{
            font-size: 10px;
            font-weight: 600;
            color: var(--accent-orange);
            margin-bottom: 6px;
        }}
        
        .shader-issues-summary.no-issues .shader-issues-title {{
            color: #22c55e;
        }}
        
        .shader-issue-item {{
            font-size: 10px;
            color: var(--text-secondary);
            padding: 2px 0;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .shader-issue-item::before {{
            content: '•';
            color: var(--accent-orange);
        }}
        
        .shader-details-actions {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .shader-action-btn {{
            flex: 1;
            min-width: 100px;
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            background: var(--accent-blue);
            color: white;
            font-size: 10px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        
        .shader-action-btn:hover {{
            filter: brightness(1.1);
            transform: translateY(-1px);
        }}
        
        .shader-action-btn.secondary {{
            background: var(--bg-medium);
            color: var(--text-primary);
        }}
        
        .shader-usage-bar {{
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid var(--bg-medium);
        }}
        
        .shader-usage-label {{
            font-size: 9px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        
        .shader-usage-chart {{
            height: 24px;
            background: var(--bg-dark);
            border-radius: 4px;
            overflow: hidden;
            display: flex;
        }}
        
        .shader-usage-segment {{
            height: 100%;
            background: var(--accent-purple);
            opacity: 0.7;
        }}
        
        /* TASK-209-D: Shader 代码预览样式 */
        .shader-code-preview {{
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid var(--bg-medium);
        }}
        
        .shader-code-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        
        .shader-code-title {{
            font-size: 10px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .shader-code-badge {{
            font-size: 9px;
            padding: 2px 6px;
            background: var(--bg-medium);
            color: var(--text-muted);
            border-radius: 3px;
        }}
        
        .shader-code-placeholder {{
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 16px;
            text-align: center;
            border: 1px dashed var(--bg-medium);
        }}
        
        .code-unavailable-icon {{
            font-size: 20px;
            opacity: 0.5;
            margin-bottom: 6px;
        }}
        
        .code-unavailable-text {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}
        
        .code-unavailable-hint {{
            font-size: 9px;
            color: var(--text-muted);
            opacity: 0.7;
        }}
        
        .texture-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-bottom: 1px solid var(--bg-dark);
            cursor: pointer;
            transition: background 0.1s;
            height: 52px;
            box-sizing: border-box;
        }}
        
        /* 虚拟滚动容器 */
        .virtual-scroll-spacer {{
            position: relative;
        }}
        
        .virtual-scroll-content {{
            position: absolute;
            left: 0;
            right: 0;
            top: 0;
        }}
        
        .texture-item:hover {{
            background: var(--bg-dark);
        }}
        
        .texture-item.selected {{
            background: var(--accent-blue);
            background: rgba(88, 166, 255, 0.15);
            border-left: 2px solid var(--accent-blue);
        }}
        
        .texture-item.hidden {{
            display: none;
        }}
        
        /* 跳转高亮动画 */
        .texture-item.jump-highlight {{
            animation: jumpPulse 1.5s ease-out;
        }}
        
        @keyframes jumpPulse {{
            0% {{ 
                background: rgba(88, 166, 255, 0.5);
                box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.5);
            }}
            50% {{
                background: rgba(88, 166, 255, 0.3);
                box-shadow: 0 0 0 6px rgba(88, 166, 255, 0.2);
            }}
            100% {{
                background: rgba(88, 166, 255, 0.15);
                box-shadow: none;
            }}
        }}
        
        .texture-item-thumb {{
            width: 40px;
            height: 40px;
            background: var(--bg-darkest);
            border-radius: 4px;
            overflow: hidden;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .texture-item-thumb img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
        
        .texture-item-info {{
            flex: 1;
            min-width: 0;
        }}
        
        .texture-item-name {{
            font-size: 11px;
            font-weight: 500;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .texture-item-meta {{
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        
        .texture-item-dims {{
            color: var(--accent-green);
        }}
        
        /* ========== 中间主画布区域 ========== */
        .main-canvas-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--bg-darkest);
            overflow: hidden;
        }}
        
        /* 画布工具栏 */
        .canvas-toolbar {{
            display: flex;
            align-items: center;
            gap: 8px;
            height: 36px;
            padding: 0 12px;
            background: var(--bg-darker);
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }}
        
        .toolbar-group {{
            display: flex;
            align-items: center;
            gap: 4px;
            padding-right: 8px;
            border-right: 1px solid var(--border);
        }}
        
        .toolbar-group:last-child {{
            border-right: none;
        }}
        
        .toolbar-btn {{
            width: 28px;
            height: 28px;
            border: 1px solid transparent;
            border-radius: 4px;
            background: transparent;
            color: var(--text-secondary);
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.1s;
        }}
        
        .toolbar-btn:hover {{
            background: var(--bg-dark);
            color: var(--text-primary);
        }}
        
        .toolbar-btn.active {{
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }}
        
        .toolbar-separator {{
            width: 1px;
            height: 20px;
            background: var(--border);
            margin: 0 4px;
        }}
        
        .zoom-display {{
            font-size: 10px;
            color: var(--text-muted);
            min-width: 45px;
            text-align: center;
            font-family: monospace;
        }}
        
        /* 通道按钮 - 紧凑版 */
        .channel-btn {{
            padding: 4px 8px;
            border: 1px solid var(--border);
            border-radius: 3px;
            background: var(--bg-dark);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.1s;
        }}
        
        .channel-btn:hover {{
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }}
        
        .channel-btn.active {{
            background: var(--accent-red);
            border-color: var(--accent-red);
            color: white;
        }}
        
        .channel-btn.disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}
        
        .channel-btn[data-channel="r"].active {{ background: #ff6b6b; border-color: #ff6b6b; }}
        .channel-btn[data-channel="g"].active {{ background: #51cf66; border-color: #51cf66; }}
        .channel-btn[data-channel="b"].active {{ background: #339af0; border-color: #339af0; }}
        .channel-btn[data-channel="a"].active {{ background: #868e96; border-color: #868e96; }}
        
        /* 主画布 */
        .canvas-viewport {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            background: repeating-conic-gradient(var(--bg-medium) 0% 25%, var(--bg-dark) 0% 50%) 50% / 16px 16px;
            position: relative;
        }}
        
        .canvas-empty {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            color: var(--text-muted);
        }}
        
        .canvas-empty-icon {{
            font-size: 48px;
            opacity: 0.3;
        }}
        
        .canvas-empty-text {{
            font-size: 12px;
        }}
        
        .preview-img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            transform-origin: center center;
            cursor: grab;
        }}
        
        .preview-img.dragging {{
            cursor: grabbing;
        }}
        
        /* 浮动颜色拾取器 */
        .color-picker-float {{
            position: absolute;
            bottom: 12px;
            left: 12px;
            padding: 6px 10px;
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid var(--border);
            border-radius: 4px;
            font-family: monospace;
            font-size: 10px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
            backdrop-filter: blur(8px);
            z-index: 100;
        }}
        
        .color-preview {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
            border: 1px solid var(--border-light);
            background: #000;
        }}
        
        .color-picker-float .coord {{
            color: var(--accent-blue);
        }}
        
        .color-picker-float .hex {{
            color: var(--accent-green);
            cursor: pointer;
        }}
        
        /* ========== 右侧面板 - 属性 ========== */
        .panel-right {{
            width: 260px;
            min-width: 200px;
            max-width: 350px;
            background: var(--bg-darker);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            overflow: hidden;
        }}
        
        .panel-right.collapsed {{
            width: 36px;
            min-width: 36px;
        }}
        
        .panel-right.collapsed .panel-content,
        .panel-right.collapsed .panel-title {{
            display: none;
        }}
        
        /* 属性面板可折叠区块 */
        .prop-section {{
            border-bottom: 1px solid var(--border);
        }}
        
        .prop-section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 10px;
            background: var(--bg-dark);
            cursor: pointer;
            user-select: none;
        }}
        
        .prop-section-header:hover {{
            background: var(--bg-medium);
        }}
        
        .prop-section-title {{
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-secondary);
        }}
        
        .prop-section-toggle {{
            font-size: 10px;
            color: var(--text-muted);
            transition: transform 0.2s;
        }}
        
        .prop-section.collapsed .prop-section-toggle {{
            transform: rotate(-90deg);
        }}
        
        .prop-section.collapsed .prop-section-content {{
            display: none;
        }}
        
        .prop-section-content {{
            padding: 10px;
            background: var(--bg-darker);
        }}
        
        /* 属性行 */
        .prop-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            font-size: 11px;
        }}
        
        .prop-label {{
            color: var(--text-muted);
        }}
        
        .prop-value {{
            color: var(--text-primary);
            font-family: monospace;
            font-size: 10px;
        }}
        
        .prop-value.highlight {{
            color: var(--accent-blue);
        }}
        
        .prop-value.text-muted {{
            color: var(--text-muted);
        }}
        
        /* Mipmap 状态指示器 */
        .mip-status {{
            font-size: 10px;
            margin-left: 4px;
        }}
        
        .mip-status.good {{
            color: var(--accent-green);
        }}
        
        .mip-status.warn {{
            color: var(--accent-yellow);
        }}
        
        .mip-status.partial {{
            color: var(--accent-orange);
        }}
        
        /* 分析提示 */
        .analysis-tip {{
            font-size: 10px;
            padding: 6px 8px;
            border-radius: 4px;
            margin-top: 8px;
            line-height: 1.4;
        }}
        
        .analysis-tip.warn {{
            background: rgba(255, 193, 7, 0.1);
            color: var(--accent-yellow);
            border-left: 2px solid var(--accent-yellow);
        }}
        
        .analysis-tip.info {{
            background: rgba(88, 166, 255, 0.1);
            color: var(--accent-blue);
            border-left: 2px solid var(--accent-blue);
        }}
        
        .analysis-tip.error {{
            background: rgba(233, 69, 96, 0.1);
            color: var(--accent-red);
            border-left: 2px solid var(--accent-red);
        }}
        
        /* 全局问题汇总 */
        .global-issues {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}
        
        .issue-summary {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}
        
        .issue-summary.has-issues {{
            color: var(--accent-yellow);
        }}
        
        .issue-row {{
            font-size: 10px;
            padding: 4px 6px;
            border-radius: 3px;
            margin-bottom: 4px;
        }}
        
        .issue-row.warn {{
            background: rgba(255, 193, 7, 0.08);
            color: var(--accent-yellow);
        }}
        
        .issue-row.info {{
            background: rgba(88, 166, 255, 0.08);
            color: var(--text-muted);
        }}
        
        /* 直方图 */
        .histogram-canvas {{
            width: 100%;
            height: 60px;
            background: var(--bg-darkest);
            border-radius: 4px;
            margin-bottom: 8px;
        }}
        
        .histogram-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            color: var(--text-muted);
            font-family: monospace;
        }}
        
        /* 调整滑块 */
        .slider-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        
        .slider-row:last-child {{
            margin-bottom: 0;
        }}
        
        .slider-row label {{
            color: var(--text-muted);
            font-size: 10px;
            min-width: 50px;
        }}
        
        .slider-row input[type="range"] {{
            flex: 1;
            height: 3px;
            -webkit-appearance: none;
            appearance: none;
            background: var(--bg-medium);
            border-radius: 2px;
            cursor: pointer;
        }}
        
        .slider-row input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 12px;
            height: 12px;
            background: var(--accent-red);
            border-radius: 50%;
            cursor: pointer;
        }}
        
        .slider-value {{
            color: var(--accent-blue);
            font-size: 10px;
            min-width: 30px;
            text-align: right;
            font-family: monospace;
        }}
        
        /* 备注区 */
        .notes-textarea {{
            width: 100%;
            min-height: 50px;
            padding: 6px 8px;
            background: var(--bg-darkest);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 11px;
            resize: vertical;
            font-family: inherit;
        }}
        
        .notes-textarea:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        /* 统计摘要 - 紧凑版 */
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
        }}
        
        .stat-mini {{
            background: var(--bg-darkest);
            border-radius: 4px;
            padding: 8px;
            text-align: center;
        }}
        
        .stat-mini-value {{
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-blue);
        }}
        
        .stat-mini-label {{
            font-size: 9px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 2px;
        }}
        
        /* ========== VRAM 分布图表 ========== */
        .chart-container {{
            padding: 8px;
            background: var(--bg-secondary);
            border-radius: 8px;
            margin-top: 8px;
        }}
        
        .chart-row {{
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
        }}
        
        .chart-box {{
            flex: 1;
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 8px;
            min-height: 140px;
        }}
        
        .chart-title {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 8px;
            text-align: center;
        }}
        
        .pie-chart {{
            position: relative;
            width: 100px;
            height: 100px;
            margin: 0 auto;
            border-radius: 50%;
            background: conic-gradient(
                var(--accent-purple) 0deg 90deg,
                var(--accent-blue) 90deg 180deg,
                var(--accent-teal) 180deg 270deg,
                var(--accent-orange) 270deg 360deg
            );
        }}
        
        .pie-chart-inner {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            background: var(--bg-dark);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            color: var(--text-primary);
        }}
        
        .chart-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 8px;
            justify-content: center;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 9px;
            color: var(--text-muted);
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 3px;
            transition: background 0.15s;
        }}
        
        .legend-item:hover {{
            background: var(--bg-hover);
        }}
        
        .legend-color {{
            width: 8px;
            height: 8px;
            border-radius: 2px;
            flex-shrink: 0;
        }}
        
        /* VRAM 总结统计卡片 */
        .vram-summary {{
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }}
        
        .vram-stat {{
            flex: 1;
            text-align: center;
            padding: 8px 4px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            border: 1px solid var(--border);
        }}
        
        .vram-stat-value {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-bright);
            margin-bottom: 2px;
        }}
        
        .vram-stat-value.warn {{
            color: #f97316;
        }}
        
        .vram-stat-value.good {{
            color: #22c55e;
        }}
        
        .vram-stat-label {{
            font-size: 9px;
            color: var(--text-muted);
        }}
        
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            height: 100px;
        }}
        
        .bar-chart.top-textures {{
            height: auto;
            max-height: 180px;
        }}
        
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            height: 16px;
        }}
        
        .bar-label {{
            width: 50px;
            font-size: 9px;
            color: var(--text-muted);
            text-align: right;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .bar-track {{
            flex: 1;
            height: 10px;
            background: var(--bg-tertiary);
            border-radius: 5px;
            overflow: hidden;
        }}
        
        .bar-fill {{
            height: 100%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }}
        
        .bar-value {{
            width: 40px;
            font-size: 9px;
            color: var(--text-muted);
        }}
        
        .bar-row.clickable {{
            cursor: pointer;
            transition: background 0.15s;
        }}
        
        .bar-row.clickable:hover {{
            background: var(--hover);
            border-radius: 4px;
        }}
        
        /* ========== 底部状态栏 ========== */
        .app-statusbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 22px;
            padding: 0 12px;
            background: var(--bg-dark);
            border-top: 1px solid var(--border);
            font-size: 10px;
            color: var(--text-muted);
            flex-shrink: 0;
        }}
        
        .status-left {{
            display: flex;
            gap: 16px;
        }}
        
        .status-item {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        /* ========== 遗留样式兼容 - 保留原有网格视图 ========== */
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
            display: none; /* 默认隐藏，网格视图时显示 */
        }}
        
        .container.show {{
            display: block;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--accent-red);
        }}
        
        .header h1 {{
            font-size: 1.5rem;
            color: var(--accent-red);
        }}
        
        .header-meta {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        /* 原有工具栏 */
        .toolbar {{
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .stats {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        /* 统计摘要面板 - 原版 */
        .stats-panel {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-darker) 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.2s;
        }}
        
        .stat-card:hover {{
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }}
        
        .stat-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 4px;
        }}
        
        .stat-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* 优化建议面板 (TASK-009) */
        .optimization-panel {{
            background: var(--bg-darker);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        
        .optimization-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 16px;
            background: var(--bg-dark);
            cursor: pointer;
            user-select: none;
        }}
        
        .optimization-header:hover {{
            background: var(--bg-medium);
        }}
        
        .optimization-title {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }}
        
        .optimization-badge {{
            background: var(--accent-orange);
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        
        .optimization-toggle {{
            color: var(--text-secondary);
            transition: transform 0.2s;
        }}
        
        .optimization-toggle.collapsed {{
            transform: rotate(-90deg);
        }}
        
        .optimization-content {{
            max-height: 400px;
            overflow-y: auto;
            padding: 0;
            transition: max-height 0.3s ease;
        }}
        
        .optimization-content.collapsed {{
            max-height: 0;
            padding: 0;
        }}
        
        .optimization-summary {{
            display: flex;
            gap: 24px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-darkest);
        }}
        
        .optimization-stat {{
            text-align: center;
        }}
        
        .optimization-stat-value {{
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--accent-yellow);
        }}
        
        .optimization-stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .optimization-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .optimization-item {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .optimization-item:last-child {{
            border-bottom: none;
        }}
        
        .optimization-item:hover {{
            background: var(--bg-dark);
        }}
        
        .optimization-priority {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-top: 6px;
            flex-shrink: 0;
        }}
        
        .optimization-priority.CRITICAL {{ background: #e94560; }}
        .optimization-priority.HIGH {{ background: #f0883e; }}
        .optimization-priority.MEDIUM {{ background: #f9c513; }}
        .optimization-priority.LOW {{ background: #3fb950; }}
        
        .optimization-item-content {{
            flex: 1;
            min-width: 0;
        }}
        
        .optimization-item-title {{
            font-weight: 600;
            margin-bottom: 4px;
            color: var(--text-primary);
        }}
        
        .optimization-item-desc {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        
        .optimization-item-meta {{
            display: flex;
            gap: 12px;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .optimization-item-savings {{
            color: var(--accent-green);
            font-weight: 600;
        }}
        
        .optimization-empty {{
            padding: 24px;
            text-align: center;
            color: var(--text-muted);
        }}
        
        /* 性能分析面板 (TASK-008) */
        .performance-panel {{
            background: var(--bg-darker);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        
        .performance-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 16px;
            background: var(--bg-dark);
            cursor: pointer;
            user-select: none;
        }}
        
        .performance-header:hover {{
            background: var(--bg-medium);
        }}
        
        .performance-title {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
        }}
        
        .performance-score {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            font-size: 1.2rem;
            font-weight: 700;
            color: white;
        }}
        
        .performance-score.good {{ background: linear-gradient(135deg, #3fb950, #2ea043); }}
        .performance-score.medium {{ background: linear-gradient(135deg, #f9c513, #d29922); }}
        .performance-score.poor {{ background: linear-gradient(135deg, #f0883e, #db6d28); }}
        .performance-score.critical {{ background: linear-gradient(135deg, #e94560, #d73a4a); }}
        
        .performance-toggle {{
            color: var(--text-secondary);
            transition: transform 0.2s;
        }}
        
        .performance-toggle.collapsed {{
            transform: rotate(-90deg);
        }}
        
        .performance-content {{
            max-height: 500px;
            overflow-y: auto;
            padding: 0;
            transition: max-height 0.3s ease;
        }}
        
        .performance-content.collapsed {{
            max-height: 0;
            padding: 0;
        }}
        
        .performance-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            padding: 16px;
            background: var(--bg-darkest);
            border-bottom: 1px solid var(--border);
        }}
        
        .performance-metric {{
            text-align: center;
            padding: 8px;
            background: var(--bg-dark);
            border-radius: 6px;
        }}
        
        .performance-metric-value {{
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--accent-blue);
        }}
        
        .performance-metric-label {{
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 4px;
        }}
        
        .performance-issues {{
            padding: 0;
            margin: 0;
            list-style: none;
        }}
        
        .performance-issue {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .performance-issue:last-child {{
            border-bottom: none;
        }}
        
        .performance-issue:hover {{
            background: var(--bg-dark);
        }}
        
        .performance-severity {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-top: 5px;
            flex-shrink: 0;
        }}
        
        .performance-severity.critical {{ background: #e94560; }}
        .performance-severity.warning {{ background: #f0883e; }}
        .performance-severity.info {{ background: #58a6ff; }}
        
        .performance-issue-content {{
            flex: 1;
            min-width: 0;
        }}
        
        .performance-issue-title {{
            font-weight: 600;
            margin-bottom: 4px;
            color: var(--text-primary);
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        
        .performance-issue-rule {{
            font-size: 0.7rem;
            padding: 2px 6px;
            background: var(--bg-medium);
            border-radius: 4px;
            color: var(--text-muted);
        }}
        
        .performance-issue-message {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        
        .performance-issue-suggestion {{
            font-size: 0.75rem;
            color: var(--accent-green);
            font-style: italic;
        }}
        
        .performance-empty {{
            padding: 24px;
            text-align: center;
            color: var(--accent-green);
        }}
        
        .performance-empty-icon {{
            font-size: 2rem;
            margin-bottom: 8px;
        }}
        
        /* 纹理网格 - 原版 */
        .texture-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 16px;
        }}
        
        .texture-card {{
            background: var(--bg-dark);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: all 0.2s;
            cursor: pointer;
            position: relative;
        }}
        
        .texture-card:hover {{
            transform: translateY(-4px);
            border-color: var(--accent-red);
            box-shadow: 0 8px 24px rgba(233, 69, 96, 0.2);
        }}
        
        .texture-card.hidden {{
            display: none;
        }}
        
        .texture-thumb {{
            width: 100%;
            height: 140px;
            background: var(--bg-darkest);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .texture-thumb img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
        
        .texture-thumb .no-preview {{
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        .texture-info {{
            padding: 12px;
        }}
        
        .texture-name {{
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 6px;
            color: #58a6ff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .texture-dims {{
            font-size: 0.85rem;
            color: #3fb950;
            margin-bottom: 4px;
        }}
        
        .texture-format {{
            font-size: 0.8rem;
            color: #8b949e;
            font-family: monospace;
        }}
        
        /* ========== Lightbox V2: 工具栏模式 ========== */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.98);
            z-index: 10000;
            flex-direction: column;
        }}
        
        .lightbox.show {{
            display: flex;
        }}
        
        /* 顶部导航栏 */
        .lightbox-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
            flex-shrink: 0;
        }}
        
        .lightbox-title {{
            color: #58a6ff;
            font-size: 0.95rem;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 50%;
        }}
        
        .lightbox-meta {{
            color: #8b949e;
            font-size: 0.8rem;
            font-family: monospace;
        }}
        
        .lightbox-nav-group {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        
        .nav-btn {{
            width: 36px;
            height: 36px;
            border: 1px solid #30363d;
            border-radius: 6px;
            background: #21262d;
            color: #e6edf3;
            font-size: 1.1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        
        .nav-btn:hover {{
            background: #30363d;
            border-color: #58a6ff;
        }}
        
        .lightbox-close {{
            background: transparent;
            border: none;
            color: #8b949e;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 4px 8px;
        }}
        
        .lightbox-close:hover {{
            color: #e94560;
        }}
        
        /* 主内容区 - 图片最大化 */
        .lightbox-main {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
            background: #0d1117;
        }}
        
        .lightbox-img-container {{
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            max-width: 95%;
            max-height: calc(100vh - 180px);
            border-radius: 4px;
            background: repeating-conic-gradient(#404040 0% 25%, #606060 0% 50%) 50% / 16px 16px;
            cursor: grab;
            overflow: hidden;
        }}
        
        .lightbox-img-container.dragging {{
            cursor: grabbing;
        }}
        
        .lightbox-img {{
            display: block;
            transform-origin: center center;
            transition: transform 0.1s ease-out;
            max-width: 90vw;
            max-height: calc(100vh - 180px);
            object-fit: contain;
        }}
        
        .lightbox-img.no-transition {{
            transition: none;
        }}
        
        /* 悬浮颜色拾取器 */
        .color-picker-float {{
            position: absolute;
            bottom: 16px;
            left: 16px;
            padding: 8px 12px;
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid #30363d;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.75rem;
            color: #e6edf3;
            display: flex;
            align-items: center;
            gap: 10px;
            backdrop-filter: blur(8px);
            z-index: 100;
        }}
        
        .color-preview {{
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 1px solid #484f58;
            background: #000;
        }}
        
        .color-picker-float .coord {{
            color: #58a6ff;
        }}
        
        .color-picker-float .hex {{
            color: #3fb950;
            cursor: pointer;
        }}
        
        .color-picker-float .hex:hover {{
            text-decoration: underline;
        }}
        
        /* 底部工具栏 */
        .lightbox-toolbar {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            padding: 12px 20px;
            background: #161b22;
            border-top: 1px solid #30363d;
            flex-shrink: 0;
            flex-wrap: wrap;
        }}
        
        .toolbar-group {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 0 12px;
            border-right: 1px solid #30363d;
        }}
        
        .toolbar-group:last-child {{
            border-right: none;
        }}
        
        .toolbar-group.channels {{
            gap: 4px;
        }}
        
        /* 缩放控制 */
        .zoom-btn {{
            width: 32px;
            height: 32px;
            border: 1px solid #30363d;
            border-radius: 4px;
            background: #21262d;
            color: #e6edf3;
            font-size: 1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
        }}
        
        .zoom-btn:hover {{
            background: #30363d;
            border-color: #58a6ff;
        }}
        
        .zoom-level {{
            color: #8b949e;
            font-size: 0.8rem;
            min-width: 50px;
            text-align: center;
            font-family: monospace;
        }}
        
        /* 通道按钮 - 紧凑版 */
        .channel-btn {{
            padding: 6px 10px;
            border: 1px solid #30363d;
            border-radius: 4px;
            background: #21262d;
            color: #8b949e;
            font-weight: 600;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.15s;
        }}
        
        .channel-btn:hover {{
            border-color: #58a6ff;
            color: #58a6ff;
        }}
        
        .channel-btn.active {{
            background: #e94560;
            border-color: #e94560;
            color: white;
        }}
        
        .channel-btn.disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}
        
        .channel-btn[data-channel="r"].active {{ background: #ff6b6b; border-color: #ff6b6b; }}
        .channel-btn[data-channel="g"].active {{ background: #51cf66; border-color: #51cf66; }}
        .channel-btn[data-channel="b"].active {{ background: #339af0; border-color: #339af0; }}
        .channel-btn[data-channel="a"].active {{ background: #868e96; border-color: #868e96; }}
        
        /* 图标工具按钮 */
        .tool-btn {{
            width: 36px;
            height: 36px;
            border: 1px solid #30363d;
            border-radius: 6px;
            background: #21262d;
            color: #8b949e;
            font-size: 1.1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
            position: relative;
        }}
        
        .tool-btn:hover {{
            background: #30363d;
            border-color: #58a6ff;
            color: #58a6ff;
        }}
        
        .tool-btn.active {{
            background: #58a6ff;
            border-color: #58a6ff;
            color: white;
        }}
        
        .tool-btn.bookmarked {{
            color: #f9c513;
            border-color: #f9c513;
        }}
        
        .tool-btn[title]:hover::after {{
            content: attr(title);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            padding: 4px 8px;
            background: #1c2128;
            color: #e6edf3;
            font-size: 0.7rem;
            white-space: nowrap;
            border-radius: 4px;
            margin-bottom: 6px;
            z-index: 1000;
        }}
        
        /* 弹出面板 */
        .popup-panel {{
            display: none;
            position: absolute;
            bottom: 70px;
            left: 50%;
            transform: translateX(-50%);
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            min-width: 280px;
            max-width: 400px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            z-index: 200;
        }}
        
        .popup-panel.show {{
            display: block;
        }}
        
        .popup-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #30363d;
        }}
        
        .popup-title {{
            color: #e6edf3;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        
        .popup-close {{
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-size: 1rem;
        }}
        
        .popup-close:hover {{
            color: #e94560;
        }}
        
        /* EID Modal 弹窗 - 全局居中 */
        .eid-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }}
        
        .eid-modal.show {{
            display: flex;
        }}
        
        .eid-modal-content {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            min-width: 360px;
            max-width: 480px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.5);
            animation: eidModalIn 0.2s ease-out;
        }}
        
        @keyframes eidModalIn {{
            from {{
                transform: scale(0.9);
                opacity: 0;
            }}
            to {{
                transform: scale(1);
                opacity: 1;
            }}
        }}
        
        .eid-modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }}
        
        .eid-modal-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .eid-badge {{
            background: var(--accent-blue);
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.9rem;
            font-weight: 700;
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .eid-modal-close {{
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.5rem;
            line-height: 1;
            padding: 4px;
            border-radius: 4px;
            transition: background 0.15s;
        }}
        
        .eid-modal-close:hover {{
            background: rgba(255,255,255,0.1);
            color: var(--accent-red);
        }}
        
        .eid-modal-body {{
            padding: 20px;
        }}
        
        .eid-info-grid {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 12px 16px;
            font-size: 0.85rem;
        }}
        
        .eid-info-label {{
            color: var(--text-muted);
            font-weight: 500;
        }}
        
        .eid-info-value {{
            color: var(--text-primary);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .eid-info-value.api-call {{
            background: var(--bg-primary);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            border: 1px solid var(--border);
        }}
        
        .eid-slot-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 4px;
        }}
        
        .eid-slot-tag {{
            background: var(--bg-primary);
            border: 1px solid var(--border);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}
        
        .eid-modal-footer {{
            padding: 12px 20px;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }}
        
        .eid-modal-btn {{
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.15s;
            border: 1px solid transparent;
        }}
        
        .eid-modal-btn.primary {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .eid-modal-btn.primary:hover {{
            background: #3a8edc;
        }}
        
        .eid-modal-btn.secondary {{
            background: var(--bg-primary);
            color: var(--text-secondary);
            border-color: var(--border);
        }}
        
        .eid-modal-btn.secondary:hover {{
            background: var(--bg-hover);
        }}
        
        .eid-modal-btn.jump {{
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
            color: white;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        .eid-modal-btn.jump:hover {{
            background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
            box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.3);
        }}
        
        /* ==================== Shader Modal Styles ==================== */
        .shader-modal {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2100;
            opacity: 0;
            visibility: hidden;
            transition: all 0.2s ease;
            backdrop-filter: blur(2px);
        }}
        
        .shader-modal.show {{
            opacity: 1;
            visibility: visible;
        }}
        
        .shader-modal-content {{
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            width: 85vw;
            max-width: 1200px;
            height: 80vh;
            max-height: 900px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            transform: scale(0.95);
            transition: transform 0.2s ease;
        }}
        
        .shader-modal.show .shader-modal-content {{
            transform: scale(1);
        }}
        
        .shader-modal-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            background: var(--bg-secondary);
            border-radius: 12px 12px 0 0;
        }}
        
        .shader-modal-title {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .shader-type-badge {{
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        
        .shader-type-badge.vs {{
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
        }}
        
        .shader-type-badge.ps {{
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
            color: white;
        }}
        
        .shader-type-badge.cs {{
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
        }}
        
        .shader-type-badge.gs {{
            background: linear-gradient(135deg, #06b6d4, #0891b2);
            color: white;
        }}
        
        .shader-type-badge.hs, .shader-type-badge.ds {{
            background: linear-gradient(135deg, #ec4899, #db2777);
            color: white;
        }}
        
        .shader-modal-name {{
            font-size: 16px;
            font-weight: 500;
            color: var(--text-primary);
        }}
        
        .shader-modal-close {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 28px;
            cursor: pointer;
            padding: 0 8px;
            transition: color 0.15s;
            line-height: 1;
        }}
        
        .shader-modal-close:hover {{
            color: #ef4444;
        }}
        
        .shader-modal-info {{
            display: flex;
            gap: 20px;
            padding: 12px 20px;
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap;
        }}
        
        .shader-info-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
        }}
        
        .shader-info-label {{
            color: var(--text-muted);
        }}
        
        .shader-info-value {{
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
        }}
        
        .shader-modal-tabs {{
            display: flex;
            gap: 4px;
            padding: 8px 20px;
            border-bottom: 1px solid var(--border-color);
            background: var(--bg-secondary);
        }}
        
        .shader-tab-btn {{
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.15s;
        }}
        
        .shader-tab-btn:hover {{
            background: var(--bg-hover);
            color: var(--text-secondary);
        }}
        
        .shader-tab-btn.active {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .shader-modal-body {{
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        
        .shader-code-container {{
            flex: 1;
            overflow: auto;
            background: #1e1e1e;
            margin: 0;
        }}
        
        .shader-code {{
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
            font-size: 12px;
            line-height: 1.5;
            color: #d4d4d4;
            white-space: pre;
            padding: 16px 20px;
            margin: 0;
            min-height: 100%;
        }}
        
        /* ASM Syntax Highlighting */
        .shader-code .hljs-comment {{
            color: #6a9955;
            font-style: italic;
        }}
        
        .shader-code .hljs-keyword {{
            color: #569cd6;
            font-weight: 500;
        }}
        
        .shader-code .hljs-register {{
            color: #9cdcfe;
        }}
        
        .shader-code .hljs-number {{
            color: #b5cea8;
        }}
        
        .shader-code .hljs-string {{
            color: #ce9178;
        }}
        
        .shader-code .hljs-type {{
            color: #4ec9b0;
        }}
        
        .shader-code .hljs-label {{
            color: #dcdcaa;
        }}
        
        .shader-signature-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        
        .shader-signature-table th {{
            background: var(--bg-tertiary);
            color: var(--text-muted);
            padding: 8px 12px;
            text-align: left;
            font-weight: 500;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .shader-signature-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }}
        
        .shader-signature-table tr:hover td {{
            background: var(--bg-hover);
        }}
        
        .shader-tab-content {{
            display: none;
            height: 100%;
            overflow: auto;
        }}
        
        .shader-tab-content.active {{
            display: block;
        }}
        
        .shader-modal-footer {{
            display: flex;
            justify-content: flex-end;
            gap: 8px;
            padding: 12px 20px;
            border-top: 1px solid var(--border-color);
            background: var(--bg-secondary);
            border-radius: 0 0 12px 12px;
        }}
        
        .shader-modal-btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .shader-modal-btn.secondary {{
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }}
        
        .shader-modal-btn.secondary:hover {{
            background: var(--bg-hover);
        }}
        
        .shader-modal-btn.primary {{
            background: linear-gradient(135deg, var(--accent-blue), #3a7ebd);
            color: white;
        }}
        
        .shader-modal-btn.primary:hover {{
            box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.3);
        }}
        
        /* Shader 表格中的查看代码按钮 */
        .btn-view-shader {{
            padding: 3px 8px;
            border: none;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-size: 10px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        
        .btn-view-shader:hover {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .btn-view-shader:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        /* ==================== End Shader Modal Styles ==================== */
        
        /* Event 节点高亮动画 */
        @keyframes highlight-pulse {{
            0%, 100% {{ 
                background: var(--bg-hover);
            }}
            50% {{ 
                background: rgba(88, 166, 255, 0.3);
                box-shadow: 0 0 0 2px var(--accent-blue);
            }}
        }}
        
        .event-node.highlight-pulse {{
            animation: highlight-pulse 0.6s ease-in-out 3;
        }}
        
        /* EID Tag 可点击样式 */
        .eid-tag {{
            background: var(--accent-blue);
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            cursor: pointer;
            transition: all 0.15s;
            border: 1px solid transparent;
        }}
        
        .eid-tag:hover {{
            background: #3a8edc;
            box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.3);
        }}
        
        /* 滑块样式 */
        .slider-group {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }}
        
        .slider-group:last-child {{
            margin-bottom: 0;
        }}
        
        .slider-group label {{
            color: #8b949e;
            font-size: 0.8rem;
            min-width: 50px;
        }}
        
        .slider-group input[type="range"] {{
            flex: 1;
            height: 4px;
            -webkit-appearance: none;
            appearance: none;
            background: #30363d;
            border-radius: 2px;
            cursor: pointer;
        }}
        
        .slider-group input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
        }}
        
        .slider-group input[type="range"]::-moz-range-thumb {{
            width: 14px;
            height: 14px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }}
        
        .slider-value {{
            color: #58a6ff;
            font-size: 0.75rem;
            min-width: 35px;
            text-align: right;
            font-family: monospace;
        }}
        
        .reset-btn {{
            padding: 4px 10px;
            background: #30363d;
            border: 1px solid #484f58;
            border-radius: 4px;
            color: #8b949e;
            font-size: 0.75rem;
            cursor: pointer;
        }}
        
        .reset-btn:hover {{
            background: #484f58;
            color: #e6edf3;
        }}
        
        /* 直方图面板 */
        .histogram-canvas {{
            width: 100%;
            height: 80px;
            background: #0d1117;
            border-radius: 4px;
        }}
        
        .histogram-labels {{
            display: flex;
            justify-content: space-between;
            margin-top: 4px;
            font-size: 0.65rem;
            color: #6e7681;
            font-family: monospace;
        }}
        
        .histogram-stats {{
            display: flex;
            gap: 12px;
            margin-top: 8px;
            font-size: 0.7rem;
            color: #8b949e;
        }}
        
        .histogram-stats span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        .histogram-stats .dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        
        .histogram-stats .dot.r {{ background: #ff6b6b; }}
        .histogram-stats .dot.g {{ background: #51cf66; }}
        .histogram-stats .dot.b {{ background: #339af0; }}
        
        .histogram-toggle {{
            display: flex;
            gap: 4px;
            margin-bottom: 8px;
        }}
        
        .histogram-toggle button {{
            padding: 4px 8px;
            border: 1px solid #30363d;
            border-radius: 4px;
            background: #21262d;
            color: #8b949e;
            font-size: 0.7rem;
            cursor: pointer;
        }}
        
        .histogram-toggle button.active {{
            background: #30363d;
            color: #e6edf3;
            border-color: #58a6ff;
        }}
        
        /* 备注面板 */
        .notes-textarea {{
            width: 100%;
            min-height: 60px;
            padding: 8px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #e6edf3;
            font-size: 0.85rem;
            resize: vertical;
            font-family: inherit;
        }}
        
        .notes-textarea:focus {{
            outline: none;
            border-color: #58a6ff;
        }}
        
        /* 3D 法线预览 */
        .normal-3d-canvas {{
            width: 100%;
            height: 120px;
            background: #0d1117;
            border-radius: 4px;
            margin-bottom: 12px;
        }}
        
        .slider-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .slider-group label {{
            color: #8b949e;
            font-size: 0.85rem;
            min-width: 60px;
        }}
        
        .slider-group input[type="range"] {{
            width: 120px;
            height: 6px;
            -webkit-appearance: none;
            appearance: none;
            background: #30363d;
            border-radius: 3px;
            cursor: pointer;
        }}
        
        .slider-group input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
            transition: transform 0.1s;
        }}
        
        .slider-group input[type="range"]::-webkit-slider-thumb:hover {{
            transform: scale(1.2);
        }}
        
        .slider-group input[type="range"]::-moz-range-thumb {{
            width: 16px;
            height: 16px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }}
        
        .slider-value {{
            color: #58a6ff;
            font-size: 0.85rem;
            min-width: 40px;
            text-align: right;
            font-family: monospace;
        }}
        
        .reset-btn {{
            padding: 6px 12px;
            background: #30363d;
            border: 1px solid #484f58;
            border-radius: 4px;
            color: #8b949e;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .reset-btn:hover {{
            background: #484f58;
            color: #e6edf3;
        }}
        
        /* 颜色拾取器 */
        .color-picker-info {{
            display: flex;
            gap: 16px;
            margin-top: 12px;
            padding: 10px 16px;
            background: #161b22;
            border-radius: 6px;
            align-items: center;
            font-family: monospace;
            font-size: 0.85rem;
        }}
        
        .color-preview {{
            width: 32px;
            height: 32px;
            border-radius: 4px;
            border: 2px solid #30363d;
            background: #000;
        }}
        
        /* 对比模式 */
        .compare-badge {{
            position: absolute;
            top: 8px;
            right: 8px;
            background: #f0883e;
            color: white;
            font-size: 0.65rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            z-index: 10;
        }}
        
        .texture-card {{
            position: relative;
        }}
        
        /* 对比视图 Lightbox */
        .compare-lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.98);
            z-index: 20000;
            flex-direction: column;
        }}
        
        .compare-lightbox.show {{
            display: flex;
        }}
        
        .compare-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }}
        
        .compare-header h2 {{
            color: #f0883e;
            font-size: 1rem;
        }}
        
        .compare-close {{
            font-size: 1.5rem;
            color: #8b949e;
            cursor: pointer;
        }}
        
        .compare-close:hover {{
            color: #e94560;
        }}
        
        .compare-container {{
            display: flex;
            flex: 1;
            gap: 4px;
            overflow: hidden;
            background: #0d1117;
        }}
        
        .compare-pane {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 8px;
        }}
        
        .compare-pane-title {{
            color: #58a6ff;
            font-size: 0.8rem;
            margin-bottom: 6px;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .compare-pane-info {{
            color: #6e7681;
            font-size: 0.7rem;
            text-align: center;
            margin-bottom: 6px;
        }}
        
        .compare-img-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: repeating-conic-gradient(#404040 0% 25%, #606060 0% 50%) 50% / 16px 16px;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
            cursor: grab;
        }}
        
        .compare-img-wrapper.dragging {{
            cursor: grabbing;
        }}
        
        .compare-img-wrapper img {{
            max-width: none;
            max-height: none;
            transform-origin: center center;
            transition: transform 0.1s ease-out;
            pointer-events: none;
            user-select: none;
        }}
        
        .compare-img-wrapper img.no-transition {{
            transition: none;
        }}
        
        .compare-zoom-label {{
            position: absolute;
            bottom: 8px;
            right: 8px;
            background: rgba(0, 0, 0, 0.7);
            color: var(--text-secondary);
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
            pointer-events: none;
        }}
        
        .compare-toolbar {{
            display: flex;
            gap: 12px;
            padding: 12px;
            justify-content: center;
            background: #161b22;
            border-top: 1px solid #30363d;
        }}
        
        .compare-toolbar button {{
            padding: 6px 12px;
            border: 1px solid #30363d;
            border-radius: 4px;
            background: #21262d;
            color: #8b949e;
            font-size: 0.8rem;
            cursor: pointer;
        }}
        
        .compare-toolbar button:hover {{
            border-color: #58a6ff;
            color: #58a6ff;
        }}
        
        .compare-toolbar button.active {{
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }}
        
        .compare-toolbar .zoom-group {{
            display: flex;
            align-items: center;
            gap: 4px;
            background: var(--bg-dark);
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid var(--border);
        }}
        
        .compare-toolbar .zoom-group button {{
            padding: 4px 8px;
            font-size: 14px;
            border: none;
            background: transparent;
        }}
        
        .compare-toolbar .zoom-label {{
            color: var(--text-secondary);
            font-size: 12px;
            min-width: 50px;
            text-align: center;
        }}
        
        .compare-diff-badge {{
            position: absolute;
            top: 8px;
            left: 8px;
            background: var(--accent-green);
            color: white;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            pointer-events: none;
        }}
        
        .compare-diff-badge.different {{
            background: var(--accent-red);
        }}
        
        /* 差异对比表格 */
        .compare-diff-table {{
            background: var(--bg-dark);
            padding: 12px 20px;
            border-top: 1px solid var(--border-color);
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            justify-content: center;
            font-size: 12px;
        }}
        
        .compare-diff-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 10px;
            background: var(--bg-light);
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        
        .compare-diff-item.same {{
            border-color: var(--accent-green);
        }}
        
        .compare-diff-item.different {{
            border-color: var(--accent-red);
            background: rgba(255, 85, 85, 0.1);
        }}
        
        .compare-diff-label {{
            color: var(--text-muted);
            font-weight: 500;
        }}
        
        .compare-diff-values {{
            display: flex;
            gap: 4px;
            align-items: center;
        }}
        
        .compare-diff-value {{
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
        }}
        
        .compare-diff-value.left {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .compare-diff-value.right {{
            background: var(--accent-purple);
            color: white;
        }}
        
        .compare-diff-arrow {{
            color: var(--text-muted);
            font-size: 10px;
        }}
        
        .compare-diff-same {{
            color: var(--accent-green);
            font-weight: 500;
        }}
        
        /* ========== 移动端适配 ========== */
        @media (max-width: 768px) {{
            .lightbox-header {{
                padding: 10px 12px;
            }}
            
            .lightbox-title {{
                font-size: 0.8rem;
                max-width: 40%;
            }}
            
            .lightbox-meta {{
                font-size: 0.7rem;
            }}
            
            .lightbox-toolbar {{
                padding: 10px 12px;
                gap: 10px;
            }}
            
            .toolbar-group {{
                padding: 0 8px;
            }}
            
            .channel-btn {{
                padding: 5px 8px;
                font-size: 0.7rem;
            }}
            
            .tool-btn {{
                width: 32px;
                height: 32px;
                font-size: 0.95rem;
            }}
            
            .zoom-btn {{
                width: 28px;
                height: 28px;
            }}
            
            .popup-panel {{
                left: 10px;
                right: 10px;
                transform: none;
                min-width: auto;
                max-width: none;
                bottom: 60px;
            }}
            
            .compare-container {{
                flex-direction: column;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            .lightbox-header {{
                flex-wrap: wrap;
                gap: 8px;
            }}
            
            .lightbox-nav-group {{
                order: -1;
                width: 100%;
                justify-content: center;
            }}
            
            .lightbox-toolbar {{
                justify-content: flex-start;
                overflow-x: auto;
            }}
            
            .toolbar-group {{
                flex-shrink: 0;
            }}
            
            .popup-panel {{
                bottom: 55px;
                padding: 12px;
            }}
        }}
        
        /* 工具提示禁用 - 移动端 */
        @media (hover: none) {{
            .tool-btn[title]:hover::after {{
                display: none;
            }}
        }}
        
        /* ========== 旧样式兼容 ========== */
        .normal-preview-btn.active {{
            background: #a371f7;
            border-color: #a371f7;
            color: white;
        }}
        
        .normal-3d-container {{
            display: none;
            margin-top: 16px;
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #30363d;
        }}
        
        .normal-3d-container.show {{
            display: block;
        }}
        
        .normal-3d-canvas {{
            width: 100%;
            height: 200px;
            border-radius: 4px;
        }}
        
        .normal-3d-controls {{
            display: flex;
            gap: 16px;
            margin-top: 12px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        
        /* 导出按钮 */
        .export-btn {{
            padding: 8px 16px;
            border: 2px solid #30363d;
            border-radius: 6px;
            background: #21262d;
            color: #8b949e;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .export-btn:hover {{
            border-color: #3fb950;
            color: #3fb950;
        }}
        
        /* 书签/标注功能 */
        .bookmark-btn {{
            padding: 8px 16px;
            border: 2px solid #30363d;
            border-radius: 6px;
            background: #21262d;
            color: #8b949e;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .bookmark-btn:hover {{
            border-color: #f9c513;
            color: #f9c513;
        }}
        
        .bookmark-btn.bookmarked {{
            background: #f9c513;
            border-color: #f9c513;
            color: #1c1c1c;
        }}
        
        .bookmark-badge {{
            position: absolute;
            top: 8px;
            left: 8px;
            font-size: 1.2rem;
            z-index: 10;
        }}
        
        .notes-panel {{
            margin-top: 16px;
            padding: 12px;
            background: #161b22;
            border-radius: 8px;
            border: 1px solid #30363d;
        }}
        
        .notes-panel textarea {{
            width: 100%;
            min-height: 60px;
            padding: 10px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #e6edf3;
            font-size: 0.9rem;
            resize: vertical;
            font-family: inherit;
        }}
        
        .notes-panel textarea:focus {{
            outline: none;
            border-color: #58a6ff;
        }}
        
        .notes-panel label {{
            display: block;
            color: #8b949e;
            font-size: 0.8rem;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .action-buttons {{
            display: flex;
            gap: 8px;
            margin-top: 16px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        
        /* 表格视图 */
        .view-toggle {{
            display: flex;
            gap: 8px;
        }}
        
        .view-btn {{
            padding: 8px 16px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #8b949e;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .view-btn.active {{
            background: #e94560;
            color: white;
            border-color: #e94560;
        }}
        
        .table-view {{
            display: none;
            overflow-x: auto;
        }}
        
        .table-view.active {{
            display: block;
        }}
        
        .grid-view.hidden {{
            display: none;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #21262d;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        th {{
            background: #161b22;
            color: #e6edf3;
            padding: 14px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            cursor: pointer;
            user-select: none;
            border-bottom: 2px solid #e94560;
        }}
        
        th:hover {{
            background: #30363d;
        }}
        
        th.sorted-asc::after {{ content: ' ▲'; color: #e94560; }}
        th.sorted-desc::after {{ content: ' ▼'; color: #e94560; }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #30363d;
        }}
        
        tr:hover {{
            background: #30363d;
        }}
        
        .thumb-cell {{
            width: 60px;
        }}
        
        .thumb-cell img {{
            width: 50px;
            height: 50px;
            object-fit: contain;
            border-radius: 4px;
            background: #0d1117;
        }}
        
        /* ========== Event Browser 视图 ========== */
        .event-browser-container {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--bg-primary);
            z-index: 100;
            flex-direction: column;
        }}
        
        .event-browser-container.show {{
            display: flex;
        }}
        
        .event-browser-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 12px 20px;
            background: var(--bg-darker);
            border-bottom: 1px solid var(--border);
        }}
        
        .event-browser-header h2 {{
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .event-browser-header .api-badge {{
            background: var(--accent-blue);
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .event-browser-header .frame-stats {{
            margin-left: auto;
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        
        .event-browser-header .frame-stats span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        .event-browser-header .frame-stats .stat-value {{
            color: var(--text-primary);
            font-weight: 600;
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .event-browser-main {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        
        /* 左侧: Event 树形列表 */
        .event-tree-panel {{
            width: 380px;
            min-width: 280px;
            max-width: 600px;
            background: var(--bg-darker);
            border-right: none;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }}
        
        /* 拖拽分隔条 */
        .panel-resizer {{
            width: 6px;
            background: var(--bg-dark);
            cursor: col-resize;
            flex-shrink: 0;
            position: relative;
            transition: background 0.15s;
            border-left: 1px solid var(--border);
            border-right: 1px solid var(--border);
        }}
        
        .panel-resizer:hover,
        .panel-resizer.dragging {{
            background: var(--accent-primary);
        }}
        
        .panel-resizer::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 2px;
            height: 40px;
            background: var(--text-muted);
            border-radius: 1px;
            opacity: 0.5;
            transition: opacity 0.15s, height 0.15s;
        }}
        
        .panel-resizer:hover::before,
        .panel-resizer.dragging::before {{
            opacity: 1;
            height: 60px;
            background: var(--bg-primary);
        }}
        
        .event-tree-toolbar {{
            padding: 8px;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 6px;
            align-items: center;
        }}
        
        .event-tree-toolbar input {{
            flex: 1;
            padding: 6px 10px;
            background: var(--bg-darkest);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 11px;
        }}
        
        .event-tree-toolbar input:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        .event-tree-toolbar button {{
            padding: 4px 8px;
            background: var(--bg-medium);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-secondary);
            font-size: 10px;
            cursor: pointer;
            white-space: nowrap;
        }}
        
        .event-tree-toolbar button:hover {{
            background: var(--bg-hover);
        }}
        
        .event-tree-toolbar select {{
            padding: 4px 8px;
            background: var(--bg-medium);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text-secondary);
            font-size: 10px;
            cursor: pointer;
            min-width: 90px;
        }}
        
        .event-tree-toolbar select:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        .event-tree-toolbar select option {{
            background: var(--bg-darkest);
            color: var(--text-primary);
        }}
        
        .event-tree-list {{
            flex: 1;
            overflow-y: auto;
            font-size: 12px;
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .event-tree-list::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .event-tree-list::-webkit-scrollbar-track {{
            background: var(--bg-darker);
        }}
        
        .event-tree-list::-webkit-scrollbar-thumb {{
            background: var(--bg-medium);
            border-radius: 4px;
        }}
        
        /* Event 树节点 */
        .event-node {{
            display: flex;
            align-items: center;
            padding: 4px 8px;
            padding-left: var(--indent, 8px);
            border-bottom: 1px solid var(--bg-dark);
            cursor: pointer;
            transition: background 0.1s;
        }}
        
        .event-node:hover {{
            background: var(--bg-dark);
        }}
        
        .event-node.selected {{
            background: rgba(88, 166, 255, 0.15);
            border-left: 2px solid var(--accent-blue);
        }}
        
        .event-node.pass {{
            background: var(--bg-dark);
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .event-node.dimmed {{
            opacity: 0.4;
        }}
        
        .event-node .expand-btn {{
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            margin-right: 4px;
            flex-shrink: 0;
            font-size: 10px;
        }}
        
        .event-node .expand-btn:empty {{
            visibility: hidden;
        }}
        
        .event-node .event-icon {{
            width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 6px;
            font-size: 12px;
            flex-shrink: 0;
        }}
        
        .event-node .event-eid {{
            color: var(--accent-blue);
            margin-right: 8px;
            min-width: 48px;
            font-weight: 600;
        }}
        
        .event-node .event-name {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
        }}
        
        .event-node .event-type-badge {{
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            margin-left: 8px;
            font-weight: 500;
        }}
        
        .event-node .event-type-badge.draw {{
            background: rgba(88, 166, 255, 0.2);
            color: var(--accent-blue);
        }}
        
        .event-node .event-type-badge.dispatch {{
            background: rgba(233, 69, 96, 0.2);
            color: var(--accent-red);
        }}
        
        .event-node .event-type-badge.pass {{
            background: rgba(163, 113, 247, 0.2);
            color: #a371f7;
        }}
        
        .event-node .event-type-badge.clear {{
            background: rgba(255, 159, 10, 0.2);
            color: var(--accent-orange);
        }}
        
        /* 右侧: Event 详情面板 */
        .event-detail-panel {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        
        .event-detail-tabs {{
            display: flex;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border);
        }}
        
        .event-detail-tabs .tab {{
            padding: 10px 16px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.15s;
        }}
        
        .event-detail-tabs .tab:hover {{
            color: var(--text-secondary);
            background: var(--bg-hover);
        }}
        
        .event-detail-tabs .tab.active {{
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
        }}
        
        .event-detail-content {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}
        
        .event-detail-empty {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-muted);
            font-size: 14px;
        }}
        
        .event-detail-empty .icon {{
            font-size: 48px;
            margin-bottom: 12px;
            opacity: 0.5;
        }}
        
        /* ========== Pass 依赖图样式 ========== */
        .pass-graph-container {{
            flex: 1;
            overflow: auto;
            padding: 16px;
            display: none;
        }}
        
        .pass-graph-container.show {{
            display: block;
        }}
        
        .pass-graph-svg {{
            background: var(--bg-darkest);
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        
        .pass-graph-svg .pass-node {{
            cursor: pointer;
            transition: filter 0.15s;
        }}
        
        .pass-graph-svg .pass-node:hover {{
            filter: brightness(1.2);
        }}
        
        .pass-graph-svg .pass-node-rect {{
            rx: 8;
            ry: 8;
        }}
        
        .pass-graph-svg .pass-node-text {{
            font-size: 11px;
            font-weight: 600;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            fill: white;
            text-anchor: middle;
            pointer-events: none;
        }}
        
        .pass-graph-svg .pass-node-stats {{
            font-size: 9px;
            font-family: 'SF Mono', Consolas, monospace;
            fill: rgba(255,255,255,0.7);
            text-anchor: middle;
            pointer-events: none;
        }}
        
        .pass-graph-svg .pass-edge {{
            fill: none;
            stroke: var(--text-muted);
            stroke-width: 2;
            opacity: 0.6;
        }}
        
        .pass-graph-svg .pass-edge-arrow {{
            fill: var(--text-muted);
            opacity: 0.6;
        }}
        
        .pass-graph-svg .resource-label {{
            font-size: 8px;
            font-family: 'SF Mono', Consolas, monospace;
            fill: var(--text-muted);
            text-anchor: middle;
        }}
        
        /* 边交互样式 */
        .pass-graph-svg .pass-edge-group {{
            cursor: pointer;
        }}
        
        .pass-graph-svg .pass-edge-hitbox {{
            fill: none;
            stroke: transparent;
            stroke-width: 12;
            pointer-events: stroke;
        }}
        
        .pass-graph-svg .pass-edge-group:hover .pass-edge {{
            stroke: var(--accent-blue);
            stroke-width: 3;
            opacity: 1;
        }}
        
        .pass-graph-svg .pass-edge-group:hover .pass-edge-hitbox + .pass-edge {{
            filter: drop-shadow(0 0 4px rgba(88, 166, 255, 0.5));
        }}
        
        /* 边 Tooltip - 资源流向提示 */
        .edge-tooltip {{
            position: fixed;
            z-index: 10002;
            background: linear-gradient(135deg, var(--bg-darkest) 0%, #1a2332 100%);
            border: 2px solid var(--accent-blue);
            border-radius: 10px;
            padding: 14px 16px;
            font-size: 13px;
            max-width: 340px;
            min-width: 260px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(88, 166, 255, 0.2);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.15s, transform 0.15s;
            transform: scale(0.95);
        }}
        
        .edge-tooltip.visible {{
            opacity: 1;
            transform: scale(1);
        }}
        
        /* 顶部标题栏：说明这是资源传递 */
        .edge-tooltip-title {{
            font-size: 11px;
            font-weight: 600;
            color: var(--accent-blue);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .edge-tooltip-title::before {{
            content: '🔗';
        }}
        
        /* 流向显示：最醒目的部分 */
        .edge-tooltip-flow {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 10px;
            margin-bottom: 12px;
            background: rgba(88, 166, 255, 0.1);
            border-radius: 6px;
            border: 1px solid rgba(88, 166, 255, 0.2);
        }}
        
        .edge-tooltip-flow .pass-name {{
            font-weight: 600;
            color: var(--text-primary);
            font-size: 12px;
            max-width: 100px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .edge-tooltip-flow .arrow {{
            font-size: 18px;
            color: var(--accent-green);
            font-weight: bold;
            animation: arrowPulse 1s infinite;
        }}
        
        @keyframes arrowPulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        /* 资源卡片 */
        .edge-tooltip-resource {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px;
            background: var(--bg-dark);
            border-radius: 6px;
        }}
        
        .edge-tooltip-thumb {{
            width: 56px;
            height: 56px;
            background: var(--bg-darker);
            border-radius: 6px;
            overflow: hidden;
            flex-shrink: 0;
            border: 2px solid var(--accent-purple);
        }}
        
        .edge-tooltip-thumb img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        
        .edge-tooltip-info {{
            flex: 1;
        }}
        
        .edge-tooltip-label {{
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 2px;
        }}
        
        .edge-tooltip-name {{
            font-weight: 700;
            color: var(--text-primary);
            font-size: 14px;
            margin-bottom: 4px;
        }}
        
        .edge-tooltip-format {{
            color: var(--accent-purple);
            font-family: 'SF Mono', Consolas, monospace;
            font-size: 12px;
        }}
        
        .edge-tooltip-size {{
            color: var(--text-secondary);
            font-size: 11px;
            margin-top: 2px;
        }}
        
        .pass-graph-legend {{
            display: flex;
            gap: 16px;
            padding: 12px 16px;
            background: var(--bg-darker);
            border-radius: 8px;
            margin-bottom: 12px;
            font-size: 11px;
            flex-wrap: wrap;
        }}
        
        .pass-graph-legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-secondary);
        }}
        
        .pass-graph-legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        
        .view-mode-toggle {{
            display: flex;
            gap: 2px;
            background: var(--bg-darkest);
            border-radius: 4px;
            padding: 2px;
        }}
        
        .view-mode-toggle button {{
            padding: 4px 10px;
            font-size: 10px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.15s;
        }}
        
        .view-mode-toggle button.active {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .view-mode-toggle button:hover:not(.active) {{
            background: var(--bg-hover);
        }}
        
        /* Event 详情卡片 */
        .event-detail-card {{
            background: var(--bg-darker);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 16px;
        }}
        
        .event-detail-card-header {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .event-detail-card-body {{
            padding: 16px;
        }}
        
        /* ========== Input/Output 缩略图网格 ========== */
        .io-thumbnail-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 12px;
        }}
        
        .io-resource-card {{
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            position: relative;
        }}
        
        .io-resource-card:hover {{
            border-color: var(--accent-blue);
            background: var(--bg-medium);
            transform: translateY(-2px);
        }}
        
        .io-resource-card.output-card {{
            border-left: 3px solid var(--accent-green);
        }}
        
        .io-resource-card.input-card {{
            border-left: 3px solid var(--accent-orange);
        }}
        
        .io-thumb {{
            width: 100%;
            aspect-ratio: 1;
            background: var(--bg-darkest);
            border-radius: 6px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        
        .io-thumb img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            image-rendering: pixelated;
        }}
        
        .io-thumb-placeholder {{
            font-size: 32px;
            opacity: 0.5;
        }}
        
        .io-info {{
            text-align: center;
        }}
        
        .io-name {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }}
        
        .io-format {{
            font-size: 10px;
            color: var(--accent-purple);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .io-size {{
            font-size: 10px;
            color: var(--text-muted);
        }}
        
        .io-slot {{
            font-size: 10px;
            color: var(--accent-blue);
            font-weight: 600;
        }}
        
        .io-jump-link {{
            position: absolute;
            bottom: 6px;
            right: 8px;
            font-size: 10px;
            color: var(--accent-blue);
            opacity: 0;
            transition: opacity 0.15s;
        }}
        
        .io-resource-card:hover .io-jump-link {{
            opacity: 1;
        }}
        
        /* Pass 推测标识 */
        .pass-node-inferred {{
            font-size: 12px;
            text-anchor: end;
        }}
        
        /* ========== Pass Tooltip 样式 ========== */
        .pass-tooltip {{
            display: none;
            position: fixed;
            z-index: 10000;
            background: var(--bg-darker);
            border: 1px solid var(--border-light);
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
            min-width: 240px;
            max-width: 360px;
            font-size: 12px;
            pointer-events: none;
        }}
        
        .pass-tooltip-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-dark);
            border-radius: 8px 8px 0 0;
        }}
        
        .pass-tooltip-name {{
            font-weight: 600;
            color: var(--text-primary);
            flex: 1;
        }}
        
        .pass-tooltip-badge {{
            font-size: 10px;
            background: var(--accent-purple);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        
        .pass-tooltip-stats {{
            display: flex;
            gap: 12px;
            padding: 8px 12px;
            color: var(--text-secondary);
            font-size: 11px;
            border-bottom: 1px solid var(--border);
        }}
        
        .pass-tooltip-stats strong {{
            color: var(--text-primary);
        }}
        
        .pass-tooltip-section {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
        }}
        
        .pass-tooltip-section:last-child {{
            border-bottom: none;
        }}
        
        .pass-tooltip-section-title {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        
        .pass-tooltip-thumbs {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .pass-tooltip-thumb-item {{
            width: 60px;
            text-align: center;
        }}
        
        .pass-tooltip-thumb-item img {{
            width: 48px;
            height: 48px;
            border-radius: 4px;
            border: 1px solid var(--border);
            margin-bottom: 4px;
        }}
        
        .pass-tooltip-thumb-name {{
            font-size: 9px;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .pass-tooltip-thumb-format {{
            font-size: 9px;
            color: var(--accent-purple);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .pass-tooltip-inputs {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }}
        
        .pass-tooltip-input-tag {{
            font-size: 10px;
            background: var(--bg-medium);
            color: var(--text-secondary);
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid var(--border);
        }}
        
        /* 参数表格 */
        .params-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .params-table tr {{
            border-bottom: 1px solid var(--bg-dark);
        }}
        
        .params-table tr:last-child {{
            border-bottom: none;
        }}
        
        .params-table td {{
            padding: 8px 0;
        }}
        
        .params-table td:first-child {{
            color: var(--text-muted);
            width: 140px;
        }}
        
        .params-table td:last-child {{
            color: var(--text-primary);
        }}
        
        .params-table th {{
            padding: 6px 8px;
            text-align: left;
            font-weight: 500;
            font-size: 11px;
            color: var(--text-muted);
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border);
        }}
        
        .btn-view-shader {{
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 500;
            color: var(--text-primary);
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        
        .btn-view-shader:hover {{
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
        }}
        
        /* ========== API 调用样式 ========== */
        .api-call-card {{
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        }}
        
        .api-signature {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 0;
        }}
        
        .api-return-type {{
            color: #79c0ff;
            font-size: 12px;
        }}
        
        .api-func-name {{
            color: #d2a8ff;
            font-weight: 600;
            font-size: 13px;
        }}
        
        .api-paren {{
            color: var(--text-muted);
            font-size: 13px;
        }}
        
        .api-params-list {{
            padding-left: 24px;
            border-left: 2px solid var(--border-color);
            margin: 4px 0 4px 12px;
        }}
        
        .api-param-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 3px 0;
            font-size: 12px;
        }}
        
        .api-param-row.compact {{
            padding: 2px 0;
            font-size: 11px;
        }}
        
        .api-param-type {{
            color: #79c0ff;
            min-width: 80px;
        }}
        
        .api-param-name {{
            color: #ffa657;
        }}
        
        .api-param-sep {{
            color: var(--text-muted);
        }}
        
        .api-param-value {{
            color: var(--text-primary);
        }}
        
        .api-param-comma {{
            color: var(--text-muted);
        }}
        
        /* 值类型着色 */
        .api-param-value .null-val {{
            color: #ff7b72;
            font-style: italic;
        }}
        
        .api-param-value .hex-val {{
            color: #a5d6ff;
        }}
        
        .api-param-value .num-val {{
            color: #7ee787;
        }}
        
        .api-param-value .bool-val {{
            color: #ff7b72;
            font-weight: 600;
        }}
        
        .api-param-value .enum-val {{
            color: #d2a8ff;
        }}
        
        .api-param-value .str-val {{
            color: #a5d6ff;
        }}
        
        .api-param-value .arr-val {{
            color: #ffa657;
        }}
        
        .api-param-value .obj-val {{
            color: var(--text-muted);
            font-size: 10px;
        }}
        
        /* 关联调用列表 */
        .related-calls-list {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .related-call-item {{
            background: var(--bg-dark);
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .related-call-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        
        .related-call-header:hover {{
            background: var(--bg-hover);
        }}
        
        .related-call-header .expand-icon {{
            color: var(--text-muted);
            font-size: 10px;
            transition: transform 0.15s;
        }}
        
        .related-call-header.expanded .expand-icon {{
            transform: rotate(90deg);
        }}
        
        .related-call-header .call-name {{
            color: #d2a8ff;
            font-weight: 500;
            font-size: 12px;
        }}
        
        .related-call-header .call-summary {{
            color: var(--text-muted);
            font-size: 11px;
            margin-left: auto;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        /* 简化格式（字符串调用）- 完整显示，允许换行 */
        .related-call-header.simple {{
            cursor: default;
            flex-wrap: wrap;
        }}
        
        .related-call-header.simple:hover {{
            background: var(--bg-hover);
        }}
        
        .related-call-header.simple .call-summary {{
            color: #a5d6ff;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            margin-left: 8px;
            max-width: 100%;
            white-space: pre-wrap;
            word-break: break-all;
            overflow: visible;
            text-overflow: unset;
            line-height: 1.5;
        }}
        
        .related-call-body {{
            padding: 8px 12px 12px 32px;
            background: var(--bg-darkest);
            border-top: 1px solid var(--border-color);
        }}
        
        .related-call-body .no-params {{
            color: var(--text-muted);
            font-size: 11px;
            font-style: italic;
        }}
        
        /* 状态分组颜色标识 */
        .related-call-item.state-IA {{
            border-left: 3px solid #58a6ff;
        }}
        
        .related-call-item.state-VS,
        .related-call-item.state-PS,
        .related-call-item.state-CS {{
            border-left: 3px solid #d2a8ff;
        }}
        
        .related-call-item.state-RS {{
            border-left: 3px solid #7ee787;
        }}
        
        .related-call-item.state-OM {{
            border-left: 3px solid #ffa657;
        }}
        
        .api-note {{
            color: var(--text-muted);
            font-size: 11px;
            line-height: 1.6;
            padding: 8px;
            background: var(--bg-dark);
            border-radius: 6px;
            border-left: 3px solid var(--accent-blue);
        }}
        
        .count-badge {{
            display: inline-block;
            background: var(--accent-primary);
            color: var(--bg-primary);
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 6px;
        }}
        
        /* 资源绑定 */
        .binding-section {{
            margin-bottom: 16px;
        }}
        
        .binding-section:last-child {{
            margin-bottom: 0;
        }}
        
        .binding-stage {{
            font-size: 11px;
            font-weight: 600;
            color: var(--accent-blue);
            padding: 6px 12px;
            background: var(--bg-dark);
            border-radius: 4px 4px 0 0;
            display: inline-block;
        }}
        
        .binding-list {{
            background: var(--bg-dark);
            border-radius: 0 4px 4px 4px;
            padding: 8px;
        }}
        
        .binding-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.1s;
        }}
        
        .binding-item:hover {{
            background: var(--bg-hover);
        }}
        
        .binding-item .slot {{
            color: var(--text-muted);
            font-size: 10px;
            min-width: 32px;
        }}
        
        .binding-item .thumb {{
            width: 32px;
            height: 32px;
            background: var(--bg-darkest);
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .binding-item .thumb img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        
        .binding-item .info {{
            flex: 1;
            overflow: hidden;
        }}
        
        .binding-item .name {{
            color: var(--text-primary);
            font-size: 11px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .binding-item .meta {{
            color: var(--text-muted);
            font-size: 10px;
        }}
        
        .binding-item .jump-link {{
            color: var(--accent-blue);
            font-size: 11px;
            opacity: 0;
            transition: opacity 0.15s;
        }}
        
        .binding-item:hover .jump-link {{
            opacity: 1;
        }}
        
        /* Constant Buffer 样式 */
        .binding-item.cb-item {{
            flex-direction: column;
            align-items: stretch;
            cursor: default;
        }}
        
        .binding-item.cb-item > .slot,
        .binding-item.cb-item > .cb-icon,
        .binding-item.cb-item > .info {{
            display: flex;
            align-items: center;
        }}
        
        .binding-item.cb-item > .slot {{
            position: absolute;
        }}
        
        .binding-item.cb-item {{
            position: relative;
            padding-left: 42px;
        }}
        
        .cb-icon {{
            font-size: 16px;
            margin-right: 6px;
        }}
        
        .binding-item .meta span {{
            margin-right: 10px;
        }}
        
        .cb-size {{
            color: var(--accent-green);
        }}
        
        .cb-offset {{
            color: var(--accent-yellow);
        }}
        
        .cb-flags {{
            background: var(--bg-hover);
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 9px;
        }}
        
        /* Vertex Buffer 样式 */
        .binding-item.vb-item {{
            position: relative;
            padding-left: 42px;
        }}
        
        .binding-item.vb-item > .slot {{
            position: absolute;
            left: 8px;
        }}
        
        .vb-icon, .ib-icon {{
            font-size: 16px;
            margin-right: 6px;
        }}
        
        .vb-stride {{
            color: var(--accent-purple);
        }}
        
        .vb-offset, .ib-offset {{
            color: var(--accent-yellow);
        }}
        
        .ib-format {{
            color: var(--accent-blue);
            background: var(--bg-hover);
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 9px;
        }}
        
        /* Index Buffer 样式 */
        .binding-item.ib-item {{
            position: relative;
            padding-left: 42px;
        }}
        
        .binding-item.ib-item > .slot {{
            position: absolute;
            left: 8px;
        }}
        
        .cb-members {{
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px dashed var(--border);
        }}
        
        .cb-members-header {{
            display: flex;
            align-items: center;
            gap: 4px;
            color: var(--text-muted);
            font-size: 10px;
            cursor: pointer;
            padding: 4px 0;
            user-select: none;
        }}
        
        .cb-members-header:hover {{
            color: var(--accent-blue);
        }}
        
        .cb-members-header .toggle-icon {{
            transition: transform 0.15s;
            font-size: 8px;
        }}
        
        .cb-members-header.expanded .toggle-icon {{
            transform: rotate(90deg);
        }}
        
        .cb-members-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
            margin-top: 4px;
        }}
        
        .cb-members-table th {{
            text-align: left;
            padding: 4px 6px;
            background: var(--bg-darkest);
            color: var(--text-muted);
            font-weight: normal;
            border-bottom: 1px solid var(--border);
        }}
        
        .cb-members-table td {{
            padding: 3px 6px;
            border-bottom: 1px solid var(--border);
        }}
        
        .cb-members-table tr:hover td {{
            background: var(--bg-hover);
        }}
        
        .member-name {{
            color: var(--accent-cyan);
        }}
        
        .member-type {{
            color: var(--accent-purple);
        }}
        
        .member-offset,
        .member-size {{
            color: var(--text-muted);
            font-family: 'Consolas', monospace;
        }}
        
        .member-value {{
            font-family: 'Consolas', monospace;
            font-size: 9px;
            max-width: 200px;
        }}
        
        .member-value code.scalar-value {{
            color: var(--accent-green);
            background: var(--bg-darkest);
            padding: 1px 4px;
            border-radius: 2px;
        }}
        
        .member-value .matrix-value {{
            display: flex;
            flex-direction: column;
            gap: 1px;
        }}
        
        .member-value .matrix-row {{
            color: var(--accent-yellow);
            background: var(--bg-darkest);
            padding: 1px 4px;
            border-radius: 2px;
            font-size: 8px;
            white-space: nowrap;
        }}
        
        .cb-resource-id {{
            background: var(--bg-darkest);
            color: var(--accent-cyan);
            padding: 1px 6px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
            font-size: 10px;
        }}
        
        /* 渲染状态 */
        .state-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }}
        
        .state-item {{
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 10px 12px;
        }}
        
        .state-item .label {{
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
        }}
        
        .state-item .value {{
            font-size: 12px;
            color: var(--text-primary);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        /* ========== Mesh Info 网格信息样式 ========== */
        .mesh-stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }}
        
        .mesh-stat-item {{
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 12px;
            text-align: center;
        }}
        
        .mesh-stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .mesh-stat-label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 4px;
        }}
        
        .mesh-layout-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
            background: var(--bg-dark);
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .mesh-layout-table th {{
            background: var(--bg-darkest);
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 10px;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        .mesh-layout-table td {{
            padding: 6px 10px;
            border-bottom: 1px solid var(--border);
        }}
        
        .mesh-layout-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .mesh-layout-table tr:hover td {{
            background: var(--bg-hover);
        }}
        
        .semantic-tag {{
            display: inline-block;
            background: var(--accent-blue);
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 500;
        }}
        
        .semantic-tag.position {{ background: var(--accent-green); }}
        .semantic-tag.normal {{ background: var(--accent-cyan); }}
        .semantic-tag.texcoord {{ background: var(--accent-purple); }}
        .semantic-tag.tangent {{ background: var(--accent-orange); }}
        .semantic-tag.color {{ background: var(--accent-pink); }}
        .semantic-tag.blendweight {{ background: var(--accent-yellow); color: #333; }}
        .semantic-tag.blendindices {{ background: #8b8b00; }}
        
        .format-code {{
            font-family: 'Consolas', monospace;
            color: var(--accent-cyan);
            font-size: 10px;
        }}
        
        .mesh-preview-section {{
            display: flex;
            gap: 16px;
            margin-top: 16px;
        }}
        
        .mesh-preview-box {{
            flex: 1;
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 12px;
        }}
        
        .mesh-preview-title {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 10px;
            text-transform: uppercase;
        }}
        
        .bbox-svg-container {{
            width: 100%;
            aspect-ratio: 4 / 3;
            background: var(--bg-darkest);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .bbox-svg-container svg {{
            max-width: 100%;
            max-height: 100%;
        }}
        
        .uv-svg-container {{
            width: 100%;
            aspect-ratio: 1 / 1;
            background: var(--bg-darkest);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .uv-svg-container svg {{
            max-width: 100%;
            max-height: 100%;
        }}
        
        .normal-preview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(28px, 1fr));
            gap: 4px;
        }}
        
        .normal-swatch {{
            width: 28px;
            height: 28px;
            border-radius: 4px;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: transform 0.1s;
        }}
        
        .normal-swatch:hover {{
            transform: scale(1.2);
            z-index: 1;
        }}
        
        .normal-swatch-tooltip {{
            position: absolute;
            background: var(--bg-darkest);
            color: var(--text-primary);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-family: 'Consolas', monospace;
            white-space: nowrap;
            pointer-events: none;
            z-index: 100;
        }}
        
        .mesh-bounds-info {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-top: 10px;
        }}
        
        .bounds-item {{
            background: var(--bg-darkest);
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 10px;
        }}
        
        .bounds-item .label {{
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 2px;
        }}
        
        .bounds-item .value {{
            color: var(--accent-cyan);
            font-family: 'Consolas', monospace;
        }}
        
        /* Input Layout 表格 */
        .input-layout-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
            background: var(--bg-dark);
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .input-layout-table th {{
            background: var(--bg-darkest);
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 10px;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        .input-layout-table td {{
            padding: 6px 10px;
            border-bottom: 1px solid var(--border);
        }}
        
        .input-layout-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .input-layout-table tr:hover td {{
            background: var(--bg-hover);
        }}
        
        /* Stride 信息 */
        .stride-info {{
            margin-top: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .stride-badge {{
            background: var(--bg-darkest);
            color: var(--accent-cyan);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-family: 'Consolas', monospace;
        }}
        
        /* 法线采样预览 */
        .normal-sample {{
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: transform 0.15s;
        }}
        
        .normal-sample:hover {{
            transform: scale(1.3);
            z-index: 10;
        }}
        
        .normal-legend {{
            margin-top: 10px;
            font-size: 10px;
            color: var(--text-muted);
        }}
        
        /* UV 预览 */
        .uv-preview-container {{
            width: 100%;
            max-width: 300px;
            aspect-ratio: 1 / 1;
            background: var(--bg-darkest);
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .uv-preview-container svg {{
            width: 100%;
            height: 100%;
        }}
        
        .uv-legend {{
            margin-top: 10px;
            font-size: 10px;
            color: var(--text-muted);
        }}
        
        /* 法线分布分析样式 */
        .normal-analysis-container {{
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }}
        
        .normal-hemisphere {{
            flex-shrink: 0;
        }}
        
        .normal-stats {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .normal-stat-item {{
            background: var(--bg-darkest);
            padding: 8px 12px;
            border-radius: 4px;
        }}
        
        .normal-stat-item .stat-label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        
        .normal-stat-item .stat-value {{
            font-family: 'Consolas', monospace;
            font-size: 12px;
        }}
        
        .normal-distribution {{
            background: var(--bg-darkest);
            padding: 8px 12px;
            border-radius: 4px;
        }}
        
        .dist-bar {{
            display: flex;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            background: var(--bg-dark);
        }}
        
        .dist-segment {{
            transition: width 0.3s;
        }}
        
        .dist-segment.up {{ background: #7ee787; }}
        .dist-segment.side {{ background: #58a6ff; }}
        .dist-segment.down {{ background: #f85149; }}
        
        .dist-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        
        .normal-hint {{
            font-size: 11px;
            padding: 6px 10px;
            border-radius: 4px;
            background: var(--bg-darkest);
        }}
        
        /* UV 分析样式 */
        .uv-analysis-container {{
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }}
        
        .uv-stats {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        
        .uv-stat-row {{
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            padding: 4px 0;
        }}
        
        .uv-stat-row .label {{
            color: var(--text-muted);
        }}
        
        .uv-stat-row .value {{
            color: var(--accent-cyan);
            font-family: 'Consolas', monospace;
        }}
        
        .uv-hint {{
            font-size: 11px;
            padding: 6px 10px;
            border-radius: 4px;
            margin-top: 8px;
        }}
        
        .uv-hint.ok {{
            background: rgba(126, 231, 135, 0.1);
            color: #7ee787;
        }}
        
        .uv-hint.warning {{
            background: rgba(248, 81, 73, 0.1);
            color: #f85149;
        }}
        
        /* 包围盒容器布局 */
        .bbox-container {{
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }}
        
        .bbox-visual {{
            flex-shrink: 0;
            width: 140px;
            height: 120px;
            background: var(--bg-darkest);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .bbox-data {{
            flex: 1;
        }}
        
        /* 统计值显示（确保 class 匹配） */
        .mesh-stat-item .stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            font-family: 'SF Mono', Consolas, monospace;
        }}
        
        .mesh-stat-item .stat-label {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 4px;
        }}
        
        /* ========== RT Timeline Component (Direction C) ========== */
        {generate_rt_timeline_css() if HAS_RT_TIMELINE and rt_tracking_data else ''}
        
        /* ========== Hotspot Component (Direction F) ========== */
        {generate_hotspot_css() if HAS_HOTSPOT and hotspot_data else ''}
    </style>
</head>
<body>
    <!-- ========== Photoshop 风格主布局 ========== -->
    <div class="app-container" id="appContainer">
        <!-- 顶部菜单栏 -->
        <div class="app-menubar">
            <div class="app-title">
                <div class="logo"></div>
                <span>RDC 纹理分析器</span>
            </div>
            <div class="app-menu">
                <span class="menu-item view-toggle" id="viewToggleBtn" onclick="toggleViewMode()">📐 网格视图</span>
                <span class="menu-item view-toggle" id="eventBrowserBtn" onclick="showEventBrowser()" style="background: rgba(163, 113, 247, 0.15); color: #a371f7;">🎮 Event Browser</span>
                <span class="menu-item dropdown-trigger" id="exportMenuTrigger">
                    导出 ▾
                    <div class="dropdown-menu" id="exportDropdown">
                        <div class="dropdown-item" onclick="exportToCSV()">📊 纹理列表 CSV</div>
                        <div class="dropdown-item" onclick="exportToJSON()">📋 纹理列表 JSON</div>
                        <div class="dropdown-item" onclick="downloadCurrentTexture()">🖼️ 下载当前纹理</div>
                        <div class="dropdown-divider"></div>
                        <div class="dropdown-item" onclick="exportReport()">📄 报告摘要 (TXT)</div>
                        <div class="dropdown-item" onclick="exportOptimizationReport()">🎯 优化建议 (MD)</div>
                        <div class="dropdown-item" onclick="exportOptimizationJSON()">🔧 优化建议 (JSON)</div>
                        <div class="dropdown-item" onclick="exportOptimizationCSV()">📋 问题清单 (CSV)</div>
                        <div class="dropdown-divider"></div>
                        <div class="dropdown-item" onclick="exportFullAnalysisJSON()">📦 完整分析数据 (JSON)</div>
                    </div>
                </span>
            </div>
            <div class="app-meta">
                <span id="frameThumbnailPreview" class="frame-thumb-preview" style="display:none;" onclick="showFrameThumbnail()">
                    <img id="frameThumbnailImg" src="" alt="Frame" />
                </span>
                <span>{rdc_name} | {timestamp}</span>
            </div>
        </div>
        
        <!-- 主工作区 -->
        <div class="app-workspace">
            <!-- 左侧面板 - 资源浏览器 (TASK-205 双列表设计) -->
            <div class="panel-left" id="panelLeft">
                <div class="panel-header" onclick="togglePanel('left')">
                    <span class="panel-title">📂 资源浏览器</span>
                    <span class="panel-toggle">▼</span>
                </div>
                
                <!-- 纹理列表区块 -->
                <div class="resource-section texture-section" id="textureSectionPanel">
                    <div class="resource-section-header" onclick="toggleResourceSection('texture')">
                        <span class="resource-section-icon">🖼️</span>
                        <span class="resource-section-title">TEXTURES</span>
                        <span class="resource-section-badge" id="textureCountBadge">0/0</span>
                        <span class="resource-section-toggle" id="textureSectionToggle">▼</span>
                    </div>
                    <div class="resource-section-content" id="textureSectionContent">
                        <div class="resource-filter-bar">
                            <div class="filter-toggle-group">
                                <button class="filter-toggle-btn active" id="textureFilterAll" onclick="setTextureFilter('all')">All</button>
                                <button class="filter-toggle-btn" id="textureFilterIssues" onclick="setTextureFilter('issues')">⚠ Issues</button>
                            </div>
                            <input type="text" class="resource-search-box" id="searchBoxApp" placeholder="🔍 搜索...">
                        </div>
                        <div class="resource-sort-bar">
                            <select class="sort-select" id="sortSelectApp">
                                <option value="id">ID</option>
                                <option value="size">尺寸</option>
                                <option value="format">格式</option>
                                <option value="name">名称</option>
                            </select>
                            <span class="stats-badge" id="statsApp">0 项</span>
                        </div>
                        <!-- 优化建议筛选提示条 -->
                        <div class="optimization-filter-bar" id="optimFilterBar" style="display:none;">
                            <span class="filter-indicator">🎯</span>
                            <span id="optimFilterTitle"></span>
                            <span id="optimFilterCount"></span>
                            <button onclick="clearOptimizationFilter()" class="filter-clear-btn">✕</button>
                        </div>
                        <div class="texture-list" id="textureListApp"></div>
                    </div>
                </div>
                
                <!-- Shader 列表区块 (TASK-205) -->
                <div class="resource-section shader-section" id="shaderSectionPanel">
                    <div class="resource-section-header" onclick="toggleResourceSection('shader')">
                        <span class="resource-section-icon">⚡</span>
                        <span class="resource-section-title">SHADERS</span>
                        <span class="resource-section-badge shader-badge" id="shaderCountBadge">0/0</span>
                        <span class="resource-section-toggle" id="shaderSectionToggle">▼</span>
                    </div>
                    <div class="resource-section-content" id="shaderSectionContent">
                        <div class="resource-filter-bar">
                            <div class="filter-toggle-group">
                                <button class="filter-toggle-btn active" id="shaderFilterAll" onclick="setShaderFilter('all')">All</button>
                                <button class="filter-toggle-btn" id="shaderFilterIssues" onclick="setShaderFilter('issues')">⚠ Issues</button>
                            </div>
                            <input type="text" class="resource-search-box" id="shaderSearchBox" placeholder="🔍 搜索...">
                        </div>
                        <!-- Shader 优化筛选提示条 -->
                        <div class="shader-filter-bar" id="shaderFilterBar" style="display:none;">
                            <span class="filter-indicator">🎯</span>
                            <span id="shaderFilterTitle"></span>
                            <span id="shaderFilterCount"></span>
                            <button onclick="clearShaderFilter()" class="filter-clear-btn">✕</button>
                        </div>
                        <div class="shader-list" id="shaderListApp"></div>
                        
                        <!-- TASK-209: Shader 详情面板 -->
                        <div class="shader-details-panel" id="shaderDetailsPanel">
                            <div class="shader-details-header">
                                <span class="shader-details-title" id="shaderDetailsTitle">Shader 详情</span>
                                <button class="shader-details-close" onclick="hideShaderDetails()" title="关闭">×</button>
                            </div>
                            <div id="shaderDetailsContent">
                                <!-- 由 JS 动态填充 -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 中间主画布区域 -->
            <div class="main-canvas-area">
                <!-- 画布工具栏 -->
                <div class="canvas-toolbar">
                    <div class="toolbar-group">
                        <button class="toolbar-btn" onclick="zoomImageApp(-0.25)" title="缩小">−</button>
                        <span class="zoom-display" id="zoomDisplayApp">100%</span>
                        <button class="toolbar-btn" onclick="zoomImageApp(0.25)" title="放大">+</button>
                        <button class="toolbar-btn" onclick="resetZoomApp()" title="适应">⊡</button>
                    </div>
                    <div class="toolbar-group">
                        <button class="channel-btn active" data-channel="rgb" onclick="switchChannelApp('rgb')">RGB</button>
                        <button class="channel-btn" data-channel="r" onclick="switchChannelApp('r')">R</button>
                        <button class="channel-btn" data-channel="g" onclick="switchChannelApp('g')">G</button>
                        <button class="channel-btn" data-channel="b" onclick="switchChannelApp('b')">B</button>
                        <button class="channel-btn" data-channel="a" onclick="switchChannelApp('a')">A</button>
                    </div>
                    <div class="toolbar-group">
                        <button class="toolbar-btn" id="histogramBtnApp" onclick="togglePropSection('histogram')" title="直方图">📊</button>
                        <button class="toolbar-btn" id="adjustBtnApp" onclick="togglePropSection('adjust')" title="调整">🎨</button>
                    </div>
                    <div class="toolbar-group" style="margin-left:auto;">
                        <button class="toolbar-btn" id="locateBtnApp" onclick="scrollToCurrentTexture()" title="在列表中定位当前纹理">🔍</button>
                    </div>
                </div>
                
                <!-- 主画布 -->
                <div class="canvas-viewport" id="canvasViewport">
                    <div class="canvas-empty" id="canvasEmpty">
                        <div class="canvas-empty-icon">🖼️</div>
                        <div class="canvas-empty-text">从左侧列表选择纹理预览</div>
                    </div>
                    <img class="preview-img" id="previewImgApp" src="" alt="" style="display:none;">
                    
                    <!-- 浮动颜色拾取器 -->
                    <div class="color-picker-float" id="colorPickerApp" style="display:none;">
                        <div class="color-preview" id="colorPreviewApp"></div>
                        <span class="coord" id="colorCoordApp">-,-</span>
                        <span class="hex" id="colorHexApp">#------</span>
                    </div>
                </div>
            </div>
            
            <!-- 右侧面板 - 属性 -->
            <div class="panel-right" id="panelRight">
                <div class="panel-header" onclick="togglePanel('right')">
                    <span class="panel-title">属性</span>
                    <span class="panel-toggle">▼</span>
                </div>
                <div class="panel-content" style="flex:1; overflow-y:auto;">
                    <!-- 统计摘要 -->
                    <div class="prop-section" id="sectionStats">
                        <div class="prop-section-header" onclick="togglePropSection('stats')">
                            <span class="prop-section-title">📊 统计</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <div class="stats-grid">
                                <div class="stat-mini">
                                    <div class="stat-mini-value" id="statTotalApp">0</div>
                                    <div class="stat-mini-label">纹理</div>
                                </div>
                                <div class="stat-mini">
                                    <div class="stat-mini-value" id="statVRAMApp">0 MB</div>
                                    <div class="stat-mini-label">VRAM</div>
                                </div>
                                <div class="stat-mini">
                                    <div class="stat-mini-value" id="statFormatsApp">0</div>
                                    <div class="stat-mini-label">格式</div>
                                </div>
                                <div class="stat-mini">
                                    <div class="stat-mini-value" id="statAvgApp">0×0</div>
                                    <div class="stat-mini-label">平均尺寸</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- VRAM 分布图表 -->
                    <div class="prop-section" id="sectionVRAMChart">
                        <div class="prop-section-header" onclick="togglePropSection('vramchart')">
                            <span class="prop-section-title">📊 VRAM 分布</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <div class="chart-container">
                                <!-- VRAM 总结统计卡片 -->
                                <div class="vram-summary" id="vramSummary">
                                    <div class="vram-stat">
                                        <div class="vram-stat-value" id="vramTotal">-</div>
                                        <div class="vram-stat-label">总 VRAM</div>
                                    </div>
                                    <div class="vram-stat">
                                        <div class="vram-stat-value" id="vramCompressed">-</div>
                                        <div class="vram-stat-label">压缩纹理</div>
                                    </div>
                                    <div class="vram-stat">
                                        <div class="vram-stat-value warn" id="vramWasted">-</div>
                                        <div class="vram-stat-label">可优化</div>
                                    </div>
                                </div>
                                
                                <!-- 格式分布饼图 -->
                                <div class="chart-box">
                                    <div class="chart-title">按格式分布</div>
                                    <div class="pie-chart" id="formatPieChart">
                                        <div class="pie-chart-inner" id="formatPieInner">-</div>
                                    </div>
                                    <div class="chart-legend" id="formatLegend"></div>
                                </div>
                                
                                <!-- 尺寸分布柱状图 -->
                                <div class="chart-box" style="margin-top:8px;">
                                    <div class="chart-title">按尺寸分布</div>
                                    <div class="bar-chart" id="sizeBarChart"></div>
                                </div>
                                
                                <!-- Top 10 最大纹理 -->
                                <div class="chart-box" style="margin-top:8px;">
                                    <div class="chart-title">🏆 Top 10 最大纹理</div>
                                    <div class="bar-chart top-textures" id="topTexturesChart"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 当前纹理信息 -->
                    <div class="prop-section" id="sectionInfo">
                        <div class="prop-section-header" onclick="togglePropSection('info')">
                            <span class="prop-section-title">ℹ️ 纹理信息</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <div class="prop-row"><span class="prop-label">ID</span><span class="prop-value" id="propId">-</span></div>
                            <div class="prop-row"><span class="prop-label">名称</span><span class="prop-value" id="propName">-</span></div>
                            <div class="prop-row"><span class="prop-label">尺寸</span><span class="prop-value highlight" id="propSize">-</span></div>
                            <div class="prop-row"><span class="prop-label">格式</span><span class="prop-value" id="propFormat">-</span></div>
                            <div class="prop-row"><span class="prop-label">Mips</span><span class="prop-value" id="propMips">-</span></div>
                            <div class="prop-row"><span class="prop-label">Layers</span><span class="prop-value" id="propLayers">-</span></div>
                        </div>
                    </div>
                    
                    <!-- 纹理分析 -->
                    <div class="prop-section" id="sectionAnalysis">
                        <div class="prop-section-header" onclick="togglePropSection('analysis')">
                            <span class="prop-section-title">🔍 分析</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content" id="textureAnalysis">
                            <div class="prop-row"><span class="prop-label">VRAM</span><span class="prop-value text-muted">-</span></div>
                            <div class="prop-row"><span class="prop-label">压缩</span><span class="prop-value text-muted">-</span></div>
                        </div>
                    </div>
                    
                    <!-- 直方图 -->
                    <div class="prop-section collapsed" id="sectionHistogram">
                        <div class="prop-section-header" onclick="togglePropSection('histogram')">
                            <span class="prop-section-title">📈 直方图</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <canvas class="histogram-canvas" id="histogramCanvasApp" width="220" height="60"></canvas>
                            <div class="histogram-labels"><span>0</span><span>128</span><span>255</span></div>
                        </div>
                    </div>
                    
                    <!-- 调整 -->
                    <div class="prop-section collapsed" id="sectionAdjust">
                        <div class="prop-section-header" onclick="togglePropSection('adjust')">
                            <span class="prop-section-title">🎨 调整</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <div class="slider-row">
                                <label>亮度</label>
                                <input type="range" id="brightnessApp" min="0" max="300" value="100" oninput="updateFilterApp()">
                                <span class="slider-value" id="brightnessValApp">100%</span>
                            </div>
                            <div class="slider-row">
                                <label>对比度</label>
                                <input type="range" id="contrastApp" min="0" max="300" value="100" oninput="updateFilterApp()">
                                <span class="slider-value" id="contrastValApp">100%</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 备注 -->
                    <div class="prop-section" id="sectionNotes">
                        <div class="prop-section-header" onclick="togglePropSection('notes')">
                            <span class="prop-section-title">📝 备注</span>
                            <span class="prop-section-toggle">▼</span>
                        </div>
                        <div class="prop-section-content">
                            <textarea class="notes-textarea" id="notesApp" placeholder="备注..."></textarea>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 底部状态栏 -->
        <div class="app-statusbar">
            <div class="status-left">
                <span class="status-item" id="statusTexture">未选中</span>
                <span class="status-item" id="statusZoom">100%</span>
            </div>
            <div class="status-right">
                <span>RDC Texture Analyzer v2.0</span>
            </div>
        </div>
    </div>
    
    <!-- ========== 原有网格视图（可切换） ========== -->
    <div class="container" id="gridContainer">
        <header class="header">
            <div style="display:flex; align-items:center; gap:16px;">
                <button onclick="toggleViewMode()" style="
                    background: var(--accent-blue);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    transition: background 0.15s;
                    white-space: nowrap;
                    flex-shrink: 0;
                " onmouseover="this.style.background='#3a8edc'" onmouseout="this.style.background='var(--accent-blue)'">
                    ← 返回主视图
                </button>
                <h1 style="margin:0;">🎮 RDC 纹理分析报告</h1>
            </div>
            <div class="header-meta">
                <div>{rdc_name}</div>
                <div>{timestamp}</div>
            </div>
        </header>
        
        <!-- 统计摘要面板 -->
        <div class="stats-panel" id="statsPanel">
            <div class="stat-card">
                <div class="stat-value" id="statTotal">0</div>
                <div class="stat-label">纹理总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statVRAM">0 MB</div>
                <div class="stat-label">预估 VRAM</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statFormats">0</div>
                <div class="stat-label">格式种类</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statAvgSize">0×0</div>
                <div class="stat-label">平均尺寸</div>
            </div>
        </div>
        
        <!-- 性能分析面板 (TASK-008) -->
        <div class="performance-panel" id="performancePanel">
            <div class="performance-header" onclick="togglePerformancePanel()">
                <div class="performance-title">
                    <div class="performance-score" id="performanceScore">--</div>
                    <span>Performance Insights</span>
                </div>
                <span class="performance-toggle" id="performanceToggle">&#9660;</span>
            </div>
            <div class="performance-content" id="performanceContent">
                <div class="performance-metrics" id="performanceMetrics"></div>
                <ul class="performance-issues" id="performanceIssues"></ul>
            </div>
        </div>
        
        <!-- 优化建议面板 (TASK-009) -->
        <div class="optimization-panel" id="optimizationPanel">
            <div class="optimization-header" onclick="toggleOptimizationPanel()">
                <div class="optimization-title">
                    <span>Optimization Suggestions</span>
                    <span class="optimization-badge" id="optimizationCount">0</span>
                </div>
                <span class="optimization-toggle" id="optimizationToggle">&#9660;</span>
            </div>
            <div class="optimization-content" id="optimizationContent">
                <div class="optimization-summary" id="optimizationSummary"></div>
                <ul class="optimization-list" id="optimizationList"></ul>
            </div>
        </div>
        
        <div class="toolbar">
            <input type="text" class="search-box" id="searchBox" placeholder="🔍 搜索纹理名称或 ID...">
            <select class="sort-select" id="formatFilter">
                <option value="">全部格式</option>
            </select>
            <select class="sort-select" id="sizeFilter">
                <option value="">全部尺寸</option>
                <option value="small">小 (≤64px)</option>
                <option value="medium">中 (65-512px)</option>
                <option value="large">大 (513-2048px)</option>
                <option value="huge">超大 (>2048px)</option>
            </select>
            <select class="sort-select" id="sortSelect">
                <option value="id">按 ID 排序</option>
                <option value="size">按尺寸排序</option>
                <option value="format">按格式排序</option>
                <option value="name">按名称排序</option>
            </select>
            <div class="view-toggle">
                <button class="view-btn active" data-view="grid">网格</button>
                <button class="view-btn" data-view="table">表格</button>
            </div>
            <div class="stats" id="stats"></div>
        </div>
        
        <div class="grid-view" id="gridView">
            <div class="texture-grid" id="textureGrid"></div>
        </div>
        
        <div class="table-view" id="tableView">
            <table>
                <thead>
                    <tr>
                        <th>缩略图</th>
                        <th data-sort="id">ID</th>
                        <th data-sort="name">名称</th>
                        <th data-sort="size">尺寸</th>
                        <th data-sort="format">格式</th>
                        <th>Mips</th>
                        <th>Layers</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
    </div>
    
    <!-- ========== Event Browser 视图 ========== -->
    <div class="event-browser-container" id="eventBrowserContainer">
        <div class="event-browser-header">
            <button onclick="toggleViewMode()" style="
                background: var(--accent-blue);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            ">← 返回</button>
            <h2>🎮 Event Browser</h2>
            <span class="api-badge" id="eventApiType">D3D11</span>
            <div class="frame-stats">
                <span>Events: <span class="stat-value" id="eventTotalCount">0</span></span>
                <span>Draws: <span class="stat-value" id="eventDrawCount">0</span></span>
                <span>Dispatches: <span class="stat-value" id="eventDispatchCount">0</span></span>
                <span>Frame: <span class="stat-value" id="eventFrameDuration">0 ms</span></span>
            </div>
        </div>
        <div class="event-browser-main">
            <!-- 左侧: Event 树形列表 / Pass 依赖图 -->
            <div class="event-tree-panel">
                <div class="event-tree-toolbar">
                    <div class="view-mode-toggle">
                        <button class="active" onclick="setEventViewMode('tree')" id="viewModeTree">📋 列表</button>
                        <button onclick="setEventViewMode('graph')" id="viewModeGraph">📊 Pass图</button>
                    </div>
                    <input type="text" id="eventSearchBox" placeholder="搜索 Event..." style="flex: 1;">
                    <select id="eventTypeFilter" onchange="renderEventTree()">
                        <option value="">所有类型</option>
                        <option value="Draw">🎨 Draw</option>
                        <option value="Dispatch">⚡ Dispatch</option>
                        <option value="Marker">📌 Marker</option>
                        <option value="Clear">🧹 Clear</option>
                        <option value="Copy">📋 Copy</option>
                    </select>
                    <select id="passFilter" onchange="renderEventTree()">
                        <option value="">所有 Pass</option>
                        <!-- Pass 选项由 JS 动态填充 -->
                    </select>
                    <button onclick="expandAllEvents()" id="expandCollapseBtn1">展开</button>
                    <button onclick="collapseAllEvents()" id="expandCollapseBtn2">折叠</button>
                </div>
                <div class="event-tree-list" id="eventTreeList">
                    <!-- Event 树节点将由 JS 动态生成 -->
                </div>
                <div class="pass-graph-container" id="passGraphContainer">
                    <!-- Pass 依赖图将由 JS 动态生成 -->
                </div>
            </div>
            
            <!-- 拖拽分隔条 -->
            <div class="panel-resizer" id="eventPanelResizer"></div>
            
            <!-- 右侧: Event 详情面板 -->
            <div class="event-detail-panel">
                <div class="event-detail-tabs">
                    <div class="tab active" data-tab="summary" onclick="switchEventTab('summary')">📋 摘要</div>
                    <div class="tab" data-tab="pipeline" onclick="switchEventTab('pipeline')">🔧 Pipeline State</div>
                    <div class="tab" data-tab="bindings" onclick="switchEventTab('bindings')">🎨 资源绑定</div>
                    <div class="tab" data-tab="mesh" onclick="switchEventTab('mesh')">📐 Mesh Info</div>
                    <div class="tab" data-tab="apicall" onclick="switchEventTab('apicall')">📝 API 调用</div>
                </div>
                <div class="event-detail-content" id="eventDetailContent">
                    <div class="event-detail-empty">
                        <div class="icon">📋</div>
                        <div>从左侧选择一个 Event 查看详情</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Lightbox V2 -->
    <div class="lightbox" id="lightbox">
        <!-- 顶部导航栏 -->
        <div class="lightbox-header">
            <div class="lightbox-nav-group">
                <button class="nav-btn" onclick="navigateLightbox(-1)" title="上一个">❮</button>
                <button class="nav-btn" onclick="navigateLightbox(1)" title="下一个">❯</button>
            </div>
            <div class="lightbox-title" id="lightboxName"></div>
            <div class="lightbox-meta" id="lightboxDetails"></div>
            <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
        </div>
        
        <!-- 主内容区 -->
        <div class="lightbox-main">
            <div class="lightbox-img-container" id="imgContainer">
                <img class="lightbox-img" id="lightboxImg" src="" alt="">
            </div>
            
            <!-- 悬浮颜色拾取器 -->
            <div class="color-picker-float" id="colorPickerInfo">
                <div class="color-preview" id="colorPreview"></div>
                <span class="coord" id="colorCoord">-,-</span>
                <span>R:<span id="colorR">-</span></span>
                <span>G:<span id="colorG">-</span></span>
                <span>B:<span id="colorB">-</span></span>
                <span>A:<span id="colorA">-</span></span>
                <span class="hex" id="colorHex" onclick="copyHex()" title="点击复制">#------</span>
            </div>
            
            <!-- 弹出面板: 直方图 -->
            <div class="popup-panel" id="histogramPanel">
                <div class="popup-header">
                    <span class="popup-title">📊 直方图</span>
                    <button class="popup-close" onclick="togglePanel('histogram')">×</button>
                </div>
                <div class="histogram-toggle">
                    <button class="active" data-mode="rgb" onclick="setHistogramMode('rgb')">RGB</button>
                    <button data-mode="luminance" onclick="setHistogramMode('luminance')">亮度</button>
                </div>
                <canvas class="histogram-canvas" id="histogramCanvas" width="300" height="80"></canvas>
                <div class="histogram-labels">
                    <span>0</span><span>64</span><span>128</span><span>192</span><span>255</span>
                </div>
                <div class="histogram-stats" id="histogramStats">
                    <span><div class="dot r"></div>R: -</span>
                    <span><div class="dot g"></div>G: -</span>
                    <span><div class="dot b"></div>B: -</span>
                </div>
            </div>
            
            <!-- 弹出面板: 调整 -->
            <div class="popup-panel" id="adjustPanel">
                <div class="popup-header">
                    <span class="popup-title">🎨 图像调整</span>
                    <button class="popup-close" onclick="togglePanel('adjust')">×</button>
                </div>
                <div class="slider-group">
                    <label>亮度</label>
                    <input type="range" id="brightnessSlider" min="0" max="300" value="100" oninput="updateImageFilter()">
                    <span class="slider-value" id="brightnessValue">100%</span>
                </div>
                <div class="slider-group">
                    <label>对比度</label>
                    <input type="range" id="contrastSlider" min="0" max="300" value="100" oninput="updateImageFilter()">
                    <span class="slider-value" id="contrastValue">100%</span>
                </div>
                <button class="reset-btn" onclick="resetFilters()">重置</button>
            </div>
            
            <!-- 弹出面板: 3D 法线 -->
            <div class="popup-panel" id="normalPanel">
                <div class="popup-header">
                    <span class="popup-title">🗻 3D 法线预览</span>
                    <button class="popup-close" onclick="togglePanel('normal')">×</button>
                </div>
                <canvas class="normal-3d-canvas" id="normal3dCanvas" width="300" height="120"></canvas>
                <div class="slider-group">
                    <label>高度</label>
                    <input type="range" id="normalHeightSlider" min="1" max="50" value="15" oninput="updateNormal3D()">
                    <span class="slider-value" id="normalHeightValue">15</span>
                </div>
                <div class="slider-group">
                    <label>光照</label>
                    <input type="range" id="normalLightSlider" min="0" max="360" value="45" oninput="updateNormal3D()">
                    <span class="slider-value" id="normalLightValue">45°</span>
                </div>
            </div>
            
            <!-- 弹出面板: 备注 -->
            <div class="popup-panel" id="notesPanel">
                <div class="popup-header">
                    <span class="popup-title">� 备注笔记</span>
                    <button class="popup-close" onclick="togglePanel('notes')">×</button>
                </div>
                <textarea class="notes-textarea" id="notesTextarea" placeholder="在此输入备注..." oninput="saveNote()"></textarea>
            </div>
        </div>
        
        <!-- 底部工具栏 -->
        <div class="lightbox-toolbar">
            <!-- 缩放组 -->
            <div class="toolbar-group">
                <button class="zoom-btn" onclick="zoomImage(-0.25)" title="缩小">−</button>
                <span class="zoom-level" id="zoomLevel">100%</span>
                <button class="zoom-btn" onclick="zoomImage(0.25)" title="放大">+</button>
                <button class="zoom-btn" onclick="resetZoom()" title="重置">⟲</button>
            </div>
            
            <!-- 通道组 -->
            <div class="toolbar-group channels">
                <button class="channel-btn active" data-channel="rgb" onclick="switchChannel('rgb')">RGB</button>
                <button class="channel-btn" data-channel="r" onclick="switchChannel('r')">R</button>
                <button class="channel-btn" data-channel="g" onclick="switchChannel('g')">G</button>
                <button class="channel-btn" data-channel="b" onclick="switchChannel('b')">B</button>
                <button class="channel-btn" data-channel="a" onclick="switchChannel('a')">A</button>
            </div>
            
            <!-- 工具按钮组 -->
            <div class="toolbar-group">
                <button class="tool-btn" onclick="togglePanel('histogram')" title="直方图" id="histogramBtn">📊</button>
                <button class="tool-btn" onclick="togglePanel('adjust')" title="调整" id="adjustBtn">🎨</button>
                <button class="tool-btn" onclick="togglePanel('normal')" title="3D法线" id="normalBtn">🗻</button>
                <button class="tool-btn" onclick="togglePanel('notes')" title="备注" id="notesBtn">📝</button>
            </div>
            
            <!-- 操作按钮组 -->
            <div class="toolbar-group">
                <button class="tool-btn" onclick="toggleCompare()" title="标记对比" id="compareBtn">⚖</button>
                <button class="tool-btn" onclick="toggleBookmark()" title="收藏" id="bookmarkBtn">⭐</button>
                <button class="tool-btn" onclick="exportTexture()" title="导出PNG">💾</button>
            </div>
        </div>
    </div>
    
    <!-- 对比视图 Lightbox -->
    <div class="compare-lightbox" id="compareLightbox">
        <div class="compare-header">
            <h2>🔍 纹理对比 <span style="font-size:0.7em;color:var(--text-muted);margin-left:8px;">滚轮缩放 · 拖拽平移</span></h2>
            <span class="compare-close" onclick="closeCompare()">&times;</span>
        </div>
        <div class="compare-container">
            <div class="compare-pane">
                <div class="compare-pane-title" id="compareTitle1">纹理 A</div>
                <div class="compare-pane-info" id="compareInfo1">-</div>
                <div class="compare-img-wrapper" id="compareWrapper1">
                    <img id="compareImg1" src="" alt="">
                    <span class="compare-zoom-label" id="compareZoom1">100%</span>
                </div>
            </div>
            <div class="compare-pane">
                <div class="compare-pane-title" id="compareTitle2">纹理 B</div>
                <div class="compare-pane-info" id="compareInfo2">-</div>
                <div class="compare-img-wrapper" id="compareWrapper2">
                    <img id="compareImg2" src="" alt="">
                    <span class="compare-zoom-label" id="compareZoom2">100%</span>
                </div>
            </div>
        </div>
        <!-- 差异对比表格 -->
        <div class="compare-diff-table" id="compareDiffTable"></div>
        <div class="compare-toolbar">
            <div class="zoom-group">
                <button onclick="compareZoomIn()" title="放大">➕</button>
                <span class="zoom-label" id="compareZoomLabel">100%</span>
                <button onclick="compareZoomOut()" title="缩小">➖</button>
                <button onclick="compareZoomReset()" title="重置">🔄</button>
            </div>
            <button onclick="toggleCompareSync()" id="compareSyncBtn" class="active" title="同步缩放/平移">🔗 同步</button>
            <button onclick="swapCompareTextures()">⇄ 交换</button>
            <button onclick="clearCompareMarks()">✖ 清除</button>
            <button onclick="closeCompare()">关闭</button>
        </div>
    </div>
    
    <!-- Event ID 详情弹窗 -->
    <div class="eid-modal" id="eidModal">
        <div class="eid-modal-content">
            <div class="eid-modal-header">
                <div class="eid-modal-title">
                    <span>📌 Event ID</span>
                    <span class="eid-badge" id="eidModalId">-</span>
                </div>
                <button class="eid-modal-close" onclick="closeEIDModal()">&times;</button>
            </div>
            <div class="eid-modal-body">
                <div class="eid-info-grid">
                    <span class="eid-info-label">🎨 Render Pass</span>
                    <span class="eid-info-value" id="eidModalPass">-</span>
                    
                    <span class="eid-info-label">⚙️ API Call</span>
                    <span class="eid-info-value api-call" id="eidModalAPI">-</span>
                    
                    <span class="eid-info-label">🔲 纹理槽位</span>
                    <div id="eidModalSlots">
                        <div class="eid-slot-list">
                            <span class="eid-slot-tag">PS Slot 0</span>
                        </div>
                    </div>
                    
                    <span class="eid-info-label">📊 绘制信息</span>
                    <span class="eid-info-value" id="eidModalDrawInfo">-</span>
                </div>
            </div>
            <div class="eid-modal-footer">
                <button class="eid-modal-btn secondary" onclick="closeEIDModal()">关闭</button>
                <button class="eid-modal-btn primary" onclick="copyEIDInfo()" title="复制信息到剪贴板">📋 复制</button>
                <button class="eid-modal-btn jump" id="eidModalJumpBtn" style="display: none;" title="在 Event Browser 中查看此事件">
                    🔍 查看详情
                </button>
            </div>
        </div>
    </div>
    
    <!-- RT Timeline Component (Direction C) -->
    {generate_rt_timeline_html(rt_tracking_data) if HAS_RT_TIMELINE and rt_tracking_data else ''}
    
    <script>
        // 纹理数据
        const textures = {textures_json};
        // 去重分析数据
        const duplicateAnalysis = {duplicates_json};
        // 热度分析数据
        const usageAnalysis = {usage_json};
        // Event/Pass 数据
        const eventPassData = {event_pass_json};
        // 帧缩略图
        const frameThumbnail = {frame_thumbnail_json};
        // 优化建议数据 (TASK-009)
        const optimizationData = {optimization_json};
        // 性能分析数据 (TASK-008)
        const performanceData = {performance_json};
        // Shader 列表数据 (TASK-205: 资源浏览器)
        const shaderData = {shader_json};
        let filteredTextures = [...textures];
        let currentLightboxIndex = 0;
        let currentSort = {{ key: 'id', asc: true }};
        let currentChannel = 'rgb';  // 当前显示的通道
        
        // ========== Photoshop 风格界面状态 ==========
        let viewMode = 'app';  // 'app' 或 'grid'
        let selectedTextureIndex = -1;
        let appZoom = 1;
        let appChannel = 'rgb';
        
        // 优化建议筛选状态 (TASK-009 方案B)
        let currentOptimizationFilter = null;  // {{ title: string, resourceNames: string[] }}
        
        // ========== 全局工具函数 ==========
        
        // 根据名称生成占位符颜色 (哈希转 HSL)
        function generateColorFromName(name) {{
            const str = String(name || 'default');
            let hash = 0;
            for (let i = 0; i < str.length; i++) {{
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }}
            const hue = Math.abs(hash) % 360;
            return `hsl(${{hue}}, 65%, 45%)`;
        }}
        
        // 初始化
        function init() {{
            populateFormatFilter();
            updateStatsPanel();
            updateStats();
            renderGrid();
            renderTable();
            setupEventListeners();
            
            // 初始化 Photoshop 风格界面
            initAppView();
        }}
        
        // ========== Photoshop 风格界面函数 ==========
        
        function initAppView() {{
            renderTextureList();
            updateAppStats();
            runGlobalAnalysis();
            renderPerformancePanel();
            renderOptimizationPanel();
            initResourceBrowser();  // TASK-205: 初始化资源浏览器双列表
            setupAppEventListeners();
        }}
        
        // 全局纹理分析
        function runGlobalAnalysis() {{
            const issues = {{
                noMipmap: [],
                partialMipmap: [],
                nonPow2: [],
                oversized: [],
                uncompressed: []
            }};
            
            textures.forEach(tex => {{
                const expectedMips = calculateExpectedMips(tex.width, tex.height);
                const actualMips = tex.mips || 1;
                const isPow2 = (n) => (n & (n - 1)) === 0;
                const isCompressed = tex.format.startsWith('BC') || tex.format.startsWith('ASTC');
                
                // 无 Mipmap
                if (actualMips === 1 && tex.width >= 64) {{
                    issues.noMipmap.push(tex);
                }} else if (actualMips < expectedMips && actualMips > 1) {{
                    issues.partialMipmap.push(tex);
                }}
                
                // 非 2 的幂
                if (!isPow2(tex.width) || !isPow2(tex.height)) {{
                    issues.nonPow2.push(tex);
                }}
                
                // 超大纹理
                if (tex.width >= 4096 || tex.height >= 4096) {{
                    issues.oversized.push(tex);
                }}
                
                // 未压缩（且尺寸大）
                if (!isCompressed && tex.width * tex.height >= 256 * 256) {{
                    issues.uncompressed.push(tex);
                }}
            }});
            
            // 更新 UI 显示问题计数
            const totalIssues = issues.noMipmap.length + issues.nonPow2.length + issues.oversized.length;
            
            // 在统计区显示问题数
            const statsSection = document.querySelector('#sectionStats .prop-section-content');
            if (statsSection && totalIssues > 0) {{
                const issueHtml = `
                    <div class="global-issues">
                        <div class="issue-summary ${{totalIssues > 0 ? 'has-issues' : ''}}">
                            ${{totalIssues}} 个潜在问题
                        </div>
                        ${{issues.noMipmap.length > 0 ? `<div class="issue-row warn">⚠ ${{issues.noMipmap.length}} 个纹理缺少 Mipmap</div>` : ''}}
                        ${{issues.nonPow2.length > 0 ? `<div class="issue-row info">ℹ ${{issues.nonPow2.length}} 个非 2 的幂尺寸</div>` : ''}}
                        ${{issues.oversized.length > 0 ? `<div class="issue-row info">ℹ ${{issues.oversized.length}} 个超大纹理 (≥4K)</div>` : ''}}
                        ${{issues.uncompressed.length > 0 ? `<div class="issue-row info">ℹ ${{issues.uncompressed.length}} 个未压缩纹理</div>` : ''}}
                    </div>
                `;
                statsSection.insertAdjacentHTML('beforeend', issueHtml);
            }}
            
            // 保存问题列表供后续使用
            window.textureIssues = issues;
            
            // 渲染去重分析面板
            renderDuplicateAnalysis();
            
            // 渲染热度分析面板
            renderUsageAnalysis();
            
            // 渲染优化建议面板 (TASK-009)
            renderOptimizationPanelInSidebar();
        }}
        
        // 渲染去重分析结果
        function renderDuplicateAnalysis() {{
            if (!duplicateAnalysis || !duplicateAnalysis.duplicate_groups) return;
            
            const groups = duplicateAnalysis.duplicate_groups || [];
            const totalWasted = duplicateAnalysis.total_wasted_bytes || 0;
            const dupCount = duplicateAnalysis.total_duplicate_count || 0;
            
            if (groups.length === 0) return;
            
            // 格式化字节数
            function formatBytes(bytes) {{
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
            }}
            
            // 根据名称生成占位符颜色
            function generateColorFromName(name) {{
                const str = String(name || 'default');
                let hash = 0;
                for (let i = 0; i < str.length; i++) {{
                    hash = str.charCodeAt(i) + ((hash << 5) - hash);
                }}
                const hue = Math.abs(hash) % 360;
                return `hsl(${{hue}}, 65%, 45%)`;
            }}
            
            const statsSection = document.querySelector('#sectionStats .prop-section-content');
            if (statsSection) {{
                const metaOnlyTag = duplicateAnalysis.metadata_only ? 
                    '<span style="color:var(--accent-yellow);font-size:10px;">(仅元数据)</span>' : '';
                
                const dupHtml = `
                    <div class="global-issues" style="margin-top:12px;border-top:1px solid var(--border);padding-top:12px;">
                        <div class="issue-summary has-issues" style="background:var(--accent-orange);color:white;">
                            🔁 发现 ${{groups.length}} 组重复纹理 ${{metaOnlyTag}}
                        </div>
                        <div class="issue-row warn">
                            ⚠ 浪费 VRAM: ${{formatBytes(totalWasted)}}
                        </div>
                        <div class="issue-row info">
                            ℹ 多余纹理: ${{dupCount}} 个
                        </div>
                        <div style="margin-top:8px;">
                            ${{groups.map((g, i) => `
                                <details class="dup-group-detail" style="margin-bottom:6px;border:1px solid var(--border);border-radius:4px;">
                                    <summary style="padding:6px 8px;cursor:pointer;background:var(--bg-secondary);font-size:11px;display:flex;align-items:center;gap:6px;">
                                        <span style="color:var(--accent-orange);font-weight:bold;">组 ${{i+1}}</span>
                                        <span style="color:var(--text-secondary);">${{g.count}} 个重复</span>
                                        <span style="color:var(--accent-red);margin-left:auto;">-${{formatBytes(g.wasted_bytes)}}</span>
                                    </summary>
                                    <div style="padding:8px;background:var(--bg-primary);">
                                        <div style="display:flex;flex-wrap:wrap;gap:8px;">
                                            ${{g.textures.map((t, j) => `
                                                <div onclick="selectTextureByResourceId(${{t.resource_id}})" style="display:flex;align-items:center;gap:6px;padding:4px 8px;background:var(--bg-secondary);border-radius:4px;font-size:10px;min-width:120px;cursor:pointer;transition:background 0.15s;" onmouseover="this.style.background='var(--bg-hover)'" onmouseout="this.style.background='var(--bg-secondary)'">
                                                    <div style="width:32px;height:32px;border-radius:3px;background:${{t.thumbnail ? 'none' : generateColorFromName(t.name || t.resource_id)}};display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden;">
                                                        ${{t.thumbnail ? '<img src="' + t.thumbnail + '" style="width:100%;height:100%;object-fit:cover;">' : '<span style="color:white;font-size:8px;text-shadow:0 1px 2px rgba(0,0,0,0.5);">' + (t.width || '?') + '</span>'}}
                                                    </div>
                                                    <div style="overflow:hidden;">
                                                        <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text-primary);max-width:100px;" title="${{t.name || 'ID:' + t.resource_id}}">${{t.name || 'ID:' + t.resource_id}}</div>
                                                        <div style="color:var(--text-muted);font-size:9px;">${{t.width || '?'}}×${{t.height || '?'}}</div>
                                                    </div>
                                                    ${{j === 0 ? '<span style="background:var(--accent-green);color:white;padding:1px 4px;border-radius:2px;font-size:8px;margin-left:auto;">保留</span>' : '<span style="background:var(--accent-red);color:white;padding:1px 4px;border-radius:2px;font-size:8px;margin-left:auto;opacity:0.7;">重复</span>'}}
                                                </div>
                                            `).join('')}}
                                        </div>
                                        <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:10px;color:var(--text-muted);">
                                            💡 建议: 保留第一个纹理，删除其余 ${{g.count - 1}} 个可节省 ${{formatBytes(g.wasted_bytes)}}
                                        </div>
                                    </div>
                                </details>
                            `).join('')}}
                        </div>
                    </div>
                `;
                statsSection.insertAdjacentHTML('beforeend', dupHtml);
            }}
            
            // 保存去重数据供导出使用
            window.duplicateAnalysis = duplicateAnalysis;
        }}
        
        // 渲染热度分析结果
        function renderUsageAnalysis() {{
            if (!usageAnalysis || (!usageAnalysis.hot_list && !usageAnalysis.cold_list)) return;
            
            const hotList = usageAnalysis.hot_list || [];
            const coldList = usageAnalysis.cold_list || [];
            const usedCount = usageAnalysis.used_textures || 0;
            const unusedCount = usageAnalysis.unused_textures || 0;
            const totalEvents = usageAnalysis.total_events || 0;
            
            // 格式化字节数
            function formatBytes(bytes) {{
                if (!bytes) return '0 B';
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
            }}
            
            // 根据名称生成占位符颜色
            function generateColorFromName(name) {{
                const str = String(name || 'default');
                let hash = 0;
                for (let i = 0; i < str.length; i++) {{
                    hash = str.charCodeAt(i) + ((hash << 5) - hash);
                }}
                const hue = Math.abs(hash) % 360;
                return `hsl(${{hue}}, 65%, 45%)`;
            }}
            
            const statsSection = document.querySelector('#sectionStats .prop-section-content');
            if (statsSection) {{
                // 计算未使用纹理的潜在浪费
                let unusedWaste = 0;
                coldList.forEach(t => {{
                    unusedWaste += t.estimated_size || 0;
                }});
                
                let usageHtml = `
                    <div class="usage-analysis" style="margin-top:12px;border-top:1px solid var(--border);padding-top:12px;">
                        <div class="issue-summary ${{unusedCount > 0 ? 'has-issues' : 'no-issues'}}" 
                             style="background:${{unusedCount > 0 ? 'var(--accent-purple)' : 'var(--accent-green)'}};color:white;">
                            🔥 纹理热度分析 (扫描 ${{totalEvents}} 事件)
                        </div>
                        <div class="issue-row ${{unusedCount > 0 ? 'warn' : 'ok'}}">
                            ${{unusedCount > 0 ? '⚠' : '✓'}} 已使用: ${{usedCount}} / 未使用: ${{unusedCount}}
                        </div>
                `;
                
                if (unusedCount > 0 && unusedWaste > 0) {{
                    usageHtml += `
                        <div class="issue-row warn">
                            💾 潜在浪费: ${{formatBytes(unusedWaste)}} (未使用纹理)
                        </div>
                    `;
                }}
                
                // 热门纹理 Top 5
                if (hotList.length > 0) {{
                    usageHtml += `
                        <div style="margin-top:8px;">
                            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">🔥 热门纹理 (Top 5):</div>
                            ${{hotList.slice(0, 5).map((t, i) => `
                                <div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between;">
                                    <span style="color:var(--accent-orange);">${{i+1}}.</span>
                                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;margin:0 4px;">
                                        ${{t.name || ('ID:' + t.resource_id)}}
                                    </span>
                                    <span style="color:var(--accent-green);white-space:nowrap;">
                                        ${{t.use_count}}×
                                    </span>
                                </div>
                            `).join('')}}
                        </div>
                    `;
                }}
                
                // 未使用纹理警告
                if (coldList.length > 0) {{
                    usageHtml += `
                        <details style="margin-top:8px;">
                            <summary style="font-size:11px;color:var(--text-muted);cursor:pointer;padding:4px 0;">
                                ❄️ 未使用纹理 (${{coldList.length}} 个，可能冗余) 
                                <span style="color:var(--accent-red);">-${{formatBytes(unusedWaste)}}</span>
                            </summary>
                            <div style="padding:8px 0;display:flex;flex-wrap:wrap;gap:6px;">
                                ${{coldList.map((t, i) => `
                                    <div onclick="selectTextureByResourceId(${{t.resource_id}})" style="display:flex;align-items:center;gap:4px;padding:4px 8px;background:var(--bg-secondary);border-radius:4px;font-size:10px;cursor:pointer;transition:background 0.15s;" onmouseover="this.style.background='var(--bg-hover)'" onmouseout="this.style.background='var(--bg-secondary)'">
                                        <div style="width:24px;height:24px;border-radius:3px;background:${{t.thumbnail ? 'none' : generateColorFromName(t.name || t.resource_id)}};display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden;">
                                            ${{t.thumbnail ? '<img src="' + t.thumbnail + '" style="width:100%;height:100%;object-fit:cover;">' : '<span style="color:white;font-size:7px;">' + (t.width || '?') + '</span>'}}
                                        </div>
                                        <div style="max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${{t.name || 'ID:' + t.resource_id}}">
                                            ${{t.name || 'ID:' + t.resource_id}}
                                        </div>
                                        <span style="color:var(--text-muted);font-size:9px;">(${{formatBytes(t.estimated_size)}})</span>
                                    </div>
                                `).join('')}}
                            </div>
                        </details>
                    `;
                }}
                
                usageHtml += '</div>';
                statsSection.insertAdjacentHTML('beforeend', usageHtml);
            }}
            
            // 保存热度数据供导出使用
            window.usageAnalysis = usageAnalysis;
        }}
        
        // ========== 虚拟滚动配置 ==========
        const VIRTUAL_SCROLL_THRESHOLD = 100;  // 超过此数量启用虚拟滚动
        const ITEM_HEIGHT = 52;  // 每个 texture-item 的高度 (px)
        const BUFFER_ITEMS = 5;  // 上下缓冲区条目数
        let virtualScrollEnabled = false;
        let scrollTop = 0;
        
        function renderTextureList() {{
            const list = document.getElementById('textureListApp');
            if (!list) return;
            
            const count = filteredTextures.length;
            document.getElementById('statsApp').textContent = `${{count}} 项`;
            
            // 小数据集直接渲染，大数据集启用虚拟滚动
            if (count <= VIRTUAL_SCROLL_THRESHOLD) {{
                virtualScrollEnabled = false;
                list.innerHTML = filteredTextures.map((tex, i) => renderTextureItem(tex, i)).join('');
                list.style.height = 'auto';
                list.onscroll = null;
            }} else {{
                virtualScrollEnabled = true;
                initVirtualScroll(list);
            }}
        }}
        
        function renderTextureItem(tex, index, isSelected = false) {{
            const selectedClass = isSelected ? ' selected' : '';
            // 生成占位符颜色
            const placeholderColor = generateColorFromName(tex.name || `Texture#${{tex.id}}`);
            const thumbContent = tex.thumbnail
                ? `<img src="${{tex.thumbnail}}" alt="" loading="lazy">`
                : `<div style="width:100%;height:100%;background:${{placeholderColor}};display:flex;align-items:center;justify-content:center;color:#fff;font-size:8px;text-shadow:0 1px 2px rgba(0,0,0,0.5);">${{tex.width}}</div>`;
            
            return `
                <div class="texture-item${{selectedClass}}" data-index="${{index}}" onclick="selectTexture(${{index}})" style="${{virtualScrollEnabled ? `position:absolute;top:${{index * ITEM_HEIGHT}}px;left:0;right:0;` : ''}}">
                    <div class="texture-item-thumb">
                        ${{thumbContent}}
                    </div>
                    <div class="texture-item-info">
                        <div class="texture-item-name">${{tex.name || `Texture #${{tex.id}}`}}</div>
                        <div class="texture-item-meta">
                            <span class="texture-item-dims">${{tex.width}}×${{tex.height}}</span>
                            <span style="margin-left:6px;">${{tex.format}}</span>
                        </div>
                    </div>
                </div>
            `;
        }}
        
        function initVirtualScroll(container) {{
            const totalHeight = filteredTextures.length * ITEM_HEIGHT;
            
            // 创建虚拟滚动容器
            container.innerHTML = `
                <div class="virtual-scroll-spacer" style="height:${{totalHeight}}px;position:relative;">
                    <div class="virtual-scroll-content" id="virtualContent"></div>
                </div>
            `;
            
            // 绑定滚动事件 (使用 requestAnimationFrame 节流)
            let rafId = null;
            container.onscroll = () => {{
                scrollTop = container.scrollTop;
                if (!rafId) {{
                    rafId = requestAnimationFrame(() => {{
                        renderVisibleItems();
                        rafId = null;
                    }});
                }}
            }};
            
            // 初始渲染 - 使用 rAF 确保 DOM 布局完成后再计算高度
            requestAnimationFrame(() => {{
                renderVisibleItems();
            }});
        }}
        
        let renderRetryCount = 0;
        const MAX_RENDER_RETRIES = 10;
        
        function renderVisibleItems() {{
            const container = document.getElementById('textureListApp');
            const content = document.getElementById('virtualContent');
            if (!container || !content) return;
            
            let viewportHeight = container.clientHeight;
            
            // 如果高度为0，使用回退策略
            if (viewportHeight === 0 || viewportHeight < 50) {{
                renderRetryCount++;
                if (renderRetryCount < MAX_RENDER_RETRIES) {{
                    // 延迟重试
                    requestAnimationFrame(() => renderVisibleItems());
                    return;
                }} else {{
                    // 达到最大重试次数，使用窗口高度的60%作为回退
                    viewportHeight = Math.max(400, window.innerHeight * 0.6);
                    console.warn('Virtual scroll: using fallback height:', viewportHeight);
                }}
            }}
            renderRetryCount = 0;  // 重置计数器
            const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - BUFFER_ITEMS);
            const endIndex = Math.min(
                filteredTextures.length,
                Math.ceil((scrollTop + viewportHeight) / ITEM_HEIGHT) + BUFFER_ITEMS
            );
            
            // 只渲染可见范围内的条目
            let html = '';
            for (let i = startIndex; i < endIndex; i++) {{
                const isSelected = (i === selectedTextureIndex);
                html += renderTextureItem(filteredTextures[i], i, isSelected);
            }}
            
            content.innerHTML = html;
            content.style.transform = `translateY(${{startIndex * ITEM_HEIGHT}}px)`;
        }}
        
        // 滚动到指定索引的纹理
        function scrollToTexture(index) {{
            if (!virtualScrollEnabled) return;
            
            const container = document.getElementById('textureListApp');
            if (!container) return;
            
            const targetTop = index * ITEM_HEIGHT;
            const viewportHeight = container.clientHeight;
            
            // 如果目标不在可视区域内，滚动到它
            if (targetTop < scrollTop || targetTop + ITEM_HEIGHT > scrollTop + viewportHeight) {{
                container.scrollTop = Math.max(0, targetTop - viewportHeight / 2 + ITEM_HEIGHT / 2);
            }}
        }}
        
        function selectTexture(index) {{
            selectedTextureIndex = index;
            const tex = filteredTextures[index];
            
            // 更新列表选中状态 (虚拟滚动模式下 DOM 元素数量与实际索引不一致)
            document.querySelectorAll('.texture-item').forEach((el) => {{
                const elIndex = parseInt(el.getAttribute('data-index'), 10);
                el.classList.toggle('selected', elIndex === index);
            }});
            
            // 显示预览图
            const img = document.getElementById('previewImgApp');
            const empty = document.getElementById('canvasEmpty');
            
            if (tex.thumbnail) {{
                img.src = tex.thumbnail;
                img.style.display = 'block';
                empty.style.display = 'none';
                
                // 显示颜色拾取器
                document.getElementById('colorPickerApp').style.display = 'flex';
            }} else {{
                // 无缩略图时生成动态 SVG 占位符
                const placeholderSvg = generatePlaceholderSvg(tex);
                img.src = placeholderSvg;
                img.style.display = 'block';
                empty.style.display = 'none';
                document.getElementById('colorPickerApp').style.display = 'none';
            }}
            
            // 更新属性面板
            updatePropPanel(tex);
            
            // 更新状态栏
            document.getElementById('statusTexture').textContent = tex.name || `#${{tex.id}}`;
            
            // 绘制直方图
            drawHistogramApp();
        }}
        
        // 通过 resource_id 选择纹理（用于右侧面板点击）
        function selectTextureByResourceId(resourceId) {{
            const index = filteredTextures.findIndex(tex => tex.id === resourceId || tex.id === parseInt(resourceId));
            if (index >= 0) {{
                selectTexture(index);
                // 滚动左侧列表到该纹理
                scrollToTextureIndex(index);
            }} else {{
                console.warn('Texture not found in filtered list:', resourceId);
            }}
        }}
        
        // 滚动到当前选中的纹理（中间面板定位按钮使用）
        function scrollToCurrentTexture() {{
            if (selectedTextureIndex >= 0) {{
                scrollToTextureIndex(selectedTextureIndex);
            }}
        }}
        
        // 滚动左侧列表到指定索引的纹理
        function scrollToTextureIndex(index) {{
            const list = document.getElementById('textureListApp');
            if (!list) return;
            
            if (virtualScrollEnabled) {{
                // 虚拟滚动模式：直接设置 scrollTop
                const targetTop = index * ITEM_HEIGHT;
                const viewportHeight = list.clientHeight || 400;
                // 滚动到让该项居中
                list.scrollTop = Math.max(0, targetTop - viewportHeight / 2 + ITEM_HEIGHT / 2);
            }} else {{
                // 普通模式：查找对应元素并滚动
                const item = list.querySelector(`[data-index="${{index}}"]`);
                if (item) {{
                    item.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    // 添加高亮动画
                    item.classList.add('jump-highlight');
                    setTimeout(() => item.classList.remove('jump-highlight'), 1500);
                }}
            }}
        }}
        
        // ========== 资源浏览器双列表功能 (TASK-205) ==========
        
        // Shader 列表状态
        let allShaders = [];              // 所有 Shader 数据
        let shaderIssueIds = new Set();   // 有问题的 Shader ID 集合
        let shaderFilterMode = 'all';     // 'all' | 'issues'
        let shaderSearchText = '';
        let selectedShaderIndex = -1;
        
        // TASK-209: Shader 到 Event 的映射（用于查看相关 Draw Call）
        let pipelineToEvents = {{}};      // {{ pipelineId: [eventEid, ...] }}
        
        // 纹理列表过滤状态
        let textureFilterMode = 'all';    // 'all' | 'issues'
        let textureIssueIds = new Set();  // 有问题的纹理 ID 集合
        
        // 初始化资源浏览器
        function initResourceBrowser() {{
            initTextureIssues();
            initShaderList();
            buildPipelineToEventsMap();   // TASK-209: 构建映射
            setupResourceSearchHandlers();
        }}
        
        // 初始化纹理问题 ID 集合
        function initTextureIssues() {{
            textureIssueIds.clear();
            if (optimizationData && optimizationData.items) {{
                optimizationData.items.forEach(item => {{
                    if (item.category === 'Texture' && item.resource_id) {{
                        textureIssueIds.add(item.resource_id);
                    }}
                }});
            }}
            updateTextureCountBadge();
        }}
        
        // 初始化 Shader 列表
        function initShaderList() {{
            allShaders = [];
            shaderIssueIds.clear();
            
            // TASK-205: 优先从 shaderData 加载完整 Shader 列表
            // shaderData 来自主 JSON 文件的 shaders 字段
            if (shaderData && shaderData.length > 0) {{
                // 首先从 optimizationData 收集有问题的 Shader
                const issuesByShader = new Map(); // shader id/name -> {{ issues: [], indices: [] }}
                
                if (optimizationData && optimizationData.items) {{
                    optimizationData.items.forEach((item, idx) => {{
                        if (item.category === 'Shader' && item.affected_resources) {{
                            item.affected_resources.forEach(shaderRef => {{
                                if (!issuesByShader.has(shaderRef)) {{
                                    issuesByShader.set(shaderRef, {{ issues: [], indices: [] }});
                                }}
                                const entry = issuesByShader.get(shaderRef);
                                entry.issues.push(item);
                                entry.indices.push(idx);
                            }});
                        }}
                    }});
                }}
                
                // 遍历 shaderData 构建 allShaders
                shaderData.forEach((shader, idx) => {{
                    const shaderId = shader.id || shader.resourceId || `shader_${{idx}}`;
                    const shaderName = shader.name || `Shader_${{shaderId}}`;
                    const shaderType = shader.type || shader.stage || 'PIPELINE';
                    
                    // 检查此 Shader 是否有优化建议
                    const issueData = issuesByShader.get(shaderId) || issuesByShader.get(shaderName) || {{ issues: [], indices: [] }};
                    const hasIssues = issueData.issues.length > 0;
                    
                    const id = `shader_${{idx}}`;
                    allShaders.push({{
                        id: id,
                        resourceId: shaderId,
                        name: shaderName,
                        type: normalizeShaderType(shaderType),
                        issueCount: issueData.issues.length,
                        issueIndices: issueData.indices,
                        severity: issueData.issues.some(i => i.severity === 'high') ? 'high' : 
                                  issueData.issues.some(i => i.severity === 'medium') ? 'medium' : 
                                  hasIssues ? 'low' : 'none',
                        issues: issueData.issues,
                        firstSeenEvent: shader.firstSeenEvent || 0,
                        bindCount: shader.bindCount || 0
                    }});
                    
                    if (hasIssues) {{
                        shaderIssueIds.add(id);
                    }}
                }});
            }} else if (optimizationData && optimizationData.items) {{
                // 回退：从 optimizationData 提取 Shader（旧逻辑）
                const shaderNamesMap = new Map();
                
                optimizationData.items.forEach((item, idx) => {{
                    if (item.category === 'Shader' && item.affected_resources) {{
                        item.affected_resources.forEach(shaderName => {{
                            if (!shaderNamesMap.has(shaderName)) {{
                                shaderNamesMap.set(shaderName, {{ issues: [], indices: [] }});
                            }}
                            const entry = shaderNamesMap.get(shaderName);
                            entry.issues.push(item);
                            entry.indices.push(idx);
                        }});
                    }}
                }});
                
                let shaderIdx = 0;
                shaderNamesMap.forEach((data, name) => {{
                    const id = `shader_${{shaderIdx++}}`;
                    allShaders.push({{
                        id: id,
                        name: name,
                        type: detectShaderTypeFromName(name),
                        issueCount: data.issues.length,
                        issueIndices: data.indices,
                        severity: data.issues.some(i => i.severity === 'high') ? 'high' : 
                                  data.issues.some(i => i.severity === 'medium') ? 'medium' : 'low',
                        issues: data.issues
                    }});
                    shaderIssueIds.add(id);
                }});
            }}
            
            updateShaderCountBadge();
            renderShaderList();
        }}
        
        // TASK-209: 构建 Pipeline/Shader 到 Event 的映射
        function buildPipelineToEventsMap() {{
            pipelineToEvents = {{}};
            
            // 从 eventPassData 中提取 Draw 事件，分析 relatedCalls 中的 vkCmdBindPipeline
            if (eventPassData && eventPassData.events) {{
                eventPassData.events.forEach(event => {{
                    // 兼容 eid / eventId 字段名
                    const eventId = event.eid || event.eventId;
                    if (!eventId) return;
                    
                    // 只处理 Draw 类型事件（兼容大小写）
                    const eventType = (event.type || '').toLowerCase();
                    if (eventType !== 'draw' && eventType !== 'drawindexed') return;
                    
                    // 从 relatedCalls 提取 pipeline ID
                    if (event.relatedCalls && Array.isArray(event.relatedCalls)) {{
                        event.relatedCalls.forEach(call => {{
                            // 匹配 vkCmdBindPipeline(pipelineBindPoint: X, pipeline: YYYYY)
                            const match = call.match(/vkCmdBindPipeline.*pipeline:\s*(\d+)/);
                            if (match) {{
                                const pipelineId = match[1];
                                if (!pipelineToEvents[pipelineId]) {{
                                    pipelineToEvents[pipelineId] = [];
                                }}
                                pipelineToEvents[pipelineId].push(eventId);
                            }}
                        }});
                    }}
                    
                    // 备用：从 pipelineState.shaders 提取（如果有）
                    if (event.pipelineState && event.pipelineState.shaders) {{
                        Object.values(event.pipelineState.shaders).forEach(shader => {{
                            const shaderId = shader.resourceId || shader.id;
                            if (shaderId) {{
                                if (!pipelineToEvents[shaderId]) {{
                                    pipelineToEvents[shaderId] = [];
                                }}
                                if (!pipelineToEvents[shaderId].includes(eventId)) {{
                                    pipelineToEvents[shaderId].push(eventId);
                                }}
                            }}
                        }});
                    }}
                }});
            }}
            
            console.log('TASK-209: Built pipelineToEvents mapping:', Object.keys(pipelineToEvents).length, 'pipelines');
        }}
        
        // 规范化 Shader 类型名称
        function normalizeShaderType(type) {{
            const t = (type || '').toUpperCase();
            if (t === 'PIPELINE' || t === 'GRAPHICS') return 'Pipeline';
            if (t.includes('VERTEX') || t === 'VS') return 'VS';
            if (t.includes('PIXEL') || t.includes('FRAGMENT') || t === 'PS' || t === 'FS') return 'PS';
            if (t.includes('COMPUTE') || t === 'CS') return 'CS';
            if (t.includes('GEOMETRY') || t === 'GS') return 'GS';
            if (t.includes('HULL') || t.includes('TESS_CONTROL') || t === 'HS') return 'HS';
            if (t.includes('DOMAIN') || t.includes('TESS_EVAL') || t === 'DS') return 'DS';
            return type || '??';
        }}
        
        // 从名称检测 Shader 类型
        function detectShaderTypeFromName(name) {{
            const n = (name || '').toLowerCase();
            if (n.endsWith('vs') || n.includes('_vs') || n.includes('vert')) return 'VS';
            if (n.endsWith('ps') || n.includes('_ps') || n.includes('frag') || n.includes('pixel')) return 'PS';
            if (n.endsWith('cs') || n.includes('_cs') || n.includes('compute')) return 'CS';
            if (n.endsWith('gs') || n.includes('_gs') || n.includes('geom')) return 'GS';
            if (n.endsWith('hs') || n.includes('_hs') || n.includes('hull')) return 'HS';
            if (n.endsWith('ds') || n.includes('_ds') || n.includes('domain')) return 'DS';
            return '??';
        }}
        
        // 更新纹理计数徽章
        function updateTextureCountBadge() {{
            const badge = document.getElementById('textureCountBadge');
            if (badge && typeof textures !== 'undefined') {{
                const total = textures.length;
                const issues = textureIssueIds.size;
                badge.textContent = `${{issues}}/${{total}}`;
            }}
        }}
        
        // 更新 Shader 计数徽章
        function updateShaderCountBadge() {{
            const badge = document.getElementById('shaderCountBadge');
            if (badge) {{
                const total = allShaders.length;
                const issues = shaderIssueIds.size;
                // 如果有问题的 shader 数量为 0，只显示总数
                badge.textContent = issues > 0 ? `${{issues}}/${{total}}` : `${{total}}`;
            }}
        }}
        
        // 设置搜索框事件监听
        function setupResourceSearchHandlers() {{
            // Shader 搜索
            const shaderSearch = document.getElementById('shaderSearchBox');
            if (shaderSearch) {{
                shaderSearch.addEventListener('input', (e) => {{
                    shaderSearchText = e.target.value.toLowerCase();
                    renderShaderList();
                }});
            }}
        }}
        
        // 渲染 Shader 列表
        function renderShaderList() {{
            const container = document.getElementById('shaderListApp');
            if (!container) return;
            
            // 过滤
            let filtered = allShaders;
            
            // 按模式过滤
            if (shaderFilterMode === 'issues') {{
                filtered = filtered.filter(s => shaderIssueIds.has(s.id));
            }}
            
            // 按搜索文本过滤
            if (shaderSearchText) {{
                filtered = filtered.filter(s => 
                    s.name.toLowerCase().includes(shaderSearchText) ||
                    s.type.toLowerCase().includes(shaderSearchText)
                );
            }}
            
            if (filtered.length === 0) {{
                container.innerHTML = `<div class="shader-empty">${{
                    shaderFilterMode === 'issues' ? '暂无 Shader 优化问题 🎉' : 
                    shaderSearchText ? '未找到匹配的 Shader' : '暂无 Shader 数据'
                }}</div>`;
                return;
            }}
            
            const html = filtered.map((shader, idx) => {{
                const hasIssue = shaderIssueIds.has(shader.id);
                const isSelected = selectedShaderIndex === idx;
                const typeClass = shader.type.toLowerCase();
                const severityIcon = shader.severity === 'high' ? '🔴' : 
                                     shader.severity === 'medium' ? '🟠' : '🟢';
                const issueText = shader.issueCount ? `${{shader.issueCount}} 项问题` : '';
                
                return `
                    <div class="shader-item${{hasIssue ? ' has-issue' : ''}}${{isSelected ? ' selected' : ''}} severity-${{shader.severity || 'low'}}" 
                         data-shader-id="${{shader.id}}" 
                         data-index="${{idx}}"
                         onclick="selectShaderItem('${{shader.id}}', ${{idx}})">
                        <span class="shader-item-icon">${{severityIcon}}</span>
                        <div class="shader-item-content">
                            <div class="shader-item-name">${{shader.name}}</div>
                            ${{issueText ? `<div class="shader-item-meta">${{issueText}}</div>` : ''}}
                        </div>
                        <span class="shader-item-type ${{typeClass}}">${{shader.type}}</span>
                    </div>
                `;
            }}).join('');
            
            container.innerHTML = html;
        }}
        
        // 切换资源区块折叠
        function toggleResourceSection(type) {{
            const section = document.getElementById(type + 'SectionPanel');
            if (section) {{
                section.classList.toggle('collapsed');
            }}
        }}
        
        // 设置纹理过滤模式
        function setTextureFilter(mode) {{
            textureFilterMode = mode;
            
            // 更新按钮状态
            document.getElementById('textureFilterAll').classList.toggle('active', mode === 'all');
            document.getElementById('textureFilterIssues').classList.toggle('active', mode === 'issues');
            
            // 重新渲染纹理列表
            renderTextureListFiltered();
        }}
        
        // 设置 Shader 过滤模式
        function setShaderFilter(mode) {{
            shaderFilterMode = mode;
            
            // 更新按钮状态
            document.getElementById('shaderFilterAll').classList.toggle('active', mode === 'all');
            document.getElementById('shaderFilterIssues').classList.toggle('active', mode === 'issues');
            
            // 重新渲染列表
            renderShaderList();
        }}
        
        // 按过滤模式渲染纹理列表
        function renderTextureListFiltered() {{
            if (typeof textures === 'undefined' || !textures) return;
            
            let filtered = textures;
            if (textureFilterMode === 'issues') {{
                filtered = textures.filter(t => textureIssueIds.has(t.id));
            }}
            
            // 调用原有的纹理列表渲染函数，传入过滤后的数据
            renderTextureListWithData(filtered);
        }}
        
        // 用指定数据渲染纹理列表
        function renderTextureListWithData(data) {{
            filteredTextures = data;
            renderTextureList();
        }}
        
        // 根据资源 ID 选择纹理并高亮
        function selectTextureByResourceId(resourceId) {{
            // 找到对应的索引
            const idx = filteredTextures.findIndex(t => t.id === resourceId);
            if (idx >= 0) {{
                selectTexture(idx);
                
                // 滚动到该项并高亮
                setTimeout(() => {{
                    const item = document.querySelector(`.texture-item[data-index="${{idx}}"]`);
                    if (item) {{
                        item.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        item.classList.add('jump-highlight');
                        setTimeout(() => item.classList.remove('jump-highlight'), 1500);
                    }}
                }}, 100);
            }}
        }}
        
        // 选择 Shader 项
        function selectShaderItem(shaderId, idx) {{
            selectedShaderIndex = idx;
            
            // 更新选中状态
            document.querySelectorAll('.shader-item').forEach((el, i) => {{
                el.classList.toggle('selected', i === idx);
            }});
            
            // TASK-209: 显示详情面板
            const shader = allShaders.find(s => s.id === shaderId);
            if (shader) {{
                showShaderDetails(shader);
            }}
        }}
        
        // TASK-209: 显示 Shader 详情面板
        function showShaderDetails(shader) {{
            const panel = document.getElementById('shaderDetailsPanel');
            const content = document.getElementById('shaderDetailsContent');
            const title = document.getElementById('shaderDetailsTitle');
            if (!panel || !content) return;
            
            // 设置标题
            title.textContent = shader.name || `Shader ${{shader.resourceId}}`;
            
            // 计算使用次数（通过 pipelineToEvents 映射）
            const usageCount = (pipelineToEvents[shader.resourceId] || []).length;
            
            // 构建详情 HTML
            let html = `
                <div class="shader-details-grid">
                    <div class="shader-detail-item">
                        <div class="shader-detail-label">Resource ID</div>
                        <div class="shader-detail-value">${{shader.resourceId || '-'}}</div>
                    </div>
                    <div class="shader-detail-item">
                        <div class="shader-detail-label">类型</div>
                        <div class="shader-detail-value type-${{shader.type.toLowerCase()}}">${{shader.type}}</div>
                    </div>
                    <div class="shader-detail-item">
                        <div class="shader-detail-label">首次出现</div>
                        <div class="shader-detail-value">Event #${{shader.firstSeenEvent || 0}}</div>
                    </div>
                    <div class="shader-detail-item">
                        <div class="shader-detail-label">Draw 调用</div>
                        <div class="shader-detail-value">${{usageCount}} 次</div>
                    </div>
                </div>
            `;
            
            // 优化问题摘要
            if (shader.issues && shader.issues.length > 0) {{
                html += `
                    <div class="shader-issues-summary">
                        <div class="shader-issues-title">⚠ ${{shader.issues.length}} 个优化建议</div>
                        ${{shader.issues.slice(0, 3).map(issue => `
                            <div class="shader-issue-item">${{issue.title || issue.type || '未知问题'}}</div>
                        `).join('')}}
                        ${{shader.issues.length > 3 ? `<div class="shader-issue-item" style="opacity:0.6">还有 ${{shader.issues.length - 3}} 个...</div>` : ''}}
                    </div>
                `;
            }} else {{
                html += `
                    <div class="shader-issues-summary no-issues">
                        <div class="shader-issues-title">✓ 暂无优化建议</div>
                    </div>
                `;
            }}
            
            // 操作按钮
            html += `
                <div class="shader-details-actions">
                    <button class="shader-action-btn" onclick="viewShaderInEvents('${{shader.resourceId}}')" ${{usageCount === 0 ? 'disabled style="opacity:0.5"' : ''}}>
                        🎮 查看相关 Event (${{usageCount}})
                    </button>
                    ${{shader.issueIndices && shader.issueIndices.length > 0 ? `
                        <button class="shader-action-btn secondary" onclick="scrollToOptimizationItem(${{shader.issueIndices[0]}})">
                            📋 跳转优化建议
                        </button>
                    ` : ''}}
                </div>
            `;
            
            // TASK-209-D: Shader 代码预览占位符
            html += `
                <div class="shader-code-preview">
                    <div class="shader-code-header">
                        <span class="shader-code-title">📜 着色器代码</span>
                        <span class="shader-code-badge">SPIR-V</span>
                    </div>
                    <div class="shader-code-placeholder">
                        <div class="code-unavailable-icon">🔒</div>
                        <div class="code-unavailable-text">反编译代码暂不可用</div>
                        <div class="code-unavailable-hint">需要在 Python 端集成 SPIRV-Cross 或导出反编译结果</div>
                    </div>
                </div>
            `;
            
            // TASK-209-E: 使用频率可视化（mini 图表）
            if (usageCount > 0 && eventPassData && eventPassData.events) {{
                const usageEvents = pipelineToEvents[shader.resourceId] || [];
                const totalEvents = eventPassData.events.length;
                const maxEid = Math.max(...eventPassData.events.map(e => e.eid || 0));
                
                // 构建简易时间轴
                const segments = [];
                const bucketSize = Math.ceil(maxEid / 20); // 20 个桶
                const buckets = new Array(20).fill(0);
                usageEvents.forEach(eid => {{
                    const bucket = Math.min(19, Math.floor(eid / bucketSize));
                    buckets[bucket]++;
                }});
                const maxBucket = Math.max(...buckets, 1);
                
                html += `
                    <div class="shader-usage-bar">
                        <div class="shader-usage-label">帧内使用分布</div>
                        <div class="shader-usage-chart">
                            ${{buckets.map((count, i) => `
                                <div class="shader-usage-segment" style="flex:1;opacity:${{0.2 + (count/maxBucket) * 0.8}}" title="区间 ${{i * bucketSize}}-${{(i+1) * bucketSize}}: ${{count}} 次"></div>
                            `).join('')}}
                        </div>
                    </div>
                `;
            }}
            
            content.innerHTML = html;
            panel.classList.add('active');
        }}
        
        // TASK-209: 隐藏 Shader 详情面板
        function hideShaderDetails() {{
            const panel = document.getElementById('shaderDetailsPanel');
            if (panel) panel.classList.remove('active');
        }}
        
        // TASK-209-B: 在 Event Browser 中查看 Shader 相关 Event
        function viewShaderInEvents(resourceId) {{
            // 切换到 Event Browser 视图
            showEventBrowser();
            
            // 设置搜索词为 pipeline ID，触发过滤
            const searchBox = document.getElementById('eventSearchBox');
            if (searchBox) {{
                // 设置 shaderFilter 全局变量用于过滤
                window.currentShaderFilter = resourceId;
                searchBox.value = `pipeline:${{resourceId}}`;
                searchBox.dispatchEvent(new Event('input'));
            }}
            
            // 高亮提示
            const eventEids = pipelineToEvents[resourceId] || [];
            if (eventEids.length > 0) {{
                // 滚动到第一个相关 Event
                setTimeout(() => {{
                    const firstEid = eventEids[0];
                    selectEvent(firstEid);
                    const node = document.querySelector(`.event-node[data-eid="${{firstEid}}"]`);
                    if (node) {{
                        node.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}
                }}, 300);
            }}
        }}
        
        // 从优化建议联动到 Shader 列表
        function highlightShaderFromOptimization(shaderId) {{
            // 切换到 Issues 模式并高亮
            setShaderFilter('issues');
            
            // 展开 Shader 区块
            const section = document.getElementById('shaderSectionPanel');
            if (section) section.classList.remove('collapsed');
            
            // 延迟后滚动并高亮
            setTimeout(() => {{
                const item = document.querySelector(`.shader-item[data-shader-id="${{shaderId}}"]`);
                if (item) {{
                    item.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    item.classList.add('selected');
                    item.style.boxShadow = '0 0 0 2px var(--accent-purple), 0 0 15px rgba(168, 85, 247, 0.3)';
                    setTimeout(() => {{ item.style.boxShadow = ''; }}, 2000);
                }}
            }}, 150);
        }}
        
        // 从优化建议联动到纹理列表
        function highlightTextureFromOptimization(textureId) {{
            // 切换到 Issues 模式
            setTextureFilter('issues');
            
            // 展开纹理区块
            const section = document.getElementById('textureSectionPanel');
            if (section) section.classList.remove('collapsed');
            
            // 延迟后选中并高亮
            setTimeout(() => {{
                selectTextureByResourceId(textureId);
            }}, 150);
        }}
        
        // 清除 Shader 过滤
        function clearShaderFilter() {{
            setShaderFilter('all');
            document.getElementById('shaderFilterBar').style.display = 'none';
        }}
        
        // 滚动到优化建议项
        function scrollToOptimizationItem(optimIndex) {{
            // 确保优化建议面板是展开状态
            const optimPanel = document.getElementById('optimizationPanel');
            const optimContent = document.getElementById('optimizationContent');
            if (optimPanel && optimContent) {{
                optimContent.style.display = 'block';
                const toggleIcon = document.getElementById('optimizationToggle');
                if (toggleIcon) toggleIcon.innerHTML = '&#9660;';
            }}
            
            // 滚动到对应卡片
            setTimeout(() => {{
                const optimCard = document.querySelector(`.optim-card[data-index="${{optimIndex}}"]`);
                if (optimCard) {{
                    optimCard.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    optimCard.style.boxShadow = '0 0 0 2px var(--accent-orange), 0 0 20px rgba(251, 146, 60, 0.3)';
                    optimCard.style.transition = 'box-shadow 0.3s ease';
                    setTimeout(() => {{ optimCard.style.boxShadow = ''; }}, 2000);
                }}
            }}, 100);
        }}
        
        function updatePropPanel(tex) {{
            document.getElementById('propId').textContent = tex.id;
            document.getElementById('propName').textContent = tex.name || '-';
            document.getElementById('propSize').textContent = `${{tex.width}}×${{tex.height}}${{tex.depth > 1 ? `×${{tex.depth}}` : ''}}`;
            document.getElementById('propFormat').textContent = tex.format;
            
            // Mipmap 分析
            const expectedMips = calculateExpectedMips(tex.width, tex.height);
            const actualMips = tex.mips || 1;
            const mipStatus = analyzeMipStatus(actualMips, expectedMips);
            document.getElementById('propMips').innerHTML = `${{actualMips}} <span class="mip-status ${{mipStatus.class}}">${{mipStatus.icon}}</span>`;
            
            document.getElementById('propLayers').textContent = tex.arrayLayers || 1;
            
            // 更新 VRAM 和分析信息
            updateTextureAnalysis(tex);
        }}
        
        // ========== 纹理分析功能 ==========
        
        // 计算期望的 Mipmap 级数
        function calculateExpectedMips(width, height) {{
            return Math.floor(Math.log2(Math.max(width, height))) + 1;
        }}
        
        // 分析 Mipmap 状态
        function analyzeMipStatus(actual, expected) {{
            if (actual >= expected) {{
                return {{ class: 'good', icon: '✓', desc: '完整 mipmap 链' }};
            }} else if (actual === 1) {{
                return {{ class: 'warn', icon: '⚠', desc: '无 mipmap，可能导致采样失真' }};
            }} else {{
                return {{ class: 'partial', icon: '◐', desc: `部分 mipmap (${{actual}}/${{expected}})` }};
            }}
        }}
        
        // 获取格式的每像素字节数
        function getBytesPerPixel(format) {{
            const bppMap = {{
                // 未压缩格式
                'R8G8B8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4, 'R8G8B8A8_SNORM': 4,
                'B8G8R8A8_UNORM': 4, 'B8G8R8A8_SRGB': 4,
                'R8G8B8_UNORM': 3, 'B8G8R8_UNORM': 3,
                'R16G16B16A16_FLOAT': 8, 'R16G16B16A16_UNORM': 8,
                'R32G32B32A32_FLOAT': 16, 'R32G32B32_FLOAT': 12,
                'R16G16_FLOAT': 4, 'R16G16_UNORM': 4,
                'R32G32_FLOAT': 8,
                'R8_UNORM': 1, 'R8_SNORM': 1,
                'R16_FLOAT': 2, 'R16_UNORM': 2,
                'R32_FLOAT': 4,
                // BC 压缩格式 (块压缩，每 4x4 像素)
                'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5, 'BC1_UNORM_SRGB': 0.5,
                'BC2_UNORM': 1, 'BC2_SRGB': 1,
                'BC3_UNORM': 1, 'BC3_SRGB': 1,
                'BC4_UNORM': 0.5, 'BC4_SNORM': 0.5,
                'BC5_UNORM': 1, 'BC5_SNORM': 1,
                'BC6H_UF16': 1, 'BC6H_SF16': 1,
                'BC7_UNORM': 1, 'BC7_SRGB': 1, 'BC7_UNORM_SRGB': 1,
                // 深度格式
                'D16_UNORM': 2, 'D24_UNORM_S8_UINT': 4, 'D32_FLOAT': 4, 'D32_FLOAT_S8X24_UINT': 8,
                // ASTC 格式 (移动端常见)
                'ASTC_4x4_UNORM': 1, 'ASTC_4x4_SRGB': 1,
                'ASTC_6x6_UNORM': 0.44, 'ASTC_8x8_UNORM': 0.25,
            }};
            return bppMap[format] || 4;  // 默认 4 bytes
        }}
        
        // 计算纹理 VRAM 占用
        function calculateTextureVRAM(tex) {{
            const bpp = getBytesPerPixel(tex.format);
            let basePixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
            
            // 计算所有 mip 级别的总像素
            let totalPixels = 0;
            let w = tex.width, h = tex.height;
            for (let m = 0; m < (tex.mips || 1); m++) {{
                totalPixels += w * h * (tex.depth || 1) * (tex.arrayLayers || 1);
                w = Math.max(1, Math.floor(w / 2));
                h = Math.max(1, Math.floor(h / 2));
            }}
            
            return totalPixels * bpp;
        }}
        
        // 更新纹理分析信息
        function updateTextureAnalysis(tex) {{
            const vram = calculateTextureVRAM(tex);
            const expectedMips = calculateExpectedMips(tex.width, tex.height);
            const isCompressed = tex.format.startsWith('BC') || tex.format.startsWith('ASTC');
            
            // 更新属性面板中的分析信息
            let analysisHtml = '';
            
            // VRAM 占用
            analysisHtml += `<div class="prop-row"><span class="prop-label">VRAM</span><span class="prop-value">${{formatBytes(vram)}}</span></div>`;
            
            // 压缩状态
            if (isCompressed) {{
                const uncompressedSize = tex.width * tex.height * 4 * (tex.mips > 1 ? 1.33 : 1);
                const ratio = (uncompressedSize / vram).toFixed(1);
                analysisHtml += `<div class="prop-row"><span class="prop-label">压缩率</span><span class="prop-value highlight">${{ratio}}:1</span></div>`;
            }} else {{
                analysisHtml += `<div class="prop-row"><span class="prop-label">压缩</span><span class="prop-value text-muted">未压缩</span></div>`;
            }}
            
            // Mipmap 建议
            if (tex.mips < expectedMips && tex.width >= 64) {{
                analysisHtml += `<div class="analysis-tip warn">⚠ 建议添加完整 mipmap 链 (${{expectedMips}} 级)</div>`;
            }}
            
            // 大纹理警告
            if (tex.width >= 4096 || tex.height >= 4096) {{
                analysisHtml += `<div class="analysis-tip info">ℹ 大尺寸纹理，注意内存占用</div>`;
            }}
            
            // 非 2 的幂警告
            const isPow2 = (n) => (n & (n - 1)) === 0;
            if (!isPow2(tex.width) || !isPow2(tex.height)) {{
                analysisHtml += `<div class="analysis-tip warn">⚠ 非 2 的幂尺寸，可能影响采样效率</div>`;
            }}
            
            // 使用位置信息 (热度分析)
            if (window.usageAnalysis) {{
                const texId = tex.id || tex.resource_id;
                
                // 首先在完整使用列表中查找（包含所有有使用数据的纹理）
                let usageEntry = (window.usageAnalysis.all_usage_list || []).find(t => 
                    (t.resource_id === texId) || (t.name === tex.name)
                );
                
                // 如果没有 all_usage_list，回退到 hot_list
                if (!usageEntry) {{
                    usageEntry = (window.usageAnalysis.hot_list || []).find(t => 
                        (t.resource_id === texId) || (t.name === tex.name)
                    );
                }}
                
                // 在冷点列表中查找（未使用的纹理）
                const coldEntry = (window.usageAnalysis.cold_list || []).find(t => 
                    (t.resource_id === texId) || (t.name === tex.name)
                );
                
                if (usageEntry) {{
                    analysisHtml += `<div class="prop-row" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                        <span class="prop-label">🔥 使用次数</span>
                        <span class="prop-value highlight" style="color:var(--accent-green);">${{usageEntry.use_count}}×</span>
                    </div>`;
                    
                    // 显示使用的 Event ID 范围
                    if (usageEntry.first_use_event !== undefined || usageEntry.last_use_event !== undefined) {{
                        const firstEID = usageEntry.first_use_event ?? '-';
                        const lastEID = usageEntry.last_use_event ?? '-';
                        analysisHtml += `<div class="prop-row">
                            <span class="prop-label">Event 范围</span>
                            <span class="prop-value">EID ${{firstEID}} → ${{lastEID}}</span>
                        </div>`;
                    }}
                    
                    // 显示使用的 Event ID 列表（如果有）
                    if (usageEntry.used_in_events && usageEntry.used_in_events.length > 0) {{
                        const events = usageEntry.used_in_events;
                        const displayEvents = events.slice(0, 8);
                        const moreCount = events.length - displayEvents.length;
                        
                        analysisHtml += `<div style="margin-top:4px;">
                            <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px;">被以下 Draw Call 使用: <span style="color:var(--accent-blue);font-size:9px;">(点击查看详情)</span></div>
                            <div style="display:flex;flex-wrap:wrap;gap:4px;">
                                ${{displayEvents.map(eid => `<span class="eid-tag" onclick="showEIDModal(${{eid}})" title="点击查看 Event ${{eid}} 详情">EID ${{eid}}</span>`).join('')}}
                                ${{moreCount > 0 ? `<span style="color:var(--text-muted);font-size:9px;padding:2px 4px;cursor:pointer;" onclick="showAllEIDsModal('${{usageEntry.name || usageEntry.resource_id}}', ${{JSON.stringify(events).replace(/"/g, '&quot;')}})" title="查看全部 ${{events.length}} 个 Event">+${{moreCount}} 更多...</span>` : ''}}
                            </div>
                        </div>`;
                    }}
                }} else if (coldEntry) {{
                    analysisHtml += `<div class="prop-row" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                        <span class="prop-label">❄️ 使用次数</span>
                        <span class="prop-value" style="color:var(--accent-red);">0 (未使用)</span>
                    </div>`;
                    analysisHtml += `<div class="analysis-tip warn" style="margin-top:4px;">
                        ⚠ 此纹理在当前帧中未被任何 Draw Call 引用，可能是冗余资源
                    </div>`;
                }} else {{
                    // 既不在 hot 也不在 cold 列表，可能是新纹理或分析数据不完整
                    analysisHtml += `<div class="prop-row" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                        <span class="prop-label">使用情况</span>
                        <span class="prop-value text-muted">无数据</span>
                    </div>`;
                }}
            }}
            
            const analysisContainer = document.getElementById('textureAnalysis');
            if (analysisContainer) {{
                analysisContainer.innerHTML = analysisHtml;
            }}
        }}
        
        // 格式化字节数
        function formatBytes(bytes) {{
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
        }}
        
        // 生成占位符 SVG（无缩略图时的回退）
        function generatePlaceholderSvg(tex) {{
            const name = tex.name || 'Texture ' + tex.id;
            let hash = 0;
            for (let i = 0; i < name.length; i++) {{
                hash = (hash * 31 + name.charCodeAt(i)) & 0xFFFFFFFF;
            }}
            const hue = hash % 360;
            const sat = 60 + (hash >> 8) % 20;
            const light = 45 + (hash >> 16) % 15;
            
            const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">' +
                '<rect fill="hsl(' + hue + ',' + sat + '%,' + light + '%)" width="256" height="256"/>' +
                '<text x="128" y="110" text-anchor="middle" fill="rgba(255,255,255,0.9)" font-size="22" font-family="Arial">' + tex.width + '×' + tex.height + '</text>' +
                '<text x="128" y="145" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="14" font-family="Arial">' + name.substring(0, 20) + '</text>' +
                '<text x="128" y="175" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="11" font-family="Arial">' + tex.format + '</text>' +
                '</svg>';
            
            return 'data:image/svg+xml;base64,' + btoa(svg);
        }}
        
        function updateAppStats() {{
            // 复用原有统计逻辑
            document.getElementById('statTotalApp').textContent = textures.length;
            
            const formats = new Set(textures.map(t => t.format));
            document.getElementById('statFormatsApp').textContent = formats.size;
            
            if (textures.length > 0) {{
                const avgW = Math.round(textures.reduce((s, t) => s + t.width, 0) / textures.length);
                const avgH = Math.round(textures.reduce((s, t) => s + t.height, 0) / textures.length);
                document.getElementById('statAvgApp').textContent = `${{avgW}}×${{avgH}}`;
            }}
            
            // VRAM 计算
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC7_UNORM': 1,
            }};
            
            let totalBytes = 0;
            textures.forEach(tex => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                totalBytes += pixels * bpp;
            }});
            
            const mb = (totalBytes / (1024 * 1024)).toFixed(1);
            document.getElementById('statVRAMApp').textContent = `${{mb}} MB`;
            
            // 渲染 VRAM 分布图表
            renderVRAMCharts();
        }}
        
        // VRAM 分布图表渲染函数
        function renderVRAMCharts() {{
            renderVRAMSummary();
            renderFormatPieChart();
            renderSizeBarChart();
            renderTopTexturesChart();
        }}
        
        // VRAM 总结统计卡片
        function renderVRAMSummary() {{
            const compressedFormats = ['BC1', 'BC3', 'BC4', 'BC5', 'BC6', 'BC7', 'ASTC', 'ETC2', 'DXT'];
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC7_UNORM': 1,
                'ASTC_4x4_UNORM': 1, 'ASTC_8x8_UNORM': 0.5,
            }};
            
            let totalBytes = 0;
            let compressedBytes = 0;
            let wastedBytes = 0;
            
            textures.forEach(tex => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                const bytes = pixels * bpp;
                totalBytes += bytes;
                
                // 检查是否为压缩格式
                const fmtPrefix = tex.format.split('_')[0];
                if (compressedFormats.some(cf => fmtPrefix.startsWith(cf))) {{
                    compressedBytes += bytes;
                }}
                
                // 检查潜在浪费：无mip的大纹理、未压缩的普通纹理
                const maxDim = Math.max(tex.width, tex.height);
                if (maxDim >= 512 && tex.mips <= 1) {{
                    wastedBytes += bytes * 0.3; // 无mip可能多加载30%
                }}
                if (maxDim >= 256 && !compressedFormats.some(cf => fmtPrefix.startsWith(cf)) && bpp >= 4) {{
                    wastedBytes += bytes * 0.5; // 未压缩可节省50%
                }}
            }});
            
            // 更新统计卡片
            const totalEl = document.getElementById('vramTotal');
            if (totalEl) {{
                const mb = (totalBytes / (1024 * 1024)).toFixed(1);
                totalEl.textContent = `${{mb}} MB`;
            }}
            
            const compressedEl = document.getElementById('vramCompressed');
            if (compressedEl) {{
                const pct = totalBytes > 0 ? ((compressedBytes / totalBytes) * 100).toFixed(0) : 0;
                compressedEl.textContent = `${{pct}}%`;
                compressedEl.classList.toggle('good', pct >= 60);
            }}
            
            const wastedEl = document.getElementById('vramWasted');
            if (wastedEl) {{
                const mb = (wastedBytes / (1024 * 1024)).toFixed(1);
                wastedEl.textContent = `~${{mb}} MB`;
            }}
        }}
        
        function renderFormatPieChart() {{
            // 按格式统计 VRAM
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC7_UNORM': 1,
                'ASTC_4x4_UNORM': 1, 'ASTC_8x8_UNORM': 0.5, 'ETC2_RGB8_UNORM': 0.5,
            }};
            
            const formatStats = {{}};
            let totalBytes = 0;
            
            textures.forEach(tex => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                const bytes = pixels * bpp;
                
                // 简化格式名（取前缀）
                const fmtKey = tex.format.split('_')[0] || tex.format;
                formatStats[fmtKey] = (formatStats[fmtKey] || 0) + bytes;
                totalBytes += bytes;
            }});
            
            // 排序取 Top 5
            const sorted = Object.entries(formatStats)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
            
            // 生成饼图渐变
            const colors = ['#a78bfa', '#60a5fa', '#34d399', '#fbbf24', '#f87171'];
            let gradientStops = [];
            let currentDeg = 0;
            
            sorted.forEach(([fmt, bytes], i) => {{
                const pct = totalBytes > 0 ? (bytes / totalBytes) : 0;
                const deg = pct * 360;
                gradientStops.push(`${{colors[i]}} ${{currentDeg}}deg ${{currentDeg + deg}}deg`);
                currentDeg += deg;
            }});
            
            // 填充剩余部分（其他格式）
            if (currentDeg < 360) {{
                gradientStops.push(`#4b5563 ${{currentDeg}}deg 360deg`);
            }}
            
            // 应用饼图
            const pie = document.getElementById('formatPieChart');
            if (pie) {{
                pie.style.background = `conic-gradient(${{gradientStops.join(', ')}})`;
            }}
            
            // 更新中心文字
            const inner = document.getElementById('formatPieInner');
            if (inner) {{
                const mb = (totalBytes / (1024 * 1024)).toFixed(1);
                inner.textContent = `${{mb}} MB`;
            }}
            
            // 生成图例
            const legend = document.getElementById('formatLegend');
            if (legend) {{
                legend.innerHTML = sorted.map(([fmt, bytes], i) => {{
                    const pct = totalBytes > 0 ? ((bytes / totalBytes) * 100).toFixed(0) : 0;
                    return `<div class="legend-item" onclick="filterByFormat('${{fmt}}')">
                        <div class="legend-color" style="background:${{colors[i]}}"></div>
                        <span>${{fmt}} ${{pct}}%</span>
                    </div>`;
                }}).join('');
            }}
        }}
        
        function renderSizeBarChart() {{
            // 按尺寸分类
            const sizeCategories = {{
                '4K+': {{ min: 3840, bytes: 0, count: 0 }},
                '2K': {{ min: 1920, max: 3839, bytes: 0, count: 0 }},
                '1K': {{ min: 1024, max: 1919, bytes: 0, count: 0 }},
                '512': {{ min: 512, max: 1023, bytes: 0, count: 0 }},
                '256': {{ min: 256, max: 511, bytes: 0, count: 0 }},
                '<256': {{ max: 255, bytes: 0, count: 0 }}
            }};
            
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC7_UNORM': 1,
            }};
            
            let totalBytes = 0;
            let maxBytes = 0;
            
            textures.forEach(tex => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                const bytes = pixels * bpp;
                totalBytes += bytes;
                
                const maxDim = Math.max(tex.width, tex.height);
                
                for (const [cat, cfg] of Object.entries(sizeCategories)) {{
                    const minOk = !cfg.min || maxDim >= cfg.min;
                    const maxOk = !cfg.max || maxDim <= cfg.max;
                    if (minOk && maxOk) {{
                        cfg.bytes += bytes;
                        cfg.count++;
                        if (cfg.bytes > maxBytes) maxBytes = cfg.bytes;
                        break;
                    }}
                }}
            }});
            
            // 渲染柱状图
            const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'];
            const chart = document.getElementById('sizeBarChart');
            if (chart) {{
                chart.innerHTML = Object.entries(sizeCategories).map(([cat, cfg], i) => {{
                    const pct = maxBytes > 0 ? (cfg.bytes / maxBytes * 100) : 0;
                    const mb = (cfg.bytes / (1024 * 1024)).toFixed(1);
                    return `<div class="bar-row">
                        <div class="bar-label">${{cat}}</div>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:${{pct}}%;background:${{colors[i]}}"></div>
                        </div>
                        <div class="bar-value">${{mb}} MB</div>
                    </div>`;
                }}).join('');
            }}
        }}
        
        // Top 10 最大纹理柱状图
        function renderTopTexturesChart() {{
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC7_UNORM': 1,
                'ASTC_4x4_UNORM': 1, 'ASTC_8x8_UNORM': 0.5,
            }};
            
            // 计算每个纹理的 VRAM 并排序
            const texturesWithSize = textures.map((tex, idx) => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                const bytes = pixels * bpp;
                return {{ tex, idx, bytes }};
            }}).sort((a, b) => b.bytes - a.bytes);
            
            // 取前 10 个
            const top10 = texturesWithSize.slice(0, 10);
            const maxBytes = top10.length > 0 ? top10[0].bytes : 0;
            
            // 生成颜色渐变（从红到蓝）
            const chart = document.getElementById('topTexturesChart');
            if (!chart) return;
            
            chart.innerHTML = top10.map((item, i) => {{
                const pct = maxBytes > 0 ? (item.bytes / maxBytes * 100) : 0;
                const mb = (item.bytes / (1024 * 1024)).toFixed(2);
                const name = item.tex.name || `Tex_${{item.tex.resourceId}}`;
                const shortName = name.length > 20 ? name.slice(0, 18) + '...' : name;
                const hue = 0 + (i / 10) * 240; // 从红(0)到蓝(240)
                const color = `hsl(${{hue}}, 70%, 55%)`;
                
                return `<div class="bar-row clickable" onclick="jumpToTexture(${{item.idx}})" title="${{name}}">
                    <div class="bar-label">#${{i + 1}}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${{pct}}%;background:${{color}}"></div>
                    </div>
                    <div class="bar-value">${{mb}} MB</div>
                </div>`;
            }}).join('');
        }}
        
        // 点击 Top 10 柱状图跳转到纹理
        function jumpToTexture(index) {{
            if (typeof selectTextureByIndex === 'function') {{
                selectTextureByIndex(index);
            }} else {{
                // 兼容：直接滚动并选中
                scrollToTextureIndex(index);
                const tex = textures[index];
                if (tex) {{
                    currentSelectedTexture = tex;
                    showTextureDetail(tex);
                }}
            }}
        }}
        
        function filterByFormat(format) {{
            // 点击图例时筛选该格式的纹理
            const searchBox = document.getElementById('searchBoxApp');
            if (searchBox) {{
                searchBox.value = format;
                searchBox.dispatchEvent(new Event('input'));
            }}
        }}
        
        // ========== 性能分析面板函数 (TASK-008) ==========
        
        function togglePerformancePanel() {{
            const content = document.getElementById('performanceContent');
            const toggle = document.getElementById('performanceToggle');
            if (content.classList.contains('collapsed')) {{
                content.classList.remove('collapsed');
                toggle.classList.remove('collapsed');
            }} else {{
                content.classList.add('collapsed');
                toggle.classList.add('collapsed');
            }}
        }}
        
        function renderPerformancePanel() {{
            const panel = document.getElementById('performancePanel');
            const scoreEl = document.getElementById('performanceScore');
            const metricsEl = document.getElementById('performanceMetrics');
            const issuesEl = document.getElementById('performanceIssues');
            
            // 隐藏面板如果没有数据
            if (!performanceData || typeof performanceData !== 'object') {{
                panel.style.display = 'none';
                return;
            }}
            
            panel.style.display = 'block';
            
            // 1. 渲染分数徽章
            const score = performanceData.overall_score ?? performanceData.score ?? '--';
            const numScore = parseInt(score);
            let scoreClass = 'good';
            if (numScore < 50) scoreClass = 'critical';
            else if (numScore < 70) scoreClass = 'poor';
            else if (numScore < 85) scoreClass = 'medium';
            
            scoreEl.textContent = score;
            scoreEl.className = `performance-score ${{scoreClass}}`;
            
            // 2. 渲染指标卡片
            const metrics = performanceData.metrics || {{}};
            const metricsHtml = Object.entries(metrics).map(([key, val]) => {{
                const label = key.replace(/_/g, ' ').toUpperCase();
                return `
                    <div class="performance-metric">
                        <div class="performance-metric-value">${{val}}</div>
                        <div class="performance-metric-label">${{label}}</div>
                    </div>
                `;
            }}).join('');
            metricsEl.innerHTML = metricsHtml || '<div style="padding:16px;text-align:center;color:#888;">No metrics available</div>';
            
            // 3. 渲染问题列表
            const issues = performanceData.issues || [];
            if (issues.length === 0) {{
                issuesEl.innerHTML = `
                    <li class="performance-empty">
                        <div class="performance-empty-icon">✓</div>
                        <div>No performance issues detected!</div>
                    </li>
                `;
            }} else {{
                issuesEl.innerHTML = issues.map(issue => {{
                    const severity = issue.severity || 'info';
                    const rule = issue.rule_id || issue.rule || '';
                    const title = issue.title || issue.message || 'Issue';
                    const message = issue.message || issue.description || '';
                    const suggestion = issue.suggestion || '';
                    
                    return `
                        <li class="performance-issue">
                            <div class="performance-severity ${{severity}}"></div>
                            <div class="performance-issue-content">
                                <div class="performance-issue-title">
                                    ${{title}}
                                    ${{rule ? `<span class="performance-issue-rule">${{rule}}</span>` : ''}}
                                </div>
                                <div class="performance-issue-message">${{message}}</div>
                                ${{suggestion ? `<div class="performance-issue-suggestion">💡 ${{suggestion}}</div>` : ''}}
                            </div>
                        </li>
                    `;
                }}).join('');
            }}
        }}
        
        // ========== 优化建议面板函数 (TASK-009) ==========
        
        function toggleOptimizationPanel() {{
            const content = document.getElementById('optimizationContent');
            const toggle = document.getElementById('optimizationToggle');
            if (content.style.display === 'none') {{
                content.style.display = 'block';
                toggle.innerHTML = '&#9660;';
            }} else {{
                content.style.display = 'none';
                toggle.innerHTML = '&#9654;';
            }}
        }}
        
        function renderOptimizationPanel() {{
            const panel = document.getElementById('optimizationPanel');
            const countBadge = document.getElementById('optimizationCount');
            const summaryDiv = document.getElementById('optimizationSummary');
            const listEl = document.getElementById('optimizationList');
            
            // 隐藏面板如果没有数据
            if (!optimizationData || !optimizationData.items || optimizationData.items.length === 0) {{
                panel.style.display = 'none';
                return;
            }}
            
            panel.style.display = 'block';
            const items = optimizationData.items;
            countBadge.textContent = items.length;
            
            // 格式化节省的字节
            function formatBytes(bytes) {{
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
            }}
            
            // 总结
            const totalSavings = optimizationData.total_savings_bytes || 0;
            summaryDiv.innerHTML = `
                <strong>Potential VRAM Savings:</strong> ${{formatBytes(totalSavings)}} 
                <span style="color:#888;">(${{items.length}} issues found)</span>
            `;
            
            // 优先级映射
            const priorityClass = {{
                'CRITICAL': 'priority-critical',
                'HIGH': 'priority-high',
                'MEDIUM': 'priority-medium',
                'LOW': 'priority-low'
            }};
            
            // 渲染列表 (TASK-205: 添加 data-index 用于 Shader 列表定位)
            listEl.innerHTML = items.map((item, idx) => `
                <li class="optimization-item optim-card" data-index="${{idx}}">
                    <span class="priority-dot ${{priorityClass[item.priority] || 'priority-low'}}"></span>
                    <span class="optimization-item-type">[${{item.category}}]</span>
                    <span class="optimization-item-desc">${{item.title}}: ${{item.description}}</span>
                    ${{item.estimated_savings_bytes > 0 ? `<span class="optimization-item-savings">-${{formatBytes(item.estimated_savings_bytes)}}</span>` : ''}}
                </li>
            `).join('');
        }}
        
        // 在左侧面板中渲染优化建议 (TASK-009)
        function renderOptimizationPanelInSidebar() {{
            if (!optimizationData || !optimizationData.items || optimizationData.items.length === 0) {{
                return;
            }}
            
            const statsSection = document.querySelector('#sectionStats .prop-section-content');
            if (!statsSection) return;
            
            const items = optimizationData.items;
            const totalSavings = optimizationData.total_savings_bytes || 0;
            
            // 格式化字节数
            function formatBytes(bytes) {{
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
            }}
            
            // 优先级样式
            const priorityColors = {{
                'CRITICAL': '#ff4444',
                'HIGH': '#ff8800',
                'MEDIUM': '#ffcc00',
                'LOW': '#44aa44'
            }};
            
            // 构建 HTML - 点击筛选主纹理列表 (方案B)
            let itemsHtml = items.map((item, idx) => {{
                const color = priorityColors[item.priority] || '#888';
                const savings = item.estimated_savings_bytes > 0 ? 
                    `<span style="color:#4CAF50;margin-left:8px;">-${{formatBytes(item.estimated_savings_bytes)}}</span>` : '';
                
                // 受影响的资源列表
                const resources = item.affected_resources || [];
                const hasResources = resources.length > 0;
                const resourceCount = resources.length;
                
                return `
                    <div class="optim-item" style="border-left: 3px solid ${{color}}; padding-left: 8px; margin: 4px 0; cursor: ${{hasResources ? 'pointer' : 'default'}};" 
                         onclick="${{hasResources ? `applyOptimizationFilter(${{idx}})` : ''}}"
                         title="${{hasResources ? '点击筛选纹理列表' : ''}}">
                        <span style="color:${{color}};">●</span> 
                        <span style="color:#aaa;">[${{item.category}}]</span> 
                        ${{item.title}}
                        ${{hasResources ? `<span style="color:#888;font-size:11px;"> (${{resourceCount}}个) →</span>` : ''}}
                        ${{savings}}
                    </div>
                `;
            }}).join('');
            
            const optimHtml = `
                <div class="optimization-suggestions" style="margin-top: 16px; border-top: 1px solid #444; padding-top: 12px;">
                    <div class="issue-summary" style="color:#4CAF50; font-weight:bold; margin-bottom:8px;">
                        🎯 优化建议 (${{items.length}})
                    </div>
                    <div style="color:#4CAF50; font-size:14px; margin-bottom:8px;">
                        预计可节省: ${{formatBytes(totalSavings)}}
                    </div>
                    ${{itemsHtml}}
                </div>
            `;
            
            statsSection.insertAdjacentHTML('beforeend', optimHtml);
        }}
        
        // 应用优化建议筛选 (方案B) - TASK-205: 支持 Shader 和 Texture 双列表联动
        function applyOptimizationFilter(idx) {{
            if (!optimizationData || !optimizationData.items[idx]) return;
            
            const item = optimizationData.items[idx];
            const resources = item.affected_resources || [];
            if (resources.length === 0) return;
            
            // 保存筛选状态
            currentOptimizationFilter = {{
                title: item.title,
                category: item.category,
                resourceNames: resources
            }};
            
            // TASK-205: 根据类别联动到对应列表
            if (item.category === 'Shader') {{
                // Shader 类别 - 联动到 Shader 列表
                applyShaderOptimizationFilter(item, resources, idx);
            }} else {{
                // 默认 Texture 类别 - 联动到纹理列表
                applyTextureOptimizationFilter(item, resources);
            }}
        }}
        
        // Shader 优化建议联动
        function applyShaderOptimizationFilter(item, resources, idx) {{
            // 切换到 Issues 模式
            setShaderFilter('issues');
            
            // 展开 Shader 区块
            const section = document.getElementById('shaderSectionPanel');
            if (section) section.classList.remove('collapsed');
            
            // 找到对应的 Shader 并高亮
            if (resources.length > 0) {{
                const targetName = resources[0]; // 取第一个资源名称
                const shader = allShaders.find(s => s.name === targetName);
                if (shader) {{
                    setTimeout(() => {{
                        const item = document.querySelector(`.shader-item[data-shader-id="${{shader.id}}"]`);
                        if (item) {{
                            item.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            item.classList.add('selected');
                            item.style.boxShadow = '0 0 0 2px var(--accent-purple), 0 0 15px rgba(168, 85, 247, 0.4)';
                            setTimeout(() => {{ item.style.boxShadow = ''; }}, 2000);
                        }}
                    }}, 150);
                }}
            }}
        }}
        
        // Texture 优化建议联动
        function applyTextureOptimizationFilter(item, resources) {{
            // 切换到 Issues 模式
            setTextureFilter('issues');
            
            // 展开纹理区块
            const section = document.getElementById('textureSectionPanel');
            if (section) section.classList.remove('collapsed');
            
            // 更新筛选提示条
            const filterBar = document.getElementById('optimFilterBar');
            const filterTitle = document.getElementById('optimFilterTitle');
            const filterCount = document.getElementById('optimFilterCount');
            
            // 按资源名称筛选纹理（更精确的匹配）
            const matchedTextures = textures.filter(tex => {{
                const texName = tex.name || `Texture #${{tex.id}}`;
                return resources.some(r => {{
                    // 提取资源名称（去除尺寸信息如 "(1024×1024, 50)"）
                    const resourceName = r.replace(/\s*\([^)]+\)$/, '').trim();
                    return texName === resourceName || texName.includes(resourceName) || resourceName.includes(texName);
                }});
            }});
            
            if (filterBar && filterTitle && filterCount) {{
                filterBar.style.display = 'block';
                filterTitle.textContent = item.title;
                filterCount.textContent = `(${{matchedTextures.length}}/${{resources.length}} 匹配)`;
            }}
            
            // 如果有匹配的纹理，滚动到第一个
            if (matchedTextures.length > 0) {{
                setTimeout(() => {{
                    selectTextureByResourceId(matchedTextures[0].id);
                }}, 150);
            }}
        }}
        
        // 清除优化建议筛选
        function clearOptimizationFilter() {{
            currentOptimizationFilter = null;
            filteredTextures = [...textures];
            
            // 隐藏筛选提示条
            const filterBar = document.getElementById('optimFilterBar');
            if (filterBar) filterBar.style.display = 'none';
            
            // 清空搜索框
            const searchBox = document.getElementById('searchBoxApp');
            if (searchBox) searchBox.value = '';
            
            // 重新渲染
            renderTextureList();
        }}
        
        function setupAppEventListeners() {{
            // 搜索框
            const searchBox = document.getElementById('searchBoxApp');
            if (searchBox) {{
                searchBox.addEventListener('input', () => {{
                    const query = searchBox.value.toLowerCase();
                    filteredTextures = textures.filter(tex => {{
                        return !query || 
                            (tex.name && tex.name.toLowerCase().includes(query)) ||
                            String(tex.id).includes(query);
                    }});
                    renderTextureList();
                }});
            }}
            
            // 排序选择
            const sortSelect = document.getElementById('sortSelectApp');
            if (sortSelect) {{
                sortSelect.addEventListener('change', () => {{
                    const key = sortSelect.value;
                    filteredTextures.sort((a, b) => {{
                        if (key === 'size') return (b.width * b.height) - (a.width * a.height);
                        if (key === 'name') return (a.name || '').localeCompare(b.name || '');
                        if (key === 'format') return a.format.localeCompare(b.format);
                        return a.id - b.id;
                    }});
                    renderTextureList();
                }});
            }}
            
            // 预览图交互
            const img = document.getElementById('previewImgApp');
            if (img) {{
                img.addEventListener('mousemove', pickColorApp);
            }}
            
            // 键盘导航 (上下箭头切换纹理)
            document.addEventListener('keydown', (e) => {{
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                
                if (e.key === 'ArrowDown') {{
                    e.preventDefault();
                    const nextIndex = Math.min(filteredTextures.length - 1, selectedTextureIndex + 1);
                    if (nextIndex !== selectedTextureIndex) {{
                        selectTexture(nextIndex);
                        scrollToTexture(nextIndex);
                    }}
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    const prevIndex = Math.max(0, selectedTextureIndex - 1);
                    if (prevIndex !== selectedTextureIndex) {{
                        selectTexture(prevIndex);
                        scrollToTexture(prevIndex);
                    }}
                }} else if (e.key === 'Home') {{
                    e.preventDefault();
                    selectTexture(0);
                    scrollToTexture(0);
                }} else if (e.key === 'End') {{
                    e.preventDefault();
                    const lastIndex = filteredTextures.length - 1;
                    selectTexture(lastIndex);
                    scrollToTexture(lastIndex);
                }}
            }});
        }}
        
        // 缩放控制
        function zoomImageApp(delta) {{
            appZoom = Math.max(0.1, Math.min(10, appZoom + delta));
            applyZoomApp();
        }}
        
        function resetZoomApp() {{
            appZoom = 1;
            applyZoomApp();
        }}
        
        function applyZoomApp() {{
            const img = document.getElementById('previewImgApp');
            if (img) {{
                img.style.transform = `scale(${{appZoom}})`;
            }}
            document.getElementById('zoomDisplayApp').textContent = `${{Math.round(appZoom * 100)}}%`;
            document.getElementById('statusZoom').textContent = `${{Math.round(appZoom * 100)}}%`;
        }}
        
        // 通道切换
        function switchChannelApp(channel) {{
            appChannel = channel;
            
            // 更新按钮状态
            document.querySelectorAll('.canvas-toolbar .channel-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.channel === channel);
            }});
            
            // 应用通道视图
            if (selectedTextureIndex >= 0) {{
                const tex = filteredTextures[selectedTextureIndex];
                const img = document.getElementById('previewImgApp');
                
                if (channel === 'rgb') {{
                    img.src = tex.thumbnail;
                    img.style.filter = '';
                }} else if (tex.channels && tex.channels[channel]) {{
                    img.src = tex.channels[channel];
                    img.style.filter = '';
                }} else {{
                    // 无通道数据，使用滤镜模拟
                    img.src = tex.thumbnail;
                    const filters = {{
                        'r': 'grayscale(100%) sepia(100%) hue-rotate(-50deg) saturate(600%)',
                        'g': 'grayscale(100%) sepia(100%) hue-rotate(50deg) saturate(600%)',
                        'b': 'grayscale(100%) sepia(100%) hue-rotate(180deg) saturate(600%)',
                        'a': 'grayscale(100%)'
                    }};
                    img.style.filter = filters[channel] || '';
                }}
            }}
        }}
        
        // 颜色拾取
        function pickColorApp(e) {{
            const img = e.target;
            const rect = img.getBoundingClientRect();
            const x = Math.floor((e.clientX - rect.left) / rect.width * img.naturalWidth);
            const y = Math.floor((e.clientY - rect.top) / rect.height * img.naturalHeight);
            
            document.getElementById('colorCoordApp').textContent = `${{x}},${{y}}`;
            
            // 简化版：只显示坐标，实际拾色需要 canvas
            document.getElementById('colorHexApp').textContent = `@${{x}},${{y}}`;
        }}
        
        // 属性面板折叠
        function togglePropSection(name) {{
            const section = document.getElementById('section' + name.charAt(0).toUpperCase() + name.slice(1));
            if (section) {{
                section.classList.toggle('collapsed');
            }}
        }}
        
        // 面板折叠
        function togglePanel(which) {{
            if (which === 'left') {{
                document.getElementById('panelLeft').classList.toggle('collapsed');
            }} else if (which === 'right') {{
                document.getElementById('panelRight').classList.toggle('collapsed');
            }}
        }}
        
        // 视图模式切换: 'app', 'grid', 'event'
        function toggleViewMode() {{
            // 从任意视图返回主视图，或从主视图切换到网格视图
            if (viewMode === 'app') {{
                viewMode = 'grid';
            }} else {{
                viewMode = 'app';
            }}
            updateViewMode();
        }}
        
        function updateViewMode() {{
            document.getElementById('appContainer').style.display = viewMode === 'app' ? 'flex' : 'none';
            document.getElementById('gridContainer').classList.toggle('show', viewMode === 'grid');
            document.getElementById('eventBrowserContainer').classList.toggle('show', viewMode === 'event');
            
            document.body.style.overflow = viewMode === 'app' ? 'hidden' : 'auto';
            document.body.style.height = viewMode === 'app' ? '100vh' : 'auto';
            
            // 更新按钮文字
            const btn = document.getElementById('viewToggleBtn');
            if (btn) {{
                btn.textContent = viewMode === 'app' ? '📐 网格视图' : '🖼️ 返回主视图';
            }}
        }}
        
        // 显示 Event Browser
        function showEventBrowser() {{
            viewMode = 'event';
            updateViewMode();
            initEventBrowser();
        }}
        
        // ========== Event Browser 逻辑 ==========
        let currentEventTab = 'summary';
        let selectedEventEid = null;
        let eventExpandState = {{}};  // 记录展开/折叠状态
        
        function initEventBrowser() {{
            if (!eventPassData || !eventPassData.events) {{
                console.log('No event data available');
                return;
            }}
            
            // TASK-210: 规范化事件字段名（eventId → eid）
            eventPassData.events.forEach(event => {{
                if (!event.eid && event.eventId) {{
                    event.eid = event.eventId;
                }}
            }});
            
            // 更新头部统计
            document.getElementById('eventApiType').textContent = eventPassData.apiType || 'Unknown';
            document.getElementById('eventTotalCount').textContent = eventPassData.totalEvents || 0;
            document.getElementById('eventDrawCount').textContent = eventPassData.totalDraws || 0;
            document.getElementById('eventDispatchCount').textContent = eventPassData.totalDispatches || 0;
            document.getElementById('eventFrameDuration').textContent = (eventPassData.frameDuration || 0).toFixed(2) + ' ms';
            
            // 填充 Pass 筛选下拉框
            const passSelect = document.getElementById('passFilter');
            if (passSelect && eventPassData.passes) {{
                eventPassData.passes.forEach(pass => {{
                    const opt = document.createElement('option');
                    opt.value = pass.name;
                    opt.textContent = pass.name;
                    passSelect.appendChild(opt);
                }});
            }}
            
            // 渲染事件树
            renderEventTree();
        }}
        
        function renderEventTree() {{
            const container = document.getElementById('eventTreeList');
            if (!container || !eventPassData.events) return;
            
            const searchTerm = document.getElementById('eventSearchBox')?.value?.toLowerCase() || '';
            const typeFilter = document.getElementById('eventTypeFilter')?.value || '';
            const passFilter = document.getElementById('passFilter')?.value || '';
            
            container.innerHTML = '';
            
            // 获取选中 Pass 对应的 events EID 列表
            let passEventEids = null;
            if (passFilter && eventPassData.passes) {{
                const selectedPass = eventPassData.passes.find(p => p.name === passFilter);
                if (selectedPass && selectedPass.events) {{
                    passEventEids = new Set(selectedPass.events);
                }}
            }}
            
            // 构建父子关系映射
            const childrenMap = {{}};
            eventPassData.events.forEach(event => {{
                if (event.parent !== null && event.parent !== undefined) {{
                    if (!childrenMap[event.parent]) {{
                        childrenMap[event.parent] = [];
                    }}
                    childrenMap[event.parent].push(event);
                }}
            }});
            
            // 获取顶级事件（parent 为 null 或 undefined）
            const rootEvents = eventPassData.events.filter(e => e.parent === null || e.parent === undefined);
            
            // 检查事件是否匹配过滤条件
            function matchesFilter(event) {{
                // TASK-209: Pipeline 过滤（搜索 "pipeline:XXXXX"）
                if (searchTerm && searchTerm.startsWith('pipeline:')) {{
                    const pipelineId = searchTerm.replace('pipeline:', '').trim();
                    const eventEids = pipelineToEvents[pipelineId] || [];
                    return eventEids.includes(event.eid);
                }}
                
                // 搜索文本过滤
                if (searchTerm && !event.name.toLowerCase().includes(searchTerm) && 
                    !String(event.eid).includes(searchTerm)) {{
                    return false;
                }}
                // 类型过滤
                if (typeFilter && event.type !== typeFilter) {{
                    return false;
                }}
                // Pass 过滤
                if (passEventEids && !passEventEids.has(event.eid)) {{
                    return false;
                }}
                return true;
            }}
            
            // 递归渲染
            function renderNode(event, depth) {{
                // 基本过滤（如果有子节点，即使不匹配也可能需要渲染）
                const children = childrenMap[event.eid] || [];
                const hasChildren = children.length > 0;
                
                // 递归检查子节点是否有匹配的
                const childHtml = hasChildren && eventExpandState[event.eid] !== false
                    ? children.map(child => renderNode(child, depth + 1)).join('')
                    : '';
                
                // 如果本节点不匹配，且没有匹配的子节点，则不渲染
                if (!matchesFilter(event) && !childHtml) {{
                    return '';
                }}
                
                // 如果本节点不匹配但有匹配的子节点，且没有过滤条件，也要显示本节点
                const showSelf = matchesFilter(event) || (childHtml && (typeFilter || passFilter || searchTerm));
                
                if (!showSelf && !childHtml) {{
                    return '';
                }}
                
                const isExpanded = eventExpandState[event.eid] !== false; // 默认展开
                const isPass = event.type === 'Marker' || event.type === 'Pass';
                const isSelected = selectedEventEid === event.eid;
                
                const indent = 8 + depth * 20;
                const icon = getEventIcon(event.type);
                const typeBadge = getTypeBadge(event.type);
                
                let html = `<div class="event-node ${{isPass ? 'pass' : ''}} ${{isSelected ? 'selected' : ''}} ${{!matchesFilter(event) ? 'dimmed' : ''}}"
                    style="--indent: ${{indent}}px"
                    data-eid="${{event.eid}}"
                    onclick="selectEvent(${{event.eid}})">
                    <span class="expand-btn" onclick="event.stopPropagation(); toggleEventExpand(${{event.eid}})">
                        ${{hasChildren ? (isExpanded ? '▼' : '▶') : ''}}
                    </span>
                    <span class="event-icon">${{icon}}</span>
                    <span class="event-eid">#${{event.eid}}</span>
                    <span class="event-name">${{event.name}}</span>
                    ${{typeBadge}}
                </div>`;
                
                // 添加已计算的子节点 HTML
                html += childHtml;
                
                return html;
            }}
            
            let html = '';
            rootEvents.forEach(event => {{
                html += renderNode(event, 0);
            }});
            
            container.innerHTML = html || '<div style="padding: 16px; color: var(--text-muted); text-align: center;">没有找到匹配的 Event</div>';
        }}
        
        function getEventIcon(type) {{
            const icons = {{
                'Marker': '📁',
                'Pass': '📁',
                'Draw': '🎨',
                'DrawIndexed': '🎨',
                'Dispatch': '⚡',
                'Clear': '🧹',
                'Copy': '📋',
                'Resolve': '🔄',
                'SetState': '⚙️'
            }};
            return icons[type] || '📌';
        }}
        
        function getTypeBadge(type) {{
            const classes = {{
                'Marker': 'pass',
                'Pass': 'pass',
                'Draw': 'draw',
                'DrawIndexed': 'draw',
                'Dispatch': 'dispatch',
                'Clear': 'clear'
            }};
            const cls = classes[type] || '';
            if (!cls) return '';
            return `<span class="event-type-badge ${{cls}}">${{type}}</span>`;
        }}
        
        function toggleEventExpand(eid) {{
            eventExpandState[eid] = !eventExpandState[eid];
            if (eventExpandState[eid] === undefined) {{
                eventExpandState[eid] = false; // 从默认展开变为折叠
            }}
            renderEventTree();
        }}
        
        function expandAllEvents() {{
            eventPassData.events.forEach(e => {{
                eventExpandState[e.eid] = true;
            }});
            renderEventTree();
        }}
        
        function collapseAllEvents() {{
            eventPassData.events.forEach(e => {{
                eventExpandState[e.eid] = false;
            }});
            renderEventTree();
        }}
        
        // ========== Pass 依赖图逻辑 ==========
        let currentEventViewMode = 'tree';  // 'tree' | 'graph'
        
        function setEventViewMode(mode) {{
            currentEventViewMode = mode;
            
            // 更新按钮状态
            document.getElementById('viewModeTree').classList.toggle('active', mode === 'tree');
            document.getElementById('viewModeGraph').classList.toggle('active', mode === 'graph');
            
            // 切换显示
            const treeList = document.getElementById('eventTreeList');
            const graphContainer = document.getElementById('passGraphContainer');
            const searchBox = document.getElementById('eventSearchBox');
            const expandBtn1 = document.getElementById('expandCollapseBtn1');
            const expandBtn2 = document.getElementById('expandCollapseBtn2');
            
            if (mode === 'tree') {{
                treeList.style.display = 'block';
                graphContainer.classList.remove('show');
                searchBox.style.display = 'block';
                expandBtn1.style.display = 'inline-block';
                expandBtn2.style.display = 'inline-block';
            }} else {{
                treeList.style.display = 'none';
                graphContainer.classList.add('show');
                searchBox.style.display = 'none';
                expandBtn1.style.display = 'none';
                expandBtn2.style.display = 'none';
                renderPassGraph();
            }}
        }}
        
        function renderPassGraph() {{
            const container = document.getElementById('passGraphContainer');
            if (!container || !eventPassData || !eventPassData.passes) {{
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">无 Pass 数据</div>';
                return;
            }}
            
            const passes = eventPassData.passes;
            if (passes.length === 0) {{
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">无 Pass 数据</div>';
                return;
            }}
            
            // Pass 类型颜色映射
            const passColors = {{
                'shadow': '#6e40c9',
                'gbuffer': '#2ea043',
                'lighting': '#f0883e',
                'postprocess': '#58a6ff',
                'transparent': '#8957e5',
                'ui': '#db61a2',
                'default': '#7d8590'
            }};
            
            // 布局参数
            const nodeWidth = 140;
            const nodeHeight = 60;
            const horizontalGap = 60;
            const verticalGap = 30;
            const padding = 40;
            
            // 计算布局：使用简单的水平流布局
            // 分析 Pass 依赖关系
            const passNodes = passes.map((pass, index) => {{
                return {{
                    ...pass,
                    index: index,
                    x: 0,
                    y: 0,
                    color: passColors[pass.type] || passColors['default']
                }};
            }});
            
            // 计算依赖边：基于 outputs → inputs 关系
            const edges = [];
            const outputToPassMap = {{}};
            
            // 记录每个 Pass 的输出
            passNodes.forEach(pass => {{
                (pass.outputs || []).forEach(output => {{
                    if (!outputToPassMap[output]) {{
                        outputToPassMap[output] = [];
                    }}
                    outputToPassMap[output].push(pass);
                }});
            }});
            
            // 找出依赖关系（谁的输入是谁的输出）
            passNodes.forEach(pass => {{
                (pass.inputs || []).forEach(input => {{
                    const producers = outputToPassMap[input] || [];
                    producers.forEach(producer => {{
                        if (producer.index < pass.index) {{
                            edges.push({{
                                from: producer,
                                to: pass,
                                resource: input
                            }});
                        }}
                    }});
                }});
            }});
            
            // 简单水平布局（如果没有复杂依赖就用简单布局）
            // 为了更好的展示，使用分层布局
            const layers = [];
            const assigned = new Set();
            
            // 第一层：没有输入依赖的 Pass
            const firstLayer = passNodes.filter(p => {{
                const hasInputFromPrior = edges.some(e => e.to.index === p.index);
                return !hasInputFromPrior;
            }});
            
            if (firstLayer.length > 0) {{
                layers.push(firstLayer);
                firstLayer.forEach(p => assigned.add(p.index));
            }}
            
            // 后续层：按顺序分配
            let remaining = passNodes.filter(p => !assigned.has(p.index));
            while (remaining.length > 0) {{
                // 取 2-3 个为一层
                const layerSize = Math.min(remaining.length, 2);
                const layer = remaining.slice(0, layerSize);
                layers.push(layer);
                layer.forEach(p => assigned.add(p.index));
                remaining = remaining.slice(layerSize);
            }}
            
            // 计算位置
            let currentX = padding;
            layers.forEach((layer, layerIndex) => {{
                const layerHeight = layer.length * (nodeHeight + verticalGap) - verticalGap;
                let currentY = padding + (layers.length > 1 ? 0 : 0);
                
                layer.forEach((pass, nodeIndex) => {{
                    pass.x = currentX;
                    pass.y = currentY + nodeIndex * (nodeHeight + verticalGap);
                }});
                
                currentX += nodeWidth + horizontalGap;
            }});
            
            // 计算 SVG 尺寸
            const maxX = Math.max(...passNodes.map(p => p.x)) + nodeWidth + padding;
            const maxY = Math.max(...passNodes.map(p => p.y)) + nodeHeight + padding;
            const svgWidth = Math.max(maxX, 400);
            const svgHeight = Math.max(maxY, 200);
            
            // 生成 SVG
            let svg = `<svg class="pass-graph-svg" width="${{svgWidth}}" height="${{svgHeight}}" viewBox="0 0 ${{svgWidth}} ${{svgHeight}}">`;
            
            // 定义箭头标记
            svg += `
                <defs>
                    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                        <polygon class="pass-edge-arrow" points="0 0, 10 3.5, 0 7" />
                    </marker>
                </defs>
            `;
            
            // 绘制边（连线）
            edges.forEach((edge, edgeIdx) => {{
                const fromX = edge.from.x + nodeWidth;
                const fromY = edge.from.y + nodeHeight / 2;
                const toX = edge.to.x;
                const toY = edge.to.y + nodeHeight / 2;
                
                // 使用贝塞尔曲线
                const midX = (fromX + toX) / 2;
                const pathD = `M${{fromX}},${{fromY}} C${{midX}},${{fromY}} ${{midX}},${{toY}} ${{toX}},${{toY}}`;
                
                // 从 producer 的 outputDetails 获取资源完整信息
                const resourceName = edge.resource || '';
                const resourceDetail = (edge.from.outputDetails || []).find(r => r.name === resourceName) || {{}};
                
                // 边 Tooltip 数据
                const edgeTooltipData = JSON.stringify({{
                    resource: resourceName,
                    format: resourceDetail.format || 'N/A',
                    size: resourceDetail.width && resourceDetail.height 
                        ? `${{resourceDetail.width}}×${{resourceDetail.height}}` : 'N/A',
                    from: edge.from.name,
                    to: edge.to.name,
                    thumbnail: resourceDetail.thumbnail || ''
                }}).replace(/"/g, '&quot;');
                
                // 绘制可交互的边（透明宽线用于 hover 检测 + 可见细线）
                svg += `<g class="pass-edge-group" data-edge-tooltip="${{edgeTooltipData}}"
                           onmouseenter="showEdgeTooltip(event, this)"
                           onmouseleave="hideEdgeTooltip()">
                    <path class="pass-edge-hitbox" d="${{pathD}}" />
                    <path class="pass-edge" d="${{pathD}}" marker-end="url(#arrowhead)" />
                </g>`;
                
                // 资源标签（在连线中点）
                const labelX = midX;
                const labelY = (fromY + toY) / 2 - 8;
                const shortResource = (resourceName || '').split('_').pop() || '';
                if (shortResource) {{
                    svg += `<text class="resource-label" x="${{labelX}}" y="${{labelY}}">${{shortResource}}</text>`;
                }}
            }});
            
            // 绘制节点
            passNodes.forEach(pass => {{
                const x = pass.x;
                const y = pass.y;
                
                // 推测标识（当 isInferred=true 时）
                const inferredBadge = pass.isInferred 
                    ? `<text class="pass-node-inferred" x="${{x + nodeWidth - 8}}" y="${{y + 12}}">🔮</text>`
                    : '';
                
                // 生成 Tooltip 数据（JSON 转义）
                const tooltipData = JSON.stringify({{
                    name: pass.name,
                    type: pass.type,
                    isInferred: pass.isInferred,
                    drawCount: pass.drawCount,
                    duration: pass.duration,
                    inputs: pass.inputs || [],
                    outputs: pass.outputs || [],
                    outputDetails: pass.outputDetails || []
                }}).replace(/"/g, '&quot;');
                
                svg += `
                    <g class="pass-node" onclick="selectPassFromGraph(${{pass.eid}})" 
                       data-eid="${{pass.eid}}"
                       data-tooltip="${{tooltipData}}"
                       onmouseenter="showPassTooltip(event, this)"
                       onmouseleave="hidePassTooltip()">
                        <rect class="pass-node-rect" x="${{x}}" y="${{y}}" 
                              width="${{nodeWidth}}" height="${{nodeHeight}}" 
                              fill="${{pass.color}}" />
                        ${{inferredBadge}}
                        <text class="pass-node-text" x="${{x + nodeWidth/2}}" y="${{y + 22}}">
                            ${{pass.name.length > 16 ? pass.name.slice(0, 14) + '...' : pass.name}}
                        </text>
                        <text class="pass-node-stats" x="${{x + nodeWidth/2}}" y="${{y + 38}}">
                            ${{pass.drawCount}} draws · ${{pass.duration.toFixed(1)}}ms
                        </text>
                        <text class="pass-node-stats" x="${{x + nodeWidth/2}}" y="${{y + 50}}">
                            EID #${{pass.eid}}${{pass.isInferred ? ' (推测)' : ''}}
                        </text>
                    </g>
                `;
            }});
            
            svg += '</svg>';
            
            // 生成 Tooltip 容器（固定在页面上）
            let tooltipHtml = '<div id="passTooltip" class="pass-tooltip"></div>';
            
            // 生成图例
            const legendItems = [...new Set(passNodes.map(p => p.type))];
            let legendHtml = '<div class="pass-graph-legend">';
            legendItems.forEach(type => {{
                const color = passColors[type] || passColors['default'];
                legendHtml += `
                    <div class="pass-graph-legend-item">
                        <div class="pass-graph-legend-color" style="background: ${{color}}"></div>
                        <span>${{type}}</span>
                    </div>
                `;
            }});
            legendHtml += '</div>';
            
            container.innerHTML = tooltipHtml + legendHtml + svg;
        }}
        
        // ========== Pass Tooltip 功能 ==========
        function showPassTooltip(event, element) {{
            const tooltip = document.getElementById('passTooltip');
            if (!tooltip) return;
            
            const data = JSON.parse(element.dataset.tooltip);
            
            // 构建 Tooltip 内容
            let html = `
                <div class="pass-tooltip-header">
                    <span class="pass-tooltip-name">${{data.name}}</span>
                    ${{data.isInferred ? '<span class="pass-tooltip-badge">🔮 推测</span>' : ''}}
                </div>
                <div class="pass-tooltip-stats">
                    <span>类型: <strong>${{data.type}}</strong></span>
                    <span>绘制: <strong>${{data.drawCount}}</strong></span>
                    <span>耗时: <strong>${{data.duration.toFixed(2)}}ms</strong></span>
                </div>
            `;
            
            // Output RTs 缩略图
            if (data.outputDetails && data.outputDetails.length > 0) {{
                html += `<div class="pass-tooltip-section">
                    <div class="pass-tooltip-section-title">🎯 Outputs</div>
                    <div class="pass-tooltip-thumbs">
                        ${{data.outputDetails.map(rt => `
                            <div class="pass-tooltip-thumb-item">
                                <img src="${{rt.thumbnail}}" alt="${{rt.name}}" />
                                <div class="pass-tooltip-thumb-name">${{rt.name.length > 12 ? rt.name.slice(0, 10) + '..' : rt.name}}</div>
                                <div class="pass-tooltip-thumb-format">${{rt.format}}</div>
                            </div>
                        `).join('')}}
                    </div>
                </div>`;
            }}
            
            // Input 列表
            if (data.inputs && data.inputs.length > 0) {{
                html += `<div class="pass-tooltip-section">
                    <div class="pass-tooltip-section-title">📥 Inputs</div>
                    <div class="pass-tooltip-inputs">
                        ${{data.inputs.map(input => `<span class="pass-tooltip-input-tag">${{input}}</span>`).join('')}}
                    </div>
                </div>`;
            }}
            
            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            
            // 定位 Tooltip（跟随鼠标，但避免超出屏幕）
            const rect = tooltip.getBoundingClientRect();
            let x = event.clientX + 15;
            let y = event.clientY + 15;
            
            // 防止超出右边界
            if (x + rect.width > window.innerWidth) {{
                x = event.clientX - rect.width - 15;
            }}
            // 防止超出下边界
            if (y + rect.height > window.innerHeight) {{
                y = event.clientY - rect.height - 15;
            }}
            
            tooltip.style.left = x + 'px';
            tooltip.style.top = y + 'px';
        }}
        
        function hidePassTooltip() {{
            const tooltip = document.getElementById('passTooltip');
            if (tooltip) {{
                tooltip.style.display = 'none';
            }}
        }}
        
        // ========== Edge Tooltip 功能 ==========
        function showEdgeTooltip(event, element) {{
            let tooltip = document.getElementById('edgeTooltip');
            if (!tooltip) {{
                tooltip = document.createElement('div');
                tooltip.id = 'edgeTooltip';
                tooltip.className = 'edge-tooltip';
                document.body.appendChild(tooltip);
            }}
            
            const data = JSON.parse(element.dataset.edgeTooltip.replace(/&quot;/g, '"'));
            
            // 构建 Tooltip 内容（全新设计：更清晰的资源流向）
            const thumbHtml = data.thumbnail 
                ? `<div class="edge-tooltip-thumb"><img src="${{data.thumbnail}}" alt="${{data.resource}}" /></div>`
                : '<div class="edge-tooltip-thumb" style="display:flex;align-items:center;justify-content:center;font-size:24px;">📦</div>';
            
            // 简化 Pass 名称显示
            const fromName = (data.from || 'Source').replace(/^Pass #\d+ \(Output: /, '').replace(/\)$/, '');
            const toName = (data.to || 'Target').replace(/^Pass #\d+ \(Output: /, '').replace(/\)$/, '');
            
            tooltip.innerHTML = `
                <div class="edge-tooltip-title">资源传递</div>
                <div class="edge-tooltip-flow">
                    <span class="pass-name" title="${{data.from}}">${{data.from || 'Source'}}</span>
                    <span class="arrow">➜</span>
                    <span class="pass-name" title="${{data.to}}">${{data.to || 'Target'}}</span>
                </div>
                <div class="edge-tooltip-resource">
                    ${{thumbHtml}}
                    <div class="edge-tooltip-info">
                        <div class="edge-tooltip-label">传递的资源</div>
                        <div class="edge-tooltip-name">${{data.resource || '未知资源'}}</div>
                        <div class="edge-tooltip-format">${{data.format || 'N/A'}}</div>
                        ${{data.size && data.size !== 'N/A' ? `<div class="edge-tooltip-size">${{data.size}}</div>` : ''}}
                    </div>
                </div>
            `;
            
            // 定位
            const rect = tooltip.getBoundingClientRect();
            let x = event.clientX + 15;
            let y = event.clientY + 15;
            
            tooltip.style.left = x + 'px';
            tooltip.style.top = y + 'px';
            
            // 显示 + 边界调整
            requestAnimationFrame(() => {{
                tooltip.classList.add('visible');
                const newRect = tooltip.getBoundingClientRect();
                if (x + newRect.width > window.innerWidth) {{
                    tooltip.style.left = (event.clientX - newRect.width - 15) + 'px';
                }}
                if (y + newRect.height > window.innerHeight) {{
                    tooltip.style.top = (event.clientY - newRect.height - 15) + 'px';
                }}
            }});
        }}
        
        function hideEdgeTooltip() {{
            const tooltip = document.getElementById('edgeTooltip');
            if (tooltip) {{
                tooltip.classList.remove('visible');
            }}
        }}
        
        function selectPassFromGraph(eid) {{
            // 切换回树形视图并选中对应的 Pass
            setEventViewMode('tree');
            
            // 展开并滚动到目标 Event
            eventExpandState[eid] = true;
            renderEventTree();
            selectEvent(eid);
            
            // 滚动到目标节点
            setTimeout(() => {{
                const node = document.querySelector(`.event-node[data-eid="${{eid}}"]`);
                if (node) {{
                    node.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}, 100);
        }}
        
        function selectEvent(eid) {{
            selectedEventEid = eid;
            
            // 更新选中状态
            document.querySelectorAll('.event-node').forEach(node => {{
                node.classList.toggle('selected', parseInt(node.dataset.eid) === eid);
            }});
            
            // 渲染详情
            renderEventDetail(eid);
        }}
        
        function renderEventDetail(eid) {{
            const event = eventPassData.events.find(e => e.eid === eid);
            if (!event) return;
            
            const content = document.getElementById('eventDetailContent');
            if (!content) return;
            
            if (currentEventTab === 'summary') {{
                content.innerHTML = renderEventSummary(event);
            }} else if (currentEventTab === 'pipeline') {{
                content.innerHTML = renderEventPipeline(event);
            }} else if (currentEventTab === 'bindings') {{
                content.innerHTML = renderEventBindings(event);
            }} else if (currentEventTab === 'mesh') {{
                content.innerHTML = renderEventMeshInfo(event);
            }} else if (currentEventTab === 'apicall') {{
                content.innerHTML = renderEventApiCall(event);
            }}
        }}
        
        // 辅助函数：收集 Marker 节点下所有子 Event 的 IO
        function collectChildrenIO(parentEid) {{
            const allEvents = eventPassData.events || [];
            let allInputs = [];
            let allOutputs = [];
            let childCount = 0;
            let drawCount = 0;
            let dispatchCount = 0;
            let clearCount = 0;
            
            // 递归收集子节点
            function collectFromChildren(eid) {{
                const children = allEvents.filter(e => e.parent === eid);
                children.forEach(child => {{
                    childCount++;
                    if (child.type === 'Draw') drawCount++;
                    if (child.type === 'Dispatch') dispatchCount++;
                    if (child.type === 'Clear') clearCount++;
                    
                    // 收集 IO（去重按 id）
                    if (child.inputs) {{
                        child.inputs.forEach(inp => {{
                            if (!allInputs.find(x => x.id === inp.id)) {{
                                allInputs.push(inp);
                            }}
                        }});
                    }}
                    if (child.outputs) {{
                        child.outputs.forEach(out => {{
                            if (!allOutputs.find(x => x.id === out.id)) {{
                                allOutputs.push(out);
                            }}
                        }});
                    }}
                    // 递归子节点
                    collectFromChildren(child.eid);
                }});
            }}
            
            collectFromChildren(parentEid);
            return {{ allInputs, allOutputs, childCount, drawCount, dispatchCount, clearCount }};
        }}
        
        function renderEventSummary(event) {{
            // ========== 检测是否为 Marker（Pass 容器）节点 ==========
            const isMarker = event.type === 'Marker' || event.flags?.includes('PushMarker');
            
            let html = `
                <div class="event-detail-card">
                    <div class="event-detail-card-header">📋 基本信息</div>
                    <div class="event-detail-card-body">
                        <table class="params-table">
                            <tr><td>Event ID</td><td><strong>#${{event.eid}}</strong></td></tr>
                            <tr><td>名称</td><td>${{event.name}}</td></tr>
                            <tr><td>类型</td><td>${{event.type}}${{isMarker ? ' <span style="color:var(--accent-primary);font-size:11px;">(Pass 容器)</span>' : ''}}</td></tr>
                        </table>
                    </div>
                </div>
            `;
            
            // ========== Marker 节点：显示 Pass 汇总 ==========
            if (isMarker) {{
                const childIO = collectChildrenIO(event.eid);
                
                // 显示 Pass 统计
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📊 Pass 统计</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                <tr><td>子 Event 总数</td><td><strong>${{childIO.childCount}}</strong></td></tr>
                                <tr><td>绘制调用 (Draw)</td><td>${{childIO.drawCount}}</td></tr>
                                <tr><td>计算调用 (Dispatch)</td><td>${{childIO.dispatchCount}}</td></tr>
                                <tr><td>清除调用 (Clear)</td><td>${{childIO.clearCount}}</td></tr>
                                <tr><td>唯一输入纹理</td><td>${{childIO.allInputs.length}}</td></tr>
                                <tr><td>唯一输出 RT</td><td>${{childIO.allOutputs.length}}</td></tr>
                            </table>
                        </div>
                    </div>
                `;
                
                // 显示聚合的 Outputs
                if (childIO.allOutputs.length > 0) {{
                    html += `
                        <div class="event-detail-card io-card">
                            <div class="event-detail-card-header">🎯 Pass 输出 (聚合)</div>
                            <div class="event-detail-card-body">
                                <div class="io-thumbnail-grid">
                                    ${{childIO.allOutputs.slice(0, 8).map((rt, idx) => {{
                                        const thumbSrc = rt.thumbnail || '';
                                        const thumbImg = thumbSrc 
                                            ? `<img src="${{thumbSrc}}" alt="${{rt.name || 'RT'}}" onerror="this.style.display='none'" />`
                                            : `<div class="io-thumb-placeholder">📦</div>`;
                                        
                                        return `<div class="io-resource-card output-card" title="${{rt.name || 'RenderTarget ' + idx}}"
                                                     onclick="${{rt.id ? 'jumpToTexture(\\'' + rt.id + '\\')' : ''}}">
                                            <div class="io-thumb">${{thumbImg}}</div>
                                            <div class="io-info">
                                                <div class="io-name">${{rt.name || 'RT' + idx}}</div>
                                                <div class="io-format">${{rt.format || 'N/A'}}</div>
                                            </div>
                                        </div>`;
                                    }}).join('')}}
                                    ${{childIO.allOutputs.length > 8 ? `<div class="io-more">+${{childIO.allOutputs.length - 8}} 更多...</div>` : ''}}
                                </div>
                            </div>
                        </div>
                    `;
                }}
                
                // 显示聚合的 Inputs
                if (childIO.allInputs.length > 0) {{
                    html += `
                        <div class="event-detail-card io-card">
                            <div class="event-detail-card-header">📥 Pass 输入 (聚合)</div>
                            <div class="event-detail-card-body">
                                <div class="io-thumbnail-grid">
                                    ${{childIO.allInputs.slice(0, 8).map((tex, idx) => {{
                                        const texData = textures.find(t => t.id === tex.id || t.name === tex.name);
                                        const thumbSrc = tex.thumbnail || texData?.thumbnail || '';
                                        const thumbImg = thumbSrc 
                                            ? `<img src="${{thumbSrc}}" alt="${{tex.name || 'Texture'}}" onerror="this.style.display='none'" />`
                                            : `<div class="io-thumb-placeholder">🖼️</div>`;
                                        
                                        return `<div class="io-resource-card input-card" title="${{tex.name || 'Texture ' + idx}}" 
                                                     onclick="${{tex.id ? 'jumpToTexture(' + tex.id + ')' : ''}}">
                                            <div class="io-thumb">${{thumbImg}}</div>
                                            <div class="io-info">
                                                <div class="io-name">${{tex.name || 'Tex' + idx}}</div>
                                                ${{tex.format ? `<div class="io-format">${{tex.format}}</div>` : ''}}
                                            </div>
                                        </div>`;
                                    }}).join('')}}
                                    ${{childIO.allInputs.length > 8 ? `<div class="io-more">+${{childIO.allInputs.length - 8}} 更多...</div>` : ''}}
                                </div>
                            </div>
                        </div>
                    `;
                }}
                
                // Marker 节点不显示 drawParams 等，直接返回
                return html;
            }}
            
            if (event.drawParams) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">🎨 绘制参数</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                ${{Object.entries(event.drawParams).map(([k, v]) => 
                                    `<tr><td>${{k}}</td><td>${{v}}</td></tr>`
                                ).join('')}}
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            if (event.dispatchParams) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">⚡ Dispatch 参数</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                ${{Object.entries(event.dispatchParams).map(([k, v]) => 
                                    `<tr><td>${{k}}</td><td>${{Array.isArray(v) ? v.join(' × ') : v}}</td></tr>`
                                ).join('')}}
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            // ========== Output Render Targets (带缩略图) ==========
            const outputs = event.outputs || (event.pipelineState?.outputTargets) || [];
            if (outputs.length > 0) {{
                html += `
                    <div class="event-detail-card io-card">
                        <div class="event-detail-card-header">🎯 Output Render Targets</div>
                        <div class="event-detail-card-body">
                            <div class="io-thumbnail-grid">
                                ${{outputs.map((rt, idx) => {{
                                    const thumbSrc = rt.thumbnail || '';
                                    const thumbImg = thumbSrc 
                                        ? `<img src="${{thumbSrc}}" alt="${{rt.name || 'RT'}}" onerror="this.style.display='none'" />`
                                        : `<div class="io-thumb-placeholder">📦</div>`;
                                    
                                    return `<div class="io-resource-card output-card" title="${{rt.name || 'RenderTarget ' + idx}}"
                                                 onclick="${{rt.id ? 'jumpToTexture(' + rt.id + ')' : ''}}">
                                        <div class="io-thumb">${{thumbImg}}</div>
                                        <div class="io-info">
                                            <div class="io-name">${{rt.name || 'RT' + idx}}</div>
                                            <div class="io-format">${{rt.format || 'N/A'}}</div>
                                            ${{rt.size ? `<div class="io-size">${{rt.size}}</div>` : ''}}
                                        </div>
                                        ${{rt.id ? '<span class="io-jump-link">跳转 →</span>' : ''}}
                                    </div>`;
                                }}).join('')}}
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // ========== Input Textures (带缩略图) ==========
            const inputs = event.inputs || [];
            if (inputs.length > 0) {{
                html += `
                    <div class="event-detail-card io-card">
                        <div class="event-detail-card-header">📥 Input Textures</div>
                        <div class="event-detail-card-body">
                            <div class="io-thumbnail-grid">
                                ${{inputs.map((tex, idx) => {{
                                    // 尝试从全局 textures 中匹配缩略图
                                    const texData = textures.find(t => t.id === tex.id || t.name === tex.name);
                                    const thumbSrc = tex.thumbnail || texData?.thumbnail || '';
                                    const thumbImg = thumbSrc 
                                        ? `<img src="${{thumbSrc}}" alt="${{tex.name || 'Texture'}}" onerror="this.style.display='none'" />`
                                        : `<div class="io-thumb-placeholder">🖼️</div>`;
                                    
                                    return `<div class="io-resource-card input-card" title="${{tex.name || 'Texture ' + idx}}" 
                                                 onclick="${{tex.id ? 'jumpToTexture(' + tex.id + ')' : ''}}">
                                        <div class="io-thumb">${{thumbImg}}</div>
                                        <div class="io-info">
                                            <div class="io-name">${{tex.name || 'Tex' + idx}}</div>
                                            <div class="io-slot">${{tex.slot !== undefined ? 't' + tex.slot : ''}}</div>
                                            ${{tex.format ? `<div class="io-format">${{tex.format}}</div>` : ''}}
                                        </div>
                                        ${{tex.id ? '<span class="io-jump-link">跳转 →</span>' : ''}}
                                    </div>`;
                                }}).join('')}}
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // 如果没有 Input/Output 数据，显示提示
            if (outputs.length === 0 && inputs.length === 0 && event.type !== 'PushMarker' && event.type !== 'PopMarker') {{
                html += `
                    <div class="event-detail-card io-card empty-io">
                        <div class="event-detail-card-body" style="text-align: center; padding: 20px; color: var(--text-muted);">
                            <div style="font-size: 24px; margin-bottom: 8px;">📭</div>
                            <div>此 Event 无 Input/Output 资源绑定数据</div>
                            <div style="font-size: 11px; margin-top: 4px;">查看 "绑定" 选项卡获取更多资源信息</div>
                        </div>
                    </div>
                `;
            }}
            
            return html;
        }}
        
        function renderEventPipeline(event) {{
            const ps = event.pipelineState;
            if (!ps) {{
                return `<div class="event-detail-empty">
                    <div class="icon">🔧</div>
                    <div>此 Event 没有 Pipeline State 数据</div>
                </div>`;
            }}
            
            let html = '';
            
            // Shaders
            if (ps.shaders) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">🔧 Shaders</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                <thead>
                                    <tr>
                                        <th style="width:120px;">Stage</th>
                                        <th>Name / Entry Point</th>
                                        <th style="width:100px;">操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                ${{Object.entries(ps.shaders).map(([stage, shader]) => {{
                                    const name = shader.debugName || shader.entryPoint || shader.resourceId || 'N/A';
                                    const hasCode = shader.sourceAsm || shader.inputSignature;
                                    const shaderJson = JSON.stringify(shader).replace(/'/g, "\\\\'").replace(/"/g, '&quot;');
                                    return `<tr>
                                        <td><span style="font-weight:500;">${{stage}}</span></td>
                                        <td style="font-family:monospace;font-size:11px;">${{name}}</td>
                                        <td>
                                            ${{hasCode ? 
                                                `<button class="btn-view-shader" onclick="showShaderModal('${{stage}}', JSON.parse(this.dataset.shader.replace(/&quot;/g, '\\\"')))" data-shader="${{shaderJson}}">
                                                    📜 查看
                                                </button>` : 
                                                `<span style="color:var(--text-muted);font-size:10px;">无详情</span>`
                                            }}
                                        </td>
                                    </tr>`;
                                }}).join('')}}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            // Viewport & Scissor
            if (ps.viewport) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📐 Viewport</div>
                        <div class="event-detail-card-body">
                            <div class="state-grid">
                                <div class="state-item">
                                    <div class="label">位置</div>
                                    <div class="value">(${{ps.viewport.x}}, ${{ps.viewport.y}})</div>
                                </div>
                                <div class="state-item">
                                    <div class="label">尺寸</div>
                                    <div class="value">${{ps.viewport.width}} × ${{ps.viewport.height}}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // Blend State
            if (ps.blendState) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">🎨 Blend State</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                <tr><td>启用</td><td>${{ps.blendState.enabled ? '是' : '否'}}</td></tr>
                                <tr><td>Src Color</td><td>${{ps.blendState.srcColor || 'N/A'}}</td></tr>
                                <tr><td>Dst Color</td><td>${{ps.blendState.dstColor || 'N/A'}}</td></tr>
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            // Depth State
            if (ps.depthState) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📏 Depth State</div>
                        <div class="event-detail-card-body">
                            <table class="params-table">
                                <tr><td>Depth Test</td><td>${{ps.depthState.testEnabled ? '开启' : '关闭'}}</td></tr>
                                <tr><td>Depth Write</td><td>${{ps.depthState.writeEnabled ? '开启' : '关闭'}}</td></tr>
                                <tr><td>比较函数</td><td>${{ps.depthState.compareFunc || 'N/A'}}</td></tr>
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            return html || `<div class="event-detail-empty">
                <div class="icon">🔧</div>
                <div>Pipeline State 数据为空</div>
            </div>`;
        }}
        
        function renderEventBindings(event) {{
            const ps = event.pipelineState;
            if (!ps || !ps.bindings) {{
                return `<div class="event-detail-empty">
                    <div class="icon">🎨</div>
                    <div>此 Event 没有资源绑定数据</div>
                </div>`;
            }}
            
            let html = '';
            
            Object.entries(ps.bindings).forEach(([stage, bindings]) => {{
                if (bindings.textures && bindings.textures.length > 0) {{
                    html += `
                        <div class="binding-section">
                            <div class="binding-stage">${{stage}} - Textures</div>
                            <div class="binding-list">
                                ${{bindings.textures.map(tex => {{
                                    // 查找纹理详情
                                    const texData = textures.find(t => t.id === tex.id);
                                    const thumb = texData?.base64 ? `<img src="data:image/png;base64,${{texData.base64}}">` : '';
                                    const size = texData ? `${{texData.width}}×${{texData.height}}` : '';
                                    
                                    return `<div class="binding-item" onclick="jumpToTexture(${{tex.id}})">
                                        <span class="slot">t${{tex.slot}}</span>
                                        <div class="thumb">${{thumb}}</div>
                                        <div class="info">
                                            <div class="name">${{tex.name || texData?.name || 'Texture ' + tex.id}}</div>
                                            <div class="meta">ID: ${{tex.id}} ${{size ? '| ' + size : ''}}</div>
                                        </div>
                                        <span class="jump-link">跳转 →</span>
                                    </div>`;
                                }}).join('')}}
                            </div>
                        </div>
                    `;
                }}
                
                // Vertex Buffers (VS 阶段)
                if (bindings.vertexBuffers && bindings.vertexBuffers.length > 0) {{
                    html += `
                        <div class="binding-section">
                            <div class="binding-stage">${{stage}} - Vertex Buffers</div>
                            <div class="binding-list vb-list">
                                ${{bindings.vertexBuffers.map(vb => `
                                    <div class="binding-item vb-item">
                                        <span class="slot">VB${{vb.slot}}</span>
                                        <div class="vb-icon">📐</div>
                                        <div class="info">
                                            <div class="name">${{vb.id}}</div>
                                            <div class="meta">
                                                <span class="vb-stride">Stride: ${{vb.stride}} bytes</span>
                                                <span class="vb-offset">Offset: ${{vb.offset}}</span>
                                            </div>
                                        </div>
                                    </div>
                                `).join('')}}
                            </div>
                        </div>
                    `;
                }}
                
                // Index Buffer (VS 阶段)
                if (bindings.indexBuffer && bindings.indexBuffer.id) {{
                    const ib = bindings.indexBuffer;
                    html += `
                        <div class="binding-section">
                            <div class="binding-stage">${{stage}} - Index Buffer</div>
                            <div class="binding-list ib-list">
                                <div class="binding-item ib-item">
                                    <span class="slot">IB</span>
                                    <div class="ib-icon">🔢</div>
                                    <div class="info">
                                        <div class="name">${{ib.id}}</div>
                                        <div class="meta">
                                            <span class="ib-format">${{ib.format || 'N/A'}}</span>
                                            <span class="ib-offset">Offset: ${{ib.offset}}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }}
                
                if (bindings.constantBuffers && bindings.constantBuffers.length > 0) {{
                    html += `
                        <div class="binding-section">
                            <div class="binding-stage">${{stage}} - Constant Buffers</div>
                            <div class="binding-list cb-list">
                                ${{bindings.constantBuffers.map(cb => {{
                                    // 格式化矩阵值显示（多行显示）
                                    const formatValue = (m) => {{
                                        if (!m.value) return '-';
                                        // 矩阵类型：多行显示
                                        if (m.rows > 1 && m.value.includes('\\n')) {{
                                            const rows = m.value.split('\\n');
                                            return `<div class="matrix-value">${{rows.map((r, i) => 
                                                `<div class="matrix-row">row${{i}}: ${{r}}</div>`
                                            ).join('')}}</div>`;
                                        }}
                                        return `<code class="scalar-value">${{m.value}}</code>`;
                                    }};
                                    
                                    const membersHtml = cb.members && cb.members.length > 0 
                                        ? `<div class="cb-members">
                                            <div class="cb-members-header" onclick="toggleCBMembers(event, this)">
                                                <span class="toggle-icon">▶</span> 
                                                成员变量 (${{cb.members.length}})
                                            </div>
                                            <div class="cb-members-body" style="display: none;">
                                                <table class="cb-members-table">
                                                    <thead>
                                                        <tr>
                                                            <th>名称</th>
                                                            <th>类型</th>
                                                            <th>偏移</th>
                                                            <th>大小</th>
                                                            <th>值</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        ${{cb.members.map(m => `
                                                            <tr>
                                                                <td class="member-name">${{m.name}}</td>
                                                                <td class="member-type">${{m.type}}</td>
                                                                <td class="member-offset">${{m.offset}}</td>
                                                                <td class="member-size">${{m.size}}</td>
                                                                <td class="member-value">${{formatValue(m)}}</td>
                                                            </tr>
                                                        `).join('')}}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>` 
                                        : '';
                                    
                                    return `<div class="binding-item cb-item">
                                        <span class="slot">b${{cb.slot}}</span>
                                        <div class="cb-icon">📦</div>
                                        <div class="info">
                                            <div class="name">${{cb.name || 'ConstantBuffer'}}</div>
                                            <div class="meta">
                                                ${{cb.resourceId ? `<span class="cb-resource-id" title="Resource ID">${{cb.resourceId}}</span>` : ''}}
                                                <span class="cb-size">Size: ${{cb.size || 'N/A'}} bytes</span>
                                                ${{cb.offset !== undefined ? `<span class="cb-offset">Offset: ${{cb.offset}}</span>` : ''}}
                                            </div>
                                            ${{membersHtml}}
                                        </div>
                                    </div>`;
                                }}).join('')}}
                            </div>
                        </div>
                    `;
                }}
            }});
            
            // Render Targets
            if (ps.renderTargets && ps.renderTargets.length > 0) {{
                html += `
                    <div class="binding-section">
                        <div class="binding-stage">Render Targets</div>
                        <div class="binding-list">
                            ${{ps.renderTargets.map((rt, i) => {{
                                const texData = textures.find(t => t.id === rt.id);
                                const thumb = texData?.base64 ? `<img src="data:image/png;base64,${{texData.base64}}">` : '';
                                
                                return `<div class="binding-item" onclick="jumpToTexture(${{rt.id}})">
                                    <span class="slot">RT${{i}}</span>
                                    <div class="thumb">${{thumb}}</div>
                                    <div class="info">
                                        <div class="name">${{rt.name || texData?.name || 'RenderTarget ' + i}}</div>
                                        <div class="meta">ID: ${{rt.id}}</div>
                                    </div>
                                    <span class="jump-link">跳转 →</span>
                                </div>`;
                            }}).join('')}}
                        </div>
                    </div>
                `;
            }}
            
            return html || `<div class="event-detail-empty">
                <div class="icon">🎨</div>
                <div>资源绑定数据为空</div>
            </div>`;
        }}
        
        function renderEventMeshInfo(event) {{
            const mesh = event.meshData;
            if (!mesh) {{
                return `<div class="event-detail-empty">
                    <div class="icon">📐</div>
                    <div>此 Event 没有网格数据</div>
                    <div class="sub">网格数据仅在 Draw 调用中可用</div>
                </div>`;
            }}
            
            let html = '';
            
            // ========== 包围盒 (Bounding Box) ==========
            if (mesh.boundingBox) {{
                const bbox = mesh.boundingBox;
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📦 包围盒 (Bounding Box)</div>
                        <div class="event-detail-card-body">
                            <div class="bbox-container">
                                <div class="bbox-visual">
                                    ${{renderBBoxSVG(bbox)}}
                                </div>
                                <div class="bbox-data">
                                    <table class="params-table">
                                        <tr><td>Min</td><td>(${{bbox.min.x}}, ${{bbox.min.y}}, ${{bbox.min.z}})</td></tr>
                                        <tr><td>Max</td><td>(${{bbox.max.x}}, ${{bbox.max.y}}, ${{bbox.max.z}})</td></tr>
                                        <tr><td>Center</td><td>(${{bbox.center.x}}, ${{bbox.center.y}}, ${{bbox.center.z}})</td></tr>
                                        <tr><td>Extents</td><td>(${{bbox.extents.x}}, ${{bbox.extents.y}}, ${{bbox.extents.z}})</td></tr>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // ========== 顶点统计 ==========
            if (mesh.statistics) {{
                const stats = mesh.statistics;
                const totalSizeKB = (stats.totalMeshSize / 1024).toFixed(2);
                
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📊 网格统计</div>
                        <div class="event-detail-card-body">
                            <div class="mesh-stats-grid">
                                <div class="mesh-stat-item">
                                    <div class="stat-value">${{stats.vertexCount.toLocaleString()}}</div>
                                    <div class="stat-label">顶点数</div>
                                </div>
                                <div class="mesh-stat-item">
                                    <div class="stat-value">${{stats.indexCount.toLocaleString()}}</div>
                                    <div class="stat-label">索引数</div>
                                </div>
                                <div class="mesh-stat-item">
                                    <div class="stat-value">${{stats.triangleCount.toLocaleString()}}</div>
                                    <div class="stat-label">三角形</div>
                                </div>
                                <div class="mesh-stat-item">
                                    <div class="stat-value">${{(stats.vertexReuseRatio * 100).toFixed(1)}}%</div>
                                    <div class="stat-label">复用率</div>
                                </div>
                            </div>
                            <table class="params-table" style="margin-top: 12px;">
                                <tr><td>拓扑类型</td><td>${{stats.topology}}</td></tr>
                                <tr><td>VB 总大小</td><td>${{Object.values(stats.vertexBufferSizes).reduce((a,b) => a+b, 0).toLocaleString()}} bytes</td></tr>
                                <tr><td>IB 大小</td><td>${{stats.indexBufferSize.toLocaleString()}} bytes</td></tr>
                                <tr><td>总计</td><td><strong>${{totalSizeKB}} KB</strong></td></tr>
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            // ========== Input Layout ==========
            if (mesh.inputLayout && mesh.inputLayout.length > 0) {{
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">📝 Input Layout</div>
                        <div class="event-detail-card-body">
                            <table class="input-layout-table">
                                <thead>
                                    <tr>
                                        <th>Semantic</th>
                                        <th>Index</th>
                                        <th>Format</th>
                                        <th>Slot</th>
                                        <th>Offset</th>
                                        <th>Size</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${{mesh.inputLayout.map(attr => `
                                        <tr>
                                            <td><span class="semantic-tag">${{attr.semantic}}</span></td>
                                            <td>${{attr.semanticIndex}}</td>
                                            <td><code>${{attr.format}}</code></td>
                                            <td>${{attr.inputSlot}}</td>
                                            <td>${{attr.offset}}</td>
                                            <td>${{attr.size}} B</td>
                                        </tr>
                                    `).join('')}}
                                </tbody>
                            </table>
                            ${{mesh.strides ? `
                                <div class="stride-info">
                                    ${{Object.entries(mesh.strides).map(([slot, stride]) => 
                                        `<span class="stride-badge">Slot ${{slot}}: ${{stride}} bytes/vertex</span>`
                                    ).join('')}}
                                </div>
                            ` : ''}}
                        </div>
                    </div>
                `;
            }}
            
            // ========== 法线预览 - 半球分布图 ==========
            if (mesh.sampledNormals && mesh.sampledNormals.length > 0) {{
                // 计算法线统计信息
                let avgNormal = {{x: 0, y: 0, z: 0}};
                let upCount = 0, sideCount = 0, downCount = 0;
                mesh.sampledNormals.forEach(n => {{
                    avgNormal.x += n.x;
                    avgNormal.y += n.y;
                    avgNormal.z += n.z;
                    if (n.y > 0.5) upCount++;
                    else if (n.y < -0.5) downCount++;
                    else sideCount++;
                }});
                const len = mesh.sampledNormals.length;
                avgNormal.x /= len;
                avgNormal.y /= len;
                avgNormal.z /= len;
                const avgLen = Math.sqrt(avgNormal.x*avgNormal.x + avgNormal.y*avgNormal.y + avgNormal.z*avgNormal.z);
                if (avgLen > 0.001) {{
                    avgNormal.x /= avgLen;
                    avgNormal.y /= avgLen;
                    avgNormal.z /= avgLen;
                }}
                
                html += `
                    <div class="event-detail-card">
                        <div class="event-detail-card-header">🌈 法线分布分析</div>
                        <div class="event-detail-card-body">
                            <div class="normal-analysis-container">
                                <!-- 半球可视化 -->
                                <div class="normal-hemisphere">
                                    ${{renderNormalHemisphereSVG(mesh.sampledNormals, avgNormal)}}
                                </div>
                                <!-- 统计信息 -->
                                <div class="normal-stats">
                                    <div class="normal-stat-item">
                                        <div class="stat-label">主方向</div>
                                        <div class="stat-value" style="color: #7ee787;">
                                            (${{avgNormal.x.toFixed(2)}}, ${{avgNormal.y.toFixed(2)}}, ${{avgNormal.z.toFixed(2)}})
                                        </div>
                                    </div>
                                    <div class="normal-distribution">
                                        <div class="dist-bar">
                                            <div class="dist-segment up" style="width: ${{(upCount/len*100).toFixed(0)}}%"></div>
                                            <div class="dist-segment side" style="width: ${{(sideCount/len*100).toFixed(0)}}%"></div>
                                            <div class="dist-segment down" style="width: ${{(downCount/len*100).toFixed(0)}}%"></div>
                                        </div>
                                        <div class="dist-labels">
                                            <span>⬆️ 上 ${{(upCount/len*100).toFixed(0)}}%</span>
                                            <span>↔️ 侧 ${{(sideCount/len*100).toFixed(0)}}%</span>
                                            <span>⬇️ 下 ${{(downCount/len*100).toFixed(0)}}%</span>
                                        </div>
                                    </div>
                                    <div class="normal-hint">
                                        ${{upCount > len * 0.7 ? '✅ 多数法线朝上 (地面/平台)' :
                                           sideCount > len * 0.7 ? '📐 多数法线朝侧面 (墙壁/柱子)' :
                                           downCount > len * 0.3 ? '⚠️ 存在向下法线 (可能有翻转)' :
                                           '📊 法线分布均匀 (曲面/球体)'}}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // UV 预览已移除 - 随机采样的 UV 三角形可视化意义不大，容易造成困惑
            
            return html || `<div class="event-detail-empty">
                <div class="icon">📐</div>
                <div>网格数据为空</div>
            </div>`;
        }}
        
        // 渲染法线分布半球图
        function renderNormalHemisphereSVG(normals, avgNormal) {{
            const size = 120;
            const cx = size / 2;
            const cy = size / 2;
            const radius = size / 2 - 10;
            
            // 绘制半球轮廓
            let svg = `
                <svg width="${{size}}" height="${{size}}" viewBox="0 0 ${{size}} ${{size}}">
                    <defs>
                        <radialGradient id="hemisphereGrad" cx="40%" cy="40%">
                            <stop offset="0%" stop-color="#2d333b"/>
                            <stop offset="100%" stop-color="#161b22"/>
                        </radialGradient>
                    </defs>
                    <circle cx="${{cx}}" cy="${{cy}}" r="${{radius}}" fill="url(#hemisphereGrad)" stroke="#30363d"/>
                    <!-- 十字参考线 -->
                    <line x1="${{cx-radius}}" y1="${{cy}}" x2="${{cx+radius}}" y2="${{cy}}" stroke="#30363d" stroke-dasharray="2,2"/>
                    <line x1="${{cx}}" y1="${{cy-radius}}" x2="${{cx}}" y2="${{cy+radius}}" stroke="#30363d" stroke-dasharray="2,2"/>
            `;
            
            // 绘制法线点 (投影到圆上)
            normals.forEach((n, i) => {{
                // 将法线方向投影到圆上 (x, z 作为平面坐标)
                const px = cx + n.x * radius * 0.85;
                const py = cy - n.z * radius * 0.85;  // z 朝上
                // 颜色根据 Y 值 (法线朝向)
                const hue = n.y > 0 ? 120 : 0;  // 朝上=绿, 朝下=红
                const lightness = 40 + Math.abs(n.y) * 30;
                svg += `<circle cx="${{px.toFixed(1)}}" cy="${{py.toFixed(1)}}" r="4" 
                         fill="hsl(${{hue}}, 70%, ${{lightness}}%)" opacity="0.8"
                         title="(${{n.x.toFixed(2)}}, ${{n.y.toFixed(2)}}, ${{n.z.toFixed(2)}})"/>`;
            }});
            
            // 绘制平均法线方向箭头
            const arrowLen = radius * 0.7;
            const ax = cx + avgNormal.x * arrowLen;
            const ay = cy - avgNormal.z * arrowLen;
            svg += `
                <line x1="${{cx}}" y1="${{cy}}" x2="${{ax.toFixed(1)}}" y2="${{ay.toFixed(1)}}" 
                      stroke="#f0883e" stroke-width="3" marker-end="url(#arrowhead)"/>
                <defs>
                    <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                        <polygon points="0 0, 6 3, 0 6" fill="#f0883e"/>
                    </marker>
                </defs>
            `;
            
            // 坐标轴标签
            svg += `
                <text x="${{cx+radius-5}}" y="${{cy+12}}" fill="#8b949e" font-size="9">+X</text>
                <text x="${{cx-12}}" y="${{cy-radius+12}}" fill="#8b949e" font-size="9">+Z</text>
                <text x="${{cx+5}}" y="${{cy+4}}" fill="#f0883e" font-size="8">●主方向</text>
            `;
            
            svg += `</svg>`;
            return svg;
        }}
        
        // 渲染包围盒的 SVG 可视化
        function renderBBoxSVG(bbox) {{
            const w = 120, h = 100;
            const cx = w / 2, cy = h / 2;
            
            // 简化的 3D 投影
            const scale = 25;
            const ex = bbox.extents.x * scale;
            const ey = bbox.extents.y * scale;
            const ez = bbox.extents.z * scale * 0.5; // 深度压缩
            
            // 立方体的 8 个顶点 (等角投影)
            const iso = (x, y, z) => {{
                const px = cx + (x - z) * 0.866;
                const py = cy - y + (x + z) * 0.5;
                return `${{px.toFixed(1)}},${{py.toFixed(1)}}`;
            }};
            
            const vertices = [
                iso(-ex, -ey, -ez), iso(ex, -ey, -ez), iso(ex, ey, -ez), iso(-ex, ey, -ez),  // 前面
                iso(-ex, -ey, ez), iso(ex, -ey, ez), iso(ex, ey, ez), iso(-ex, ey, ez)       // 后面
            ];
            
            // 绘制边
            const edges = [
                [0,1], [1,2], [2,3], [3,0],  // 前面
                [4,5], [5,6], [6,7], [7,4],  // 后面
                [0,4], [1,5], [2,6], [3,7]   // 连接
            ];
            
            let lines = edges.map(([a, b]) => 
                `<line x1="${{vertices[a].split(',')[0]}}" y1="${{vertices[a].split(',')[1]}}" 
                       x2="${{vertices[b].split(',')[0]}}" y2="${{vertices[b].split(',')[1]}}" 
                       stroke="#58a6ff" stroke-width="1.5" opacity="0.8"/>`
            ).join('');
            
            // 中心点
            const center = iso(0, 0, 0);
            lines += `<circle cx="${{center.split(',')[0]}}" cy="${{center.split(',')[1]}}" r="3" fill="#f0883e"/>`;
            
            return `<svg width="${{w}}" height="${{h}}" viewBox="0 0 ${{w}} ${{h}}">
                <rect width="100%" height="100%" fill="#21262d" rx="4"/>
                ${{lines}}
            </svg>`;
        }}
        
        // renderUVPreviewSVG 已移除 - UV 三角形可视化无实际价值
        
        // ========== API 调用详情渲染 ==========
        function renderEventApiCall(event) {{
            const apiCall = event.apiCall;
            
            // 无 API 调用数据
            if (!apiCall) {{
                return `<div class="event-detail-empty">
                    <div class="icon">📝</div>
                    <div>此 Event 类型无 API 调用数据</div>
                    <div class="hint">仅 Draw/Dispatch 调用包含详细 API 指令</div>
                </div>`;
            }}
            
            let html = '';
            
            // 主调用签名卡片
            html += `
                <div class="event-detail-card api-call-card">
                    <div class="event-detail-card-header">📝 主调用指令</div>
                    <div class="event-detail-card-body">
                        <div class="api-signature">
                            <span class="api-return-type">${{apiCall.returnType || 'void'}}</span>
                            <span class="api-func-name">${{apiCall.signature}}</span>
                            <span class="api-paren">(</span>
                        </div>
                        <div class="api-params-list">
                            ${{apiCall.params.map((p, i) => `
                                <div class="api-param-row">
                                    <span class="api-param-type">${{p.type}}</span>
                                    <span class="api-param-name">${{p.name}}</span>
                                    <span class="api-param-sep">=</span>
                                    <span class="api-param-value">${{formatApiValue(p.value, p.type)}}</span>
                                    ${{i < apiCall.params.length - 1 ? '<span class="api-param-comma">,</span>' : ''}}
                                </div>
                            `).join('')}}
                        </div>
                        <div class="api-signature">
                            <span class="api-paren">);</span>
                        </div>
                    </div>
                </div>
            `;
            
            // 关联调用（如 IASetIndexBuffer, RSSetViewports 等）
            // 过滤掉 null/undefined 值，并兼容字符串和对象格式
            const validRelatedCalls = (apiCall.relatedCalls || []).filter(c => c != null);
            
            if (validRelatedCalls.length > 0) {{
                html += `
                    <div class="event-detail-card api-call-card">
                        <div class="event-detail-card-header">🔗 关联状态调用 <span class="count-badge">${{validRelatedCalls.length}}</span></div>
                        <div class="event-detail-card-body">
                            <div class="related-calls-list">
                                ${{validRelatedCalls.map(call => {{
                                    // 兼容字符串格式：直接是调用签名字符串
                                    if (typeof call === 'string') {{
                                        // 从字符串中提取函数名
                                        const funcMatch = call.match(/^([a-zA-Z_][a-zA-Z0-9_:]*)\s*\(/);
                                        const funcName = funcMatch ? funcMatch[1] : call.split('(')[0];
                                        // 提取参数部分作为摘要
                                        const paramsMatch = call.match(/\(([^)]*)\)/);
                                        const paramsSummary = paramsMatch ? paramsMatch[1] : '';
                                        
                                        return `
                                            <div class="related-call-item">
                                                <div class="related-call-header simple">
                                                    <span class="call-name">${{funcName}}</span>
                                                    <span class="call-summary">${{paramsSummary.length > 60 ? paramsSummary.slice(0, 60) + '...' : paramsSummary}}</span>
                                                </div>
                                            </div>
                                        `;
                                    }}
                                    
                                    // 对象格式：包含 name, params, summary 等字段
                                    return `
                                        <div class="related-call-item ${{call.stateGroup ? 'state-' + call.stateGroup : ''}}">
                                            <div class="related-call-header" onclick="toggleRelatedCall(this)">
                                                <span class="expand-icon">▶</span>
                                                <span class="call-name">${{call.name}}</span>
                                                <span class="call-summary">${{call.summary || ''}}</span>
                                            </div>
                                            <div class="related-call-body" style="display:none;">
                                                ${{call.params ? call.params.map(p => `
                                                    <div class="api-param-row compact">
                                                        <span class="api-param-name">${{p.name}}</span>
                                                        <span class="api-param-sep">=</span>
                                                        <span class="api-param-value">${{formatApiValue(p.value, p.type)}}</span>
                                                    </div>
                                                `).join('') : '<div class="no-params">无参数</div>'}}
                                            </div>
                                        </div>
                                    `;
                                }}).join('')}}
                            </div>
                        </div>
                    </div>
                `;
            }}
            
            // 调用说明
            html += `
                <div class="event-detail-card">
                    <div class="event-detail-card-header">💡 说明</div>
                    <div class="event-detail-card-body">
                        <div class="api-note">
                            此数据模拟自 RenderDoc 捕获的 API 调用序列。<br/>
                            实际生产环境中，这些指令直接来自 RDC 文件的 StructuredFile Chunk 数据。
                        </div>
                    </div>
                </div>
            `;
            
            return html;
        }}
        
        // 格式化 API 参数值
        function formatApiValue(value, type) {{
            if (value === null || value === undefined) return '<span class="null-val">NULL</span>';
            
            // 十六进制整数 (句柄/地址)
            if (typeof value === 'number' && (type?.includes('Handle') || type?.includes('Ptr') || type?.includes('UINT64'))) {{
                return `<span class="hex-val">0x${{value.toString(16).toUpperCase()}}</span>`;
            }}
            
            // 普通数字
            if (typeof value === 'number') {{
                return `<span class="num-val">${{value}}</span>`;
            }}
            
            // 布尔值
            if (typeof value === 'boolean') {{
                return `<span class="bool-val">${{value ? 'TRUE' : 'FALSE'}}</span>`;
            }}
            
            // 字符串
            if (typeof value === 'string') {{
                // 枚举值检测 (包含下划线或全大写)
                if (/^[A-Z][A-Z0-9_]+$/.test(value) || value.includes('_')) {{
                    return `<span class="enum-val">${{value}}</span>`;
                }}
                return `<span class="str-val">"${{value}}"</span>`;
            }}
            
            // 数组
            if (Array.isArray(value)) {{
                if (value.length <= 4) {{
                    return `<span class="arr-val">[${{value.join(', ')}}]</span>`;
                }}
                return `<span class="arr-val">[${{value.slice(0, 3).join(', ')}}, ... +${{value.length - 3}}]</span>`;
            }}
            
            // 对象
            if (typeof value === 'object') {{
                return `<span class="obj-val">${{JSON.stringify(value)}}</span>`;
            }}
            
            return String(value);
        }}
        
        // 切换关联调用的展开/折叠
        function toggleRelatedCall(headerEl) {{
            const body = headerEl.nextElementSibling;
            const icon = headerEl.querySelector('.expand-icon');
            const isExpanded = body.style.display !== 'none';
            
            body.style.display = isExpanded ? 'none' : 'block';
            icon.textContent = isExpanded ? '▶' : '▼';
            headerEl.classList.toggle('expanded', !isExpanded);
        }}
        
        function switchEventTab(tab) {{
            currentEventTab = tab;
            
            // 更新 tab 状态
            document.querySelectorAll('.event-detail-tabs .tab').forEach(t => {{
                t.classList.toggle('active', t.dataset.tab === tab);
            }});
            
            // 重新渲染详情
            if (selectedEventEid !== null) {{
                renderEventDetail(selectedEventEid);
            }}
        }}
        
        function jumpToTexture(texId) {{
            // 切换回主视图并选中纹理
            viewMode = 'app';
            updateViewMode();
            
            // 使用 selectTextureByResourceId 选中纹理
            selectTextureByResourceId(texId);
            
            // 滚动后添加高亮闪烁效果
            setTimeout(() => {{
                const selected = document.querySelector('.texture-item.selected');
                if (selected) {{
                    selected.classList.add('jump-highlight');
                    setTimeout(() => selected.classList.remove('jump-highlight'), 1500);
                }}
            }}, 150);
        }}
        
        // 切换 Constant Buffer 成员变量展开/折叠
        function toggleCBMembers(e, headerEl) {{
            e.stopPropagation();
            const membersBody = headerEl.nextElementSibling;
            const isExpanded = membersBody.style.display !== 'none';
            
            membersBody.style.display = isExpanded ? 'none' : 'block';
            headerEl.classList.toggle('expanded', !isExpanded);
        }}
        
        // Event Browser 搜索
        document.addEventListener('DOMContentLoaded', function() {{
            const searchBox = document.getElementById('eventSearchBox');
            if (searchBox) {{
                searchBox.addEventListener('input', function() {{
                    renderEventTree();
                }});
            }}
            
            // ========== Event 面板拖拽调整宽度 ==========
            initPanelResizer();
        }});
        
        // 初始化面板拖拽分隔条
        function initPanelResizer() {{
            const resizer = document.getElementById('eventPanelResizer');
            const panel = document.querySelector('.event-tree-panel');
            
            if (!resizer || !panel) return;
            
            // 从 localStorage 恢复宽度
            const savedWidth = localStorage.getItem('eventPanelWidth');
            if (savedWidth) {{
                const width = parseInt(savedWidth, 10);
                if (width >= 280 && width <= 600) {{
                    panel.style.width = width + 'px';
                }}
            }}
            
            let isDragging = false;
            let startX = 0;
            let startWidth = 0;
            
            resizer.addEventListener('mousedown', function(e) {{
                isDragging = true;
                startX = e.clientX;
                startWidth = panel.offsetWidth;
                
                resizer.classList.add('dragging');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                
                e.preventDefault();
            }});
            
            document.addEventListener('mousemove', function(e) {{
                if (!isDragging) return;
                
                const diff = e.clientX - startX;
                let newWidth = startWidth + diff;
                
                // 限制范围
                newWidth = Math.max(280, Math.min(600, newWidth));
                
                panel.style.width = newWidth + 'px';
            }});
            
            document.addEventListener('mouseup', function(e) {{
                if (!isDragging) return;
                
                isDragging = false;
                resizer.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                
                // 保存到 localStorage
                localStorage.setItem('eventPanelWidth', panel.offsetWidth);
            }});
        }}
        
        // 滤镜调整
        function updateFilterApp() {{
            const brightness = document.getElementById('brightnessApp').value;
            const contrast = document.getElementById('contrastApp').value;
            
            document.getElementById('brightnessValApp').textContent = brightness + '%';
            document.getElementById('contrastValApp').textContent = contrast + '%';
            
            const img = document.getElementById('previewImgApp');
            if (img) {{
                img.style.filter = `brightness(${{brightness}}%) contrast(${{contrast}}%)`;
            }}
        }}
        
        // 直方图绘制 (简化版)
        function drawHistogramApp() {{
            const canvas = document.getElementById('histogramCanvasApp');
            if (!canvas) return;
            
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 占位：显示渐变条表示无数据
            const grad = ctx.createLinearGradient(0, 0, canvas.width, 0);
            grad.addColorStop(0, '#1a1a2e');
            grad.addColorStop(1, '#2a2a3e');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = '#6e7681';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('选中纹理后显示直方图', canvas.width / 2, canvas.height / 2 + 4);
        }}
        
        // ========== 导出功能 ==========
        
        // 导出为 CSV
        function exportToCSV() {{
            const headers = ['ID', '名称', '宽度', '高度', '深度', '格式', 'Mips', 'Layers', 'VRAM (KB)'];
            const rows = filteredTextures.map(tex => {{
                const vram = calculateTextureVRAM(tex);
                return [
                    tex.id,
                    `"${{(tex.name || '').replace(/"/g, '""')}}"`,  // 转义引号
                    tex.width,
                    tex.height,
                    tex.depth || 1,
                    tex.format,
                    tex.mips || 1,
                    tex.arrayLayers || 1,
                    (vram / 1024).toFixed(2)
                ].join(',');
            }});
            
            const csv = [headers.join(','), ...rows].join('\\n');
            downloadFile(csv, 'textures_export.csv', 'text/csv');
        }}
        
        // 导出为 JSON
        function exportToJSON() {{
            const exportData = {{
                exportTime: new Date().toISOString(),
                totalTextures: filteredTextures.length,
                textures: filteredTextures.map(tex => ({{
                    id: tex.id,
                    name: tex.name || null,
                    width: tex.width,
                    height: tex.height,
                    depth: tex.depth || 1,
                    format: tex.format,
                    mips: tex.mips || 1,
                    arrayLayers: tex.arrayLayers || 1,
                    estimatedVRAM: calculateTextureVRAM(tex),
                    hasThumbnail: !!tex.thumbnail
                }}))
            }};
            
            const json = JSON.stringify(exportData, null, 2);
            downloadFile(json, 'textures_export.json', 'application/json');
        }}
        
        // 导出完整分析数据（含 Events 和 Passes）
        function exportFullAnalysisJSON() {{
            const issues = window.textureIssues || {{}};
            const dupAnalysis = window.duplicateAnalysis || {{}};
            const usageAnalysis = window.usageAnalysis || {{}};
            
            const exportData = {{
                exportTime: new Date().toISOString(),
                exportVersion: '1.0',
                
                // 基础信息
                summary: {{
                    totalTextures: textures.length,
                    totalVRAM: calculateTotalVRAM(),
                    formatDistribution: getFormatDistribution(),
                    issueCount: {{
                        noMipmap: issues.noMipmap?.length || 0,
                        nonPow2: issues.nonPow2?.length || 0,
                        oversized: issues.oversized?.length || 0,
                        uncompressed: issues.uncompressed?.length || 0
                    }}
                }},
                
                // Event/Pass 数据
                eventPassData: eventPassData ? {{
                    apiType: eventPassData.apiType,
                    totalEvents: eventPassData.totalEvents,
                    totalDraws: eventPassData.totalDraws,
                    totalDispatches: eventPassData.totalDispatches,
                    frameDuration: eventPassData.frameDuration,
                    passes: eventPassData.passes?.map(p => ({{
                        name: p.name,
                        type: p.type,
                        isInferred: p.isInferred,
                        drawCount: p.drawCount,
                        duration: p.duration,
                        inputs: p.inputs,
                        outputs: p.outputs
                    }})) || [],
                    events: eventPassData.events?.map(e => ({{
                        eid: e.eid,
                        name: e.name,
                        displayName: e.displayName,
                        type: e.type,
                        duration: e.duration,
                        parent: e.parent
                    }})) || []
                }} : null,
                
                // 纹理列表（简化版，无缩略图）
                textures: textures.map(tex => ({{
                    id: tex.id,
                    name: tex.name || null,
                    width: tex.width,
                    height: tex.height,
                    depth: tex.depth || 1,
                    format: tex.format,
                    mips: tex.mips || 1,
                    arrayLayers: tex.arrayLayers || 1,
                    estimatedVRAM: calculateTextureVRAM(tex)
                }})),
                
                // 去重分析
                duplicateAnalysis: dupAnalysis.duplicate_groups ? {{
                    totalGroups: dupAnalysis.duplicate_groups.length,
                    wastedVRAM: dupAnalysis.wasted_vram,
                    groups: dupAnalysis.duplicate_groups.map(g => ({{
                        hash: g.hash,
                        textureIds: g.textures.map(t => t.id),
                        wastedCount: g.textures.length - 1
                    }}))
                }} : null,
                
                // 使用情况
                usageAnalysis: usageAnalysis.used_textures ? {{
                    usedCount: usageAnalysis.used_textures.length,
                    unusedCount: usageAnalysis.unused_textures.length,
                    unusedIds: usageAnalysis.unused_textures.map(t => t.id)
                }} : null
            }};
            
            // 辅助函数
            function getFormatDistribution() {{
                const dist = {{}};
                textures.forEach(tex => {{
                    const fmt = tex.format || 'Unknown';
                    dist[fmt] = (dist[fmt] || 0) + 1;
                }});
                return dist;
            }}
            
            const json = JSON.stringify(exportData, null, 2);
            downloadFile(json, 'rdc_full_analysis.json', 'application/json');
        }}
        
        // 下载当前选中的纹理图片
        function downloadCurrentTexture() {{
            if (selectedTextureIndex < 0 || selectedTextureIndex >= filteredTextures.length) {{
                alert('请先选择一个纹理');
                return;
            }}
            
            const tex = filteredTextures[selectedTextureIndex];
            if (!tex.thumbnail) {{
                alert('该纹理没有缩略图数据');
                return;
            }}
            
            // 创建下载链接
            const link = document.createElement('a');
            link.href = tex.thumbnail;
            link.download = `${{tex.name || 'texture_' + tex.id}}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
        
        // 生成报告摘要
        function exportReport() {{
            const issues = window.textureIssues || {{}};
            const totalVRAM = calculateTotalVRAM();
            
            let report = `# RDC 纹理分析报告\\n`;
            report += `生成时间: ${{new Date().toLocaleString()}}\\n\\n`;
            report += `## 总体统计\\n`;
            report += `- 纹理总数: ${{textures.length}}\\n`;
            report += `- 预估 VRAM: ${{(totalVRAM / 1024 / 1024).toFixed(2)}} MB\\n`;
            report += `- 格式种类: ${{new Set(textures.map(t => t.format)).size}}\\n\\n`;
            
            report += `## 问题汇总\\n`;
            if (issues.noMipmap?.length) {{
                report += `- ⚠️ 无 Mipmap: ${{issues.noMipmap.length}} 个\\n`;
            }}
            if (issues.nonPow2?.length) {{
                report += `- ⚠️ 非2的幂尺寸: ${{issues.nonPow2.length}} 个\\n`;
            }}
            if (issues.oversized?.length) {{
                report += `- ⚠️ 超大纹理 (≥4K): ${{issues.oversized.length}} 个\\n`;
            }}
            if (issues.uncompressed?.length) {{
                report += `- ⚠️ 未压缩: ${{issues.uncompressed.length}} 个\\n`;
            }}
            
            // 添加去重分析结果
            const dupAnalysis = window.duplicateAnalysis || {{}};
            if (dupAnalysis.duplicate_groups?.length > 0) {{
                report += `\\n## 🔁 重复纹理分析\\n`;
                report += `- 发现 ${{dupAnalysis.duplicate_groups.length}} 组重复纹理\\n`;
                report += `- 浪费 VRAM: ${{(dupAnalysis.total_wasted_bytes / 1024 / 1024).toFixed(2)}} MB\\n`;
                report += `- 多余纹理数: ${{dupAnalysis.total_duplicate_count}} 个\\n`;
                if (dupAnalysis.metadata_only) {{
                    report += `- ⚠️ *仅基于元数据检测（未验证内容哈希）*\\n`;
                }}
                
                report += `\\n### 重复组详情 (前10组)\\n\\n`;
                dupAnalysis.duplicate_groups.slice(0, 10).forEach((group, idx) => {{
                    const texNames = group.textures.map(t => t.name || `ID:${{t.resource_id}}`).join(', ');
                    report += `**组 ${{idx + 1}}** (${{group.count}} 个重复, 浪费 ${{(group.wasted_bytes / 1024).toFixed(1)}} KB)\\n`;
                    report += `- 纹理: ${{texNames}}\\n`;
                    if (group.textures[0]) {{
                        const t = group.textures[0];
                        report += `- 规格: ${{t.width}}×${{t.height}}, ${{t.format}}\\n`;
                    }}
                    report += `\\n`;
                }});
                
                if (dupAnalysis.duplicate_groups.length > 10) {{
                    report += `... 还有 ${{dupAnalysis.duplicate_groups.length - 10}} 组\\n`;
                }}
            }}
            
            // 添加热度分析结果
            const usageData = window.usageAnalysis || {{}};
            if (usageData.hot_list?.length > 0 || usageData.cold_list?.length > 0) {{
                report += `\\n## 🔥 纹理热度分析\\n`;
                report += `- 扫描事件数: ${{usageData.total_events || 0}}\\n`;
                report += `- 已使用纹理: ${{usageData.used_textures || 0}}\\n`;
                report += `- 未使用纹理: ${{usageData.unused_textures || 0}}\\n\\n`;
                
                // 热门纹理
                if (usageData.hot_list?.length > 0) {{
                    report += `### 🔥 热门纹理 (Top 10)\\n\\n`;
                    report += `| 排名 | 纹理 | 引用次数 | 尺寸 |\\n`;
                    report += `|------|------|----------|------|\\n`;
                    usageData.hot_list.slice(0, 10).forEach((t, i) => {{
                        const name = t.name || `ID:${{t.resource_id}}`;
                        const size = t.estimated_size ? (t.estimated_size / 1024).toFixed(1) + ' KB' : '-';
                        report += `| ${{i + 1}} | ${{name}} | ${{t.use_count}}× | ${{size}} |\\n`;
                    }});
                    report += `\\n`;
                }}
                
                // 未使用纹理（冷数据）
                if (usageData.cold_list?.length > 0) {{
                    report += `### ❄️ 未使用纹理 (可能冗余)\\n\\n`;
                    let coldWaste = 0;
                    usageData.cold_list.forEach(t => {{ coldWaste += t.estimated_size || 0; }});
                    report += `- ⚠️ 潜在浪费: ${{(coldWaste / 1024 / 1024).toFixed(2)}} MB\\n\\n`;
                    
                    report += `| 纹理 | 尺寸 | 格式 |\\n`;
                    report += `|------|------|------|\\n`;
                    usageData.cold_list.slice(0, 20).forEach(t => {{
                        const name = t.name || `ID:${{t.resource_id}}`;
                        const size = t.estimated_size ? (t.estimated_size / 1024).toFixed(1) + ' KB' : '-';
                        report += `| ${{name}} | ${{size}} | ${{t.format || '-'}} |\\n`;
                    }});
                    
                    if (usageData.cold_list.length > 20) {{
                        report += `\\n... 还有 ${{usageData.cold_list.length - 20}} 个未使用纹理\\n`;
                    }}
                    report += `\\n`;
                }}
            }}
            
            report += `\\n## 纹理列表 (前50个)\\n\\n`;
            report += `| ID | 名称 | 尺寸 | 格式 | Mips |\\n`;
            report += `|----|------|------|------|------|\\n`;
            textures.slice(0, 50).forEach(tex => {{
                report += `| ${{tex.id}} | ${{tex.name || '-'}} | ${{tex.width}}×${{tex.height}} | ${{tex.format}} | ${{tex.mips || 1}} |\\n`;
            }});
            
            if (textures.length > 50) {{
                report += `\\n... 还有 ${{textures.length - 50}} 个纹理\\n`;
            }}
            
            downloadFile(report, 'texture_report.md', 'text/markdown');
        }}
        
        // 导出优化建议报告
        function exportOptimizationReport() {{
            const dupData = window.duplicateAnalysis || {{}};
            const usageData = window.usageAnalysis || {{}};
            const issues = window.textureIssues || {{}};
            
            let report = `# 🎯 纹理优化建议报告\\n\\n`;
            report += `**文件**: {rdc_name}\\n`;
            report += `**生成时间**: ${{new Date().toLocaleString()}}\\n\\n`;
            report += `---\\n\\n`;
            
            // 计算预估节省
            let totalSavings = 0;
            let itemCount = 0;
            
            report += `## 📊 总览\\n\\n`;
            
            // 统计问题
            const summaryItems = [];
            
            // 1. 重复纹理
            if (dupData.duplicate_groups?.length > 0) {{
                summaryItems.push(`重复纹理: ${{dupData.duplicate_groups.length}} 组`);
                totalSavings += dupData.total_wasted_bytes || 0;
                itemCount++;
            }}
            
            // 2. 未使用纹理
            if (usageData.cold_list?.length > 0) {{
                let coldWaste = 0;
                usageData.cold_list.forEach(t => {{ coldWaste += t.estimated_size || 0; }});
                summaryItems.push(`未使用纹理: ${{usageData.cold_list.length}} 个`);
                totalSavings += coldWaste;
                itemCount++;
            }}
            
            // 3. 无 Mipmap
            if (issues.noMipmap?.length > 0) {{
                summaryItems.push(`无 Mipmap: ${{issues.noMipmap.length}} 个`);
                itemCount++;
            }}
            
            // 4. 未压缩
            if (issues.uncompressed?.length > 0) {{
                summaryItems.push(`未压缩: ${{issues.uncompressed.length}} 个`);
                itemCount++;
            }}
            
            // 5. 超大纹理
            if (issues.oversized?.length > 0) {{
                summaryItems.push(`超大纹理 (4K+): ${{issues.oversized.length}} 个`);
                itemCount++;
            }}
            
            // 6. 非 POT
            if (issues.nonPow2?.length > 0) {{
                summaryItems.push(`非 POT 尺寸: ${{issues.nonPow2.length}} 个`);
                itemCount++;
            }}
            
            report += `| 指标 | 值 |\\n`;
            report += `|------|-----|\\n`;
            report += `| 发现问题数 | ${{itemCount}} 类 |\\n`;
            report += `| 预计可节省 | **${{(totalSavings / 1024 / 1024).toFixed(2)}} MB** |\\n\\n`;
            
            if (summaryItems.length > 0) {{
                report += `**问题汇总**: ${{summaryItems.join(' | ')}}\\n\\n`;
            }}
            
            // ====== 高优先级 ======
            report += `## 🟠 高优先级 (强烈建议)\\n\\n`;
            
            // 重复纹理详情
            if (dupData.duplicate_groups?.length > 0) {{
                report += `### 1. 移除重复纹理 *(可节省 ${{(dupData.total_wasted_bytes / 1024 / 1024).toFixed(2)}} MB)*\\n\\n`;
                report += `**类别**: 清理冗余\\n\\n`;
                report += `检测到 ${{dupData.duplicate_groups.length}} 组内容相同的重复纹理。\\n\\n`;
                report += `**操作步骤**:\\n`;
                report += `- [ ] 确认重复纹理是否应该共用同一资源\\n`;
                report += `- [ ] 在资产管理系统中合并重复项\\n`;
                report += `- [ ] 更新所有引用指向唯一资源\\n\\n`;
                
                report += `<details>\\n<summary>重复组详情 (前5组)</summary>\\n\\n`;
                dupData.duplicate_groups.slice(0, 5).forEach((g, i) => {{
                    const names = g.textures.map(t => t.name || ('ID:' + t.resource_id)).join(', ');
                    report += '**组 ' + (i+1) + '**: ' + g.count + ' 个重复 (' + (g.wasted_bytes/1024).toFixed(1) + ' KB)\\n';
                    report += '- ' + names + '\\n\\n';
                }});
                report += `</details>\\n\\n---\\n\\n`;
            }}
            
            // 未使用纹理详情
            if (usageData.cold_list?.length > 0) {{
                let coldWaste = 0;
                usageData.cold_list.forEach(t => {{ coldWaste += t.estimated_size || 0; }});
                
                report += `### 2. 清理未使用纹理 *(可节省 ${{(coldWaste / 1024 / 1024).toFixed(2)}} MB)*\\n\\n`;
                report += `**类别**: 清理冗余\\n\\n`;
                report += `在帧中有 ${{usageData.cold_list.length}} 个纹理从未被 Draw Call 引用。\\n\\n`;
                report += `**操作步骤**:\\n`;
                report += `- [ ] 确认这些纹理是否确实不需要\\n`;
                report += `- [ ] 检查是否为其他帧使用的资源\\n`;
                report += `- [ ] 优化资源加载策略\\n\\n`;
                
                report += `<details>\\n<summary>未使用纹理列表 (前10个)</summary>\\n\\n`;
                usageData.cold_list.slice(0, 10).forEach(t => {{
                    const name = t.name || ('ID:' + t.resource_id);
                    const size = t.estimated_size ? (t.estimated_size / 1024).toFixed(1) + ' KB' : '-';
                    report += '- ' + name + ' (' + size + ')\\n';
                }});
                report += `</details>\\n\\n---\\n\\n`;
            }}
            
            // ====== 中优先级 ======
            report += `## 🟡 中优先级 (建议)\\n\\n`;
            
            // 无 Mipmap
            if (issues.noMipmap?.length > 0) {{
                report += `### 为 ${{issues.noMipmap.length}} 个纹理生成 Mipmap\\n\\n`;
                report += `**类别**: 质量优化\\n\\n`;
                report += `缺少 Mipmap 会导致远距离采样时的摩尔纹和性能问题。\\n\\n`;
                report += `**操作步骤**:\\n`;
                report += `- [ ] 在纹理导入设置中启用 'Generate Mipmaps'\\n`;
                report += `- [ ] 对于 UI 纹理可跳过\\n\\n`;
                
                report += `<details>\\n<summary>涉及资源 (${{issues.noMipmap.length}} 个)</summary>\\n\\n`;
                issues.noMipmap.slice(0, 20).forEach(id => {{
                    const tex = textures.find(t => t.id === id);
                    if (tex) report += '- ' + (tex.name || 'ID:'+id) + ' (' + tex.width + '×' + tex.height + ')\\n';
                }});
                report += `</details>\\n\\n---\\n\\n`;
            }}
            
            // 超大纹理
            if (issues.oversized?.length > 0) {{
                report += `### 评估 ${{issues.oversized.length}} 个 4K+ 超大纹理\\n\\n`;
                report += `**类别**: 内存优化\\n\\n`;
                report += `超大纹理占用大量 VRAM，应评估是否真正需要如此高分辨率。\\n\\n`;
                report += `**操作步骤**:\\n`;
                report += `- [ ] 评估实际渲染中的可见尺寸\\n`;
                report += `- [ ] 考虑流式加载 (Texture Streaming)\\n\\n`;
                
                report += `<details>\\n<summary>涉及资源</summary>\\n\\n`;
                issues.oversized.slice(0, 10).forEach(id => {{
                    const tex = textures.find(t => t.id === id);
                    if (tex) report += '- ' + (tex.name || 'ID:'+id) + ' (' + tex.width + '×' + tex.height + ', ' + tex.format + ')\\n';
                }});
                report += `</details>\\n\\n---\\n\\n`;
            }}
            
            // ====== 最佳实践 ======
            report += `## 💡 最佳实践参考\\n\\n`;
            report += `1. **压缩格式**: 优先使用 BC7 (高质量) 或 BC1 (体积优先)\\n`;
            report += `2. **Mipmap**: 所有运行时纹理都应有 Mipmap (UI除外)\\n`;
            report += `3. **尺寸规范**: 使用 2 的幂次尺寸 (256, 512, 1024...)\\n`;
            report += `4. **避免重复**: 使用纹理图集或共享引用\\n`;
            report += `5. **按需加载**: 大纹理考虑流式加载\\n\\n`;
            report += `---\\n*报告由 RenderDoc Texture Analyzer 自动生成*\\n`;
            
            downloadFile(report, 'optimization_report.md', 'text/markdown');
        }}
        
        // 导出优化建议 JSON (机器可读格式)
        function exportOptimizationJSON() {{
            const dupData = window.duplicateAnalysis || {{}};
            const usageData = window.usageAnalysis || {{}};
            const issues = window.textureIssues || {{}};
            
            // 计算各类问题节省的空间
            let coldWaste = 0;
            (usageData.cold_list || []).forEach(t => {{ coldWaste += t.estimated_size || 0; }});
            
            const exportData = {{
                meta: {{
                    file: "{rdc_name}",
                    generated: new Date().toISOString(),
                    version: "2.0"
                }},
                summary: {{
                    total_textures: textures.length,
                    total_vram: calculateTotalVRAM(),
                    issue_categories: 0,
                    estimated_savings: 0
                }},
                issues: {{
                    duplicates: {{
                        count: dupData.duplicate_groups?.length || 0,
                        wasted_bytes: dupData.total_wasted_bytes || 0,
                        priority: "high",
                        groups: (dupData.duplicate_groups || []).map(g => ({{
                            hash: g.hash,
                            count: g.count,
                            wasted_bytes: g.wasted_bytes,
                            textures: g.textures.map(t => ({{
                                id: t.resource_id,
                                name: t.name || ""
                            }}))
                        }}))
                    }},
                    unused: {{
                        count: usageData.cold_list?.length || 0,
                        wasted_bytes: coldWaste,
                        priority: "high",
                        textures: (usageData.cold_list || []).map(t => ({{
                            id: t.resource_id,
                            name: t.name || "",
                            size: t.estimated_size || 0
                        }}))
                    }},
                    no_mipmap: {{
                        count: issues.noMipmap?.length || 0,
                        priority: "medium",
                        textures: (issues.noMipmap || []).map(t => ({{
                            id: t.id,
                            name: t.name || "",
                            width: t.width,
                            height: t.height,
                            format: t.format
                        }}))
                    }},
                    oversized: {{
                        count: issues.oversized?.length || 0,
                        priority: "medium",
                        textures: (issues.oversized || []).map(t => ({{
                            id: t.id,
                            name: t.name || "",
                            width: t.width,
                            height: t.height,
                            format: t.format
                        }}))
                    }},
                    uncompressed: {{
                        count: issues.uncompressed?.length || 0,
                        priority: "low",
                        textures: (issues.uncompressed || []).map(t => ({{
                            id: t.id,
                            name: t.name || "",
                            width: t.width,
                            height: t.height,
                            format: t.format
                        }}))
                    }},
                    non_power_of_two: {{
                        count: issues.nonPow2?.length || 0,
                        priority: "low",
                        textures: (issues.nonPow2 || []).map(t => ({{
                            id: t.id,
                            name: t.name || "",
                            width: t.width,
                            height: t.height,
                            format: t.format
                        }}))
                    }}
                }}
            }};
            
            // 计算汇总
            let issueCount = 0;
            let totalSavings = 0;
            
            if (exportData.issues.duplicates.count > 0) {{
                issueCount++;
                totalSavings += exportData.issues.duplicates.wasted_bytes;
            }}
            if (exportData.issues.unused.count > 0) {{
                issueCount++;
                totalSavings += exportData.issues.unused.wasted_bytes;
            }}
            if (exportData.issues.no_mipmap.count > 0) issueCount++;
            if (exportData.issues.oversized.count > 0) issueCount++;
            if (exportData.issues.uncompressed.count > 0) issueCount++;
            if (exportData.issues.non_power_of_two.count > 0) issueCount++;
            
            exportData.summary.issue_categories = issueCount;
            exportData.summary.estimated_savings = totalSavings;
            
            const json = JSON.stringify(exportData, null, 2);
            downloadFile(json, 'optimization_report.json', 'application/json');
        }}
        
        // 导出优化建议 CSV (简化表格)
        function exportOptimizationCSV() {{
            const dupData = window.duplicateAnalysis || {{}};
            const usageData = window.usageAnalysis || {{}};
            const issues = window.textureIssues || {{}};
            
            let csv = 'Category,Priority,Texture ID,Texture Name,Width,Height,Format,Issue Details,Estimated Savings (KB)\\n';
            
            // 重复纹理
            (dupData.duplicate_groups || []).forEach(g => {{
                g.textures.slice(1).forEach(t => {{  // 跳过第一个（保留项）
                    const tex = textures.find(x => x.id === t.resource_id);
                    csv += `Duplicate,High,${{t.resource_id}},"${{(t.name || '').replace(/"/g, '""')}}",${{tex?.width || 0}},${{tex?.height || 0}},${{tex?.format || ''}},"Group: ${{g.hash.substring(0,8)}}",${{(g.wasted_bytes / g.count / 1024).toFixed(1)}}\\n`;
                }});
            }});
            
            // 未使用纹理
            (usageData.cold_list || []).forEach(t => {{
                const tex = textures.find(x => x.id === t.resource_id);
                csv += `Unused,High,${{t.resource_id}},"${{(t.name || '').replace(/"/g, '""')}}",${{tex?.width || 0}},${{tex?.height || 0}},${{tex?.format || ''}},"Never used in frame",${{((t.estimated_size || 0) / 1024).toFixed(1)}}\\n`;
            }});
            
            // 无 Mipmap (issues.noMipmap 存储的是纹理对象而非 ID)
            (issues.noMipmap || []).forEach(tex => {{
                if (tex) {{
                    csv += `NoMipmap,Medium,${{tex.id}},"${{(tex.name || '').replace(/"/g, '""')}}",${{tex.width}},${{tex.height}},${{tex.format}},"Only 1 mip level",0\\n`;
                }}
            }});
            
            // 超大纹理
            (issues.oversized || []).forEach(tex => {{
                if (tex) {{
                    csv += `Oversized,Medium,${{tex.id}},"${{(tex.name || '').replace(/"/g, '""')}}",${{tex.width}},${{tex.height}},${{tex.format}},"4K+ resolution",0\\n`;
                }}
            }});
            
            // 未压缩
            (issues.uncompressed || []).forEach(tex => {{
                if (tex) {{
                    csv += `Uncompressed,Low,${{tex.id}},"${{(tex.name || '').replace(/"/g, '""')}}",${{tex.width}},${{tex.height}},${{tex.format}},"Consider BC7/ASTC",0\\n`;
                }}
            }});
            
            // 非 POT
            (issues.nonPow2 || []).forEach(tex => {{
                if (tex) {{
                    csv += `NonPOT,Low,${{tex.id}},"${{(tex.name || '').replace(/"/g, '""')}}",${{tex.width}},${{tex.height}},${{tex.format}},"Non power-of-two",0\\n`;
                }}
            }});
            
            downloadFile(csv, 'optimization_issues.csv', 'text/csv');
        }}
        
        // 计算单个纹理的 VRAM
        function calculateTextureVRAM(tex) {{
            const bpp = getBytesPerPixel(tex.format);
            let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
            const mips = tex.mips || 1;
            
            // 计算所有 mip 级别
            if (mips > 1) {{
                let w = tex.width, h = tex.height;
                let totalPixels = 0;
                for (let m = 0; m < mips; m++) {{
                    totalPixels += w * h;
                    w = Math.max(1, Math.floor(w / 2));
                    h = Math.max(1, Math.floor(h / 2));
                }}
                pixels = totalPixels * (tex.depth || 1) * (tex.arrayLayers || 1);
            }}
            
            return pixels * bpp;
        }}
        
        // 计算总 VRAM
        function calculateTotalVRAM() {{
            return textures.reduce((sum, tex) => sum + calculateTextureVRAM(tex), 0);
        }}
        
        // 通用下载函数
        function downloadFile(content, filename, mimeType) {{
            const blob = new Blob([content], {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }}
        
        // 更新统计摘要面板
        function updateStatsPanel() {{
            // 总数
            document.getElementById('statTotal').textContent = textures.length;
            
            // 格式种类
            const formats = new Set(textures.map(t => t.format));
            document.getElementById('statFormats').textContent = formats.size;
            
            // 平均尺寸
            if (textures.length > 0) {{
                const avgW = Math.round(textures.reduce((s, t) => s + t.width, 0) / textures.length);
                const avgH = Math.round(textures.reduce((s, t) => s + t.height, 0) / textures.length);
                document.getElementById('statAvgSize').textContent = `${{avgW}}×${{avgH}}`;
            }}
            
            // 预估 VRAM (根据格式估算每像素字节数)
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5,
                'BC2_UNORM': 1, 'BC2_SRGB': 1,
                'BC3_UNORM': 1, 'BC3_SRGB': 1,
                'BC4_UNORM': 0.5, 'BC5_UNORM': 1,
                'BC6H_UF16': 1, 'BC7_UNORM': 1, 'BC7_SRGB': 1,
                'R8_UNORM': 1, 'R16_FLOAT': 2, 'R32_FLOAT': 4,
                'D24_UNORM_S8_UINT': 4, 'D32_FLOAT': 4,
            }};
            
            let totalBytes = 0;
            textures.forEach(tex => {{
                const bpp = bppMap[tex.format] || 4;  // 默认 4 bytes
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                
                // 考虑 mipmap（约增加 1/3）
                if (tex.mips > 1) {{
                    pixels = Math.floor(pixels * 1.33);
                }}
                
                totalBytes += pixels * bpp;
            }});
            
            // 转换为 MB
            const mb = (totalBytes / (1024 * 1024)).toFixed(1);
            document.getElementById('statVRAM').textContent = `${{mb}} MB`;
        }}
        
        // 填充格式筛选下拉框
        function populateFormatFilter() {{
            const formats = [...new Set(textures.map(t => t.format))].sort();
            const select = document.getElementById('formatFilter');
            formats.forEach(fmt => {{
                const opt = document.createElement('option');
                opt.value = fmt;
                opt.textContent = fmt;
                select.appendChild(opt);
            }});
        }}
        
        // 应用所有筛选条件
        function applyFilters() {{
            const query = document.getElementById('searchBox').value.toLowerCase();
            const formatFilter = document.getElementById('formatFilter').value;
            const sizeFilter = document.getElementById('sizeFilter').value;
            
            filteredTextures = textures.filter(tex => {{
                // 文本搜索
                const matchText = !query || 
                    (tex.name && tex.name.toLowerCase().includes(query)) ||
                    String(tex.id).includes(query);
                
                // 格式筛选
                const matchFormat = !formatFilter || tex.format === formatFilter;
                
                // 尺寸筛选
                let matchSize = true;
                if (sizeFilter) {{
                    const maxDim = Math.max(tex.width, tex.height);
                    switch (sizeFilter) {{
                        case 'small': matchSize = maxDim <= 64; break;
                        case 'medium': matchSize = maxDim > 64 && maxDim <= 512; break;
                        case 'large': matchSize = maxDim > 512 && maxDim <= 2048; break;
                        case 'huge': matchSize = maxDim > 2048; break;
                    }}
                }}
                
                return matchText && matchFormat && matchSize;
            }});
            
            sortTextures();
            updateStats();
            renderGrid();
            renderTable();
        }}
        
        function updateStats() {{
            const visible = filteredTextures.length;
            const total = textures.length;
            document.getElementById('stats').textContent = 
                visible === total ? `共 ${{total}} 个纹理` : `显示 ${{visible}} / ${{total}} 个纹理`;
        }}
        
        function renderGrid() {{
            const grid = document.getElementById('textureGrid');
            grid.innerHTML = filteredTextures.map((tex, idx) => `
                <div class="texture-card" onclick="openLightbox(${{idx}})">
                    <div class="texture-thumb">
                        ${{tex.thumbnail 
                            ? `<img src="${{tex.thumbnail}}" alt="Texture">` 
                            : '<span class="no-preview">无预览</span>'}}
                    </div>
                    <div class="texture-info">
                        <div class="texture-name" title="${{tex.name || 'Texture #' + tex.id}}">${{tex.name || 'Texture #' + tex.id}}</div>
                        <div class="texture-dims">${{tex.width}} × ${{tex.height}}</div>
                        <div class="texture-format">${{tex.format}}</div>
                    </div>
                </div>
            `).join('');
        }}
        
        function renderTable() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = filteredTextures.map((tex, idx) => `
                <tr onclick="openLightbox(${{idx}})" style="cursor:pointer">
                    <td class="thumb-cell">
                        ${{tex.thumbnail ? `<img src="${{tex.thumbnail}}" alt="">` : '-'}}
                    </td>
                    <td>${{tex.id}}</td>
                    <td>${{tex.name || '-'}}</td>
                    <td>${{tex.width}} × ${{tex.height}}</td>
                    <td>${{tex.format}}</td>
                    <td>${{tex.mips}}</td>
                    <td>${{tex.arrayLayers}}</td>
                </tr>
            `).join('');
        }}
        
        function setupEventListeners() {{
            // 搜索和筛选 - 统一使用 applyFilters
            document.getElementById('searchBox').addEventListener('input', applyFilters);
            document.getElementById('formatFilter').addEventListener('change', applyFilters);
            document.getElementById('sizeFilter').addEventListener('change', applyFilters);
            
            // 排序选择
            document.getElementById('sortSelect').addEventListener('change', function(e) {{
                currentSort.key = e.target.value;
                sortTextures();
                renderGrid();
                renderTable();
            }});
            
            // 视图切换
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    
                    const view = this.dataset.view;
                    document.getElementById('gridView').classList.toggle('hidden', view !== 'grid');
                    document.getElementById('tableView').classList.toggle('active', view === 'table');
                }});
            }});
            
            // 表头排序
            document.querySelectorAll('th[data-sort]').forEach(th => {{
                th.addEventListener('click', function() {{
                    const key = this.dataset.sort;
                    if (currentSort.key === key) {{
                        currentSort.asc = !currentSort.asc;
                    }} else {{
                        currentSort.key = key;
                        currentSort.asc = true;
                    }}
                    
                    // 更新表头样式
                    document.querySelectorAll('th').forEach(h => {{
                        h.classList.remove('sorted-asc', 'sorted-desc');
                    }});
                    this.classList.add(currentSort.asc ? 'sorted-asc' : 'sorted-desc');
                    
                    sortTextures();
                    renderGrid();
                    renderTable();
                }});
            }});
            
            // ESC 关闭 lightbox
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') closeLightbox();
                if (e.key === 'ArrowLeft') navigateLightbox(-1);
                if (e.key === 'ArrowRight') navigateLightbox(1);
            }});
        }}
        
        function sortTextures() {{
            filteredTextures.sort((a, b) => {{
                let valA, valB;
                switch (currentSort.key) {{
                    case 'id':
                        valA = a.id; valB = b.id;
                        break;
                    case 'size':
                        valA = a.width * a.height;
                        valB = b.width * b.height;
                        break;
                    case 'format':
                        valA = a.format; valB = b.format;
                        break;
                    case 'name':
                        valA = a.name || ''; valB = b.name || '';
                        break;
                    default:
                        valA = a.id; valB = b.id;
                }}
                
                if (typeof valA === 'string') {{
                    return currentSort.asc 
                        ? valA.localeCompare(valB)
                        : valB.localeCompare(valA);
                }}
                return currentSort.asc ? valA - valB : valB - valA;
            }});
        }}
        
        function openLightbox(index) {{
            currentLightboxIndex = index;
            updateLightbox();
            document.getElementById('lightbox').classList.add('show');
        }}
        
        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('show');
            // 关闭时也关闭所有弹出面板
            closeAllPanels();
        }}
        
        // ===== 弹出面板管理 =====
        const panels = {{
            histogram: {{ panel: 'histogramPanel', btn: 'histogramBtn' }},
            adjust: {{ panel: 'adjustPanel', btn: 'adjustBtn' }},
            normal: {{ panel: 'normalPanel', btn: 'normalBtn' }},
            notes: {{ panel: 'notesPanel', btn: 'notesBtn' }}
        }};
        
        function togglePanel(name) {{
            const config = panels[name];
            if (!config) return;
            
            const panel = document.getElementById(config.panel);
            const btn = document.getElementById(config.btn);
            const isOpen = panel.classList.contains('show');
            
            // 关闭所有其他面板
            closeAllPanels();
            
            if (!isOpen) {{
                panel.classList.add('show');
                btn.classList.add('active');
                
                // 特殊处理：打开直方图时重新计算
                if (name === 'histogram') {{
                    drawHistogram();
                }}
                // 打开 3D 法线时渲染预览
                if (name === 'normal') {{
                    renderNormal3D();
                }}
            }}
        }}
        
        function closeAllPanels() {{
            Object.values(panels).forEach(({{ panel, btn }}) => {{
                document.getElementById(panel).classList.remove('show');
                document.getElementById(btn).classList.remove('active');
            }});
        }}
        
        function navigateLightbox(delta) {{
            currentLightboxIndex += delta;
            if (currentLightboxIndex < 0) currentLightboxIndex = filteredTextures.length - 1;
            if (currentLightboxIndex >= filteredTextures.length) currentLightboxIndex = 0;
            updateLightbox();
        }}
        
        function updateLightbox() {{
            const tex = filteredTextures[currentLightboxIndex];
            currentChannel = 'rgb';  // 切换纹理时重置为 RGB
            
            // 关闭所有弹出面板
            closeAllPanels();
            
            // 重置滤镜
            resetFilters();
            
            // 更新按钮状态
            updateChannelButtons(tex);
            
            // 显示图像
            showChannelImage(tex, 'rgb');
            
            // 更新标题和详情
            document.getElementById('lightboxName').textContent = tex.name || `Texture #${{tex.id}}`;
            document.getElementById('lightboxDetails').textContent = 
                `${{tex.width}}×${{tex.height}} · ${{tex.format}} · Mips:${{tex.mips}}`;
            
            // 更新书签按钮状态
            updateBookmarkButton();
            
            // 更新对比按钮状态
            updateCompareButton();
            
            // 加载备注
            loadNote();
        }}
        
        function updateChannelButtons(tex) {{
            const channels = tex.channels || {{}};
            const buttons = document.querySelectorAll('.channel-btn');
            
            buttons.forEach(btn => {{
                const ch = btn.dataset.channel;
                btn.classList.remove('active', 'disabled');
                
                if (ch === 'rgb') {{
                    // RGB 始终可用
                    btn.classList.add('active');
                }} else {{
                    // 检查通道是否可用
                    if (!channels[ch]) {{
                        btn.classList.add('disabled');
                        btn.title = ch === 'a' && channels.a === null 
                            ? 'Alpha = 255 (全不透明)' 
                            : '通道不可用';
                    }} else {{
                        btn.title = '';
                    }}
                }}
            }});
        }}
        
        function switchChannel(channel) {{
            const tex = filteredTextures[currentLightboxIndex];
            const channels = tex.channels || {{}};
            
            // 检查通道是否可用
            if (channel !== 'rgb' && !channels[channel]) {{
                return;  // 不可用的通道不响应点击
            }}
            
            currentChannel = channel;
            
            // 更新按钮激活状态
            document.querySelectorAll('.channel-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.channel === channel);
            }});
            
            // 切换图像
            showChannelImage(tex, channel);
        }}
        
        function showChannelImage(tex, channel) {{
            const img = document.getElementById('lightboxImg');
            const channels = tex.channels || {{}};
            
            if (channel === 'rgb') {{
                img.src = tex.thumbnail || '';
            }} else if (channels[channel]) {{
                img.src = channels[channel];
            }} else {{
                img.src = tex.thumbnail || '';  // Fallback
            }}
        }}
        
        // 亮度/对比度调整
        function updateImageFilter() {{
            const brightness = document.getElementById('brightnessSlider').value;
            const contrast = document.getElementById('contrastSlider').value;
            const img = document.getElementById('lightboxImg');
            
            // 更新显示值
            document.getElementById('brightnessValue').textContent = brightness + '%';
            document.getElementById('contrastValue').textContent = contrast + '%';
            
            // 应用 CSS filter
            img.style.filter = `brightness(${{brightness}}%) contrast(${{contrast}}%)`;
        }}
        
        function resetFilters() {{
            document.getElementById('brightnessSlider').value = 100;
            document.getElementById('contrastSlider').value = 100;
            updateImageFilter();
        }}
        
        // ===== 颜色拾取器 =====
        const pickerCanvas = document.createElement('canvas');
        const pickerCtx = pickerCanvas.getContext('2d', {{ willReadFrequently: true }});
        let pickerReady = false;
        
        // 图片加载完成后绘制到隐藏 Canvas
        document.getElementById('lightboxImg').addEventListener('load', function() {{
            const img = this;
            pickerCanvas.width = img.naturalWidth;
            pickerCanvas.height = img.naturalHeight;
            pickerCtx.drawImage(img, 0, 0);
            pickerReady = true;
            
            // 计算并绘制直方图
            calculateAndDrawHistogram();
        }});
        
        // ===== 直方图功能 =====
        let histogramMode = 'rgb';  // 'rgb' 或 'luminance'
        let histogramData = {{ r: [], g: [], b: [], luminance: [] }};
        
        function setHistogramMode(mode) {{
            histogramMode = mode;
            
            // 更新按钮状态
            document.querySelectorAll('.histogram-toggle button').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.mode === mode);
            }});
            
            // 重新绘制
            drawHistogram();
        }}
        
        function calculateAndDrawHistogram() {{
            if (!pickerReady) return;
            
            // 初始化直方图数据 (0-255)
            histogramData = {{
                r: new Array(256).fill(0),
                g: new Array(256).fill(0),
                b: new Array(256).fill(0),
                luminance: new Array(256).fill(0)
            }};
            
            // 采样像素（对于大图片进行采样以提高性能）
            const w = pickerCanvas.width;
            const h = pickerCanvas.height;
            const totalPixels = w * h;
            const sampleRate = totalPixels > 500000 ? Math.ceil(totalPixels / 500000) : 1;
            
            try {{
                const imageData = pickerCtx.getImageData(0, 0, w, h);
                const data = imageData.data;
                
                let rSum = 0, gSum = 0, bSum = 0;
                let sampleCount = 0;
                
                for (let i = 0; i < data.length; i += 4 * sampleRate) {{
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];
                    
                    histogramData.r[r]++;
                    histogramData.g[g]++;
                    histogramData.b[b]++;
                    
                    // 计算亮度 (Rec. 601)
                    const lum = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    histogramData.luminance[lum]++;
                    
                    rSum += r;
                    gSum += g;
                    bSum += b;
                    sampleCount++;
                }}
                
                // 更新统计信息
                const rMean = Math.round(rSum / sampleCount);
                const gMean = Math.round(gSum / sampleCount);
                const bMean = Math.round(bSum / sampleCount);
                
                document.getElementById('histogramStats').innerHTML = `
                    <span><div class="dot r"></div>R: 均值 ${{rMean}}</span>
                    <span><div class="dot g"></div>G: 均值 ${{gMean}}</span>
                    <span><div class="dot b"></div>B: 均值 ${{bMean}}</span>
                `;
                
                drawHistogram();
            }} catch (err) {{
                console.error('Histogram calculation failed:', err);
            }}
        }}
        
        function drawHistogram() {{
            const canvas = document.getElementById('histogramCanvas');
            const ctx = canvas.getContext('2d');
            
            // 设置 Canvas 实际尺寸
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * window.devicePixelRatio;
            canvas.height = rect.height * window.devicePixelRatio;
            ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
            
            const width = rect.width;
            const height = rect.height;
            
            // 清空画布
            ctx.clearRect(0, 0, width, height);
            
            if (histogramMode === 'luminance') {{
                // 亮度直方图 - 白色
                drawChannel(ctx, histogramData.luminance, width, height, 'rgba(200, 200, 200, 0.8)');
            }} else {{
                // RGB 叠加直方图
                drawChannel(ctx, histogramData.b, width, height, 'rgba(51, 154, 240, 0.5)');
                drawChannel(ctx, histogramData.g, width, height, 'rgba(81, 207, 102, 0.5)');
                drawChannel(ctx, histogramData.r, width, height, 'rgba(255, 107, 107, 0.5)');
            }}
        }}
        
        function drawChannel(ctx, data, width, height, color) {{
            const max = Math.max(...data) || 1;
            const barWidth = width / 256;
            
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(0, height);
            
            for (let i = 0; i < 256; i++) {{
                const barHeight = (data[i] / max) * height * 0.95;
                const x = i * barWidth;
                ctx.lineTo(x, height - barHeight);
            }}
            
            ctx.lineTo(width, height);
            ctx.closePath();
            ctx.fill();
        }}
        
        // 鼠标移动时读取像素
        document.getElementById('lightboxImg').addEventListener('mousemove', function(e) {{
            if (!pickerReady) return;
            
            const img = this;
            const rect = img.getBoundingClientRect();
            
            // 计算图片内的实际坐标（考虑 object-fit: contain 缩放）
            const scaleX = img.naturalWidth / rect.width;
            const scaleY = img.naturalHeight / rect.height;
            const scale = Math.max(scaleX, scaleY);
            
            // 计算图片在容器内的偏移
            const displayW = img.naturalWidth / scale;
            const displayH = img.naturalHeight / scale;
            const offsetX = (rect.width - displayW) / 2;
            const offsetY = (rect.height - displayH) / 2;
            
            // 鼠标在图片上的相对位置
            const mouseX = e.clientX - rect.left - offsetX;
            const mouseY = e.clientY - rect.top - offsetY;
            
            // 转换为图片原始坐标
            const imgX = Math.floor(mouseX * scale);
            const imgY = Math.floor(mouseY * scale);
            
            // 边界检查
            if (imgX < 0 || imgX >= img.naturalWidth || imgY < 0 || imgY >= img.naturalHeight) {{
                return;
            }}
            
            // 读取像素
            try {{
                const pixel = pickerCtx.getImageData(imgX, imgY, 1, 1).data;
                const r = pixel[0], g = pixel[1], b = pixel[2], a = pixel[3];
                const hex = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('').toUpperCase();
                
                // 更新 UI
                document.getElementById('colorCoord').textContent = `X:${{imgX}} Y:${{imgY}}`;
                document.getElementById('colorR').textContent = r;
                document.getElementById('colorG').textContent = g;
                document.getElementById('colorB').textContent = b;
                document.getElementById('colorA').textContent = a;
                document.getElementById('colorHex').textContent = hex;
                document.getElementById('colorPreview').style.background = `rgba(${{r}},${{g}},${{b}},${{a/255}})`;
            }} catch (err) {{
                // Canvas 读取失败（跨域等）
            }}
        }});
        
        // 鼠标离开时重置显示
        document.getElementById('lightboxImg').addEventListener('mouseleave', function() {{
            document.getElementById('colorCoord').textContent = 'X: - Y: -';
            document.getElementById('colorR').textContent = '-';
            document.getElementById('colorG').textContent = '-';
            document.getElementById('colorB').textContent = '-';
            document.getElementById('colorA').textContent = '-';
            document.getElementById('colorHex').textContent = '#------';
            document.getElementById('colorPreview').style.background = '#000';
        }});
        
        // 复制十六进制颜色值
        function copyHex() {{
            const hex = document.getElementById('colorHex').textContent;
            if (hex && hex !== '#------') {{
                navigator.clipboard.writeText(hex).then(() => {{
                    const el = document.getElementById('colorHex');
                    const orig = el.textContent;
                    el.textContent = '已复制!';
                    setTimeout(() => el.textContent = orig, 800);
                }});
            }}
        }}
        
        // ===== 缩放和拖拽 =====
        let zoomScale = 1;
        let panX = 0, panY = 0;
        let isDragging = false;
        let dragStartX = 0, dragStartY = 0;
        let dragStartPanX = 0, dragStartPanY = 0;
        
        const imgContainer = document.getElementById('imgContainer');
        const lightboxImg = document.getElementById('lightboxImg');
        
        function updateTransform() {{
            lightboxImg.style.transform = `scale(${{zoomScale}}) translate(${{panX}}px, ${{panY}}px)`;
            document.getElementById('zoomLevel').textContent = Math.round(zoomScale * 100) + '%';
        }}
        
        function zoomImage(delta) {{
            zoomScale = Math.max(0.25, Math.min(10, zoomScale + delta));
            updateTransform();
        }}
        
        function resetZoom() {{
            zoomScale = 1;
            panX = 0;
            panY = 0;
            updateTransform();
        }}
        
        // 鼠标滚轮缩放
        imgContainer.addEventListener('wheel', function(e) {{
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.15 : 0.15;
            zoomScale = Math.max(0.25, Math.min(10, zoomScale + delta));
            updateTransform();
        }}, {{ passive: false }});
        
        // 拖拽平移
        imgContainer.addEventListener('mousedown', function(e) {{
            if (zoomScale <= 1) return;  // 未缩放时不拖拽
            isDragging = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            dragStartPanX = panX;
            dragStartPanY = panY;
            imgContainer.classList.add('dragging');
            lightboxImg.classList.add('no-transition');
            e.preventDefault();
        }});
        
        document.addEventListener('mousemove', function(e) {{
            if (!isDragging) return;
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            panX = dragStartPanX + dx / zoomScale;
            panY = dragStartPanY + dy / zoomScale;
            updateTransform();
        }});
        
        document.addEventListener('mouseup', function() {{
            if (isDragging) {{
                isDragging = false;
                imgContainer.classList.remove('dragging');
                lightboxImg.classList.remove('no-transition');
            }}
        }});
        
        // 双击重置
        imgContainer.addEventListener('dblclick', function() {{
            resetZoom();
        }});
        
        // 切换纹理时重置缩放
        const originalUpdateLightbox = updateLightbox;
        updateLightbox = function() {{
            resetZoom();
            originalUpdateLightbox();
            // 更新操作按钮状态
            updateCompareUI();
            // 加载备注
            loadNote();
            // 隐藏 3D 法线预览
            const normalPanel = document.getElementById('normalPanel');
            if (normalPanel) normalPanel.classList.remove('show');
            const normalBtn = document.getElementById('normalBtn');
            if (normalBtn) normalBtn.classList.remove('active');
        }};
        
        // ===== 功能 7: 纹理对比模式 =====
        let compareMarks = [];  // 最多存 2 个纹理索引
        
        function toggleCompare() {{
            const tex = filteredTextures[currentLightboxIndex];
            const texId = tex.id;
            
            const idx = compareMarks.findIndex(m => m.id === texId);
            if (idx >= 0) {{
                // 已标记，取消
                compareMarks.splice(idx, 1);
            }} else {{
                // 添加标记
                if (compareMarks.length >= 2) {{
                    compareMarks.shift();  // 移除最早的
                }}
                compareMarks.push({{ id: texId, index: currentLightboxIndex }});
            }}
            
            updateCompareUI();
            renderGrid();  // 更新网格显示标记
            
            // 如果已有 2 个标记，自动打开对比视图
            if (compareMarks.length === 2) {{
                openCompare();
            }}
        }}
        
        function updateCompareUI() {{
            const tex = filteredTextures[currentLightboxIndex];
            const isMarked = compareMarks.some(m => m.id === tex.id);
            const btn = document.getElementById('compareBtn');
            
            if (isMarked) {{
                btn.classList.add('active');
            }} else {{
                btn.classList.remove('active');
            }}
        }}
        
        // ========== 对比视图同步缩放/平移 ==========
        let compareState = {{
            zoom: 1,
            panX: 0,
            panY: 0,
            syncEnabled: true,
            isDragging: false,
            dragStart: {{ x: 0, y: 0 }},
            dragPane: null
        }};
        
        function openCompare() {{
            if (compareMarks.length < 2) {{
                alert('请先标记 2 张纹理进行对比');
                return;
            }}
            
            // 找到对应纹理
            const tex1 = textures.find(t => t.id === compareMarks[0].id);
            const tex2 = textures.find(t => t.id === compareMarks[1].id);
            
            if (!tex1 || !tex2) return;
            
            // 重置对比状态
            compareState.zoom = 1;
            compareState.panX = 0;
            compareState.panY = 0;
            
            // 更新对比视图
            document.getElementById('compareTitle1').textContent = tex1.name || `Texture #${{tex1.id}}`;
            document.getElementById('compareInfo1').textContent = `${{tex1.width}}×${{tex1.height}} | ${{tex1.format}}`;
            document.getElementById('compareImg1').src = tex1.thumbnail || '';
            
            document.getElementById('compareTitle2').textContent = tex2.name || `Texture #${{tex2.id}}`;
            document.getElementById('compareInfo2').textContent = `${{tex2.width}}×${{tex2.height}} | ${{tex2.format}}`;
            document.getElementById('compareImg2').src = tex2.thumbnail || '';
            
            // 生成差异对比表格
            renderCompareDiffTable(tex1, tex2);
            
            // 更新缩放显示
            updateCompareTransform();
            
            document.getElementById('compareLightbox').classList.add('show');
            
            // 初始化对比视图事件
            initCompareEvents();
        }}
        
        // 生成差异对比表格
        function renderCompareDiffTable(tex1, tex2) {{
            const bppMap = {{
                'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
                'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
                'BC1_UNORM': 0.5, 'BC3_UNORM': 1, 'BC5_UNORM': 1, 'BC7_UNORM': 1,
                'D32_FLOAT': 4, 'D24_UNORM_S8_UINT': 4, 'D16_UNORM': 2,
            }};
            
            // 计算 VRAM
            const calcVRAM = (tex) => {{
                const bpp = bppMap[tex.format] || 4;
                let pixels = tex.width * tex.height * (tex.depth || 1) * (tex.arrayLayers || 1);
                if (tex.mips > 1) pixels = Math.floor(pixels * 1.33);
                return pixels * bpp;
            }};
            
            const vram1 = calcVRAM(tex1);
            const vram2 = calcVRAM(tex2);
            
            // 定义要对比的属性
            const props = [
                {{ label: '宽度', v1: tex1.width, v2: tex2.width, unit: 'px' }},
                {{ label: '高度', v1: tex1.height, v2: tex2.height, unit: 'px' }},
                {{ label: '格式', v1: tex1.format, v2: tex2.format, unit: '' }},
                {{ label: 'Mips', v1: tex1.mips || 1, v2: tex2.mips || 1, unit: '' }},
                {{ label: 'Layers', v1: tex1.arrayLayers || 1, v2: tex2.arrayLayers || 1, unit: '' }},
                {{ label: 'VRAM', v1: (vram1 / 1024 / 1024).toFixed(2), v2: (vram2 / 1024 / 1024).toFixed(2), unit: 'MB' }},
            ];
            
            // 生成 HTML
            const html = props.map(p => {{
                const isSame = String(p.v1) === String(p.v2);
                const cls = isSame ? 'same' : 'different';
                const valueHtml = isSame
                    ? `<span class="compare-diff-same">${{p.v1}}${{p.unit}}</span>`
                    : `<div class="compare-diff-values">
                        <span class="compare-diff-value left">${{p.v1}}${{p.unit}}</span>
                        <span class="compare-diff-arrow">vs</span>
                        <span class="compare-diff-value right">${{p.v2}}${{p.unit}}</span>
                       </div>`;
                return `<div class="compare-diff-item ${{cls}}">
                    <span class="compare-diff-label">${{p.label}}</span>
                    ${{valueHtml}}
                </div>`;
            }}).join('');
            
            document.getElementById('compareDiffTable').innerHTML = html;
        }}
        
        function closeCompare() {{
            document.getElementById('compareLightbox').classList.remove('show');
        }}
        
        function updateCompareTransform() {{
            const transform = `scale(${{compareState.zoom}}) translate(${{compareState.panX}}px, ${{compareState.panY}}px)`;
            const zoomPercent = Math.round(compareState.zoom * 100) + '%';
            
            // 同步两边
            document.getElementById('compareImg1').style.transform = transform;
            document.getElementById('compareImg2').style.transform = transform;
            document.getElementById('compareZoom1').textContent = zoomPercent;
            document.getElementById('compareZoom2').textContent = zoomPercent;
            document.getElementById('compareZoomLabel').textContent = zoomPercent;
        }}
        
        function compareZoomIn() {{
            compareState.zoom = Math.min(compareState.zoom * 1.25, 10);
            updateCompareTransform();
        }}
        
        function compareZoomOut() {{
            compareState.zoom = Math.max(compareState.zoom / 1.25, 0.1);
            updateCompareTransform();
        }}
        
        function compareZoomReset() {{
            compareState.zoom = 1;
            compareState.panX = 0;
            compareState.panY = 0;
            updateCompareTransform();
        }}
        
        function toggleCompareSync() {{
            compareState.syncEnabled = !compareState.syncEnabled;
            const btn = document.getElementById('compareSyncBtn');
            if (compareState.syncEnabled) {{
                btn.classList.add('active');
                btn.textContent = '🔗 同步';
            }} else {{
                btn.classList.remove('active');
                btn.textContent = '🔓 独立';
            }}
        }}
        
        function initCompareEvents() {{
            const wrapper1 = document.getElementById('compareWrapper1');
            const wrapper2 = document.getElementById('compareWrapper2');
            
            // 滚轮缩放
            [wrapper1, wrapper2].forEach(wrapper => {{
                wrapper.onwheel = (e) => {{
                    e.preventDefault();
                    const delta = e.deltaY > 0 ? 0.9 : 1.1;
                    compareState.zoom = Math.min(Math.max(compareState.zoom * delta, 0.1), 10);
                    updateCompareTransform();
                }};
                
                // 拖拽平移
                wrapper.onmousedown = (e) => {{
                    if (e.button !== 0) return;
                    compareState.isDragging = true;
                    compareState.dragStart = {{ x: e.clientX, y: e.clientY }};
                    compareState.dragPane = wrapper;
                    wrapper.classList.add('dragging');
                    
                    const img1 = document.getElementById('compareImg1');
                    const img2 = document.getElementById('compareImg2');
                    img1.classList.add('no-transition');
                    img2.classList.add('no-transition');
                }};
            }});
            
            document.addEventListener('mousemove', handleCompareMouseMove);
            document.addEventListener('mouseup', handleCompareMouseUp);
        }}
        
        function handleCompareMouseMove(e) {{
            if (!compareState.isDragging) return;
            
            const dx = (e.clientX - compareState.dragStart.x) / compareState.zoom;
            const dy = (e.clientY - compareState.dragStart.y) / compareState.zoom;
            
            compareState.panX += dx;
            compareState.panY += dy;
            compareState.dragStart = {{ x: e.clientX, y: e.clientY }};
            
            updateCompareTransform();
        }}
        
        function handleCompareMouseUp() {{
            if (!compareState.isDragging) return;
            
            compareState.isDragging = false;
            
            const wrapper1 = document.getElementById('compareWrapper1');
            const wrapper2 = document.getElementById('compareWrapper2');
            wrapper1.classList.remove('dragging');
            wrapper2.classList.remove('dragging');
            
            const img1 = document.getElementById('compareImg1');
            const img2 = document.getElementById('compareImg2');
            img1.classList.remove('no-transition');
            img2.classList.remove('no-transition');
        }}
        
        // ========== EID Modal 功能 ==========
        
        // 模拟的 Draw Call 数据（真实数据需从 RDC 分析器导出）
        const mockDrawCallData = {{
            getPassName: (eid) => {{
                // 根据 EID 范围模拟不同的 Render Pass
                if (eid < 1000) return 'EarlyDepthPass';
                if (eid < 3000) return 'ShadowDepthPass';
                if (eid < 6000) return 'BasePass';
                if (eid < 9000) return 'LightingPass';
                if (eid < 12000) return 'TranslucentPass';
                return 'PostProcessPass';
            }},
            getAPICall: (eid) => {{
                const calls = [
                    'vkCmdDrawIndexed',
                    'vkCmdDraw',
                    'vkCmdDrawIndirect',
                    'vkCmdDispatch',
                    'glDrawElements',
                    'glDrawArrays',
                    'ID3D12GraphicsCommandList::DrawIndexedInstanced',
                    'ID3D11DeviceContext::DrawIndexed'
                ];
                return calls[eid % calls.length];
            }},
            getSlots: (eid) => {{
                // 模拟纹理绑定槽位
                const baseSlot = eid % 4;
                const slots = [`PS Slot ${{baseSlot}}`];
                if (eid % 3 === 0) slots.push(`PS Slot ${{baseSlot + 4}}`);
                if (eid % 5 === 0) slots.push('CS Slot 0');
                return slots;
            }},
            getDrawInfo: (eid) => {{
                const vertices = (eid * 37) % 10000 + 100;
                const instances = (eid % 5) + 1;
                return `${{vertices.toLocaleString()}} vertices × ${{instances}} instance${{instances > 1 ? 's' : ''}}`;
            }}
        }};
        
        // 当前显示的 EID（用于复制功能）
        let currentEIDInfo = null;
        
        function showEIDModal(eid) {{
            const modal = document.getElementById('eidModal');
            
            // 获取模拟数据
            const passName = mockDrawCallData.getPassName(eid);
            const apiCall = mockDrawCallData.getAPICall(eid);
            const slots = mockDrawCallData.getSlots(eid);
            const drawInfo = mockDrawCallData.getDrawInfo(eid);
            
            // 更新 Modal 内容
            document.getElementById('eidModalId').textContent = eid;
            document.getElementById('eidModalPass').textContent = passName;
            document.getElementById('eidModalAPI').textContent = apiCall;
            document.getElementById('eidModalDrawInfo').textContent = drawInfo;
            
            // 渲染槽位列表
            const slotsHtml = slots.map(s => `<span class="eid-slot-tag">${{s}}</span>`).join('');
            document.getElementById('eidModalSlots').innerHTML = `<div class="eid-slot-list">${{slotsHtml}}</div>`;
            
            // 保存当前信息（用于复制）
            currentEIDInfo = {{
                eid: eid,
                pass: passName,
                api: apiCall,
                slots: slots,
                drawInfo: drawInfo
            }};
            
            // 检查是否有 Event Browser 数据
            const hasEventBrowser = eventPassData && eventPassData.events && eventPassData.events.length > 0;
            const jumpBtn = document.getElementById('eidModalJumpBtn');
            if (jumpBtn) {{
                if (hasEventBrowser) {{
                    // 检查此 EID 是否存在于 Event 数据中
                    const eventExists = eventPassData.events.some(e => e.eid === eid);
                    jumpBtn.style.display = eventExists ? 'flex' : 'none';
                    jumpBtn.onclick = () => jumpToEventBrowser(eid);
                }} else {{
                    jumpBtn.style.display = 'none';
                }}
            }}
            
            // 显示 Modal
            modal.classList.add('show');
        }}
        
        // 跳转到 Event Browser 并选中指定 EID
        function jumpToEventBrowser(eid) {{
            // 关闭当前弹框
            closeEIDModal();
            
            // 切换到 Event Browser 视图
            updateViewMode('event');
            
            // 展开包含此 EID 的父节点
            const event = eventPassData.events.find(e => e.eid === eid);
            if (event && event.parent) {{
                // 递归展开所有父节点
                let parentEid = event.parent;
                while (parentEid) {{
                    eventExpandState[parentEid] = true;
                    const parentEvent = eventPassData.events.find(e => e.eid === parentEid);
                    parentEid = parentEvent ? parentEvent.parent : null;
                }}
            }}
            
            // 重新渲染树
            renderEventTree();
            
            // 选中指定 Event
            setTimeout(() => {{
                selectEvent(eid);
                
                // 滚动到该节点
                const targetNode = document.querySelector(`.event-node[data-eid="${{eid}}"]`);
                if (targetNode) {{
                    targetNode.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    
                    // 添加高亮动画
                    targetNode.classList.add('highlight-pulse');
                    setTimeout(() => targetNode.classList.remove('highlight-pulse'), 2000);
                }}
            }}, 100);
        }}
        
        function closeEIDModal() {{
            document.getElementById('eidModal').classList.remove('show');
            currentEIDInfo = null;
        }}
        
        function copyEIDInfo() {{
            if (!currentEIDInfo) return;
            
            const text = `Event ID: ${{currentEIDInfo.eid}}
Render Pass: ${{currentEIDInfo.pass}}
API Call: ${{currentEIDInfo.api}}
Texture Slots: ${{currentEIDInfo.slots.join(', ')}}
Draw Info: ${{currentEIDInfo.drawInfo}}`;
            
            navigator.clipboard.writeText(text).then(() => {{
                // 显示复制成功提示
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = '✓ 已复制';
                btn.style.background = 'var(--accent-green)';
                setTimeout(() => {{
                    btn.textContent = originalText;
                    btn.style.background = '';
                }}, 1500);
            }}).catch(err => {{
                console.error('复制失败:', err);
                alert('复制失败，请手动复制');
            }});
        }}
        
        // ==================== Shader Modal Functions ====================
        let currentShaderData = null;
        
        function getShaderTypeBadgeClass(stageName) {{
            const map = {{
                'Vertex Shader': 'vs',
                'Pixel Shader': 'ps',
                'Compute Shader': 'cs',
                'Geometry Shader': 'gs',
                'Hull Shader': 'hs',
                'Domain Shader': 'ds'
            }};
            return map[stageName] || 'vs';
        }}
        
        function getShaderTypeAbbrev(stageName) {{
            const map = {{
                'Vertex Shader': 'VS',
                'Pixel Shader': 'PS',
                'Compute Shader': 'CS',
                'Geometry Shader': 'GS',
                'Hull Shader': 'HS',
                'Domain Shader': 'DS'
            }};
            return map[stageName] || stageName;
        }}
        
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        function highlightAsmCode(code) {{
            if (!code) return '';
            let escaped = escapeHtml(code);
            
            // DXBC/DXIL/SPIRV 语法高亮
            escaped = escaped
                // 注释
                .replace(/(\/\/.*$|;.*$)/gm, '<span class="hljs-comment">$1</span>')
                // 关键字（指令）
                .replace(/\\b(dcl_|def|mov|add|mul|mad|dp[234]|sample|sample_l|sample_d|sample_c|ld|store|ret|if_|else|endif|loop|endloop|break|continue|discard|rsq|sqrt|rcp|min|max|abs|saturate|frc|floor|ceil|round|log|exp|sin|cos|tan|asin|acos|atan|pow|step|lerp|clamp|sign|normalize|length|distance|dot|cross|reflect|refract|transpose|determinant|any|all|clip|texld|texldp|texldb|texldd|tex2D|tex3D|texCUBE|texldl)\\b/gi, '<span class="hljs-keyword">$1</span>')
                // 寄存器
                .replace(/\\b([vorcst]\\d+|r\\d+|o\\d+|t\\d+|s\\d+|cb\\d+|icb\\d+|x\\d+|v\\d+_\\d+)\\b/gi, '<span class="hljs-register">$1</span>')
                // 数字
                .replace(/\\b(-?\\d+\\.?\\d*[fhl]?)\\b/g, '<span class="hljs-number">$1</span>')
                // 类型
                .replace(/\\b(float[234]?|int[234]?|uint[234]?|half[234]?|bool|void|float[234]x[234]|matrix|Texture2D|Texture3D|TextureCube|SamplerState|cbuffer|ConstantBuffer)\\b/g, '<span class="hljs-type">$1</span>')
                // 标签
                .replace(/^(\\w+:)/gm, '<span class="hljs-label">$1</span>');
            
            return escaped;
        }}
        
        function showShaderModal(stageName, shaderData) {{
            currentShaderData = {{ stage: stageName, ...shaderData }};
            
            const abbrev = getShaderTypeAbbrev(stageName);
            const badgeClass = getShaderTypeBadgeClass(stageName);
            const displayName = shaderData.debugName || shaderData.entryPoint || 'Unnamed Shader';
            
            // 创建模态框 HTML
            const modal = document.createElement('div');
            modal.className = 'shader-modal';
            modal.id = 'shaderModal';
            modal.onclick = (e) => {{ if (e.target === modal) closeShaderModal(); }};
            
            // 构建输入签名表格
            let inputSigHtml = '<div style="padding:20px;color:var(--text-muted);">无输入签名数据</div>';
            if (shaderData.inputSignature && shaderData.inputSignature.length > 0) {{
                inputSigHtml = `
                    <table class="shader-signature-table">
                        <thead>
                            <tr>
                                <th>Semantic</th>
                                <th>Index</th>
                                <th>Register</th>
                                <th>Type</th>
                                <th>Components</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${{shaderData.inputSignature.map(sig => `
                                <tr>
                                    <td>${{sig.semantic || 'N/A'}}</td>
                                    <td>${{sig.index ?? 0}}</td>
                                    <td>${{sig.register ?? 'N/A'}}</td>
                                    <td>${{sig.type || 'float'}}</td>
                                    <td>${{sig.components ?? 4}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }}
            
            // 构建输出签名表格
            let outputSigHtml = '<div style="padding:20px;color:var(--text-muted);">无输出签名数据</div>';
            if (shaderData.outputSignature && shaderData.outputSignature.length > 0) {{
                outputSigHtml = `
                    <table class="shader-signature-table">
                        <thead>
                            <tr>
                                <th>Semantic</th>
                                <th>Index</th>
                                <th>Register</th>
                                <th>Type</th>
                                <th>Components</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${{shaderData.outputSignature.map(sig => `
                                <tr>
                                    <td>${{sig.semantic || 'N/A'}}</td>
                                    <td>${{sig.index ?? 0}}</td>
                                    <td>${{sig.register ?? 'N/A'}}</td>
                                    <td>${{sig.type || 'float'}}</td>
                                    <td>${{sig.components ?? 4}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }}
            
            // 反汇编代码
            let asmCode = shaderData.sourceAsm || shaderData.sourceAsmError || '// 无反汇编代码可用\\n// 请确保在提取 Pipeline State 时包含了 Shader 反汇编';
            const highlightedAsm = highlightAsmCode(asmCode);
            
            // 常量缓冲区信息
            let cbHtml = '<div style="padding:20px;color:var(--text-muted);">无常量缓冲区数据</div>';
            if (shaderData.constantBuffers && shaderData.constantBuffers.length > 0) {{
                cbHtml = `
                    <table class="shader-signature-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Bind Point</th>
                                <th>Size (bytes)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${{shaderData.constantBuffers.map(cb => `
                                <tr>
                                    <td>${{cb.name || 'Unnamed'}}</td>
                                    <td>${{cb.bindPoint ?? 'N/A'}}</td>
                                    <td>${{cb.byteSize ?? 0}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }}
            
            modal.innerHTML = `
                <div class="shader-modal-content">
                    <div class="shader-modal-header">
                        <div class="shader-modal-title">
                            <span class="shader-type-badge ${{badgeClass}}">${{abbrev}}</span>
                            <span class="shader-modal-name">${{displayName}}</span>
                        </div>
                        <button class="shader-modal-close" onclick="closeShaderModal()">&times;</button>
                    </div>
                    <div class="shader-modal-info">
                        <div class="shader-info-item">
                            <span class="shader-info-label">Resource ID:</span>
                            <span class="shader-info-value">${{shaderData.resourceId || 'N/A'}}</span>
                        </div>
                        <div class="shader-info-item">
                            <span class="shader-info-label">Entry Point:</span>
                            <span class="shader-info-value">${{shaderData.entryPoint || 'main'}}</span>
                        </div>
                        <div class="shader-info-item">
                            <span class="shader-info-label">Encoding:</span>
                            <span class="shader-info-value">${{shaderData.encoding || 'Unknown'}}</span>
                        </div>
                        ${{shaderData.sourceAsmTruncated ? '<div class="shader-info-item"><span style="color:#f59e0b;">⚠️ 代码已截断</span></div>' : ''}}
                    </div>
                    <div class="shader-modal-tabs">
                        <button class="shader-tab-btn active" onclick="switchShaderTab(this, 'asm')">📜 反汇编</button>
                        <button class="shader-tab-btn" onclick="switchShaderTab(this, 'input')">📥 输入签名</button>
                        <button class="shader-tab-btn" onclick="switchShaderTab(this, 'output')">📤 输出签名</button>
                        <button class="shader-tab-btn" onclick="switchShaderTab(this, 'cb')">📦 常量缓冲区</button>
                    </div>
                    <div class="shader-modal-body">
                        <div class="shader-tab-content active" id="shaderTabAsm">
                            <div class="shader-code-container">
                                <pre class="shader-code">${{highlightedAsm}}</pre>
                            </div>
                        </div>
                        <div class="shader-tab-content" id="shaderTabInput">
                            ${{inputSigHtml}}
                        </div>
                        <div class="shader-tab-content" id="shaderTabOutput">
                            ${{outputSigHtml}}
                        </div>
                        <div class="shader-tab-content" id="shaderTabCb">
                            ${{cbHtml}}
                        </div>
                    </div>
                    <div class="shader-modal-footer">
                        <button class="shader-modal-btn secondary" onclick="closeShaderModal()">关闭</button>
                        <button class="shader-modal-btn primary" onclick="copyShaderCode()">📋 复制代码</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // 延迟显示动画
            requestAnimationFrame(() => {{
                modal.classList.add('show');
            }});
        }}
        
        function closeShaderModal() {{
            const modal = document.getElementById('shaderModal');
            if (modal) {{
                modal.classList.remove('show');
                setTimeout(() => modal.remove(), 200);
            }}
            currentShaderData = null;
        }}
        
        function switchShaderTab(btn, tabId) {{
            // 更新按钮状态
            btn.parentElement.querySelectorAll('.shader-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 切换内容
            const tabMap = {{
                'asm': 'shaderTabAsm',
                'input': 'shaderTabInput',
                'output': 'shaderTabOutput',
                'cb': 'shaderTabCb'
            }};
            
            document.querySelectorAll('.shader-tab-content').forEach(c => c.classList.remove('active'));
            const targetTab = document.getElementById(tabMap[tabId]);
            if (targetTab) targetTab.classList.add('active');
        }}
        
        function copyShaderCode() {{
            if (!currentShaderData) return;
            
            const code = currentShaderData.sourceAsm || '// No code available';
            navigator.clipboard.writeText(code).then(() => {{
                const btn = event.target;
                const originalText = btn.innerHTML;
                btn.innerHTML = '✓ 已复制';
                btn.style.background = 'var(--accent-green)';
                setTimeout(() => {{
                    btn.innerHTML = originalText;
                    btn.style.background = '';
                }}, 1500);
            }}).catch(err => {{
                console.error('复制失败:', err);
                alert('复制失败，请手动复制');
            }});
        }}
        // ==================== End Shader Modal Functions ====================
        
        // 显示全部 EID 列表弹窗
        function showAllEIDsModal(textureName, events) {{
            // 创建临时弹窗显示所有 EID
            const modal = document.createElement('div');
            modal.className = 'eid-modal show';
            modal.style.zIndex = '10000';
            modal.innerHTML = `
                <div class="eid-modal-content" style="max-width:600px;max-height:80vh;">
                    <div class="eid-modal-header">
                        <div class="eid-modal-title">
                            <span>📋 所有使用位置</span>
                        </div>
                        <button class="eid-modal-close" onclick="this.closest('.eid-modal').remove()">&times;</button>
                    </div>
                    <div class="eid-modal-body" style="max-height:60vh;overflow-y:auto;">
                        <div style="margin-bottom:12px;color:var(--text-muted);font-size:0.85rem;">
                            纹理 <strong style="color:var(--text-primary);">${{textureName}}</strong> 被以下 ${{events.length}} 个 Event 使用:
                        </div>
                        <div style="display:flex;flex-wrap:wrap;gap:6px;">
                            ${{events.map(eid => `<span class="eid-tag" onclick="event.stopPropagation();showEIDModal(${{eid}});this.closest('.eid-modal').remove();" title="点击查看详情">EID ${{eid}}</span>`).join('')}}
                        </div>
                    </div>
                    <div class="eid-modal-footer">
                        <button class="eid-modal-btn secondary" onclick="this.closest('.eid-modal').remove()">关闭</button>
                    </div>
                </div>
            `;
            
            // 点击背景关闭
            modal.addEventListener('click', (e) => {{
                if (e.target === modal) modal.remove();
            }});
            
            document.body.appendChild(modal);
        }}
        
        // ESC 关闭 EID Modal
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                const eidModal = document.getElementById('eidModal');
                if (eidModal && eidModal.classList.contains('show')) {{
                    closeEIDModal();
                    e.stopPropagation();
                }}
                // 也关闭动态创建的"全部 EID"弹窗
                document.querySelectorAll('.eid-modal.show').forEach(m => {{
                    if (m.id !== 'eidModal') m.remove();
                }});
            }}
        }});
        
        // 点击背景关闭 EID Modal
        document.getElementById('eidModal').addEventListener('click', function(e) {{
            if (e.target === this) closeEIDModal();
        }});
        
        function swapCompareTextures() {{
            if (compareMarks.length === 2) {{
                compareMarks.reverse();
                openCompare();
            }}
        }}
        
        function clearCompareMarks() {{
            compareMarks = [];
            updateCompareUI();
            renderGrid();
            closeCompare();
        }}
        
        // 更新 renderGrid 以显示对比标记
        const originalRenderGrid = renderGrid;
        renderGrid = function() {{
            const grid = document.getElementById('textureGrid');
            grid.innerHTML = filteredTextures.map((tex, idx) => {{
                const isMarked = compareMarks.some(m => m.id === tex.id);
                const markNum = compareMarks.findIndex(m => m.id === tex.id) + 1;
                const isBookmarked = bookmarks[tex.id];
                
                return `
                <div class="texture-card" onclick="openLightbox(${{idx}})">
                    ${{isMarked ? `<span class="compare-badge">对比 ${{markNum}}</span>` : ''}}
                    ${{isBookmarked ? '<span class="bookmark-badge">⭐</span>' : ''}}
                    <div class="texture-thumb">
                        ${{tex.thumbnail 
                            ? `<img src="${{tex.thumbnail}}" alt="Texture">` 
                            : '<span class="no-preview">无预览</span>'}}
                    </div>
                    <div class="texture-info">
                        <div class="texture-name" title="${{tex.name || 'Texture #' + tex.id}}">${{tex.name || 'Texture #' + tex.id}}</div>
                        <div class="texture-dims">${{tex.width}} × ${{tex.height}}</div>
                        <div class="texture-format">${{tex.format}}</div>
                    </div>
                </div>
                `;
            }}).join('');
        }};
        
        // ===== 功能 8: 法线图 3D 预览 =====
        let normal3dActive = false;
        
        function toggleNormalPreview() {{
            normal3dActive = !normal3dActive;
            const container = document.getElementById('normalPanel');
            const btn = document.getElementById('normalBtn');
            
            if (container && btn) {{
                if (normal3dActive) {{
                    container.classList.add('show');
                    btn.classList.add('active');
                    renderNormal3D();
                }} else {{
                    container.classList.remove('show');
                    btn.classList.remove('active');
                }}
            }}
        }}
        
        function updateNormal3D() {{
            if (normal3dActive) {{
                renderNormal3D();
            }}
        }}
        
        function renderNormal3D() {{
            if (!pickerReady) return;
            
            const canvas = document.getElementById('normal3dCanvas');
            const ctx = canvas.getContext('2d');
            
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
            
            const heightScale = parseFloat(document.getElementById('normalHeightSlider').value);
            const lightAngle = parseFloat(document.getElementById('normalLightSlider').value) * Math.PI / 180;
            
            // 光照方向
            const lightX = Math.cos(lightAngle);
            const lightY = Math.sin(lightAngle);
            const lightZ = 0.5;  // 固定 Z 分量
            const lightLen = Math.sqrt(lightX*lightX + lightY*lightY + lightZ*lightZ);
            const lx = lightX/lightLen, ly = lightY/lightLen, lz = lightZ/lightLen;
            
            // 源图像数据
            const srcW = pickerCanvas.width;
            const srcH = pickerCanvas.height;
            const srcData = pickerCtx.getImageData(0, 0, srcW, srcH).data;
            
            // 目标图像
            const dstW = canvas.width;
            const dstH = canvas.height;
            const dstImageData = ctx.createImageData(dstW, dstH);
            const dstData = dstImageData.data;
            
            // 采样比例
            const scaleX = srcW / dstW;
            const scaleY = srcH / dstH;
            
            for (let y = 0; y < dstH; y++) {{
                for (let x = 0; x < dstW; x++) {{
                    // 映射到源图像坐标
                    const sx = Math.floor(x * scaleX);
                    const sy = Math.floor(y * scaleY);
                    const si = (sy * srcW + sx) * 4;
                    
                    // 法线贴图: RGB -> XYZ (假设: R=X, G=Y, B=Z, 范围 0-255 映射到 -1~1)
                    const nx = (srcData[si] / 255) * 2 - 1;
                    const ny = (srcData[si+1] / 255) * 2 - 1;
                    const nz = (srcData[si+2] / 255) * 2 - 1;
                    
                    // 归一化法线
                    const nLen = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
                    const nnx = nx/nLen, nny = ny/nLen, nnz = nz/nLen;
                    
                    // 点积计算漫反射
                    let dot = nnx*lx + nny*ly + nnz*lz;
                    dot = Math.max(0, dot);  // 裁剪负值
                    
                    // 添加高度感（环境光 + 漫反射）
                    const ambient = 0.2;
                    const diffuse = dot * 0.8 * (heightScale / 25);
                    const intensity = Math.min(1, ambient + diffuse);
                    
                    // 输出颜色（灰度光照）
                    const gray = Math.floor(intensity * 255);
                    const di = (y * dstW + x) * 4;
                    dstData[di] = gray;
                    dstData[di+1] = gray;
                    dstData[di+2] = gray;
                    dstData[di+3] = 255;
                }}
            }}
            
            ctx.putImageData(dstImageData, 0, 0);
        }}
        
        // ===== 功能 9: 导出单张纹理 =====
        function exportTexture() {{
            const tex = filteredTextures[currentLightboxIndex];
            if (!tex.thumbnail) {{
                alert('该纹理没有可导出的图像数据');
                return;
            }}
            
            // 创建下载链接
            const link = document.createElement('a');
            link.download = `${{tex.name || 'texture_' + tex.id}}.png`;
            link.href = tex.thumbnail;  // Base64 Data URL
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
        
        // ===== 功能 10: 书签/标注功能 =====
        // 使用 localStorage 存储书签和备注
        const storageKey = 'rdc_texture_bookmarks_' + '{rdc_name}'.replace(/[^a-zA-Z0-9]/g, '_');
        let bookmarks = {{}};
        let notes = {{}};
        
        // 加载存储的数据
        function loadBookmarksAndNotes() {{
            try {{
                const saved = localStorage.getItem(storageKey);
                if (saved) {{
                    const data = JSON.parse(saved);
                    bookmarks = data.bookmarks || {{}};
                    notes = data.notes || {{}};
                }}
            }} catch (e) {{
                console.warn('Failed to load bookmarks:', e);
            }}
        }}
        
        function saveBookmarksAndNotes() {{
            try {{
                localStorage.setItem(storageKey, JSON.stringify({{
                    bookmarks: bookmarks,
                    notes: notes
                }}));
            }} catch (e) {{
                console.warn('Failed to save bookmarks:', e);
            }}
        }}
        
        function toggleBookmark() {{
            const tex = filteredTextures[currentLightboxIndex];
            if (bookmarks[tex.id]) {{
                delete bookmarks[tex.id];
            }} else {{
                bookmarks[tex.id] = true;
            }}
            saveBookmarksAndNotes();
            updateBookmarkButton();
            renderGrid();
        }}
        
        function updateBookmarkButton() {{
            const tex = filteredTextures[currentLightboxIndex];
            const bookmarkBtn = document.getElementById('bookmarkBtn');
            if (bookmarks[tex.id]) {{
                bookmarkBtn.classList.add('bookmarked');
            }} else {{
                bookmarkBtn.classList.remove('bookmarked');
            }}
        }}
        
        function updateCompareButton() {{
            updateCompareUI();  // 复用现有逻辑
        }}
        
        function loadNote() {{
            const tex = filteredTextures[currentLightboxIndex];
            const textarea = document.getElementById('notesTextarea');
            textarea.value = notes[tex.id] || '';
        }}
        
        function saveNote() {{
            const tex = filteredTextures[currentLightboxIndex];
            const textarea = document.getElementById('notesTextarea');
            const value = textarea.value.trim();
            
            if (value) {{
                notes[tex.id] = value;
            }} else {{
                delete notes[tex.id];
            }}
            saveBookmarksAndNotes();
        }}
        
        // ESC 关闭对比视图
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && document.getElementById('compareLightbox').classList.contains('show')) {{
                closeCompare();
            }}
        }});
        
        // 初始化时加载书签
        loadBookmarksAndNotes();
        
        // ========== 帧缩略图功能 ==========
        function initFrameThumbnail() {{
            if (frameThumbnail && frameThumbnail.length > 0) {{
                const preview = document.getElementById('frameThumbnailPreview');
                const img = document.getElementById('frameThumbnailImg');
                if (preview && img) {{
                    img.src = frameThumbnail;
                    preview.style.display = 'inline-flex';
                }}
            }}
        }}
        
        function showFrameThumbnail() {{
            if (!frameThumbnail) return;
            
            // 创建弹窗
            let modal = document.getElementById('frameThumbModal');
            if (!modal) {{
                modal = document.createElement('div');
                modal.id = 'frameThumbModal';
                modal.className = 'frame-thumb-modal';
                modal.innerHTML = `
                    <span class="close-btn" onclick="hideFrameThumbnail()">&times;</span>
                    <img src="${{frameThumbnail}}" alt="Frame Capture" />
                    <div class="caption">📸 帧捕获预览 (点击空白处关闭)</div>
                `;
                modal.onclick = function(e) {{
                    if (e.target === modal) hideFrameThumbnail();
                }};
                document.body.appendChild(modal);
            }}
            modal.classList.add('active');
        }}
        
        function hideFrameThumbnail() {{
            const modal = document.getElementById('frameThumbModal');
            if (modal) modal.classList.remove('active');
        }}
        
        // 初始化帧缩略图
        initFrameThumbnail();
        
        // RT Timeline 功能 (Direction C)
        {generate_rt_timeline_js() if HAS_RT_TIMELINE and rt_tracking_data else ''}
        
        // Hotspot 功能 (Direction F)
        {generate_hotspot_js() if HAS_HOTSPOT and hotspot_data else ''}
        
        // 启动
        init();
        
        // Hotspot 初始化 (Direction F)
        {generate_hotspot_html(hotspot_data) if HAS_HOTSPOT and hotspot_data else ''}
    </script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[OK] Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate offline RDC texture report')
    parser.add_argument('rdc_path', help='Path to RDC file or textures.json')
    parser.add_argument('-o', '--output', help='Output HTML path', default=None)
    
    args = parser.parse_args()
    
    rdc_path = Path(args.rdc_path)
    if not rdc_path.exists():
        print(f"[ERROR] File not found: {rdc_path}")
        return 1
    
    output_path = args.output or str(rdc_path.with_suffix('.html'))
    
    print(f"\n=== Generating Offline Report for {rdc_path.name} ===\n")
    
    # 支持直接传入 textures.json
    if rdc_path.name == 'textures.json' or rdc_path.suffix == '.json':
        with open(rdc_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        tex_list = manifest if isinstance(manifest, list) else manifest.get("textures", [])
        textures = []
        for tex in tex_list:
            res_id = tex.get("resource_id") or tex.get("id")
            textures.append({
                "id": res_id,
                "name": tex.get("name", ""),
                "width": tex.get("width", 0),
                "height": tex.get("height", 0),
                "depth": tex.get("depth", 1),
                "format": tex.get("format", "UNKNOWN"),
                "mips": tex.get("mips", 1),
                "arrayLayers": tex.get("arrayLayers", 1),
                "thumbnail": tex.get("thumbnail", ""),
                "channels": tex.get("channels", {})
            })
        print(f"  [OK] Loaded {len(textures)} textures from {rdc_path}")
    else:
        textures = load_textures_from_export(str(rdc_path))
    
    if not textures:
        print("[WARN] No textures found, generating empty report")
    
    generate_offline_html(textures, rdc_path.name, output_path)
    
    return 0


if __name__ == '__main__':
    exit(main())
